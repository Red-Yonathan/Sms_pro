import os
import sys

def _resolve_checkmark_path():
    candidates = []
    if hasattr(sys, "_MEIPASS"):
        candidates.append(os.path.join(sys._MEIPASS, "checkmark.png"))
    script_dir = os.path.dirname(os.path.abspath(__file__))
    candidates.append(os.path.join(script_dir, "checkmark.png"))
    if getattr(sys, "frozen", False):
        exe_dir = os.path.dirname(os.path.abspath(sys.executable))
        candidates.append(os.path.join(exe_dir, "checkmark.png"))
    for p in candidates:
        if os.path.exists(p):
            return p.replace("\\", "/")
    return os.path.join(script_dir, "checkmark.png").replace("\\", "/")

CHECKMARK_PATH = _resolve_checkmark_path()


def ensure_checkmark_icon():
    global CHECKMARK_PATH
    if not os.path.exists(CHECKMARK_PATH):
        try:
            from PySide6.QtCore import Qt, QPointF
            from PySide6.QtGui import QImage, QPainter, QPen, QColor, QPainterPath
            save_dir = os.path.dirname(os.path.abspath(sys.executable)) if getattr(sys, "frozen", False) else os.path.dirname(os.path.abspath(__file__))
            target = os.path.join(save_dir, "checkmark.png")
            img = QImage(32, 32, QImage.Format_ARGB32_Premultiplied)
            img.fill(Qt.transparent)
            painter = QPainter(img)
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(QColor(2, 20, 13), 3.5)
            pen.setCapStyle(Qt.RoundCap)
            pen.setJoinStyle(Qt.RoundJoin)
            painter.setPen(pen)
            path = QPainterPath()
            path.moveTo(QPointF(7, 16))
            path.lineTo(QPointF(13, 23))
            path.lineTo(QPointF(25, 8))
            painter.drawPath(path)
            painter.end()
            img.save(target)
            CHECKMARK_PATH = target.replace("\\", "/")
        except Exception:
            pass


ensure_checkmark_icon()

# ==============================================================================
# SmsBlast Pro - Theme Palette & Visual System
# ==============================================================================
# QUICK COLOR TWEAK GUIDE:
# - Want to change the MESSAGE INPUT color? -> Edit 'message_text' and 'message_glow'.
# - Want to change TARGET FILES green?      -> Edit 'target_green', 'target_bg', 'target_border'.
# - Want to change MAIN CYAN ACCENTS?       -> Edit 'accent', 'accent_hover', 'border'.
# - Want to change FINISHED ROWS green?     -> Edit 'done_green', 'done_border'.
# - Want to change ERROR / DANGER red?      -> Edit 'danger', 'danger_soft'.
# - Want to change WINDOW DARKNESS?         -> Edit 'window_tint', 'window_tint_wallpaper'.
# ==============================================================================

