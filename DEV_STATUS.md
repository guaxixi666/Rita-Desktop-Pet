# Development status

Updated: 2026-09-23

## Current phase

**Release Candidate 0.1.0** — phases 1–12, Rita UI art pass, extensible Skin Pack system, and the interaction/layout stabilization pass are complete.

## Final acceptance

- Automated tests: **85 passed** with both Qt offscreen and the native Windows Qt platform.
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

## Rita UI art pass

- Replaced the engineering placeholder pet with an original transparent 3x2 Rita-inspired chibi sprite sheet covering idle, walk, sit, stretch, critical, and sleep.
- Rebuilt the compact usage bubble with the Umbral Rose palette, 6 px rounded progress bars, restrained rose accents, hierarchy-aware typography, and state-specific desaturation.
- Centralized all palette and typography values in `src/codex_usage_pet/ui/theme.py`; no default Qt blue remains in the pet, bubble, tray, or menus.
- Added hover response, blink, state fade, panel fade, click-to-toggle, recovered stretch, and per-pose optical alignment while preserving the existing low-frequency animation controller.
- Visual QA artifacts: `artifacts/ui/rita-ui-final.png` and `artifacts/ui/rita-states-final.png`. The final composition was reviewed and adjusted once to reduce the visual gap between the bubble and narrow idle pose.
- Final rebuilt EXE smoke test: exit 0, real App Server read (`5h used=80%`, `weekly used=48%` at 2026-09-23 12:01 +08:00), and zero newly remaining App Server processes.
- Final portable test: freshly extracted outside the source tree, exit 0, the same real quota read, zero newly remaining App Server processes, and all release/license files present.

## Skin Pack acceptance

- Added manifest-driven Skin Packs with independent state assets, theme colors, decorator, preferred dimensions, anchors, and per-pose offsets. New folders are discovered without modifying application code.
- Migrated the default Rita appearance to `skins/rita_umbral_rose/` and added the independent `rita_moonlit_rose` cool-theme demonstration pack. Both packages contain all six state mappings; the second intentionally reuses the same original project art under its own directory.
- Added manual selection, no-repeat random selection, rescanning, user skin directory access, 6/12/24/48-hour intervals, daily fixed local times, and custom `HH:MM` input.
- Persisted `current_skin`, auto mode, interval, fixed time, last successful/change-cycle UTC timestamp, and no-repeat preference. Restart, 24-hour due, 72-hour overdue, no catch-up loop, clock rollback, and fixed-time behavior are covered by deterministic tests.
- Missing walk/sit/stretch/sleep states fall back to idle; critical falls back to sit and then idle. Invalid manifests are skipped and logged.
- Native visual switch test changed Umbral Rose to Moonlit Rose while CRITICAL and confirmed `state=critical`, `activity=critical`, unchanged window position, and the new `#8F7EB8` theme. Evidence: `artifacts/ui/skin-rita-umbral.png` and `artifacts/ui/skin-rita-moonlit.png`.
- Frozen and freshly extracted portable smoke tests both exited 0, performed a real App Server read, loaded both bundled manifests, and left zero new App Server processes. The final acceptance read was 5h used 4% / weekly used 52% at 2026-09-23 15:45 +08:00; values are time-sensitive.

## Interaction and layout acceptance

- Removed the permanent idle walk/bob/sway sequence. NORMAL now holds a static idle pose; no timer changes the pet window position.
- Hover triggers one 520 ms blink per pointer entry with a 1.5-second cooldown. Click has higher priority, interrupts a just-started hover or autonomous action, plays one 720 ms response with a 1-second cooldown, then returns to the quota-driven pose.
- NORMAL schedules a probabilistic blink/stretch/sit at a fresh random 30–120-second interval. LOW, CRITICAL, EMPTY, and RECOVERED keep priority and cannot be overridden by random idle actions.
- Split the character and quota bubble into independent top-level transparent tool windows. The character keeps a persisted bottom-center screen anchor; bubble show/hide, direction changes, pose changes, and skin changes do not participate in character layout.
- Runtime alpha bounding-box cropping uses threshold 15 and a 4 px safe margin. The default idle window changed from 232x244 (56,608 px) to 137x204 (27,948 px), a 50.63% area reduction.
- Native capture measured the same character anchor `(1865, 1001)` and geometry `(1767, 789, 137, 204)` before and after hiding the bubble: exact delta `(0, 0)`. A ten-cycle show/hide regression test also remained drift-free.
- Native visual QA artifacts: `artifacts/ui/pet-idle.png`, `pet-hover.png`, `pet-click.png`, `bubble-open.png`, and `bubble-closed.png`. One visual correction moved the blink eyelid from the fringe to the visible eye.
- Final rebuilt EXE and freshly extracted portable smoke tests both exited 0, read the real App Server (`5h used=29%`, `weekly used=56%` at 2026-09-23 16:29 +08:00), loaded both bundled skins, and left zero new App Server processes. All project, third-party, Qt/GPL/LGPL license files were present in the extracted release.

## Bugs fixed during final acceptance

- Delayed Codex executable resolution until the refresh worker starts, so a missing CLI shows the normal unavailable state instead of crashing application construction.
- Expanded log redaction to cover `Authorization`, `Cookie`, and session credentials.
- Corrected 5h/weekly classification if an App Server returns the windows in reversed field order.
- Extended frozen smoke duration so it validates a real App Server handshake and first quota read, rather than only Qt startup/shutdown.
- Retained ownership of the tray context menu and detached it during shutdown, removing a nondeterministic Windows fast-exit crash exposed by the fresh portable smoke test.
- Fixed the idle blink frame's Windows Qt `QPen` overload mismatch. The fault appeared only when frame 7 rendered after several seconds and caused `0xC0000409` during smoke tests; a direct blink-frame render regression test now covers it.

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
