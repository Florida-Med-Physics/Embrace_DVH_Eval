#!/usr/bin/env python3
"""
DVH -> EQD2 Autopopulator
-------------------------
Reads an absolute cumulative DVH text export and writes physical dose values
into an existing gynecologic HDR EQD2 workbook, preserving the workbook's
existing EQD2 formulas and formatting.

No third-party Python packages are required.
"""

import os
import re
import shutil
import tempfile
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

NS_MAIN = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"
NS_REL = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_PKGREL = "http://schemas.openxmlformats.org/package/2006/relationships"
ET.register_namespace("", NS_MAIN)
ET.register_namespace("r", NS_REL)

Q = lambda tag: f"{{{NS_MAIN}}}{tag}"

FRACTION_COLS = {1: "C", 2: "D", 3: "E", 4: "F", 5: "G", 6: "H"}

# Physical-dose/volume cells in the EQD2 template.
# Metrics are only written when that metric exists in the worksheet template.
STRUCTURES = {
    "gtvres": {
        "aliases": ["gtvres"],
        "volume_row": 38,
        "metrics": {"D98": 39},
        "kind": "target",
    },
    "ctv_hr": {
        "aliases": ["ctv_hr", "ctvhr"],
        "volume_row": 42,
        "metrics": {"D98": 43, "D90": 45, "D50": 47},
        "kind": "target",
    },
    "ctv_ir": {
        "aliases": ["ctv_ir", "ctvir"],
        "volume_row": 50,
        "metrics": {"D98": 51, "D90": 53},
        "kind": "target",
    },
    "bladder": {
        "aliases": ["bladder"],
        "volume_row": 56,
        "metrics": {"D0.1cc": 59, "D2cc": 61},
        "kind": "oar",
    },
    "rectum": {
        "aliases": ["rectum"],
        "volume_row": 64,
        "metrics": {"D0.1cc": 67, "D2cc": 69},
        "kind": "oar",
    },
    "sigmoid": {
        "aliases": ["colon_sigmoid", "sigmoid"],
        "volume_row": 72,
        "metrics": {"D0.1cc": 73, "D2cc": 75},
        "kind": "oar",
    },
    "bowel": {
        "aliases": ["bowel", "intestines", "intestine"],
        "volume_row": 78,
        "metrics": {"D0.1cc": 79, "D2cc": 81},
        "kind": "oar",
    },
}


def normalize_roi(name):
    s = name.strip().lower()
    s = re.sub(r"_fx[1-6]\b", "", s)
    s = re.sub(r"[^a-z0-9]+", "_", s).strip("_")
    return s


def structure_key(roi_name):
    n = normalize_roi(roi_name)
    for key, cfg in STRUCTURES.items():
        if n in cfg["aliases"]:
            return key
    return None


def parse_dvh(path):
    text = Path(path).read_text(encoding="utf-8", errors="replace")

    dose_unit = "cGy" if re.search(r"Absolute Dose\s*-\s*\[cGy\]", text, re.I) else "Gy"
    if not re.search(r"Cumulative mode", text, re.I):
        raise ValueError("This app expects a cumulative DVH export.")

    patient = re.search(r"^Patient:\s*(.*)$", text, re.M)
    patient_id = re.search(r"^Patient Id:\s*(.*)$", text, re.M)
    plan = re.search(r"^Plan:\s*(.*)$", text, re.M)

    roi_parts = re.split(r"^ROI:\s*(.+?)\s*$", text, flags=re.M)
    rois = {}
    fractions = set()

    for i in range(1, len(roi_parts), 2):
        roi_name = roi_parts[i].strip()
        body = roi_parts[i + 1]

        mfx = re.search(r"_fx([1-6])\b", roi_name, re.I)
        if mfx:
            fractions.add(int(mfx.group(1)))

        rows = []
        for m in re.finditer(
            r"^\s*\d+\s+([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s+"
            r"([-+]?\d*\.?\d+(?:[Ee][-+]?\d+)?)\s*$",
            body,
            flags=re.M,
        ):
            dose = float(m.group(1))
            vol = float(m.group(2))
            if dose_unit.lower() == "cgy":
                dose /= 100.0
            rows.append((dose, vol))

        # Some ROIs can be present without DVH data (e.g. Implant).
        if rows:
            rois[roi_name] = rows

    # Fallback to Plan name if ROI suffixes do not identify a fraction.
    if not fractions and plan:
        mfx = re.search(r"fx\s*([1-6])", plan.group(1), re.I)
        if mfx:
            fractions.add(int(mfx.group(1)))

    if len(fractions) != 1:
        raise ValueError(
            "Could not uniquely determine the fraction number. "
            f"Detected fractions: {sorted(fractions) if fractions else 'none'}"
        )

    return {
        "patient": patient.group(1).strip() if patient else "",
        "patient_id": patient_id.group(1).strip() if patient_id else "",
        "plan": plan.group(1).strip() if plan else "",
        "fraction": next(iter(fractions)),
        "rois": rois,
        "dose_unit": dose_unit,
    }


