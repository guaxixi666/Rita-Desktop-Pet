# Development status

Updated: 2026-09-23

## Current phase

Phases 1–12 complete for the MVP.

## Completed

- Researched all four requested repositories and verified their MIT licenses.
- Verified the current official Codex App Server documentation and generated schema from local Codex CLI 0.155.0-alpha.9.2.
- Implemented the persistent App Server client, official handshake, full reads, update-event handling, bounded reconnect, and child cleanup.
- Implemented typed 5h/weekly/credits parsing with local reset times.
- Live-verified this machine's ChatGPT account without exposing account identity.
- Implemented the transparent frameless desktop pet and compact usage bubble.
- Implemented quota-linked states, low-frequency animation, tray/context menu, user-level startup, settings, rotating redacted logs, and error recovery.
- Added PyInstaller onedir spec and build script.
- Built and smoke-tested `dist/CodexUsagePet/CodexUsagePet.exe`.
- Added open-source research and attribution documents.
- Added deterministic idle/walk/sit/stretch/critical/sleep behavior scheduling,
  an original application icon, runtime licensing notes, and a portable ZIP.

## Test status

- `pytest`: 28 passed on Python 3.13.13 / Windows.
- Offscreen Qt application smoke test: passed.
- Live App Server read: passed (account/rate-limit values returned).
- Frozen application smoke test: passed with exit code 0; the child process
  stopped without a shutdown-time reconnect.
- Visual offscreen snapshot: rendered and inspected; pet and usage layout are intact. The offscreen Qt plugin did not render system fonts faithfully, so a normal visible Windows run remains the authoritative font check.

## Next (optional enhancements)

- Add external sprite sheets, an installer, and code signing if desired.

## Known issues

- The build is unsigned and may trigger SmartScreen.
- The machine has Python 3.13; Python 3.11/3.12 remains the recommended release build target even though tests pass on 3.13.
- App Server fields may vary by Codex version/account; absent values are shown as unavailable rather than guessed.
- No installer or automatic updater is included in the MVP.
- Live Windows visual automation could not run on 2026-09-23 because the
  computer-use helper returned no app inventory; offscreen pose rendering and
  frozen smoke tests still passed.
