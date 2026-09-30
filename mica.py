"""
mica.py
========
Applies a real OS-level blurred backdrop behind the window.

For the blur to be VISIBLE three things must all be true (the first
version of this app only did #2, which is why nothing showed):
  1. the Qt window is translucent (Qt.WA_TranslucentBackground, set in
     MainWindow) and does NOT paint an opaque background over itself
  2. a DWM backdrop is requested (Mica / Acrylic / Win10 blur-behind)
  3. the DWM frame is extended over the whole client area
     (DwmExtendFrameIntoClientArea with -1 margins) -- done here

>>> TOGGLES <<<
ENABLE_NATIVE_BLUR : False = plain opaque-ish painted background, no OS blur.
BACKDROP_MODE      : "acrylic" -> real blur of whatever is behind the window
                                  (closest to the frosted-glass look)
                     "mica"    -> Win11 wallpaper-tinted material (subtle;
                                  does NOT blur windows behind it)
                     "tabbed"  -> Win11 "Mica Alt"
"""
import sys
import ctypes
from ctypes import wintypes

ENABLE_NATIVE_BLUR = True   # <-- TOGGLE ME
BACKDROP_MODE = "acrylic"   # <-- "acrylic" | "mica" | "tabbed"

_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_SYSTEMBACKDROP_TYPE = 38   # Win11 22H2+ (build 22621)
_DWMWA_MICA_EFFECT = 1029         # early Win11 builds (22000)
_BACKDROP_TYPES = {"mica": 2, "acrylic": 3, "tabbed": 4}

_WCA_ACCENT_POLICY = 19
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4


class _MARGINS(ctypes.Structure):
    _fields_ = [("l", ctypes.c_int), ("r", ctypes.c_int), ("t", ctypes.c_int), ("b", ctypes.c_int)]


class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [("AccentState", ctypes.c_int), ("AccentFlags", ctypes.c_int),
                ("GradientColor", ctypes.c_uint), ("AnimationId", ctypes.c_int)]


class _WINCOMPATTRDATA(ctypes.Structure):
    _fields_ = [("Attribute", ctypes.c_int), ("Data", ctypes.POINTER(_ACCENT_POLICY)),
                ("SizeOfData", ctypes.c_size_t)]


def native_blur_wanted():
    return ENABLE_NATIVE_BLUR and sys.platform == "win32"


def apply_mica(hwnd, dark=True, gradient_abgr=0x99050A02):
    """Returns a short description of what was applied ("Acrylic (Win11)",
    "Mica (Win11)", "Acrylic (Win10 fallback)") or None if nothing took
    effect. gradient_abgr is only used by the Win10 fallback (AABBGGRR)."""
    if not native_blur_wanted() or not hwnd:
        return None
    dwmapi = ctypes.windll.dwmapi
    try:
        value = ctypes.c_int(1 if dark else 0)
        dwmapi.DwmSetWindowAttribute(hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE,
                                     ctypes.byref(value), ctypes.sizeof(value))
        # Let the DWM material extend under the entire client area.
        margins = _MARGINS(-1, -1, -1, -1)
        dwmapi.DwmExtendFrameIntoClientArea(hwnd, ctypes.byref(margins))
    except Exception:
        pass

    mode = BACKDROP_MODE if BACKDROP_MODE in _BACKDROP_TYPES else "acrylic"
    try:
        backdrop = ctypes.c_int(_BACKDROP_TYPES[mode])
        if dwmapi.DwmSetWindowAttribute(hwnd, _DWMWA_SYSTEMBACKDROP_TYPE,
                                        ctypes.byref(backdrop), ctypes.sizeof(backdrop)) == 0:
            return f"{mode.capitalize()} (Win11)"
        legacy = ctypes.c_int(1)
        if dwmapi.DwmSetWindowAttribute(hwnd, _DWMWA_MICA_EFFECT,
                                        ctypes.byref(legacy), ctypes.sizeof(legacy)) == 0:
            return "Mica (Win11 early build)"
    except Exception:
        pass

    try:  # Windows 10 fallback
        accent = _ACCENT_POLICY()
        accent.AccentState = _ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2
        accent.GradientColor = gradient_abgr
        data = _WINCOMPATTRDATA()
        data.Attribute = _WCA_ACCENT_POLICY
        data.SizeOfData = ctypes.sizeof(accent)
        data.Data = ctypes.pointer(accent)
        ctypes.windll.user32.SetWindowCompositionAttribute(hwnd, ctypes.byref(data))
        return "Acrylic (Win10 fallback)"
    except Exception:
        return None
