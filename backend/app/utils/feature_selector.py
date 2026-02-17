from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from app.core.constants import CONTEXT_ALLOWLIST_PATTERNS, IDENTITY_COLUMNS, TARGET_COLUMNS
from app.models.schemas import FeatureToggleConfig


@dataclass
class FeatureSelectionResult:
    selected_features: list[str]
    control_knobs: list[str]
    context_numeric: list[str]
    context_categorical: list[str]
    keyword_forced_context: list[str]
    counts: dict[str, int]


def _normalize_name(name: str) -> tuple[str, str, str]:
    name_norm = re.sub(r"\s+", " ", str(name).strip())
    alt1 = name_norm.replace("_", ".")
    alt2 = name_norm.replace(".", "_")
    return name_norm, alt1, alt2


def _matches_any_variant(col: str, patterns: list[re.Pattern[str]]) -> bool:
    variants = _normalize_name(col)
    return any(rx.match(v.lower()) for v in variants for rx in patterns)


def detect_control_knobs(columns: list[str], include_main_gas_alt: bool = True) -> dict[str, list[str]]:
    pwr_patterns = [re.compile(r"^c\d+\.pwr$"), re.compile(r"^c\d+_pwr$")]
    main_patterns = [re.compile(r"^c\d+\.(maingas[123])$"), re.compile(r"^c\d+_(maingas[123])$")]
    seg_patterns = [re.compile(r"^c\d+\.s(1|2|3|4|5|6|7|8|9|10|11)g$"), re.compile(r"^c\d+_s(1|2|3|4|5|6|7|8|9|10|11)g$")]
    mg_patterns = [re.compile(r"^c\d+\.m[123]g$"), re.compile(r"^c\d+_m[123]g$")]

    power = sorted([c for c in columns if _matches_any_variant(c, pwr_patterns)])
    main = sorted([c for c in columns if _matches_any_variant(c, main_patterns)])
    seg = sorted([c for c in columns if _matches_any_variant(c, seg_patterns)])
    mg = sorted([c for c in columns if _matches_any_variant(c, mg_patterns)]) if include_main_gas_alt else []

    return {
        "power": power,
        "main_gas": main,
        "main_gas_alt": mg,
        "segment_gas": seg,
    }


def build_knob_debug(columns: list[str], control: dict[str, list[str]]) -> dict[str, object]:
    def with_repr(names: list[str]) -> list[dict[str, str]]:
        return [{"name": str(x), "repr": repr(x)} for x in names]

    contains_pwr = [c for c in columns if "pwr" in str(c).lower()]
    contains_maingas = [c for c in columns if "maingas" in str(c).lower()]
    contains_s1g = [c for c in columns if "s1g" in str(c).lower()]

    warnings: list[str] = []
    if contains_pwr and len(control["power"]) == 0:
        warnings.append(
            "Detected columns containing 'pwr' but power regex matched 0 columns. Check hidden spaces, separators (_ vs .), or naming drift."
        )

    return {
        "total_cols": len(columns),
        "sample_cols_first_50": with_repr(columns[:50]),
        "columns_containing_pwr": with_repr(contains_pwr[:100]),
        "columns_containing_mainGas": with_repr(contains_maingas[:100]),
        "columns_containing_s1g": with_repr(contains_s1g[:100]),
        "warnings": warnings,
    }


def detect_groups(df: pd.DataFrame, include_main_gas_alt: bool = True, include_keyword_allowlist: bool = True, include_debug: bool = False) -> dict[str, list[str] | dict[str, object]]:
    columns = list(df.columns)
    control = detect_control_knobs(columns, include_main_gas_alt=include_main_gas_alt)
    control_all = set(sum(control.values(), []))
    targets = [c for c in TARGET_COLUMNS if c in columns]

    numeric_cols = set(df.select_dtypes(include=["number"]).columns)
    context_numeric = sorted(
        c
        for c in numeric_cols
        if c not in set(targets) and c not in control_all and c not in set(IDENTITY_COLUMNS)
    )

    forced: list[str] = []
    if include_keyword_allowlist:
        allow_rx = re.compile("|".join(f"(?:{p})" for p in CONTEXT_ALLOWLIST_PATTERNS), re.IGNORECASE)
        for c in columns:
            if c in targets or c in IDENTITY_COLUMNS or c in control_all:
                continue
            if allow_rx.search(str(c)):
                forced.append(c)
        forced = sorted(list(set(forced)))
        context_numeric = sorted(list(set(context_numeric).union(set(forced))))

    categorical = sorted(
        c
        for c in df.select_dtypes(include=["object", "string", "category", "bool"]).columns
        if c not in set(targets) and c not in control_all and c not in set(IDENTITY_COLUMNS)
    )

    return {
        "targets": targets,
        "control_knobs": sorted(list(control_all)),
        "power": control["power"],
        "main_gas": control["main_gas"],
        "main_gas_alt": control["main_gas_alt"],
        "segment_gas": control["segment_gas"],
        "context_numeric": context_numeric,
        "context_categorical": categorical,
        "keyword_forced_context": forced,
        "identity": [c for c in IDENTITY_COLUMNS if c in columns],
        "knob_debug": build_knob_debug(columns, control) if include_debug else {},
    }


def select_features(df: pd.DataFrame, toggles: FeatureToggleConfig) -> FeatureSelectionResult:
    groups = detect_groups(
        df,
        include_main_gas_alt=toggles.include_main_gas_alt,
        include_keyword_allowlist=toggles.include_context_keyword_allowlist,
    )

    control: list[str] = []
    if toggles.include_power:
        control.extend(groups["power"])
    if toggles.include_main_gas:
        control.extend(groups["main_gas"])
    if toggles.include_main_gas_alt:
        control.extend(groups["main_gas_alt"])
    if toggles.include_segment_gas:
        control.extend(groups["segment_gas"])

    control = sorted(list(dict.fromkeys(control)))

    context_numeric = [c for c in groups["context_numeric"] if c not in set(control)] if toggles.include_context_numeric else []
    context_categorical = [c for c in groups["context_categorical"] if c not in set(control)] if toggles.include_context_categorical else []

    selected = control + context_numeric + context_categorical
    seen = set()
    selected = [c for c in selected if not (c in seen or seen.add(c))]

    return FeatureSelectionResult(
        selected_features=selected,
        control_knobs=control,
        context_numeric=context_numeric,
        context_categorical=context_categorical,
        keyword_forced_context=groups["keyword_forced_context"],
        counts={
            "targets": len(groups["targets"]),
            "control_knobs": len(control),
            "power": len(groups["power"]),
            "main_gas": len(groups["main_gas"]),
            "segment_gas": len(groups["segment_gas"]),
            "main_gas_alt": len(groups["main_gas_alt"]),
            "context_numeric": len(context_numeric),
            "context_categorical": len(context_categorical),
            "keyword_forced_context": len(groups["keyword_forced_context"]),
            "total": len(selected),
        },
    )
