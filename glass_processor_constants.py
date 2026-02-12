from __future__ import annotations

from typing import List, Set

# UNC root (day folders: root\YYYY\MM\DD)
INPUT_DEFAULT = r"\\a98sw143pcor0ap.za.if.atcsg.net\instruments\calarasi\process"
START_DEFAULT = "2025-11-14"
END_DEFAULT = "2026-02-11"

PATTERN_DEFAULT = "*_glassFile.csv"
OUTPUT_DEFAULT = r"C:\proiect corelare\data\processed\glass_processed\ALL_GLASS_PROCESSED.xlsx"
TMP_CSV_DEFAULT = r"C:\proiect corelare\data\processed\glass_processed\_ALL_GLASS_PROCESSED_TMP.csv"

KEEP_COMPS: Set[int] = {
    4,
    5,
    7,
    9,
    10,
    11,
    13,
    15,
    16,
    18,
    20,
    22,
    25,
    27,
    28,
    30,
    33,
    35,
    36,
    39,
    40,
    42,
    43,
    46,
    47,
    49,
    52,
    53,
    55,
    58,
    60,
    62,
    63,
    65,
    67,
    69,
}

FINAL_COLS: List[str] = [
    "date",
    "plate",
    "comp",
    "nomGasSegment",
    "nomProcessSpeed_mm",
    "glassThickness",
    "actTargetMaterial1",
    "actPower",
    "actPowerPMF",
    "actCurrent",
    "actCurrentIMF",
    "actSigmaCurrent",
    "actVoltage",
    "actVoltageUMF",
    "actSigmaVoltage",
    "actArcRate1",
    "actFreq",
    "actVacuumPressure",  # NOT rounded
    "Ar_flow",
    "N2_flow",
    "O2_flow",
    "actSegGas1Flow",
    "actSegGas2Flow",
    "actSegGas3Flow",
    "actSegGas4Flow",
    "actSegGas5Flow",
    "actSegGas6Flow",
    "actSegGas7Flow",
    "actSegGas8Flow",
    "actSegGas9Flow",
    "actSegGas10Flow",
    "actSegGas11Flow",
    "actHArc",
    "actSArc",
    "actSArcB",
    "actWaterFlowShielding",
    "actWaterFlowSurround",
]

# Input column name sources
SRC_DATE = "optoplexGTime"
SRC_PLATE = "glassId"
SRC_LOC = "Location"
SRC_NOMGASSEG = "nomGasSegment"

SRC_AR = "actMainGas1Flow"
SRC_N2 = "actMainGas2Flow"
SRC_O2 = "actMainGas3Flow"

# columns we do NOT round (strings / ids / special)
NO_ROUND = {
    "date",
    "plate",
    "comp",
    "nomGasSegment",
    "actTargetMaterial1",
    "actVacuumPressure",
}
