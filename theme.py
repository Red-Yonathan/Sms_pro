# Holographic Fintech / Cyberpunk Glassmorphism Palette
COLORS = {
    "bg": "#02040A",
    "bg2": "#050D1A",
    "sidebar": "rgba(4, 8, 18, 0.88)",
    "surface": "rgba(12, 20, 35, 0.55)",
    "surface2": "rgba(16, 26, 44, 0.72)",
    "surface3": "rgba(28, 44, 72, 0.85)",
    "border": "rgba(0, 240, 255, 0.16)",
    "border2": "rgba(0, 240, 255, 0.55)",
    "text": "#F0F9FF",
    "muted": "#8BA3B8",
    "muted2": "#4A6670",
    "accent": "#00F0FF",
    "accent_hover": "#80F8FF",
    "accent_soft": "rgba(0, 240, 255, 0.10)",
    "cyan": "#00F0FF",
    "blue": "#2563FF",
    "purple": "#7000FF",
    "success": "#00FF9D",
    "success_soft": "rgba(0, 255, 157, 0.12)",
    "warning": "#FFD700",
    "warning_soft": "rgba(255, 215, 0, 0.12)",
    "danger": "#FF3366",
    "danger_soft": "rgba(255, 51, 102, 0.15)",
    # NEW: message/recipient input text gets its own neon color so it
    # visually stands out from ordinary UI text (see #MessageInput below).
    "message_text": "#FF2EC4",
    "message_glow": "#FF2EC4",
    # NEW: window background tint painted UNDER the glass panels. Alpha
    # controls how much of the OS-level Mica/Acrylic blur (see mica.py)
    # shows through. 0.90 alpha == "90% opaque" per the requested look.
    "window_tint": "rgba(2, 4, 10, 230)",       # 230/255 ~= 90%
    "window_tint_wallpaper": "rgba(2, 4, 10, 160)",  # lighter so a chosen wallpaper still reads through
    # Project-marker warning color (folder that wasn't created by this app)
    "warn_marker": "#FF3366",
}

STYLESHEET = """
* {{ 
    font-size: 13px; 
}}
QMainWindow {{ background: transparent; }}
#CentralWidget {{ background: transparent; color: {text}; }}
QWidget {{ color: {text}; }}
#ManualPage, #BatchPage, #ProjectsPage {{ background: transparent; }}
QStackedWidget {{ background: transparent; }}
QScrollArea, QScrollArea > QWidget > QWidget {{ background: transparent; }}
#Sidebar {{ background: {sidebar}; border-right: 1px solid {border}; }}
#BrandTitle {{ font-size: 19px; font-weight: 700; color: {text}; letter-spacing: -0.3px; }}
#BrandSub {{ font-size: 11px; color: {muted}; }}
#Topbar {{ background: rgba(4, 8, 18, 0.55); border-bottom: 1px solid {border}; }}
#PageTitle {{ font-size: 26px; font-weight: 700; color: {text}; letter-spacing: -0.5px; }}
#PageSubtitle {{ color: {muted}; font-size: 13px; }}
#Card {{ background: {surface}; border: 1px solid {border}; border-top: 1px solid rgba(255, 255, 255, 0.06); border-radius: 14px; }}
#SectionTitle {{ font-size: 14px; font-weight: 700; color: {text}; }}
#Muted {{ color: {muted}; }}
#TinyMuted {{ color: {muted2}; font-size: 11px; }}
#StatNumber {{ font-size: 26px; font-weight: 750; color: {text}; }}
#StatLabel {{ color: {muted}; font-size: 10px; font-weight: 700; letter-spacing: 0.8px; }}
QLineEdit, QPlainTextEdit, QComboBox, QSpinBox, QTableWidget {{
    background: {surface2}; color: {text};
    border: 1px solid {border}; border-radius: 8px;
    padding: 10px 12px; selection-background-color: {accent}; selection-color: #030712;
}}
QLineEdit:focus, QPlainTextEdit:focus, QComboBox:focus, QSpinBox:focus {{
    border: 1px solid {border2}; background: {surface3};
}}
QPlainTextEdit {{ padding: 12px; }}
/* Message / recipient entry boxes: distinct glowing neon text color */
#MessageInput {{ color: {message_text}; font-weight: 650; }}
QTableWidget {{ gridline-color: {border}; }}
QHeaderView::section {{
    background: {surface2}; color: {muted}; border: 0; border-bottom: 1px solid {border};
    padding: 6px 8px; font-weight: 700;
}}
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
QProgressBar {{ background: {surface2}; border: 1px solid {border}; border-radius: 6px; height: 8px; text-align: center; color: transparent; }}
QProgressBar::chunk {{ background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 {purple}, stop:0.6 {accent}, stop:1 {accent_hover}); border-radius: 6px; }}
QListWidget {{ background: transparent; border: 0; outline: 0; }}
QListWidget::item {{ border: 0; padding: 0; margin: 2px 0; }}
QScrollBar:vertical {{ width: 6px; background: transparent; }}
QScrollBar::handle:vertical {{ background: {border2}; border-radius: 3px; min-height: 28px; }}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{ height: 0; }}
QScrollBar:horizontal {{ height: 6px; background: transparent; }}
QScrollBar::handle:horizontal {{ background: {border2}; border-radius: 3px; min-width: 28px; }}
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {{ width: 0; }}
#Status {{ color: {success}; font-size: 11px; font-weight: 700; }}
#Loading {{ color: {accent}; font-size: 12px; font-weight: 600; }}
#CodeNote {{ background: {surface2}; color: {muted}; border: 1px solid {border}; border-radius: 8px; padding: 10px; font-family: Consolas, monospace; }}
#Log {{ background: {surface2}; border: 1px solid {border}; border-radius: 8px; color: {muted}; font-family: Consolas, monospace; font-size: 11px; }}
QCheckBox {{ spacing: 8px; color: {text}; }}
QCheckBox::indicator {{ width: 16px; height: 16px; border-radius: 4px; border: 1px solid {border2}; background: {surface2}; }}
QCheckBox::indicator:checked {{ background: {accent}; border-color: {accent}; }}
#FileRow {{ background: {surface2}; border: 1px solid {border}; border-radius: 8px; }}
#FileRow:hover {{ background: {surface3}; border-color: {border2}; }}
#FileName {{ font-weight: 600; }}
#FileMeta {{ color: {muted}; font-size: 11px; }}
#ProjectCard {{ background: {surface}; border: 1px solid {border}; border-radius: 14px; }}
#ProjectCardInvalid {{ background: {surface}; border: 1px solid {danger}; border-radius: 14px; }}
#ProjectName {{ font-size: 15px; font-weight: 750; color: {text}; }}
#ProjectWarn {{ color: {warn_marker}; font-weight: 700; font-size: 11px; }}
#DialogTitle {{ font-size: 20px; font-weight: 750; color: {text}; }}
QDialog, QMessageBox, QFileDialog {{ background: #050A14; color: {text}; }}
QDialog QLabel, QMessageBox QLabel, QFileDialog QLabel {{ color: {text}; }}
QToolTip {{ background: rgba(12, 20, 35, 0.95); color: {text}; border: 1px solid {border2}; border-radius: 6px; padding: 6px 10px; font-size: 11px; }}
"""
