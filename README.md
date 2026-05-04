# Missing Trace ID Tool

This project is a small desktop CSV workflow built for one job today:
find missing `TMGID######` trace IDs and export them to a new CSV.

It is also being cleaned up as the base for a second pipeline with the same
import -> detect column -> calculate gaps -> export flow, but with a
different identifier format for Company IDs.

## Current Scope

- Import a CSV file with record data
- Auto-detect the most likely Trace ID column
- Accept an optional expected total record count
- Find missing `TMGID######` values in the expected range
- Export the missing IDs to a CSV report
- Provide a simple PySide6 interface for non-technical users

## Planned Direction

The current code is still trace-specific. The next iteration should keep the
shared CSV workflow while separating identifier-specific rules such as:

- column detection hints
- ID parsing and formatting
- output column names
- validation messages

That future split should make it easier to support both Trace ID and Company
ID workflows without duplicating the whole UI.

## Tech Stack

- Python
- PySide6
- pandas
- PyInstaller

## Project Structure

```text
main.py                         # Application entry point
main_window.py                  # Main window and UI workflow
trace_logic.py                  # Trace-specific parsing and gap logic
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
2. The app tries to auto-detect the Trace ID column.
3. It extracts the numeric part of each matching ID.
4. It finds missing values from `1` to the highest detected ID.
5. If an expected total is entered, the search range expands to that value.
6. The app exports the missing IDs to a new CSV file.

## Packaging

```bash
pyinstaller zoho_trace_id_gap_finder.spec
```

Build outputs are created in `build/` and `dist/`, which are ignored by git.

## Notes

- The current parser expects values like `TMGID000123`
- If an export file is open in Excel, saving may fail until the file is closed
- `data/` is for local inputs and outputs and is intentionally ignored
- There are no automated tests yet, so manual verification is still important