def dose_at_cumulative_volume(rows, target_cc):
    """Linear interpolation of dose at an absolute cumulative volume."""
    if not rows:
        return None

    rows = sorted(rows, key=lambda x: x[0])

    # DVH export may start above 0 Gy. If requested volume is above the first
    # cumulative volume, the dose is effectively below the first bin.
    if target_cc >= rows[0][1]:
        return 0.0

    for (d1, v1), (d2, v2) in zip(rows, rows[1:]):
        if (v1 >= target_cc >= v2) or (v1 <= target_cc <= v2):
            if abs(v2 - v1) < 1e-12:
                return d1
            f = (target_cc - v1) / (v2 - v1)
            return d1 + f * (d2 - d1)

    # If the requested hottest volume is smaller than the final reported
    # cumulative volume, use the last available dose bin.
    if target_cc <= rows[-1][1]:
        return rows[-1][0]

    return None


def calculate_metrics(parsed):
    results = {}
    ignored = []

    for roi_name, rows in parsed["rois"].items():
        key = structure_key(roi_name)
        if not key:
            ignored.append(roi_name)
            continue

        cfg = STRUCTURES[key]
        total_cc = rows[0][1]
        metrics = {}

        if cfg["kind"] == "target":
            for metric in cfg["metrics"]:
                pct = float(metric[1:])  # D98 -> 98
                metrics[metric] = dose_at_cumulative_volume(
                    rows, total_cc * pct / 100.0
                )
        else:
            if "D0.1cc" in cfg["metrics"]:
                metrics["D0.1cc"] = dose_at_cumulative_volume(rows, 0.1)
            if "D2cc" in cfg["metrics"]:
                metrics["D2cc"] = dose_at_cumulative_volume(rows, 2.0)

        results[key] = {
            "roi_name": roi_name,
            "volume_cc": total_cc,
            "metrics": metrics,
        }

    return results, ignored


def _xlsx_sheet_paths(xlsx_path):
    with zipfile.ZipFile(xlsx_path, "r") as zin:
        wb_root = ET.fromstring(zin.read("xl/workbook.xml"))
        rel_root = ET.fromstring(zin.read("xl/_rels/workbook.xml.rels"))

        rels = {}
        for rel in rel_root:
            rels[rel.attrib["Id"]] = rel.attrib["Target"]

        sheets = {}
        sheets_node = wb_root.find(Q("sheets"))
        for s in sheets_node:
            name = s.attrib["name"]
            rid = s.attrib[f"{{{NS_REL}}}id"]
            target = rels[rid]
            if target.startswith("/"):
                target = target.lstrip("/")
            elif not target.startswith("xl/"):
                target = "xl/" + target
            sheets[name] = target.replace("\\", "/")
        return sheets


def list_sheet_names(xlsx_path):
    return list(_xlsx_sheet_paths(xlsx_path).keys())


