# Missing Trace ID Tool

This project is a desktop spreadsheet workflow for finding missing
identifiers and exporting the gaps to a new CSV or Excel file.

It currently supports two pipelines in the same interface:

- Trace IDs in the format `TMGID######`
- Company IDs in the format `ACC######`
- Optional Zoho CRM fetches for Trace ID and Company ID lookup datasets

## Current Scope

- Import a CSV, TSV, or Excel file with record data
- Fetch Trace ID records from Zoho CRM
- Fetch Company ID records from Zoho CRM
- Auto-detect Trace ID and Company ID columns
- Run either pipeline independently or both together
- Accept optional expected totals for each ID type
- Find missing `TMGID######` and `ACC######` values
- Export the missing IDs to a CSV or Excel report
- Provide a simple PySide6 interface for non-technical users

## Detection Rules

- The app first looks for column headers related to Trace ID or Company ID
- If a header is not found, it falls back to scanning sample values for
  entries that start with `TMGID` or `ACC`
- If both are found, both pipelines are enabled and calculated together
- If only one is found, the other pipeline stays disabled

## Tech Stack

- Python
- PySide6
- pandas
- PyInstaller
- requests

## Project Structure

```text
main.py                         # Application entry point
main_window.py                  # Main window and UI workflow
trace_logic.py                  # Identifier parsing and gap logic
zoho_client.py                  # Embedded Zoho CRM client for standalone builds
zoho_integration.py             # Zoho lookup dataset fetch helpers
zoho_trace_id_gap_finder.spec   # PyInstaller build configuration
requirements.txt                # Runtime dependencies
README.md                       # Project overview
AGENTS.md                       # AI-focused project map and guidance
.gitignore                      # Repository ignore rules
data/                           # Local sample files and exports (ignored)
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

For Zoho fetch support, place `.env` beside `main.py` during development or
beside the packaged executable after building. The local `.zoho_cache.json`
token cache is also stored beside the app.

## Current Workflow

1. Open the app and import a CSV, TSV, or Excel file, and/or fetch a pipeline
   dataset from Zoho CRM.
2. The app tries to auto-detect Trace ID and Company ID columns per pipeline.
3. It extracts the numeric part of each matching ID series.
4. It finds missing values in each enabled pipeline.
5. If an expected total is entered, the search range expands to that value.
6. The app exports the missing IDs to a new CSV or Excel file.

## Packaging

```bash
pyinstaller zoho_trace_id_gap_finder.spec
```

The current spec is configured for a one-file Windows build with no console
window and uses `missing_id_icon.ico` as the executable icon. The output file
name is `Missing Trace-Company ID Tool.exe` because Windows does not allow `/`
in executable file names.

If you regenerate the executable from the command line instead of the spec,
use the equivalent options:

```bash
pyinstaller --onefile --windowed --name "Missing Trace-Company ID Tool" --icon missing_id_icon.ico main.py
```

Build outputs are created in `build/` and `dist/`, which are ignored by git.

## Notes

- The current parser expects values like `TMGID000123` and `ACC000123`
- Each pipeline can use its own in-memory dataframe source
- If an export file is open in Excel, saving may fail until the file is closed
- `data/` is for local inputs and outputs and is intentionally ignored
- There are no automated tests yet, so manual verification is still important
