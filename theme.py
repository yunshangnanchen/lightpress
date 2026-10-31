"""轻压的配色、系统主题检测与窗口标题栏适配。"""

from __future__ import annotations

import ctypes
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

THEME_MODES = {
    "system": "跟随系统",
    "light": "浅色",
    "dark": "深色",
}


@dataclass(frozen=True)
class Palette:
    mode: str
    BG: str
    CARD: str
    CARD_ALT: str
    CARD_SOFT: str
    BORDER: str
    DIVIDER: str
    SOFT: str
    TEXT: str
    MUTED: str
    FAINT: str
    ACCENT: str
    ACCENT_HOVER: str
    ACCENT_DARK: str
    ACCENT_SOFT: str
    ACCENT_TEXT: str
    ON_ACCENT: str
    LINK: str
    AMBER: str
    AMBER_SOFT: str
    RED: str
    RED_HOVER: str
    RED_SOFT: str
    ON_DANGER: str
    TABLE_HEAD: str
    TABLE_ALT: str
    PROGRESS_TROUGH: str
    SCROLLBAR: str
    INPUT_BG: str
    DROP_BG: str
    DROP_BG_HOVER: str
    DROP_BORDER: str
    DROP_DASH: str
    FOLDER_FRONT: str
    FOLDER_BACK: str
    FOLDER_BORDER: str
    SLIDER_TRACK: str
    SLIDER_HALO: str
    SLIDER_TICK: str
    SLIDER_DISABLED: str
    SLIDER_KNOB: str
    SLIDER_EDGE: str
    DISABLED_FILL: str
    DISABLED_FG: str
    TAG_OK: str
    TAG_KEPT: str
    TAG_ERROR: str

    def backgrounds(self) -> dict[str, str]:
        return {
            key: value
            for key, value in asdict(self).items()
            if key
            in {
                "BG",
                "CARD",
                "CARD_ALT",
                "CARD_SOFT",
                "BORDER",
                "DIVIDER",
                "SOFT",
                "AMBER_SOFT",
                "RED_SOFT",
                "ACCENT_SOFT",
                "TABLE_HEAD",
                "TABLE_ALT",
                "PROGRESS_TROUGH",
                "SCROLLBAR",
                "INPUT_BG",
                "DISABLED_FILL",
            }
        }

    def backgrounds_for_mapping(self) -> dict[str, str]:
        """包含所有可能成为背景/边框的色值。"""
        result = self.backgrounds()
        for key in (
            "DROP_BG",
            "DROP_BG_HOVER",
            "DROP_BORDER",
            "DROP_DASH",
            "FOLDER_FRONT",
            "FOLDER_BACK",
            "FOLDER_BORDER",
            "SLIDER_TRACK",
            "SLIDER_HALO",
            "SLIDER_TICK",
            "SLIDER_DISABLED",
            "SLIDER_KNOB",
            "SLIDER_EDGE",
        ):
            result[key] = getattr(self, key)
        return result

    def foregrounds_for_mapping(self) -> dict[str, str]:
        result = {}
        for key in (
            "TEXT",
            "MUTED",
            "FAINT",
            "ACCENT",
            "ACCENT_DARK",
            "ACCENT_TEXT",
            "LINK",
            "AMBER",
            "RED",
            "DISABLED_FG",
            "TAG_OK",
            "TAG_KEPT",
            "TAG_ERROR",
        ):
            result[key] = getattr(self, key)
        return result


LIGHT = Palette(
    mode="light",
    BG="#f3f7f4",
    CARD="#ffffff",
    CARD_ALT="#fbfdfc",
    CARD_SOFT="#f8fbf9",
    BORDER="#dde7e1",
    DIVIDER="#edf3ef",
    SOFT="#eef5f0",
    TEXT="#18261f",
    MUTED="#687970",
    FAINT="#98a79f",
    ACCENT="#0f8f76",
    ACCENT_HOVER="#0a725e",
    ACCENT_DARK="#0a725e",
    ACCENT_SOFT="#e4f5ef",
    ACCENT_TEXT="#0a725e",
    ON_ACCENT="#ffffff",
    LINK="#0f8f76",
    AMBER="#a06a18",
    AMBER_SOFT="#fff6e5",
    RED="#b24740",
    RED_HOVER="#943a34",
    RED_SOFT="#fceae8",
    ON_DANGER="#ffffff",
    TABLE_HEAD="#f5f9f6",
    TABLE_ALT="#fbfdfc",
    PROGRESS_TROUGH="#e9f0ec",
    SCROLLBAR="#cfddd6",
    INPUT_BG="#f7faf8",
    DROP_BG="#f9fdfb",
    DROP_BG_HOVER="#f0fbf6",
    DROP_BORDER="#a9cbbd",
    DROP_DASH="#b9d9cc",
    FOLDER_FRONT="#e5f5ee",
    FOLDER_BACK="#d7eee5",
    FOLDER_BORDER="#c6e5d9",
    SLIDER_TRACK="#e4eee8",
    SLIDER_HALO="#e2efe9",
    SLIDER_TICK="#b7c9c0",
    SLIDER_DISABLED="#b9d4c9",
    SLIDER_KNOB="#ffffff",
    SLIDER_EDGE="#b8c9c0",
    DISABLED_FILL="#dfe8e3",
    DISABLED_FG="#93a69c",
    TAG_OK="#1b5b4b",
    TAG_KEPT="#a06a18",
    TAG_ERROR="#b24740",
)