def _col_num(col):
    n = 0
    for ch in col:
        n = n * 26 + (ord(ch.upper()) - 64)
    return n


def _cell_ref_parts(ref):
    m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
    return m.group(1), int(m.group(2))


def _ensure_cell(sheet_root, cell_ref):
    col, row_num = _cell_ref_parts(cell_ref)
    sheet_data = sheet_root.find(Q("sheetData"))
    if sheet_data is None:
        sheet_data = ET.SubElement(sheet_root, Q("sheetData"))

    row = None
    for r in sheet_data.findall(Q("row")):
        if int(r.attrib.get("r", "0")) == row_num:
            row = r
            break
    if row is None:
        row = ET.Element(Q("row"), {"r": str(row_num)})
        inserted = False
        for idx, r in enumerate(list(sheet_data)):
            if int(r.attrib.get("r", "0")) > row_num:
                sheet_data.insert(idx, row)
                inserted = True
                break
        if not inserted:
            sheet_data.append(row)

    for c in row.findall(Q("c")):
        if c.attrib.get("r") == cell_ref:
            return c

    new_cell = ET.Element(Q("c"), {"r": cell_ref})
    new_col_num = _col_num(col)
    inserted = False
    for idx, c in enumerate(list(row)):
        cref = c.attrib.get("r", "")
        if cref:
            ccol, _ = _cell_ref_parts(cref)
            if _col_num(ccol) > new_col_num:
                row.insert(idx, new_cell)
                inserted = True
                break
    if not inserted:
        row.append(new_cell)
    return new_cell


def _set_numeric_cell(sheet_root, cell_ref, value):
    cell = _ensure_cell(sheet_root, cell_ref)

    # Preserve style/index attributes but replace formula/content with a value.
    for child in list(cell):
        if child.tag in (Q("f"), Q("v"), Q("is")):
            cell.remove(child)
    cell.attrib.pop("t", None)

    v = ET.SubElement(cell, Q("v"))
    v.text = f"{float(value):.12g}"


def populate_workbook(template_path, output_path, sheet_name, parsed, metrics):
    sheet_paths = _xlsx_sheet_paths(template_path)
    if sheet_name not in sheet_paths:
        raise ValueError(f"Worksheet not found: {sheet_name}")

    target_sheet_path = sheet_paths[sheet_name]
    fraction = parsed["fraction"]
    col = FRACTION_COLS[fraction]

    updates = {}
    for key, result in metrics.items():
        cfg = STRUCTURES[key]

        # Volume: write only into the fraction column, same convention as doses.
        updates[f"{col}{cfg['volume_row']}"] = result["volume_cc"]

        for metric_name, value in result["metrics"].items():
            if value is None:
                continue
            row = cfg["metrics"].get(metric_name)
            if row:
                updates[f"{col}{row}"] = value

    # Copy zip to a new archive, replacing only the selected worksheet XML and
    # requesting a full Excel recalculation on open.
    with zipfile.ZipFile(template_path, "r") as zin:
        with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)

                if item.filename == target_sheet_path:
                    root = ET.fromstring(data)
                    for ref, val in updates.items():
                        _set_numeric_cell(root, ref, val)
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)

                elif item.filename == "xl/workbook.xml":
                    root = ET.fromstring(data)
                    calcpr = root.find(Q("calcPr"))
                    if calcpr is None:
                        calcpr = ET.SubElement(root, Q("calcPr"))
                    calcpr.set("calcMode", "auto")
                    calcpr.set("fullCalcOnLoad", "1")
                    calcpr.set("forceFullCalc", "1")
                    data = ET.tostring(root, encoding="utf-8", xml_declaration=True)

                zout.writestr(item, data)

    return updates


def default_output_name(template_path, parsed):
    p = Path(template_path)
    stem = p.stem
    label = parsed.get("patient_id") or parsed.get("patient") or parsed.get("plan") or "populated"
    label = re.sub(r"[^A-Za-z0-9._-]+", "_", label).strip("_")
    return str(p.with_name(f"{stem}_{label}_Fx{parsed['fraction']}{p.suffix}"))


