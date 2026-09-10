DVH → EQD2 Autopopulator
==========================

What it does
------------
- Reads an absolute cumulative DVH .txt export.
- Detects the fraction from ROI suffixes such as "_fx1" (or from the Plan line).
- Converts cGy to Gy when required.
- Interpolates cumulative DVH values to calculate:
  * GTVres: D98
  * CTV_HR: D98, D90, D50
  * CTV_IR: D98, D90
  * Bladder / Rectum / Sigmoid / Bowel: D0.1 cc and D2 cc
- Writes the physical dose and structure-volume values into the selected
  FX1-4 worksheet at the correct fraction column (F1=C ... F6=H).
- Leaves the workbook's EQD2 formulas, tolerances, formatting, and other
  worksheet content intact.
- Unmatched structures are reported but ignored.

Run it
------
1. Keep "DVH_to_EQD2.py" and the EQD2 workbook in the same folder.
2. Double-click the script if .py files are associated with Python, or run:
       python DVH_to_EQD2.py
3. Choose the DVH .txt export.
4. Choose the desired worksheet (HIPO, Clinical_GP, Goal, etc.).
5. Click "Preview values".
6. Click "Populate EQD2 workbook".
7. Open the new workbook in Excel. It is flagged for full recalculation.

Python
------
The application uses only Python's standard library (including tkinter).
No pip-installed packages are required.

Important QA note
-----------------
This is a clinical workflow automation aid. Independently verify the first
several cases against your TPS / approved manual workflow before clinical use,
especially ROI naming, DVH export mode/units, fraction identification, and the
definition/interpolation of D0.1 cc / D2 cc / Dx metrics.