DARK = Palette(
    mode="dark",
    BG="#0c1210",
    CARD="#151e1a",
    CARD_ALT="#19241f",
    CARD_SOFT="#1a2520",
    BORDER="#2b3a33",
    DIVIDER="#22302a",
    SOFT="#202d27",
    TEXT="#e9f3ee",
    MUTED="#a3b6ac",
    FAINT="#74897e",
    ACCENT="#27b99b",
    ACCENT_HOVER="#34cbab",
    ACCENT_DARK="#70e2c7",
    ACCENT_SOFT="#10342b",
    ACCENT_TEXT="#83e8cf",
    ON_ACCENT="#06130f",
    LINK="#50dcbc",
    AMBER="#e3b25a",
    AMBER_SOFT="#352914",
    RED="#d76d64",
    RED_HOVER="#e78179",
    RED_SOFT="#381c19",
    ON_DANGER="#190807",
    TABLE_HEAD="#1a2520",
    TABLE_ALT="#18211d",
    PROGRESS_TROUGH="#25362e",
    SCROLLBAR="#3c4e45",
    INPUT_BG="#1b2721",
    DROP_BG="#111a16",
    DROP_BG_HOVER="#14241e",
    DROP_BORDER="#3a6153",
    DROP_DASH="#335347",
    FOLDER_FRONT="#1d3b30",
    FOLDER_BACK="#254c3e",
    FOLDER_BORDER="#356152",
    SLIDER_TRACK="#293b33",
    SLIDER_HALO="#20372e",
    SLIDER_TICK="#50665b",
    SLIDER_DISABLED="#3d5f52",
    SLIDER_KNOB="#e4f7f0",
    SLIDER_EDGE="#4a695c",
    DISABLED_FILL="#26362f",
    DISABLED_FG="#6b8075",
    TAG_OK="#6ad8b5",
    TAG_KEPT="#e3b25a",
    TAG_ERROR="#ef9189",
)


def current_palette(mode: str) -> Palette:
    if mode == "dark":
        return DARK
    if mode == "light":
        return LIGHT
    return DARK if system_is_dark() else LIGHT


def system_is_dark() -> bool:
    """读取 Windows 的应用深色模式。非 Windows 默认浅色。"""
    if sys.platform != "win32":
        return False
    try:
        import winreg

        path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
        return int(value) == 0
    except Exception:
        return False


def load_theme_mode(path: Path) -> str:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        mode = str(data.get("theme", "system"))
        return mode if mode in THEME_MODES else "system"
    except Exception:
        return "system"


def save_theme_mode(path: Path, mode: str) -> None:
    if mode not in THEME_MODES:
        return
    try:
        data: dict[str, Any] = {}
        if path.exists():
            try:
                loaded = json.loads(path.read_text(encoding="utf-8"))
                if isinstance(loaded, dict):
                    data = loaded
            except Exception:
                pass
        data["theme"] = mode
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except OSError:
        pass


def _top_level_hwnd(root) -> int | None:
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        hwnd = root.winfo_id()
        parent = user32.GetParent(hwnd)
        return int(parent or hwnd)
    except Exception:
        return None


def apply_titlebar_theme(root, dark: bool) -> None:
    """让 Windows 原生标题栏跟随应用主题。"""
    hwnd = _top_level_hwnd(root)
    if not hwnd:
        return
    try:
        root.update_idletasks()
        value = ctypes.c_int(1 if dark else 0)
        for attribute in (20, 19):  # DWMWA_USE_IMMERSIVE_DARK_MODE (new/old)
            result = ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, attribute, ctypes.byref(value), ctypes.sizeof(value)
            )
            if result == 0:
                break
        # 窗口边框颜色（Windows 11）：深色使用低对比边框
        border = ctypes.c_int(0x1E2A24 if dark else 0xF3F7F4)
        try:
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 34, ctypes.byref(border), ctypes.sizeof(border)
            )
        except Exception:
            pass
        # 运行中切换标题栏颜色时，DWM 有时需要一次非客户区重绘才会生效
        user32 = ctypes.windll.user32
        user32.SetWindowPos(
            hwnd,
            0,
            0,
            0,
            0,
            0,
            0x0001 | 0x0002 | 0x0004 | 0x0010 | 0x0020,
        )
        user32.RedrawWindow(
            hwnd,
            None,
            None,
            0x0001 | 0x0080 | 0x0100 | 0x0400,
        )
        root.update_idletasks()
    except Exception:
        pass
