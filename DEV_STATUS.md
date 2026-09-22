# Development status

Updated: 2026-09-22

## Current phase

Phases 1–3 complete; Phase 4 tests are being added.

## Completed

- Reviewed the four requested repositories and their MIT licenses.
- Verified the official Codex App Server handshake and rate-limit schema.
- Selected Python + PySide6 and a modular `src/` layout.
- Added a persistent official App Server JSON-RPC client with initialization,
  notification handling, bounded retry, and child-process cleanup.
- Added typed 5-hour/weekly/credits models and pet quota states.

## Test status

- Tests not yet installed or run.

## Next

- Add and run parser/App Server lifecycle tests.
- Build the desktop pet MVP.

## Known issues

- No runnable UI yet.
- The current machine has Python 3.13, while 3.11/3.12 remains the recommended
  development and packaging target.
