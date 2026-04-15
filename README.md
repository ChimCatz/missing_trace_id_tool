# Missing Trace ID Tool v2

Desktop tool for scanning CSV files, detecting missing `TMGID` trace IDs, and exporting the gaps to a CSV report.

## What It Does

- Imports a CSV file containing trace records
- Auto-detects the most likely Trace ID column
- Lets the user optionally enter an expected total record count
- Calculates missing `TMGID######` values from the detected range
- Exports the missing IDs to a new CSV file
- Provides a simple PySide6 desktop interface for non-technical users

## Tech Stack

- Python
- PySide6
- pandas
- PyInstaller for packaging

## Project Structure

```text
main.py                         # App entry point
main_window.py                  # Main UI and user workflow
trace_logic.py                  # Trace parsing and missing-ID logic
zoho_trace_id_gap_finder.spec   # PyInstaller build config
requirements.txt                # Python dependencies
README.md                       # Human overview
AGENTS.md                       # AI-focused project map and editing guidance
.gitignore
data/                           # Local sample/input/output files (ignored)
```

`data/` is optional and can be created locally when needed for sample files or exports.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## How It Works

1. Open the app and import a CSV file.
2. The app tries to auto-detect the trace ID column.
3. It extracts the numeric part of each trace ID.
4. It finds missing values between `1` and the highest detected ID.
5. If an expected total is entered, the range expands to that value when needed.
6. The missing IDs can then be exported as a CSV.

## Packaging

To build a Windows executable with PyInstaller:

```bash
pyinstaller zoho_trace_id_gap_finder.spec
```

Build outputs are generated in `build/` and `dist/`, which are intentionally ignored by git.

## Notes

- The app expects trace IDs in a format like `TMGID000123`
- If a CSV is open in Excel, exporting may fail until the file is closed
- `AGENTS.md` is included to help future AI-assisted development stay fast and focused
- There are currently no automated tests, so manual verification is important after behavior changes
