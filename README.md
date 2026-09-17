# EMBRACE-2 EQD2 Dashboard

A Python desktop port of `EMBRACE2_EQD2_Excel_Autogenerator (19).m` supplied September 16, 2026. The Python interface follows the MATLAB dashboard: patient and plan details, prior RT, targets, organs at risk, editable physical doses and volumes, calculated EQD2 rows, colored totals, and Excel export.

## Launch

- **macOS:** double-click `Python/Launch_EMBRACE.command`. On the development Mac this selects the compatible Python runtime bundled with Codex; elsewhere it uses `python3`.
- **Windows:** double-click `Python/Launch_EMBRACE.bat`.
- **Terminal:** `python3 Python/EMBRACE2_EQD2_Excel_Autogenerator.py`.

Requires Python 3.9+ with working Tkinter. For source-code execution, install PDF support with `python3 -m pip install -r Python/requirements.txt`. Packaged applications include all dependencies. MATLAB and Excel are not required to run the dashboard. Excel is needed to recalculate the exported template formulas. The macOS system Python/Tk on the development machine crashes during window creation; the launcher avoids that installation when the bundled runtime is available.

## Workflow

1. Select 3, 4, or 5 brachytherapy fractions (default: 4).
2. Load each fraction's cumulative absolute DVH TXT using its Load button. The button determines the fraction; ROI suffixes do not select it.
3. Each import fills that fraction and later fractions not explicitly loaded. Explicit later imports are protected. Manual edits affect only the edited cell and do not protect the fraction from subsequent carry-forward.
4. Edit blue physical-dose cells and prior RT values. Structure names are neutral and volumes are read-only. Press Enter or leave the cell to calculate. Prior RT defaults to 1.8 Gy × 25 fractions.
5. Export the current course. The app finds `EQD2_with_tolerances_090126.xlsx` beside the script or in `Matlab`, or prompts for a template. It updates every sheet whose name contains `FX1-4`.

Green totals meet the planning goal / soft constraint. Yellow totals miss that goal but meet the tolerance / hard constraint. Red totals fail the tolerance. Blank constraints have no color. Comparisons retain MATLAB's strict `<` and `>` operators and inclusive `90–95` range.

## Calculation parity

- Dose contribution: `d × (1 + d/(α/β)) / (1 + 2/(α/β))`.
- α/β = 10 Gy for targets, 3 Gy for OARs. Prior RT contribution uses its dose per fraction and fraction count.
- Target metrics: GTV_res D98; CTV_HR D98/D90/D50; CTV_IR D98/D90. OAR metrics: bladder, rectum, sigmoid and bowel D0.1cc/D2cc. Each structure has a per-fraction volume.
- Structure aliases, dose-sorted linear interpolation, nearest-volume fallback and maximum cumulative volume follow the supplied MATLAB code.
- Imported and edited physical values are stored to two decimal places before EQD2 calculation, matching MATLAB's table behavior. Totals sum unrounded EQD2 contributions, then display one decimal. Constraint colors retain the original two-decimal comparison precision; display rounding does not change the stored doses or calculations.
- Shortening the course clears inactive fractions. Expanding it copies the most recent explicitly loaded fraction into new columns. Clear All preserves the selected course length and resets prior RT.
- As in MATLAB, metrics absent from a subsequent DVH import retain existing values; clear the dashboard when beginning a new case. Duplicate recognized ROIs use the last matching ROI in file order.

## Deliberate safeguards in the Python port

Patient name and ID are checked together before changing course state. Nonfinite numeric input and explicitly relative volume exports are rejected. The source template cannot be overwritten. Export clears missing/inactive physical inputs, including the template's sixth-fraction column, so its sample values and physical carry formulas cannot contribute. Calculated formulas, formatting and other archive contents remain intact. Stale formula caches in updated sheets are removed and full Excel recalculation is requested on open. The exporter expects the supplied template's existing cell layout.

The template contains additional sections beyond the dashboard; those remain unchanged. Export is a populated template, not a screenshot of the dashboard. Blank metrics can display differently after Excel recalculates the template's existing formulas.

## Verification

Run `python3 -m unittest discover -s Python/tests -v`. Synthetic tests cover unit conversion, metrics, interpolation boundaries, invalid input, carry protection, course resizing, atomic patient mismatch handling, prior RT/EQD2, rounding, constraint boundaries and export preservation. No patient DVH data is included.

A live Tkinter smoke test verified window construction, the displayed EQD2 result and fraction controls. The port was checked against the MATLAB source; MATLAB execution and native Excel recalculation have not been performed. Clinical commissioning against approved cases remains separate from these software tests.

The earlier `Python/DVH_to_EQD2.py` single-fraction utility is retained but is not used by this dashboard.

## Standalone applications

Packaged builds include Python, Tkinter, and the Excel template. End users do not need to install Python.

- **Apple Silicon Mac:** unzip `EMBRACE-EQD2-macOS-arm64.zip`, then open `EMBRACE EQD2.app`. You may drag it to Applications.
- **64-bit Windows:** unzip `EMBRACE-EQD2-Windows-x64.zip`, then double-click `EMBRACE EQD2.exe`.

The Mac build targets Apple Silicon (M-series), not Intel Macs. These builds have no publisher certificate or Apple notarization; another computer may display an operating-system security prompt. Organization-managed computers may require IT approval.

GitHub Actions builds both platforms and retains downloadable ZIP artifacts for 30 days. Find the latest successful **Build desktop applications** run under the repository's **Actions** tab. Patient files are not included or sent to the build service.

To rebuild locally, create a virtual environment on the target operating system, install `packaging/requirements.txt`, and run `python packaging/build.py`. The script builds the app, launches the packaged executable for GUI/calculation/template-export checks, then creates the ZIP in `dist`. Windows executables must be built on Windows. The build smoke-test report is stored in `build/packaged-smoke-test.json`.


## Compact dashboard and PDF reports

The dashboard uses one decimal place for displayed dose/volume values, retains input precision for calculation, keeps fraction headers visible during scrolling, and reserves blue for editable dose inputs. Structure names and read-only DVH volumes use neutral backgrounds. Source filenames are available under **Show source files**.

**Export PDF** creates a printable report of the current course, with separate target and OAR pages, prior RT, per-fraction physical doses and EQD2, totals, constraints, color coding and source-file details. PDF generation does not require Excel. The Excel exporter continues to preserve the supplied template's styles and formulas.

## Plan comparison tab

Load one TXT into each of up to four plan slots. Each slot is an independent scenario: the same DVH doses are repeated for the selected 3, 4, or 5 fractions, then the shared prior RT contribution is added. Physical-dose rows show one fraction; total EQD2 rows show the entire scenario. Planning goals and soft/hard constraints are the same as the course dashboard. The comparison has its own fraction-count selector so exploring a shorter course does not erase imported fractions in the dashboard. Changing the comparison count or shared prior RT updates every loaded comparison plan.

Plans must refer to the same patient. The comparison and dashboard keep their DVH inputs separate. A plan reload fully replaces that comparison slot, including clearing metrics absent from the new file. **Export comparison PDF** saves the side-by-side scenario results. Empty cells indicate unavailable metrics, not zero dose.
