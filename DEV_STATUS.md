# Development status

Updated: 2026-09-24

## Current phase

**Release Candidate 0.1.0** — phases 1–12, Rita UI art pass, extensible Skin Pack system, interaction/layout stabilization, hatch-pet animation upgrade, and configurable Action Policy are complete.

## Final acceptance

- Automated tests: **148 passed** with Qt offscreen; the release build repeats the full suite before packaging.
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
- Added state fade, panel fade, click-to-toggle, recovered stretch, and per-pose optical alignment. The later natural-animation pass replaced the original painted eyelid and single-pose interaction placeholders.
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
- Hover triggers its dedicated 6-frame/600 ms glance-and-smile sequence once per pointer entry with a 1.5-second cooldown. Click has higher priority, interrupts Hover or an interruptible autonomous action, plays its dedicated 8-frame/800 ms response, then returns to the quota-driven pose.
- NORMAL schedules weighted Blink/Wave/Stretch actions at a fresh random 30–120-second interval. LOW, CRITICAL, EMPTY, and RECOVERED keep priority and cannot be overridden by random idle actions.
- Split the character and quota bubble into independent top-level transparent tool windows. The character keeps a persisted bottom-center screen anchor; bubble show/hide, direction changes, pose changes, and skin changes do not participate in character layout.
- Alpha scanning uses threshold 15 and a 4 px safe margin. The current implementation promotes cropping to a Skin-wide all-action Union Bounds so animation geometry remains fixed; Umbral Rose is 226×225 and Moonlit Rose is 223×225 in the current asset set.
- Native and automated capture retain the same character anchor before and after hiding the bubble with exact delta `(0, 0)`. A ten-cycle show/hide regression test also remains drift-free.
- Native visual QA artifacts: `artifacts/ui/pet-idle.png`, `pet-hover.png`, `pet-click.png`, `bubble-open.png`, and `bubble-closed.png`. One visual correction moved the blink eyelid from the fringe to the visible eye.
- Final rebuilt EXE and freshly extracted portable smoke tests both exited 0, read the real App Server (`5h used=29%`, `weekly used=56%` at 2026-09-23 16:29 +08:00), loaded both bundled skins, and left zero new App Server processes. All project, third-party, Qt/GPL/LGPL license files were present in the extracted release.

## Bugs fixed during final acceptance

- Delayed Codex executable resolution until the refresh worker starts, so a missing CLI shows the normal unavailable state instead of crashing application construction.
- Expanded log redaction to cover `Authorization`, `Cookie`, and session credentials.
- Corrected 5h/weekly classification if an App Server returns the windows in reversed field order.
- Extended frozen smoke duration so it validates a real App Server handshake and first quota read, rather than only Qt startup/shutdown.
- Retained ownership of the tray context menu and detached it during shutdown, removing a nondeterministic Windows fast-exit crash exposed by the fresh portable smoke test.
- Fixed the former painted-eyelid blink's Windows Qt `QPen` overload mismatch. The painted overlay has since been retired in favor of a six-frame sprite sequence; direct sequence rendering remains covered.

## Natural animation acceptance

- Added newly rendered transparent sprite sequences for Blink (6 frames/14 FPS), Hover (6/10), Click (8/10), Wave (8/10), Stretch (8/10), and Sleep React (8/9). Idle remains static; existing true sit, fatigued critical, and curled sleep poses remain in use.
- Click no longer reuses Stretch. EMPTY clicks now play Sleep React and return to sleep. Random NORMAL actions use weighted Blink/Wave/Stretch choices; quota states still block random actions.
- Animation timing, loop behavior, cooldown, and interruptibility are declared in each skin manifest instead of being hardcoded per action in the widget.
- Runtime frame crops are cached on first use, bounded shared alpha metadata is reused, and all per-skin caches are cleared on skin change. No frame reads from disk occur during playback.
- Every sequence uses a normalized transparent 512x512 logical cell. Automated alpha audits measured a 0-pixel bottom-edge delta across every frame of all six sequences.
- The current renderer uses one all-action alpha Union Bounds for the entire Skin lifecycle. Native contact-sheet rendering and tests confirmed constant geometry and a fixed bottom-center screen anchor for every frame; the usage bubble also remains fixed during Click.
- Visual QA contact sheets are in `artifacts/animations/`: Blink, Hover, Click, Wave, Stretch, Sleep React, plus the idle/sit/critical/sleep state poses. Generated candidates with only whole-image motion were not used.
- Final rebuilt EXE and freshly extracted portable ZIP both exited 0, read the real App Server (`5h used=58%`, `weekly used=60%` at 2026-09-23 17:21 +08:00), included both skins' animation assets and all license files, and left zero new App Server processes.

