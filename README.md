# Phone Sender Pro 4.0 - setup & what changed

## 1. Install
```
pip install -r requirements.txt
```
That's `PySide6`, `pandas`, `openpyxl` (needed by pandas for .xlsx), `aiohttp`, `python-dotenv`.
Put every `.py` file in the same folder, then `python main.py`.

## 2. New files (why they exist)
| File | Purpose |
|---|---|
| `phone_utils.py` | All phone cleaning/validation + file readers (txt/json/csv/xlsx). Pure Python, no Qt. |
| `ui_common.py` | Shared widgets: `Card`, glow helpers, `AnimatedNavButton`, `UnicodeTextEdit`. |
| `theme.py` | Colors + stylesheet. Added `message_text`/`message_glow` (neon input color) and `window_tint` (the 90%-opaque overlay). |
| `mica.py` | **The real fix for the blur you were chasing.** Applies native Windows 11 Mica (falls back to Windows 10 Acrylic blur-behind) to the actual window chrome via `DwmSetWindowAttribute`/`SetWindowCompositionAttribute`. Toggle: `mica.ENABLE_NATIVE_BLUR = True/False` at the top of the file. |
| `wallpaper.py` | Copies a chosen image into `Wallpaper/`, remembers it in `current_wallpaper.txt`. Reset button in Settings clears it. |
| `projects.py` | Project folder + manifest (`.sms_project.json`) management — no Qt. |
| `project_ui.py` | Projects tab UI: card list, "+ New Project", and the per-project workspace (add files, see sent/unsent/failed, send only what's unsent). |
| `excel_dialog.py` | The Excel column picker dialog + `resolve_excel_columns()` used by both Batch and Projects. |
| `progress_panel.py` | The overall + per-file live progress bars (with the two distinct "done" glow themes). |
| `error_logger.py` | Writes ONLY errors to `Logs/errors.log` (rotates at 2MB, keeps 3 backups). |
| `sender.py` | Same concurrent sender, with the missing `import re` fixed (this was crashing every send before) and a new `phone_result` signal so Projects can track sent/unsent per phone. |

## 3. Why testing.py's transparency wasn't real blur
`WA_TranslucentBackground` + a semi-transparent stylesheet only fades to whatever
was already composited behind the window when it was drawn — it does **not** blur
the desktop or other windows live, which is why it looked flat. Real blur needs the
OS compositor. That's what `mica.py` does: it calls into DWM directly. It keeps your
normal title bar (Windows 11 Explorer works exactly this way), so I did **not** make
the main window frameless — much simpler and it plays nicer with dragging/resizing/
maximizing than the frameless approach in `testing.py`.

On non-Windows this silently no-ops and you just get the painted `window_tint`
overlay (still glassy, just not compositor-blurred).

## 4. Text "glow"
Qt style sheets have no `text-shadow`, so literal per-glyph glow on typed text isn't
achievable without a custom text renderer. What's shipped instead: message/recipient
boxes get a distinct neon color (`#MessageInput` in theme.py) and a soft ambient glow
around the box itself on focus — visually reads as "the input glows," which is the
closest honest approximation. Flagging this so it's not a surprise.

## 5. Excel column picker — flow
Add files/folder → any `.xlsx`/`.xls` gets previewed (5 rows, scrollable columns,
cells >15 chars cut with `...`) → auto-detected column shown in green with Yes,
or red warning if nothing matched → type/click a column → optional "use for all"
checkbox remembers it for the rest of that batch. Declining/cancelling skips that
one file (logged, not a hard error).

## 6. Projects
`Projects/<name>/` holds a `.sms_project.json` manifest: every tracked file's path,
and every phone number's `sent`/`sent_at`/`error`. "Send to all unsent recipients"
only sends what hasn't succeeded yet — re-running a project after a partial failure
won't double-send. A folder without a valid signed manifest shows up red/disabled
in the Projects list instead of being trusted.

## 7. Settings
Concurrency (manual + batch/project) and wallpaper now live only in Settings; the
manual page no longer shows a concurrency line.

## 8. All of this was tested headless
Every module was syntax-checked and exercised (window construction, page switching,
phone parsing for both JSON shapes, Excel detection/override, project manifest
read/write/mark-sent, progress-bar completion) with `QT_QPA_PLATFORM=offscreen`
before being handed to you — actual on-screen rendering (the blur, the glow, layout
polish) you'll obviously want to eyeball on your own Windows machine.
