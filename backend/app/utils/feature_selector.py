from __future__ import annotations

import re
from dataclasses import dataclass

import pandas as pd

from app.core.constants import CONTEXT_ALLOWLIST_PATTERNS, FEATURE_REGEX_CONFIG, IDENTITY_COLUMNS, TARGET_COLUMNS
from app.models.schemas import FeatureToggleConfig


@dataclass
class FeatureSelectionResult:
    selected_features: list[str]
    control_knobs: list[str]
    context_numeric: list[str]
    context_categorical: list[str]
    keyword_forced_context: list[str]
    counts: dict[str, int]


def _match(columns: list[str], pattern: str) -> list[str]:
    rx = re.compile(pattern)
    return sorted([c for c in columns if rx.match(c)])


def detect_control_knobs(columns: list[str], include_main_gas_alt: bool = True) -> dict[str, list[str]]:
    groups = {
        "power": _match(columns, FEATURE_REGEX_CONFIG["power"]),
        "main_gas": _match(columns, FEATURE_REGEX_CONFIG["main_gas"]),
        "main_gas_alt": _match(columns, FEATURE_REGEX_CONFIG["main_gas_alt"]) if include_main_gas_alt else [],
        "segment_gas": _match(columns, FEATURE_REGEX_CONFIG["segment_gas"]),
    }
    return groups


def detect_groups(df: pd.DataFrame, include_main_gas_alt: bool = True, include_keyword_allowlist: bool = True) -> dict[str, list[str]]:
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

    forced = []
    if include_keyword_allowlist:
        allow_rx = re.compile("|".join(f"(?:{p})" for p in CONTEXT_ALLOWLIST_PATTERNS), re.IGNORECASE)
        control_union_rx = re.compile(
            f"(?:{FEATURE_REGEX_CONFIG['power']})|(?:{FEATURE_REGEX_CONFIG['main_gas']})|(?:{FEATURE_REGEX_CONFIG['main_gas_alt']})|(?:{FEATURE_REGEX_CONFIG['segment_gas']})"
        )
        for c in columns:
            if c in targets or c in IDENTITY_COLUMNS:
                continue
            if control_union_rx.match(c):
                continue
            if allow_rx.search(c):
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

    context_numeric = groups["context_numeric"] if toggles.include_context_numeric else []
    context_categorical = groups["context_categorical"] if toggles.include_context_categorical else []

    selected = control + context_numeric + context_categorical
    seen = set()
    selected = [c for c in selected if not (c in seen or seen.add(c))]

    return FeatureSelectionResult(
        selected_features=selected,
        control_knobs=sorted(list(dict.fromkeys(control))),
        context_numeric=context_numeric,
        context_categorical=context_categorical,
        keyword_forced_context=groups["keyword_forced_context"],
        counts={
            "targets": len(groups["targets"]),
            "control_knobs": len(control),
            "context_numeric": len(context_numeric),
            "context_categorical": len(context_categorical),
            "keyword_forced_context": len(groups["keyword_forced_context"]),
            "total": len(selected),
        },
    )
