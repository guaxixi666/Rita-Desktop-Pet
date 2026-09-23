# Development status

Updated: 2026-09-23

## Current phase

**Release Candidate 0.1.0** — phases 1–12 and final acceptance are complete.

## Final acceptance

- Automated tests: **42 passed** with both Qt offscreen and the native Windows Qt platform.
- Frozen EXE smoke test: exit code 0; completed a real App Server read; no new App Server process remained after exit.
- Portable test: extracted into a new `%TEMP%` directory outside the source tree, completed a real App Server read, exited 0, and left no child process behind.
- Live Codex App Server read: account type `chatgpt`, plan `plus`, Codex bucket, 5-hour and weekly windows, credits, and reset-credit count were returned.
- Acceptance snapshot: 5h used 34% / remaining 66%, reset 2026-09-23 15:19:28 +08:00; weekly used 41% / remaining 59%, reset 2026-09-28 16:03:35 +08:00. Credits balance was 0 (`hasCredits=false`); one reset credit was reported. Values are time-sensitive.
- Raw/display comparison: raw `usedPercent` and `resetsAt` mapped exactly; UI displayed `100 - usedPercent` and local reset time. No rounding difference existed in this snapshot.
- UI/interaction: transparent frameless tool window, topmost toggle, drag/lock behavior, usage visibility, opacity, refresh interval, tray/menu creation, screen-bound clamping, and DPI metadata passed native Qt tests.
- State machine: idle, walk, sit, stretch, critical, sleep, and RECOVERED-to-NORMAL behavior passed injected-data tests without changing the real account.
- Persistence: position, opacity, usage visibility, refresh interval, topmost, and lock settings survived two frozen-process restarts.
- Error path: a frozen run with Codex removed from `PATH` stayed alive, logged the failure, and exited cleanly; an injected outage recovered successfully after an immediate refresh.
- Startup: the current-user Run-key value was enabled, verified, disabled, and restored without administrator access.
- Logs: five acceptance log files were scanned; no bearer token, Authorization header, Cookie, access/refresh/session token, or session credential pattern was present.
- Distribution: project MIT license, third-party notices, LGPLv3 text, GPLv3 text, and runtime license README are present in both the onedir release and portable ZIP.

## Bugs fixed during final acceptance

- Delayed Codex executable resolution until the refresh worker starts, so a missing CLI shows the normal unavailable state instead of crashing application construction.
- Expanded log redaction to cover `Authorization`, `Cookie`, and session credentials.
- Corrected 5h/weekly classification if an App Server returns the windows in reversed field order.
- Extended frozen smoke duration so it validates a real App Server handshake and first quota read, rather than only Qt startup/shutdown.

## Release artifacts

- `dist/CodexUsagePet/CodexUsagePet.exe`
- `dist/CodexUsagePet-portable.zip`
- `packaging/CodexUsagePet.iss` and `build-installer.ps1`

Inno Setup 6 is not installed on this machine, so no installer executable was built.

## Known limitations

- The build is unsigned and can trigger Windows SmartScreen.
- The release was built with Python 3.13.13; Python 3.11/3.12 remains the recommended development target.
- App Server fields vary by account and Codex version; absent optional fields are hidden instead of guessed.
- Physical acceptance used the single connected 1920x1080, 96-DPI display. Multi-display placement is covered by screen-aware code and boundary tests, but no second physical monitor was available.
- The Windows computer-use helper returned no app inventory, so automated pixel-level menu clicking was unavailable. Native Qt interaction tests, visible frozen runs, rendered snapshots, persistence checks, and tray creation supplied the UI evidence instead.
- No automatic updater or code signing is included.
