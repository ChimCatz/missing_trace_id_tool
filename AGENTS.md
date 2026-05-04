# AGENTS.md

## Purpose

This file gives AI coding agents a compact map of the project so they can
work with less unnecessary file reading and lower token usage.

Primary goal of this repo:
- Load a CSV of records
- Detect Trace ID and Company ID columns
- Find missing `TMGID######` and `ACC######` values
- Export the missing IDs to a new CSV

Near-term product direction:
- Keep shared CSV workflow stable
- Support Trace ID and Company ID pipelines in the same interface
- Prefer separating shared workflow from identifier-specific rules

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
- `trace_logic.py`: identifier parsing and missing-ID calculation helpers
- `requirements.txt`: runtime dependencies
- `zoho_trace_id_gap_finder.spec`: PyInstaller packaging config
- `data/`: optional local input/output samples, not intended for git

## Runtime Flow

1. App starts in `main.py`
2. `MainWindow` builds the interface and wires UI events
3. User imports a CSV
4. App loads the CSV with `pandas.read_csv`
5. App tries to auto-detect Trace ID and Company ID columns
6. `trace_logic.extract_numbers()` parses numeric portions from values
7. `trace_logic.find_missing_ids()` generates the missing ID ranges
8. User exports missing IDs as a CSV

## Current Behavior Notes

- Trace IDs are expected to look like `TMGID000123`
- Company IDs are expected to look like `ACC000123`
- Column auto-detection first checks headers, then falls back to sample values
- Trace missing IDs are calculated from `1` through the larger of:
  - the highest detected Trace ID
  - the optional expected Trace count entered by the user
- Company missing IDs are calculated from `0` through the larger of:
  - the highest detected Company ID
  - the optional expected Company count entered by the user
- Export writes one column per active pipeline

## Architecture Direction

The project now supports Trace ID and Company ID workflows together. When
extending it further:

- keep shared CSV import/export orchestration in `main_window.py`
- keep identifier parsing and gap rules outside the UI layer
- prefer small pipeline-specific helpers over one large mixed logic module
- preserve current Trace ID and Company ID behavior unless the task explicitly
  changes it

## Known Constraints

- The app is a desktop GUI, so many features are easiest to verify manually
- `export_missing()` currently handles `PermissionError`, but broad export
  failures are not surfaced beyond that
- `calculate_stats()` counts scanned records using total DataFrame rows, not
  just valid ID rows
- There are no automated tests yet

## Editing Guidelines

- Keep business rules in `trace_logic.py` when possible
- Keep UI orchestration in `main_window.py`
- Avoid moving data-processing rules deeper into the UI layer
- Preserve the current user flow unless the task explicitly changes UX
- Favor small, readable methods over large multi-purpose handlers
- Reuse the current formatting conventions:
  `f"TMGID{number:06d}"` and `f"ACC{number:06d}"`
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
- Import a CSV with valid `TMGID` and/or `ACC` columns
- Verify auto-detection picks the expected columns
- Verify missing IDs update when expected counts change
- Verify export works to a writable CSV path

If changing ID logic, also test:
- rows with blanks
- rows without matching trace IDs
- rows without matching company IDs
- nonstandard column names
- expected count smaller than largest detected ID
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
- support configurable prefixes beyond `TMGID` and `ACC`
- add automated tests for `trace_logic.py`
- add sample anonymized test data
- split UI styling and logic if the window keeps growing
