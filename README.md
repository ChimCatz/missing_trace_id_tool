# Missing Trace ID Tool

This project is a desktop CSV workflow for finding missing identifiers and
exporting the gaps to a new CSV.

It currently supports two pipelines in the same interface:

- Trace IDs in the format `TMGID######`
- Company IDs in the format `ACC######`

## Current Scope

- Import a CSV file with record data
- Auto-detect Trace ID and Company ID columns
- Run either pipeline independently or both together
- Accept optional expected totals for each ID type
- Find missing `TMGID######` and `ACC######` values
- Export the missing IDs to a CSV report
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

## Project Structure

```text
main.py                         # Application entry point
main_window.py                  # Main window and UI workflow
trace_logic.py                  # Identifier parsing and gap logic
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

## Current Workflow

1. Open the app and import a CSV file.
2. The app tries to auto-detect Trace ID and Company ID columns.
3. It extracts the numeric part of each matching ID series.
4. It finds missing values in each enabled pipeline.
5. If an expected total is entered, the search range expands to that value.
6. The app exports the missing IDs to a new CSV file.

## Packaging

```bash
pyinstaller zoho_trace_id_gap_finder.spec
```

Build outputs are created in `build/` and `dist/`, which are ignored by git.

## Notes

- The current parser expects values like `TMGID000123` and `ACC000123`
- If an export file is open in Excel, saving may fail until the file is closed
- `data/` is for local inputs and outputs and is intentionally ignored
- There are no automated tests yet, so manual verification is still important
