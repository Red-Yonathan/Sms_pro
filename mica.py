"""
mica.py
========
Applies a real OS-level blurred backdrop behind the window chrome
(Windows 11 "Mica"/"Acrylic", falling back to the Windows 10 acrylic
blur-behind trick). This is what actually produces the frosted-glass
look behind your content -- painting a semi-transparent rectangle in
Qt alone (as in the old testing.py) only fades to whatever is fully
buffered behind the window, it does NOT blur the desktop/other windows.

>>> TOGGLE <<<
Flip this to False to disable native blur-behind entirely and fall
back to the plain semi-transparent painted background (theme.py's
"window_tint"). Useful if Mica causes issues on a given machine/VM,
or if you're on Linux/macOS where none of this applies anyway.
"""
import sys
import ctypes

ENABLE_NATIVE_BLUR = True  # <-- TOGGLE ME

# DWM attribute ids (Windows)
_DWMWA_USE_IMMERSIVE_DARK_MODE = 20
_DWMWA_SYSTEMBACKDROP_TYPE = 38  # Windows 11 22H2+

# DWMSBT_* backdrop types
_DWMSBT_MAINWINDOW = 2   # Mica
_DWMSBT_TRANSIENTWINDOW = 3  # Acrylic
_DWMSBT_TABBEDWINDOW = 4  # Mica Alt

# Windows 10 undocumented SetWindowCompositionAttribute accent policy
_WCA_ACCENT_POLICY = 19
_ACCENT_ENABLE_ACRYLICBLURBEHIND = 4
_ACCENT_ENABLE_BLURBEHIND = 3


class _ACCENT_POLICY(ctypes.Structure):
    _fields_ = [
        ("AccentState", ctypes.c_int),
        ("AccentFlags", ctypes.c_int),
        ("GradientColor", ctypes.c_uint),
        ("AnimationId", ctypes.c_int),
    ]


class _WINCOMPATTRDATA(ctypes.Structure):
    _fields_ = [
        ("Attribute", ctypes.c_int),
        ("Data", ctypes.POINTER(_ACCENT_POLICY)),
        ("SizeOfData", ctypes.c_size_t),
    ]


def apply_mica(hwnd, dark=True, gradient_bgra=0xE60A0402):
    """Try Win11 Mica, then Win10 acrylic blur-behind. Returns True on
    (best-effort) success, False if unsupported/unavailable -- callers
    should treat False as "fine, the painted tint alone will show."
    gradient_bgra: AABBGGRR tint used by the Win10 fallback only
    (default ~90% opaque dark navy, matching theme.py's window_tint).
    """
    if not ENABLE_NATIVE_BLUR or sys.platform != "win32" or not hwnd:
        return False
    try:
        dwmapi = ctypes.windll.dwmapi
        value = ctypes.c_int(1 if dark else 0)
        dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(value), ctypes.sizeof(value)
        )
        backdrop = ctypes.c_int(_DWMSBT_MAINWINDOW)
        result = dwmapi.DwmSetWindowAttribute(
            hwnd, _DWMWA_SYSTEMBACKDROP_TYPE, ctypes.byref(backdrop), ctypes.sizeof(backdrop)
        )
        if result == 0:
            return True
    except Exception:
        pass

    try:
        accent = _ACCENT_POLICY()
        accent.AccentState = _ACCENT_ENABLE_ACRYLICBLURBEHIND
        accent.AccentFlags = 2
        accent.GradientColor = gradient_bgra
        data = _WINCOMPATTRDATA()
        data.Attribute = _WCA_ACCENT_POLICY
        data.SizeOfData = ctypes.sizeof(accent)
        data.Data = ctypes.pointer(accent)
        set_attr = ctypes.windll.user32.SetWindowCompositionAttribute
        set_attr(hwnd, ctypes.byref(data))
        return True
    except Exception:
        return False
