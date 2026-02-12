from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from glass_processor_constants import (
    END_DEFAULT,
    INPUT_DEFAULT,
    OUTPUT_DEFAULT,
    PATTERN_DEFAULT,
    START_DEFAULT,
    TMP_CSV_DEFAULT,
)
from glass_processor_parsing import parse_ymd
from glass_processor_pipeline import stream_to_tmp_csv, tmp_csv_to_excel


class GlassProcessorUI(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Glass Processor - Friendly UI")
        self.geometry("920x620")

        self.var_input = tk.StringVar(value=INPUT_DEFAULT)
        self.var_start = tk.StringVar(value=START_DEFAULT)
        self.var_end = tk.StringVar(value=END_DEFAULT)
        self.var_pattern = tk.StringVar(value=PATTERN_DEFAULT)
        self.var_output = tk.StringVar(value=OUTPUT_DEFAULT)
        self.var_tmp = tk.StringVar(value=TMP_CSV_DEFAULT)
        self.var_buffer = tk.StringVar(value="200000")
        self.var_keep_tmp = tk.BooleanVar(value=False)

        self._build_widgets()

    def _build_widgets(self) -> None:
        frm = ttk.Frame(self, padding=12)
        frm.pack(fill=tk.BOTH, expand=True)

        ttk.Label(frm, text="Input root (UNC path)").grid(row=0, column=0, sticky="w")
        ttk.Entry(frm, textvariable=self.var_input, width=90).grid(row=1, column=0, sticky="ew", padx=(0, 8))

        ttk.Label(frm, text="Date range").grid(row=2, column=0, sticky="w", pady=(10, 0))
        date_row = ttk.Frame(frm)
        date_row.grid(row=3, column=0, sticky="ew")
        ttk.Label(date_row, text="Start").pack(side=tk.LEFT)
        ttk.Entry(date_row, textvariable=self.var_start, width=16).pack(side=tk.LEFT, padx=(8, 16))
        ttk.Label(date_row, text="End").pack(side=tk.LEFT)
        ttk.Entry(date_row, textvariable=self.var_end, width=16).pack(side=tk.LEFT, padx=8)

        ttk.Label(frm, text="File pattern").grid(row=4, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(frm, textvariable=self.var_pattern, width=45).grid(row=5, column=0, sticky="w")

        ttk.Label(frm, text="Output XLSX").grid(row=6, column=0, sticky="w", pady=(10, 0))
        out_row = ttk.Frame(frm)
        out_row.grid(row=7, column=0, sticky="ew")
        ttk.Entry(out_row, textvariable=self.var_output, width=78).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(out_row, text="Browse", command=self._browse_output).pack(side=tk.LEFT, padx=(8, 0))

        ttk.Label(frm, text="Temporary CSV").grid(row=8, column=0, sticky="w", pady=(10, 0))
        tmp_row = ttk.Frame(frm)
        tmp_row.grid(row=9, column=0, sticky="ew")
        ttk.Entry(tmp_row, textvariable=self.var_tmp, width=78).pack(side=tk.LEFT, fill=tk.X, expand=True)
        ttk.Button(tmp_row, text="Browse", command=self._browse_tmp).pack(side=tk.LEFT, padx=(8, 0))

        adv_row = ttk.Frame(frm)
        adv_row.grid(row=10, column=0, sticky="w", pady=(10, 0))
        ttk.Label(adv_row, text="Buffer rows").pack(side=tk.LEFT)
        ttk.Entry(adv_row, textvariable=self.var_buffer, width=12).pack(side=tk.LEFT, padx=(8, 16))
        ttk.Checkbutton(adv_row, text="Keep temp CSV", variable=self.var_keep_tmp).pack(side=tk.LEFT)

        action_row = ttk.Frame(frm)
        action_row.grid(row=11, column=0, sticky="ew", pady=(14, 8))
        ttk.Button(action_row, text="Run processing", command=self._run_clicked).pack(side=tk.LEFT)

        ttk.Label(frm, text="Logs").grid(row=12, column=0, sticky="w")
        self.log = tk.Text(frm, height=16, wrap="word")
        self.log.grid(row=13, column=0, sticky="nsew")

        frm.columnconfigure(0, weight=1)
        frm.rowconfigure(13, weight=1)

    def _browse_output(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".xlsx", filetypes=[("Excel", "*.xlsx")])
        if path:
            self.var_output.set(path)

    def _browse_tmp(self) -> None:
        path = filedialog.asksaveasfilename(defaultextension=".csv", filetypes=[("CSV", "*.csv")])
        if path:
            self.var_tmp.set(path)

    def _append_log(self, msg: str) -> None:
        self.log.insert(tk.END, msg + "\n")
        self.log.see(tk.END)
        self.update_idletasks()

    def _run_clicked(self) -> None:
        t = threading.Thread(target=self._run_processing, daemon=True)
        t.start()

    def _run_processing(self) -> None:
        try:
            start_d = parse_ymd(self.var_start.get())
            end_d = parse_ymd(self.var_end.get())
            if end_d < start_d:
                raise ValueError("End date must be >= start date")

            buffer_rows = int(self.var_buffer.get())
            if buffer_rows <= 0:
                raise ValueError("Buffer rows must be > 0")

            input_root = Path(self.var_input.get())
            tmp_csv = Path(self.var_tmp.get())
            output_xlsx = Path(self.var_output.get())

            self._append_log("Starting processing...")
            rows = stream_to_tmp_csv(
                input_root=input_root,
                start_d=start_d,
                end_d=end_d,
                pattern=self.var_pattern.get(),
                tmp_csv=tmp_csv,
                flush_rows=buffer_rows,
            )
            self._append_log(f"TMP CSV ready with {rows:,} rows. Exporting Excel...")
            tmp_csv_to_excel(tmp_csv, output_xlsx)
            self._append_log(f"Done. Excel written to: {output_xlsx}")

            if not self.var_keep_tmp.get() and tmp_csv.exists():
                tmp_csv.unlink()
                self._append_log(f"Removed temp file: {tmp_csv}")

            messagebox.showinfo("Success", "Processing completed successfully.")
        except Exception as exc:
            self._append_log(f"[ERROR] {exc}")
            messagebox.showerror("Error", str(exc))


if __name__ == "__main__":
    app = GlassProcessorUI()
    app.mainloop()