class App(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("DVH → EQD2 Autopopulator")
        self.geometry("790x630")
        self.minsize(740, 560)

        self.dvh_var = tk.StringVar()
        self.template_var = tk.StringVar()
        self.output_var = tk.StringVar()
        self.sheet_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Choose a DVH .txt file and EQD2 workbook.")

        self._build()

        local_template = Path(__file__).with_name("EQD2_with_tolerances_090126.xlsx")
        if local_template.exists():
            self.template_var.set(str(local_template))
            self.refresh_sheets()

    def _build(self):
        pad = {"padx": 12, "pady": 7}

        title = ttk.Label(self, text="DVH → EQD2 Autopopulator", font=("TkDefaultFont", 16, "bold"))
        title.pack(pady=(14, 5))

        subtitle = ttk.Label(
            self,
            text="Imports an absolute cumulative DVH text export and fills one fraction column while preserving EQD2 formulas.",
            wraplength=740,
            justify="center",
        )
        subtitle.pack(pady=(0, 12))

        form = ttk.Frame(self)
        form.pack(fill="x", padx=16)

        self._file_row(form, 0, "DVH text file", self.dvh_var, self.pick_dvh)
        self._file_row(form, 1, "EQD2 workbook", self.template_var, self.pick_template)
        self._file_row(form, 2, "Output workbook", self.output_var, self.pick_output)

        ttk.Label(form, text="Worksheet").grid(row=3, column=0, sticky="w", **pad)
        self.sheet_combo = ttk.Combobox(form, textvariable=self.sheet_var, state="readonly", width=52)
        self.sheet_combo.grid(row=3, column=1, sticky="ew", **pad)
        ttk.Button(form, text="Refresh", command=self.refresh_sheets).grid(row=3, column=2, **pad)
        form.columnconfigure(1, weight=1)

        ttk.Separator(self).pack(fill="x", padx=16, pady=10)

        button_frame = ttk.Frame(self)
        button_frame.pack(fill="x", padx=16)
        ttk.Button(button_frame, text="Preview values", command=self.preview).pack(side="left")
        ttk.Button(button_frame, text="Populate EQD2 workbook", command=self.run_populate).pack(side="right")

        ttk.Label(self, text="Preview / log").pack(anchor="w", padx=18, pady=(12, 4))
        self.log = tk.Text(self, height=20, wrap="word")
        self.log.pack(fill="both", expand=True, padx=16, pady=(0, 10))

        ttk.Label(self, textvariable=self.status_var).pack(fill="x", padx=16, pady=(0, 12))

    def _file_row(self, parent, row, label, var, command):
        pad = {"padx": 12, "pady": 7}
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", **pad)
        ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", **pad)
        ttk.Button(parent, text="Browse…", command=command).grid(row=row, column=2, **pad)

    def pick_dvh(self):
        p = filedialog.askopenfilename(
            title="Choose DVH text export",
            filetypes=[("Text files", "*.txt"), ("All files", "*.*")]
        )
        if p:
            self.dvh_var.set(p)
            try:
                parsed = parse_dvh(p)
                if self.template_var.get() and not self.output_var.get():
                    self.output_var.set(default_output_name(self.template_var.get(), parsed))
                self.preview()
            except Exception as e:
                messagebox.showerror("DVH error", str(e))

    def pick_template(self):
        p = filedialog.askopenfilename(
            title="Choose EQD2 workbook",
            filetypes=[("Excel workbooks", "*.xlsx *.xlsm"), ("All files", "*.*")]
        )
        if p:
            self.template_var.set(p)
            self.refresh_sheets()
            if self.dvh_var.get():
                try:
                    parsed = parse_dvh(self.dvh_var.get())
                    self.output_var.set(default_output_name(p, parsed))
                except Exception:
                    pass

    def pick_output(self):
        ext = Path(self.template_var.get()).suffix or ".xlsx"
        p = filedialog.asksaveasfilename(
            title="Save populated workbook as",
            defaultextension=ext,
            filetypes=[("Excel workbook", f"*{ext}"), ("All files", "*.*")]
        )
        if p:
            self.output_var.set(p)

    def refresh_sheets(self):
        p = self.template_var.get().strip()
        if not p:
            return
        try:
            names = list_sheet_names(p)
            preferred = [n for n in names if "FX1-4" in n.upper()]
            self.sheet_combo["values"] = preferred or names
            if self.sheet_var.get() not in (preferred or names):
                self.sheet_var.set((preferred or names)[0] if (preferred or names) else "")
        except Exception as e:
            messagebox.showerror("Workbook error", str(e))

    def _get_data(self):
        if not self.dvh_var.get():
            raise ValueError("Choose a DVH text file.")
        if not self.template_var.get():
            raise ValueError("Choose an EQD2 workbook.")
        if not self.sheet_var.get():
            raise ValueError("Choose a worksheet.")

        parsed = parse_dvh(self.dvh_var.get())
        metrics, ignored = calculate_metrics(parsed)

        if not metrics:
            raise ValueError("No recognized EQD2 structures were found in the DVH file.")

        if not self.output_var.get():
            self.output_var.set(default_output_name(self.template_var.get(), parsed))

        return parsed, metrics, ignored

    def preview(self):
        try:
            parsed, metrics, ignored = self._get_data()
        except Exception as e:
            self.log.delete("1.0", "end")
            self.log.insert("end", str(e))
            return

        self.log.delete("1.0", "end")
        self.log.insert("end", f"Patient: {parsed['patient']}\n")
        self.log.insert("end", f"Patient ID: {parsed['patient_id']}\n")
        self.log.insert("end", f"Plan: {parsed['plan']}\n")
        self.log.insert("end", f"Detected fraction: F{parsed['fraction']}\n")
        self.log.insert("end", f"Input dose unit: {parsed['dose_unit']} (converted to Gy for workbook)\n\n")

        labels = {
            "gtvres": "GTVres", "ctv_hr": "CTVHR", "ctv_ir": "CTVIR",
            "bladder": "Bladder", "rectum": "Rectum",
            "sigmoid": "Sigmoid", "bowel": "Bowel"
        }

        for key, result in metrics.items():
            self.log.insert("end", f"{labels[key]}  [{result['roi_name']}]\n")
            self.log.insert("end", f"  Volume: {result['volume_cc']:.3f} cc\n")
            for m, v in result["metrics"].items():
                self.log.insert("end", f"  {m}: {v:.3f} Gy\n")
            self.log.insert("end", "\n")

        if ignored:
            self.log.insert("end", "Ignored ROIs (no matching EQD2 row):\n")
            for roi in ignored:
                self.log.insert("end", f"  - {roi}\n")

        self.status_var.set("Preview complete. Review values, then populate the workbook.")

    def run_populate(self):
        try:
            parsed, metrics, ignored = self._get_data()
            out = self.output_var.get().strip()
            if os.path.abspath(out) == os.path.abspath(self.template_var.get()):
                raise ValueError("Choose a different output filename so the template is not overwritten.")

            updates = populate_workbook(
                self.template_var.get(),
                out,
                self.sheet_var.get(),
                parsed,
                metrics,
            )

            self.preview()
            self.log.insert("end", "\nCells written:\n")
            for ref, val in sorted(updates.items(), key=lambda kv: (_cell_ref_parts(kv[0])[1], _col_num(_cell_ref_parts(kv[0])[0]))):
                self.log.insert("end", f"  {ref} = {val:.4f}\n")

            self.status_var.set(f"Done: {out}")
            messagebox.showinfo(
                "Complete",
                f"Populated F{parsed['fraction']} on worksheet:\n{self.sheet_var.get()}\n\nSaved to:\n{out}"
            )
        except Exception as e:
            messagebox.showerror("Error", str(e))
            self.status_var.set("Error — see message.")

if __name__ == "__main__":
    App().mainloop()