COLORS = {
    # --------------------------------------------------------------------------
    # 1. WINDOW BACKGROUND & GLASS SURFACES
    # --------------------------------------------------------------------------
    "bg": "#02040A",                         # Deep obsidian base window background
    "bg2": "#050D1A",                        # Slightly lighter dark navy tone
    "sidebar": "rgba(4, 8, 18, 0.88)",       # Translucent sidebar panel background
    "surface": "rgba(10, 18, 34, 0.50)",     # Base translucent card surface
    "surface2": "rgba(14, 25, 45, 0.52)",    # Input box and secondary surface background
    "surface3": "rgba(22, 38, 66, 0.65)",    # Hovered surface / elevated input background
    "border": "rgba(0, 240, 255, 0.32)",     # Default cyan glass border (32% opacity)
    "border2": "rgba(0, 240, 255, 0.65)",    # Highlighted / active cyan border (65% opacity)

    # --------------------------------------------------------------------------
    # 2. TYPOGRAPHY & GENERAL TEXT
    # --------------------------------------------------------------------------
    "text": "#F0F9FF",                       # Bright crisp white-cyan primary text
    "muted": "#8BA3B8",                      # Soft slate secondary text / descriptions
    "muted2": "#4A6670",                     # Dim placeholder & hint label text

    # --------------------------------------------------------------------------
    # 3. NEON CYAN ACCENTS (Buttons, Tabs, Brand Glows)
    # --------------------------------------------------------------------------
    "accent": "#00F0FF",                     # Signature electric cyan accent
    "accent_hover": "#80F8FF",               # Lighter cyan glow for button hover states
    "accent_soft": "rgba(0, 240, 255, 0.10)",# Soft cyan wash for selected nav buttons
    "cyan": "#00F0FF",                       # Pure neon cyan
    "blue": "#2563FF",                       # Royal blue accent
    "purple": "#7000FF",                     # Deep neon purple for progress chunk gradient

    # --------------------------------------------------------------------------
    # 4. GREEN PALETTE: TARGET FILES AREA, LOADING & API SUCCESS
    # (Matches the vivid emerald green from the API test success response box)
    # --------------------------------------------------------------------------
    "success": "#00FF9D",                    # Bright emerald green text & active borders
    "success_soft": "rgba(0, 255, 157, 0.15)",# Translucent green tint for banners & cards
    "target_green": "#00FF9D",               # Target files card border & title color
    "target_bg": "rgba(0, 32, 20, 0.45)",    # Target files card translucent dark green background
    "target_list_bg": "rgba(0, 22, 14, 0.40)",# List area dark green background
    "target_border": "rgba(0, 255, 157, 0.55)",# Green perimeter border for target files

    # --------------------------------------------------------------------------
    # 5. MESSAGE BOX: TEXT COLOR, BACKGROUND & FOCUS GLOW AURA
    # --------------------------------------------------------------------------
    "message_text": "#FFFFFF",               # <-- [TEXT COLOR] Change typed message text color here (e.g. #FFFFFF for White)
    "message_glow": "#FFD700",               # <-- [GLOW COLOR] Focus border & aura glow color
    "message_glow_radius": "16px",           # <-- [GLOW AREA/RADIUS] Area/spread of the glow
    "message_bg": "rgba(12, 16, 26, 0.55)",  # <-- [BACKGROUND] Message input box background
    "warning": "#FFD700",                    # Amber / gold warning marker
    "warning_soft": "rgba(255, 215, 0, 0.12)",# Subtle gold wash

    # --------------------------------------------------------------------------
    # 6. COMPLETED / DONE FILES IN TARGET AREA (Vivid Emerald Green)
    # --------------------------------------------------------------------------
    "done_green": "#00FF9D",                 # 100% completed file row emerald green
    "done_border": "#00FF9D",                # 100% completed file row glowing border
    "done_orange": "#00FF9D",                # Alias to emerald green for target files
    "done_file_bg": "rgba(0, 220, 130, 0.40)",
    "done_file_border": "#00FF9D",
    "checkmark_icon": CHECKMARK_PATH,        # Path to checkmark image for checked checkboxes

    # --------------------------------------------------------------------------
    # 7. RED / DANGER PALETTE (Errors, Stop, Delete)
    # --------------------------------------------------------------------------
    "danger": "#FF3366",                     # Crimson red for delete buttons & errors
    "danger_soft": "rgba(255, 51, 102, 0.15)",# Soft crimson wash for danger button hovers
    "warn_marker": "#FF3366",                # Project-marker warning color

    # --------------------------------------------------------------------------
    # 8. WINDOW BLUR & WALLPAPER TINTS
    # --------------------------------------------------------------------------
    "window_tint": "rgba(2, 4, 10, 230)",       # 90% opaque tint over Win11 Mica/Acrylic blur
    "window_tint_wallpaper": "rgba(2, 4, 10, 160)", # Lighter tint when wallpaper image is active
}

