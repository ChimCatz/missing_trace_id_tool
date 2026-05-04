# AGENTS.md

## Purpose

This file gives AI coding agents a compact map of the project so they can
work with less unnecessary file reading and lower token usage.

Primary goal of this repo:
- Load a CSV of trace records
- Detect the trace ID column
- Find missing `TMGID######` values
- Export the missing IDs to a new CSV

Near-term product direction:
- Keep the existing trace workflow stable
- Prepare the codebase for a second identifier pipeline for Company IDs
- Prefer separating shared CSV workflow from identifier-specific rules

## Fast Start

If you are an AI agent, read files in this order unless the task clearly
requires something else:

1. `README.md`
2. `main.py`
3. `main_window.py`
4. `trace_logic.py`
5. `requirements.txt`
6. `zoho_trace_id_gap_finder.spec` only if the task involves packaging

Usually skip these unless explicitly needed:
- `venv/`
- `build/`
- `dist/`
- `__pycache__/`
- files under `data/`
- generated CSV exports

## Project Layout

- `main.py`: application entry point, creates `QApplication`, opens
  `MainWindow`
- `main_window.py`: main PySide6 UI and most current app behavior
- `trace_logic.py`: trace ID parsing and missing-ID calculation helpers
- `requirements.txt`: runtime dependencies
- `zoho_trace_id_gap_finder.spec`: PyInstaller packaging config
- `data/`: optional local input/output samples, not intended for git

## Runtime Flow

1. App starts in `main.py`
2. `MainWindow` builds the interface and wires UI events
3. User imports a CSV
4. App loads the CSV with `pandas.read_csv`
5. App tries to auto-detect the trace column
6. `trace_logic.extract_numbers()` parses numeric portions from values
7. `trace_logic.find_missing()` generates the missing `TMGID######` range
8. User exports missing IDs as a CSV

## Current Behavior Notes

- Trace IDs are expected to look like `TMGID000123`
- Column auto-detection first checks column names containing `trace`
- Fallback detection checks sample cell values for `TMGID\d+`
- Missing IDs are calculated from `1` through the larger of:
  - the highest detected trace ID
  - the optional expected record count entered by the user
- Export currently writes one column named `Missing Trace IDs`

## Architecture Direction

The project is still trace-specific today. When preparing for Company ID
support:

- keep shared CSV import/export orchestration in `main_window.py`
- keep identifier parsing and gap rules outside the UI layer
- avoid hard-coding new Company ID behavior directly into unrelated trace code
- prefer small pipeline-specific helpers over one large mixed logic module
- do not rename the current trace workflow unless the task explicitly requires
  it

## Known Constraints

- The app is a desktop GUI, so many features are easiest to verify manually
- `export_missing()` currently handles `PermissionError`, but broad export
  failures are not surfaced beyond that
- `calculate_stats()` counts scanned records using total DataFrame rows, not
  just valid trace-ID rows
- `extract_numbers()` captures the first numeric group in a value, which is
  fine for current `TMGID######` input but could misread other mixed-format
  strings
- There are no automated tests yet

## Editing Guidelines

- Keep business rules in `trace_logic.py` when possible
- Keep UI orchestration in `main_window.py`
- Avoid moving data-processing rules deeper into the UI layer
- Preserve the current user flow unless the task explicitly changes UX
- Favor small, readable methods over large multi-purpose handlers
- Reuse the existing `TMGID` formatting convention:
  `f"TMGID{number:06d}"`
- If adding Company ID support later, isolate the new format rules instead of
  weakening the current trace behavior
- Keep repository hygiene in place: ignore virtual environments, build output,
  caches, and local sample data

## Safe Change Patterns

For logic changes:
- update `trace_logic.py` first
- then wire any UI messaging or validation in `main_window.py`

For UI-only changes:
- prefer `_build_ui()`, `_apply_styles()`, and small helper methods

For packaging tasks:
- check `zoho_trace_id_gap_finder.spec`
- verify ignored output folders in `.gitignore`

## Verification

Recommended lightweight checks after changes:

- Run: `python main.py`
- Import a CSV with a valid `TMGID` column
- Verify auto-detection picks the expected column
- Verify missing IDs update when expected count changes
- Verify export works to a writable CSV path

If changing trace logic, also test:
- rows with blanks
- rows without matching trace IDs
- nonstandard column names
- expected count smaller than largest detected ID

If preparing shared logic for multiple ID types, also test:
- the current trace workflow still behaves exactly the same
- identifier-specific labels do not leak into the wrong workflow
- export column names still match the active pipeline

## Token-Saving Guidance For AI Agents

- Do not read `venv`, `build`, `dist`, `__pycache__`, or `data` by default
- Do not inspect the `.git` directory
- Only open `zoho_trace_id_gap_finder.spec` for build-related work
- Prefer targeted reads over full-file rereads once you know the relevant
  method names

## Good First Improvements

Useful future tasks:
- add drag-and-drop CSV import
- improve invalid-column and invalid-file feedback
- support configurable trace prefixes beyond `TMGID`
- extract a reusable ID-pipeline abstraction for Trace ID and Company ID flows
- add automated tests for `trace_logic.py`
- add sample anonymized test data
- split UI styling and logic if the window keeps growing