## Hatch-pet animation upgrade

- Used the installed `hatch-pet` workflow for identity locking, action planning, deterministic grid normalization, contact sheets, timed motion previews, alpha hygiene, and anchor QA. `imagegen` produced new original 12-frame Tidy Hair and 10-frame Sit Transition sheets for both Rita palettes.
- Retired the awkward raised-arms Stretch artwork. The existing `stretch` state now maps to the restrained Tidy Hair action so RECOVERED behavior remains compatible without changing the Skin Pack core.
- Added per-frame `frame_durations_ms`; explicit frame timing takes priority over FPS and supports preparation, hold, and recovery beats. Blink is 600 ms, Hover 1100 ms, Click 1500 ms, Wave 2400 ms, Tidy Hair 2920 ms, Sleep React 2400 ms, and Sit Transition 1600 ms.
- LOW now plays Sit Transition once and settles on its exact final seated frame. Random NORMAL actions wait 45–150 seconds, then enforce 15–30 seconds of idle after a completed action. CRITICAL and EMPTY remain protected from random actions.
- QA validation covers frame count, duration count, non-empty frames, transparent RGB residue, safe edges, and bottom-anchor drift. Both skins pass with 0 px bottom drift and zero transparent-pixel RGB residue. Reports and previews live under `artifacts/animations/`.
- Visual QA rejected the first equal-row extraction of Sit Transition because it produced cross-cell fragments; adaptive alpha-seam extraction fixed the grid before acceptance.
- Final character captures are in `artifacts/screenshots/`: idle, hover, click, sit, critical, sleep, and bubble-open. The character anchor remained unchanged (`delta=(0, 0)`) while the bubble was toggled.
- Final frozen EXE and a portable ZIP freshly extracted outside the source tree both passed `--smoke-test` with exit code 0. The portable copy included the project license, third-party notices, and Qt/GPL/LGPL license files.

## Release artifacts

- `dist/CodexUsagePet/CodexUsagePet.exe`
- `dist/CodexUsagePet-portable.zip`
- `packaging/CodexUsagePet.iss` and `build-installer.ps1`

Inno Setup 6 is not installed on this machine, so no installer executable was built.

## Desktop shortcut acceptance

- Added “创建桌面快捷方式” and “删除桌面快捷方式” to the pet and tray context menus. Creating again updates the same `Codex Usage Pet.lnk`, which supports a Portable folder moving to a new path.
- The Desktop location comes from Qt `QStandardPaths.DesktopLocation`; the frozen target comes from `sys.executable`. Development mode disables both actions and never points a link at `python.exe`.
- The link is written with native Unicode `IShellLinkW`/`IPersistFile` COM APIs. Its target, working directory, and icon all point to the running EXE; no administrator rights or extra runtime dependency is required.
- Automated suite: **116 passed**. The release EXE and portable ZIP were rebuilt, and the ZIP contains the updated executable and documentation.
- A real link was created at the current user's Desktop and inspected successfully: filename, target, working directory, and icon were correct, including the Chinese target path. A freshly extracted Portable EXE then replaced the target in-place, and a second update restored the release path while the Desktop still contained exactly one link.
- Explorer/PowerShell launch verification was blocked by the host's enterprise Code Integrity policy because the locally rebuilt EXE is unsigned (events 3033/3077, policy ID `{0283ac0f-fff1-49ae-ada1-8a933130cad6}`). The policy was not bypassed or modified.

## Configurable Action Policy acceptance

