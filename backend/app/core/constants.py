from __future__ import annotations

TARGET_COLUMNS = [
    "L_RG_mean", "L_RG_std", "a_RG_mean", "a_RG_std", "b_RG_mean", "b_RG_std",
    "L_RF_mean", "L_RF_std", "a_RF_mean", "a_RF_std", "b_RF_mean", "b_RF_std",
    "L_T_mean", "L_T_std", "a_T_mean", "a_T_std", "b_T_mean", "b_T_std",
]

IDENTITY_COLUMNS = ["plate", "day", "file_ts", "ts"]

FEATURE_REGEX_CONFIG = {
    "power": r"^c\\d+\\.pwr$",
    "main_gas": r"^c\\d+\\.mainGas[123]$",
    "main_gas_alt": r"^c\\d+\\.m[123]g$",
    "segment_gas": r"^c\\d+\\.s(1|2|3|4|5|6|7|8|9|10|11)g$",
}

CONTEXT_ALLOWLIST_PATTERNS = [
    r"vacuum|pressure",
    r"life|target.*life|remaining.*life|erosion|usage",
    r"sigma|std|stdev|variance",
    r"current|voltage|power",
    r"freq|frequency",
    r"temperature|temp",
    r"speed",
    r"thickness|glassThickness",
    r"kwh|energy",
]
