# Missing Trace ID Tool v2

Desktop tool for scanning CSV files, detecting missing `TMGID` trace IDs, and exporting the gaps to a new CSV report.

## Features

- Import CSV files with trace records
- Auto-detect the most likely Trace ID column
- Optionally set an expected total record count
- Calculate missing `TMGID` values from the detected range
- Export missing IDs to a CSV file
- Simple PySide6 desktop interface

## Tech Stack

- Python
- PySide6
- pandas

## Project Structure

```text
main.py
main_window.py
trace_logic.py
requirements.txt
README.md
.gitignore
```

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

## Build Executable

If you want to package the app later with PyInstaller:

```bash
pyinstaller zoho_trace_id_gap_finder.spec
```

## Notes

- The app expects trace IDs in a format like `TMGID000123`
- If a CSV is open in Excel, exporting may fail until the file is closed
- The `data/`, `build/`, `dist/`, and local virtual environment folders should stay out of git