- Inserted a policy/selector layer between events and the existing animation player. Hover, Click, Random Idle, RECOVERED, and NORMAL/LOW/CRITICAL/EMPTY state phases now choose from Skin-defined weighted candidates rather than forcing one animation in UI code.
- LOW, CRITICAL, and EMPTY each support distinct `on_enter`, persistent `idle`, and `on_exit` pools. Existing priority remains system state > Click > Hover > Random Idle > idle; priority selects the event class, never the concrete animation.
- Candidates support `none`, per-action cooldown ranges, `allowed_states`, missing-asset filtering, and three-item session history with immediate-repeat avoidance. Empty or unsupported pools safely use the base pose.
- Added per-Skin enable/disable overrides and one-click restoration of Skin defaults. The current Chinese card/Chip interface is documented in the later animation anchoring section. Overrides persist independently by Skin ID without modifying the manifest.
- Extended Skin Pack state IDs to support future custom animations without adding them to the `PetActivity` enum. Both bundled Rita skins now declare different action weights, timing, and response frequency.
- Native Qt policy QA ran 60 selections each for Hover, Click, and Random Idle. Umbral Rose produced Hover/none/Blink = 24/13/23, Click/Wave/Tidy Hair/none = 22/13/17/8, and Wave/Tidy Hair/Blink/none = 10/20/19/11; the screen anchor stayed fixed at every selection. Evidence: `artifacts/action-policy-validation.json`.
- At completion of the Action Policy phase, **130 tests passed**, including selection diversity, unsupported/state filtering, cooldown, repeat avoidance, single/empty pools, `none`, user override/reset, per-Skin personality, custom action IDs, concise `action_pools` compatibility, state phase ordering, priority protection, and anchor preservation.
- Rebuilt frozen EXE and portable ZIP both passed `--smoke-test` with exit code 0. A freshly extracted portable copy ran outside the source directory, left no App Server child process, and contained both Skin policies plus project/Qt license files.

## App Server Explorer-launch repair

- Reproduced the old frozen failure with an Explorer-equivalent restricted PATH: UI started and the log collapsed discovery failure to `Usage read failed: AppServerError`. In the same environment, `shutil.which("codex")`, `codex.exe`, and `codex.cmd` all returned `None` although Codex Desktop had installed a valid executable under the current user's `%LOCALAPPDATA%` tree.
- Added structured `AppServerError` metadata and chaining for `discover_codex`, `spawn_app_server`, `initialize_request`, `initialized_notification`, `account_read`, `rate_limits_read`, and `response_parse`. Diagnostics retain original type/message, `__cause__`, exit code, redacted stderr, and JSON-RPC code/message.
- Discovery now checks PATH plus Codex Desktop and common per-user npm launcher locations without hardcoding a username. Windows `.cmd` launchers use a hidden command shell and passed an integration test from a path containing spaces.
- Source mode with PATH deliberately limited to Windows system directories discovered the Codex Desktop executable, completed every protocol stage, and read real data: 5h used 44%, weekly used 79% at 2026-09-24 09:43 +08:00.
- At completion of the App Server repair phase, **136 tests passed**. Credential redaction now also covers `Authorization: Bearer ...` as one complete header value.
- Rebuilt frozen mode with the same restricted PATH exited 0 and read 5h used 60% / weekly used 81%. Opening the EXE through the Windows Explorer Shell verb read 61% / 81%.
- The existing Desktop shortcut was verified to target the rebuilt EXE with the correct working directory. Launched with no Codex directory in PATH, it discovered the per-user executable and read 5h used 62% / weekly used 82%.
- The post-acceptance application log contained zero unredacted Bearer, Authorization, Cookie, access/refresh/session token, or session credential matches.

## Animation anchoring and Chinese interaction UI

