from __future__ import annotations

import csv
from pathlib import Path
import tkinter as tk
from tkinter import ttk


DATASET_PATH = Path("data/dataset.csv")


def load_rows(product: str, day: str, target: str) -> list[dict[str, str]]:
    if not DATASET_PATH.exists():
        return []
    rows: list[dict[str, str]] = []
    with DATASET_PATH.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if product and row.get("product") != product:
                continue
            if day and row.get("day") != day:
                continue
            if target not in row:
                continue
            rows.append(row)
    return rows


def detect_knobs(columns: list[str]) -> list[str]:
    knobs: list[str] = []
    for col in columns:
        if "." not in col or not col.startswith("c"):
            continue
        suffix = col.split(".", 1)[1]
        if suffix == "pwr" or suffix in {"m1g", "m2g", "m3g"} or (suffix.startswith("s") and suffix.endswith("g")):
            knobs.append(col)
    return knobs


def optimize(product: str, day: str, target: str, tolerance: float, mode: str, active_knobs: str) -> str:
    rows = load_rows(product, day, target)
    if not rows:
        return "Nu am găsit date pentru filtrul selectat sau target invalid."

    values = [float(r[target]) for r in rows if r.get(target)]
    if not values:
        return "Target-ul selectat nu are valori numerice."

    baseline = sum(values) / len(values)
    desired = baseline - min(tolerance, 1.0) * 0.5

    columns = list(rows[0].keys())
    knobs = [k.strip() for k in active_knobs.split(",") if k.strip()] if active_knobs.strip() else detect_knobs(columns)
    knobs = knobs[:3]

    if not knobs:
        return "Nu am detectat knobs modificabile (pwr/main gas/segment gas)."

    step = 0.1 if mode.upper() == "SAFE" else 0.3

    lines = []
    lines.append("Goal")
    lines.append(f"- Product: {product}")
    lines.append(f"- Target: {target}")
    lines.append(f"- Tolerance: ±{tolerance:.1f}")
    lines.append("")
    lines.append("Current")
    lines.append(f"- Baseline: {baseline:.3f}")
    lines.append("")
    lines.append("Top 3 soluții")

    for rank in range(1, 4):
        deltas = {k: round(rank * step, 3) for k in knobs}
        predicted = baseline + (desired - baseline) * 0.5
        risk = "low" if mode.upper() == "SAFE" else "medium"
        cost_plate = round(sum(abs(v) for v in deltas.values()) * 0.2, 3)
        lines.append(f"{rank}) deltas={deltas}, predicted={predicted:.3f}, risk={risk}, €/plate={cost_plate}")

    return "\n".join(lines)


class App(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Coater Optimizer - Minimal GUI")
        self.geometry("820x620")

        self.product = tk.StringVar(value="P1")
        self.day = tk.StringVar(value="")
        self.target = tk.StringVar(value="a_star_RG_mean")
        self.tolerance = tk.StringVar(value="0.5")
        self.mode = tk.StringVar(value="SAFE")
        self.knobs = tk.StringVar(value="")

        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Product").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.product, width=24).grid(row=1, column=0, sticky="we", padx=4)

        ttk.Label(frm, text="Day (optional)").grid(row=0, column=1, sticky="w")
        ttk.Entry(frm, textvariable=self.day, width=24).grid(row=1, column=1, sticky="we", padx=4)

        ttk.Label(frm, text="Target").grid(row=2, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.target, width=24).grid(row=3, column=0, sticky="we", padx=4)

        ttk.Label(frm, text="Tolerance").grid(row=2, column=1, sticky="w")
        ttk.Entry(frm, textvariable=self.tolerance, width=24).grid(row=3, column=1, sticky="we", padx=4)

        ttk.Label(frm, text="Mode").grid(row=4, column=0, sticky="w")
        ttk.Combobox(frm, textvariable=self.mode, values=["SAFE", "AGGRESSIVE"], state="readonly").grid(row=5, column=0, sticky="we", padx=4)

        ttk.Label(frm, text="Active knobs (comma-separated, optional)").grid(row=6, column=0, columnspan=2, sticky="w")
        ttk.Entry(frm, textvariable=self.knobs, width=56).grid(row=7, column=0, columnspan=2, sticky="we", padx=4)

        ttk.Button(frm, text="Run Optimizer", command=self.run_optimizer).grid(row=8, column=0, columnspan=2, pady=10)

        self.output = tk.Text(frm, wrap="word")
        self.output.grid(row=9, column=0, columnspan=2, sticky="nsew")

        frm.columnconfigure(0, weight=1)
        frm.columnconfigure(1, weight=1)
        frm.rowconfigure(9, weight=1)

    def run_optimizer(self) -> None:
        try:
            tolerance = float(self.tolerance.get())
        except ValueError:
            self.output.delete("1.0", tk.END)
            self.output.insert(tk.END, "Tolerance trebuie să fie numeric.")
            return

        result = optimize(
            product=self.product.get().strip(),
            day=self.day.get().strip(),
            target=self.target.get().strip(),
            tolerance=tolerance,
            mode=self.mode.get().strip(),
            active_knobs=self.knobs.get().strip(),
        )
        self.output.delete("1.0", tk.END)
        self.output.insert(tk.END, result)


if __name__ == "__main__":
    App().mainloop()
