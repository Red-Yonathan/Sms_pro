# SmsBlast Pro - complete set

**Replace ALL files in your project folder with these** (older copies of `project_ui.py`,
`projects.py`, `theme.py`, `ui_common.py`, `progress_panel.py` will not work with the new `main.py`).

    pip install -r requirements.txt
    python main.py

Files: main.py, theme.py, ui_common.py, mica.py, wallpaper.py, phone_utils.py, excel_dialog.py,
file_loader.py (new), progress_panel.py, projects.py, project_ui.py, sender.py, error_logger.py

## What's new in this drop
- **Crash fix** (`AttributeError: '_SixMetaPathImporter'...`): main.py now imports pandas before PySide6
  and keeps the `six` workaround.
- **Projects mirror Batch**: checkbox + red X on every tracked file, select all / uncheck all, small send
  button, overall + per-file progress, activity log. Sends only the CHECKED files' not-yet-sent numbers.
  Files that are fully sent start unchecked. Rows show `N numbers - S sent (P%) - F failed - U unsent`.
- **Delete project**: red X on each project card (confirm dialog; source files are never deleted).
- **Resume**: reopening a project auto-loads its files and progress; closing mid-send keeps progress
  (numbers not yet tried stay unsent; failed ones are retried on the next send).
- **Storage rewritten for big projects**: header file + one data file per tracked file, progress saved
  every ~4s instead of per number. Old-format projects (like red_01) migrate automatically on first load.
- Resize grips, distinct total-bar gradient, blur fix (see mica.py toggles ENABLE_NATIVE_BLUR / BACKDROP_MODE).

## Round 4 changes
- **Project panel**: header shows the project's folder + reports path with **Open project folder** and
  **Open reports folder** buttons. A finished file (nothing unsent/failed) is unchecked and its row turns
  green with a DONE label - live while sending and when the project is reopened.
- **Interrupt**: every file's progress card has **Interrupt**, and the overall bar has **Interrupt all**
  (Manual, Batch and Projects). Interrupted files show an amber bar; numbers not yet attempted stay unsent
  and are picked up next time. (Requests already in flight at the moment you click - at most your
  concurrency setting - may have been delivered but not recorded.)
- **Wallpaper fix**: the darkening layer was painted with a CSS-style colour string Qt cannot parse, which
  made it solid black. Now a real QColor; tune `WALLPAPER_DIM_ALPHA` in main.py (lower = brighter wallpaper).
- **Folders**: everything lives under the app folder as
      Projects/<project>/  (.sms_project.json, data/, Reports/<date>/)
      Reports/<date>/      (manual + batch reports; replaces the scattered Report_(date) folders)
      Logs/errors.log, Wallpaper/