- Root cause confirmed in both layers: action-level alpha unions changed `PetWidget` size and forced `PetWindow` repositioning, while the built-in frame sheets also used inconsistent transparent padding/contact centers. The old idle manifest added a further `offset_x=-37`.
- All frames now map into one 232×244 logical canvas using a normalized bottom-center contact anchor. A single all-action Union Bounding Box plus 4 px safe padding is calculated only when a Skin loads or reloads; animation playback never resizes or moves the character window.
- Built-in idle now uses the animation-aligned standing frame, removing the former scale pop at the start and end of Hover, Click, Wave, Tidy Hair, and Sit Transition.
- Hatch-pet-style QA reports 0.0 px maximum foot-anchor drift for every action in both bundled skins. Umbral Rose PetWindow geometry remained `[497, 377, 226, 225]` from first to last sampled frame; Moonlit Rose remained `[500, 377, 223, 225]`.
- Debug overlays for idle→Hover→idle, idle→Click→idle, idle→Wave→idle, and idle→Sit are under `artifacts/animations/debug/`; `anchor-drift-report.json` contains foot, face, head-top, Union Bounds, and geometry evidence.
- Replaced the engineering checkbox/tabs dialog with a Rita-themed Chinese page using collapsible event cards, action Chips, immediate preview, per-card “皮肤默认/自定义” source labels, and a localized restore confirmation.
- Added persistent quiet mode. It suppresses Hover and Random Idle at runtime only; Click and LOW/CRITICAL/EMPTY system behavior remain enabled, and the user's English action IDs are not rewritten.
- Centralized visible labels in `ui/localization.py`; internal action/event IDs, manifest keys, settings JSON, and RPC methods remain English. Missing localization keys fall back safely.
- Windows screenshot QA found and fixed initial scroll displacement and a light viewport leak. Final screenshot: `artifacts/ui/interaction-settings-cn.png`.
- Current automated suite: **148 passed**.
- Rebuilt frozen EXE smoke test exited 0 and read real App Server data (`5h used=45%`, `weekly used=90%`). A freshly extracted portable copy outside the source tree exited 0 and read `46% / 90%`; both left zero new Codex child processes, and all release/license files were present.

## Animation regression repair

- The playback/render chain was isolated before modification. Direct pixel hashes and a live Qt event-loop trace proved that sprite slicing, per-frame cache identity, QTimer ownership, frame index advancement, `update()`, and unified-canvas painting were working in source mode.
- The apparent freeze came from two delivery/trigger regressions: the shipped EXE predated the last source commit, and the default Hover/Click policies could select `none` while autonomous idle waited 60–180 seconds with a 48% trigger probability. A single pointer entry or click could therefore produce no visible response, followed by a long static interval.
- Both bundled Rita defaults now guarantee a visible Hover and Click candidate while retaining weighted ActionSelector behavior, cooldowns, user overrides, `none` for Random Idle/state policy, English internal IDs, and the Chinese display layer.
- Added a direct diagnostic `play_action(action_id)` path that bypasses randomness but uses the same player, frame cache, timer, canvas, and painter. Quiet mode still blocks only Hover/Random Idle and does not block this diagnostic path.
- Multi-frame timing now safely falls back to FPS or 100 ms if an optional Skin supplies an invalid/non-positive per-frame duration; one-frame static poses still create no timer.
- `artifacts/regression/animation-diagnostics.txt` records real timer traces. Rendered evidence: `blink-fixed.gif` (6/6 unique), `click-fixed.gif` (8/8), `wave-fixed.gif` (8/8), and `sit-fixed.gif` (10/10). Canvas size and anchor are constant; PetWindow position, size, and bottom-center anchor drift are all 0 px.
- Automated suite: **161 passed** with Qt offscreen, including normalized rendered-pixel checks, cache identity, real QTimer advancement, localization ID preservation, quiet-mode diagnostic playback, the hidden English-ID animation test entry, deterministic default interaction, real click-event routing, geometry stability, idle restoration, and post-Skin-switch playback.
- The rebuilt frozen EXE played the forced Wave path on the real Windows desktop, produced `artifacts/regression/frozen-wave-runtime.png`, read real App Server usage (`5h used=72%`, `weekly used=95%`), and exited 0. The freshly extracted portable build played Click, read `73% / 95%`, exited 0, included all release/license files, and left zero new Codex child processes. The application log had zero sensitive credential-pattern matches.

## Known limitations

- The build is unsigned and can trigger Windows SmartScreen.
- This development host currently enforces an enterprise signing policy for newly rebuilt executables; the unsigned RC cannot be launched from the Codex worker until signed or explicitly allowed by the administrator.
- The release was built with Python 3.13.13; Python 3.11/3.12 remains the recommended development target.
- App Server fields vary by account and Codex version; absent optional fields are hidden instead of guessed.
- Physical acceptance used the single connected 1920x1080, 96-DPI display. Multi-display placement is covered by screen-aware code and boundary tests, but no second physical monitor was available.
- The Windows computer-use helper returned no app inventory, so automated pixel-level menu clicking was unavailable. Native Qt interaction tests, visible frozen runs, rendered snapshots, persistence checks, and tray creation supplied the UI evidence instead.
- No automatic updater or code signing is included.