STYLESHEET = """
* {{ 
    font-size: 13px; 
}}

/* =========================================================================
   CORE WINDOW & CONTAINER STRUCTURE
   ========================================================================= */
QMainWindow {{ background: transparent; }}
#CentralWidget {{ background: transparent; color: {text}; }}
QWidget {{ color: {text}; }}
#ManualPage, #BatchPage, #ProjectsPage {{ background: transparent; }}
QStackedWidget {{ background: transparent; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
#ProjectScroll, #ProjectScroll > QWidget, #ProjectScroll > QWidget > QWidget, #ProjectBody {{ background: transparent; border: 0; outline: 0; }}
#SettingsScroll, #SettingsScroll > QWidget, #SettingsScroll > QWidget > QWidget, #SettingsBody {{ background: transparent; border: 0; outline: 0; }}
#Sidebar {{ background: {sidebar}; border-right: 1px solid {border}; }}
#BrandTitle {{ font-size: 19px; font-weight: 700; color: {text}; letter-spacing: -0.3px; }}
#BrandSub {{ font-size: 11px; color: {muted}; }}
#Topbar {{ background: rgba(4, 8, 18, 0.55); border-bottom: 1px solid {border}; }}
#PageTitle {{ font-size: 26px; font-weight: 700; color: {text}; letter-spacing: -0.5px; }}
#PageSubtitle {{ color: {muted}; font-size: 13px; }}

/* Base Glass Card */
#Card {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(10, 18, 32, 0.50), stop:1 rgba(6, 12, 22, 0.55));
    border: 1.5px solid rgba(0, 240, 255, 0.38);
    border-top: 1.8px solid rgba(0, 240, 255, 0.72);
    border-radius: 14px;
}}
#SectionTitle {{ font-size: 14px; font-weight: 700; color: {text}; }}
#Muted {{ color: {muted}; }}
#TinyMuted {{ color: {muted2}; font-size: 11px; }}
#StatNumber {{ font-size: 26px; font-weight: 750; color: {text}; }}
#StatLabel {{ color: {muted}; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; }}

/* =========================================================================
   INPUT CONTROLS (Text edits, Combos, Spinners)
   ========================================================================= */
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QTableWidget {{
    background: {surface2}; color: {text};
    border: 1px solid {border}; border-radius: 8px;
    padding: 10px 12px; selection-background-color: {accent}; selection-color: #030712;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {border2}; background: {surface3};
}}
QPlainTextEdit {{ padding: 12px; }}

/* =========================================================================
   MESSAGE BOX (The typed characters glow with incandescent golden neon bloom)
   ========================================================================= */
#MessageInput {{
    color: {message_text};
    font-weight: 550;
    border: 1.2px solid rgba(0, 240, 255, 0.35);
    background: {message_bg};
    selection-background-color: rgba(255, 160, 0, 0.65);
    selection-color: #030712;
}}
#MessageInput:focus {{
    border: 1.5px solid {message_glow};
    background: rgba(18, 22, 34, 0.70);
}}

/* =========================================================================
   TARGET / TRACKED FILES AREA (Vivid Emerald Green from the Clipped Image)
   ========================================================================= */
#TargetFilesCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 {target_bg}, stop:1 rgba(0, 18, 12, 0.55));
    border: 1.5px solid {target_border};
    border-top: 1.8px solid {target_green};
    border-radius: 14px;
}}
#TargetFilesTitle {{
    font-size: 15px;
    font-weight: 750;
    color: {target_green};
    letter-spacing: -0.2px;
}}
#TrackedFileList, #BatchFileList {{
    background: {target_list_bg};
    border: 1.2px solid rgba(0, 255, 157, 0.35);
    border-radius: 10px;
    padding: 6px 4px;
}}
#TargetFilesLoading {{
    color: {target_green};
    font-size: 12px;
    font-weight: 750;
    background: rgba(0, 255, 157, 0.15);
    border: 1.5px solid {target_green};
    border-radius: 8px;
    padding: 6px 12px;
}}
#TargetFilesCard QCheckBox::indicator:checked,
#BatchFileList QCheckBox::indicator:checked,
#TrackedFileList QCheckBox::indicator:checked {{
    background: {target_green};
    border-color: {target_green};
    image: url({checkmark_icon});
}}
#TargetFilesCard QCheckBox::indicator:checked:hover,
#BatchFileList QCheckBox::indicator:checked:hover,
#TrackedFileList QCheckBox::indicator:checked:hover {{
    background: #50FFBA;
    border-color: #50FFBA;
    image: url({checkmark_icon});
}}

/* Unprocessed files row within target files */
#FileRow {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 32, 20, 0.50), stop:1 rgba(0, 22, 15, 0.45));
    border: 1.2px solid rgba(0, 255, 157, 0.35);
    border-radius: 9px;
}}
#FileRow:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 48, 28, 0.68), stop:1 rgba(0, 36, 22, 0.62));
    border-color: rgba(0, 255, 157, 0.85);
}}

/* 100% completed / sent file row (Vivid Emerald Green matching Target Files) */
#FileRow[done="true"] {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 160, 95, 0.55), stop:0.4 rgba(0, 225, 135, 0.65), stop:0.8 rgba(0, 195, 115, 0.60), stop:1 rgba(0, 160, 95, 0.55));
    border: 1.8px solid {done_green};
}}
#FileRow[done="true"]:hover {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 rgba(0, 185, 110, 0.70), stop:0.4 rgba(0, 255, 157, 0.80), stop:0.8 rgba(0, 220, 130, 0.75), stop:1 rgba(0, 185, 110, 0.70));
    border-color: #38EF7D;
}}
#FileRow[done="true"] #FileName {{ color: #FFFFFF; font-weight: 750; }}
#FileRow[done="true"] #FileMeta {{ color: #E8FFF4; font-weight: 600; }}
#FileRow[done="true"] #DeleteButton {{ background: rgba(0, 0, 0, 0.25); border: 1px solid rgba(255, 255, 255, 0.40); color: #FFFFFF; }}
#FileRow[done="true"] #DeleteButton:hover {{ background: rgba(255, 51, 102, 0.85); border-color: {danger}; color: #FFFFFF; }}
#FileRow[done="true"] QCheckBox::indicator {{ border-color: rgba(255, 255, 255, 0.65); background: rgba(0, 0, 0, 0.30); }}
#FileRow[done="true"] QCheckBox::indicator:checked {{ background: {done_green}; border-color: {done_green}; image: url({checkmark_icon}); }}

#FileName {{ font-weight: 600; }}
#FileMeta {{ color: {muted}; font-size: 11px; }}
#DeleteButton {{
    background: transparent; border: 1px solid {danger_soft}; border-radius: 6px;
    color: {danger}; font-weight: 800; font-size: 13px; padding: 0;
}}
#DeleteButton:hover {{ background: {danger_soft}; border-color: {danger}; color: #FFFFFF; }}

/* =========================================================================
   SCROLLBARS: WIDE (13px) & EASY TO GRAB WITH CLEAR CONTRAST HANDLES
   ========================================================================= */
QScrollBar:vertical {{
    width: 13px;
    background: rgba(4, 10, 20, 0.45);
    border-radius: 6px;
    margin: 2px;
}}
QScrollBar::handle:vertical {{
    background: rgba(0, 240, 255, 0.52);
    border: 1px solid rgba(0, 240, 255, 0.75);
    border-radius: 5px;
    min-height: 38px;
}}
QScrollBar::handle:vertical:hover {{
    background: rgba(0, 240, 255, 0.85);
    border: 1px solid #00F0FF;
}}
QScrollBar::handle:vertical:pressed {{
    background: #00F0FF;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
    height: 0;
}}
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
}}

QScrollBar:horizontal {{
    height: 13px;
    background: rgba(4, 10, 20, 0.45);
    border-radius: 6px;
    margin: 2px;
}}
QScrollBar::handle:horizontal {{
    background: rgba(0, 240, 255, 0.52);
    border: 1px solid rgba(0, 240, 255, 0.75);
    border-radius: 5px;
    min-width: 38px;
}}
QScrollBar::handle:horizontal:hover {{
    background: rgba(0, 240, 255, 0.85);
    border: 1px solid #00F0FF;
}}
QScrollBar::handle:horizontal:pressed {{
    background: #00F0FF;
}}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{
    width: 0;
}}
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {{
    background: transparent;
}}

/* =========================================================================
   BUTTONS & NAVIGATION
   ========================================================================= */
QPushButton {{
    background: {surface2}; color: {text};
    border: 1px solid {border}; border-radius: 8px;
    padding: 8px 14px; font-weight: 600;
}}
QPushButton:hover {{ background: {surface3}; border-color: {border2}; color: {text}; }}
QPushButton:pressed {{ background: {border2}; }}
QPushButton:disabled {{ color: {muted2}; background: rgba(15, 23, 42, 0.4); border-color: rgba(255, 255, 255, 0.05); }}

#PrimaryButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent_hover});
    border: 0; color: #030712; font-weight: 750; border-radius: 8px;
}}
#PrimaryButton:hover {{ background: {accent_hover}; color: #01040A; }}
#PrimaryButton:disabled {{ background: {surface2}; color: {muted2}; border: 1px solid {border}; }}

#DangerButton {{ color: {danger}; border: 1px solid {danger_soft}; background: {surface2}; border-radius: 8px; }}
#DangerButton:hover {{ background: {danger_soft}; border-color: {danger}; }}

#NavButton {{ background: transparent; border: 0; color: {muted}; text-align: left; padding: 11px 14px; border-radius: 8px; font-weight: 600; }}
#NavButton:hover {{ background: {surface2}; color: {text}; }}
#NavButton:checked {{ background: {accent_soft}; color: {accent}; border-left: 3px solid {accent}; }}

#SmallPrimaryButton {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {accent}, stop:1 {accent_hover});
    border: 0; color: #030712; font-weight: 750; border-radius: 8px; padding: 8px 20px;
}}
#SmallPrimaryButton:hover {{ background: {accent_hover}; color: #01040A; }}
#SmallPrimaryButton:disabled {{ background: {surface2}; color: {muted2}; border: 1px solid {border}; }}

#PauseButton {{
    background: {surface2}; color: {text}; border: 1px solid {border};
    border-radius: 6px; padding: 2px 14px; font-weight: 650;
}}
#PauseButton:hover {{ background: {surface3}; border-color: {border2}; }}
#PauseButton[paused="true"] {{ background: rgba(255, 165, 0, 0.25); color: #FFA500; border-color: #FFA500; }}
#PauseButton:disabled {{ background: {surface2}; color: {muted2}; border-color: {border}; }}

/* Progress Bar */
QProgressBar {{ background: {surface2}; border: 1px solid {border}; border-radius: 6px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {purple}, stop:0.6 {accent}, stop:1 {accent_hover}); border-radius: 6px; }}

#OverallProgressCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1,
        stop:0 rgba(28, 18, 6, 0.55),
        stop:0.45 rgba(22, 14, 5, 0.60),
        stop:1 rgba(14, 9, 3, 0.65)
    );
    border: 1.8px solid rgba(255, 175, 0, 0.70);
    border-top: 1.8px solid rgba(255, 225, 115, 0.95);
    border-bottom: 1.8px solid rgba(255, 140, 0, 0.50);
    border-radius: 14px;
}}
QProgressBar#OverallProgressBar {{
    background: rgba(18, 12, 6, 0.85);
    border: 1.2px solid rgba(255, 165, 0, 0.35);
    border-radius: 10px;
    height: 18px;
    text-align: center;
    color: transparent;
}}
QProgressBar#OverallProgressBar::chunk {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:0,
        stop:0 #FF5500,
        stop:0.22 #FF9100,
        stop:0.48 #FFEA00,
        stop:0.62 #FFFDE7,
        stop:0.78 #FFD600,
        stop:1 #FF8F00
    );
    border-radius: 9px;
}}

/* Checkboxes */
QCheckBox {{ spacing: 8px; color: {text}; }}
QCheckBox::indicator {{
    width: 17px;
    height: 17px;
    border-radius: 4px;
    border: 1px solid {border2};
    background: {surface2};
}}
QCheckBox::indicator:hover {{
    border-color: {accent};
}}
QCheckBox::indicator:checked {{
    background: {accent};
    border-color: {accent};
    image: url({checkmark_icon});
}}
QCheckBox::indicator:checked:hover {{
    background: {accent_hover};
    border-color: {accent_hover};
    image: url({checkmark_icon});
}}

/* Tables & Lists */
QTableWidget {{ gridline-color: {border}; }}
QHeaderView::section {{
    background: {surface2}; color: {muted}; border: 0; border-bottom: 1px solid {border};
    padding: 6px 8px; font-weight: 700;
}}
QListWidget {{ background: transparent; border: 0; outline: 0; }}
QListWidget::item {{ border: 0; padding: 0; margin: 3px 0; }}

/* Status & Activity */
#Status {{ color: {success}; font-size: 11px; font-weight: 700; }}
#Loading {{ color: {success}; font-size: 12px; font-weight: 600; }}
#CodeNote {{ background: {surface2}; color: {muted}; border: 1px solid {border}; border-radius: 8px; padding: 10px; font-family: Consolas, monospace; }}
#Log {{
    background: rgba(6, 12, 22, 0.52);
    border: 1.2px solid rgba(0, 240, 255, 0.28);
    border-radius: 8px;
    color: {muted};
    font-family: Consolas, monospace;
    font-size: 11px;
}}

#ReconnectBanner {{
    background: rgba(255, 51, 102, 0.16); border: 1.5px solid #FF3366;
    border-radius: 8px; padding: 6px 12px;
}}
#ReconnectText {{ color: #FF4D6D; font-weight: 700; font-size: 12px; }}
QSizeGrip {{ background: transparent; width: 16px; height: 16px; }}
QStatusBar {{ background: transparent; border-top: 1px solid {border}; }}
QStatusBar::item {{ border: none; }}

#ProjectCard {{
    background: qlineargradient(x1:0, y1:0, x2:0, y2:1, stop:0 rgba(10, 18, 32, 0.50), stop:1 rgba(6, 12, 22, 0.55));
    border: 1.5px solid rgba(0, 240, 255, 0.38);
    border-top: 1.8px solid rgba(0, 240, 255, 0.72);
    border-radius: 14px;
}}
#ProjectCardInvalid {{ background: {surface}; border: 1px solid {danger}; border-radius: 14px; }}
#ProjectName {{ font-size: 15px; font-weight: 750; color: {text}; }}
#ProjectWarn {{ color: {warn_marker}; font-weight: 700; font-size: 11px; }}
#DialogTitle {{ font-size: 20px; font-weight: 750; color: {text}; }}
QDialog {{ background: transparent; color: {text}; }}
QMessageBox, QFileDialog {{ background: #050A14; color: {text}; }}
QDialog QLabel, QMessageBox QLabel, QFileDialog QLabel {{ color: {text}; }}
QToolTip {{ background: rgba(12, 20, 35, 0.95); color: {text}; border: 1px solid {border2}; border-radius: 6px; padding: 6px 10px; font-size: 11px; }}
"""

