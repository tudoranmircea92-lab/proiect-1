from __future__ import annotations

import fnmatch
import json
from pathlib import Path
from typing import Any, Dict


class KnobRules:
    def __init__(self, path: str = "coater_ui_v6_full_architecture/config/knob_rules.json"):
        self.path = Path(path)
        self.data: Dict[str, Any] = json.loads(self.path.read_text(encoding="utf-8")) if self.path.exists() else {}

    def bounds_for(self, knob: str) -> Dict[str, Any]:
        defaults = self.data.get("defaults", {})
        best = defaults.get("*", {"min": -1e6, "max": 1e6, "step": 0.1, "unit": "unitless"})
        for pattern, cfg in defaults.items():
            if pattern == "*":
                continue
            if fnmatch.fnmatch(knob.lower(), pattern.lower()):
                best = {**best, **cfg}
        return best

    def group_for(self, knob: str) -> str:
        rules = self.data.get("group_rules", {})
        for group, patterns in rules.items():
            for p in patterns:
                if fnmatch.fnmatch(knob.lower(), p.lower()):
                    return group
        return "Other"

    def all(self) -> Dict[str, Any]:
        return self.data
