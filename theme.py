"""轻压的 Material 3 配色、系统主题检测与窗口标题栏适配。

界面遵循 Google Material 3 的色彩角色（color roles）：
surface / surface-container-* / primary / primary-container / outline 等。
浅色主题取 Google 产品常用的蓝色主色，深色主题使用 M3 的深色 tonal 映射。
"""

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


def mix_hex(base: str, overlay: str, ratio: float) -> str:
    """在两个 #rrggbb 之间插值，用来合成 Material 的状态层。"""
    ratio = max(0.0, min(1.0, float(ratio)))
    try:
        source = str(base).lstrip("#")
        target = str(overlay).lstrip("#")
        if len(source) != 6 or len(target) != 6:
            return base
        channels = [
            round(
                int(source[index : index + 2], 16) * (1 - ratio)
                + int(target[index : index + 2], 16) * ratio
            )
            for index in (0, 2, 4)
        ]
    except (TypeError, ValueError):
        return base
    return "#{:02x}{:02x}{:02x}".format(*channels)


@dataclass(frozen=True)
class Palette:
    mode: str
    # 基础表面
    BG: str
    CARD: str
    CARD_ALT: str
    CARD_SOFT: str
    BORDER: str
    DIVIDER: str
    SOFT: str
    # 文本
    TEXT: str
    MUTED: str
    FAINT: str
    # 主色
    ACCENT: str
    ACCENT_HOVER: str
    ACCENT_DARK: str
    ACCENT_SOFT: str
    ACCENT_TEXT: str
    ON_ACCENT: str
    LINK: str
    # 语义色
    AMBER: str
    AMBER_SOFT: str
    RED: str
    RED_HOVER: str
    RED_SOFT: str
    ON_DANGER: str
    SUCCESS: str
    SUCCESS_SOFT: str
    ON_SUCCESS_SOFT: str
    # 表格与滚动
    TABLE_HEAD: str
    TABLE_ALT: str
    PROGRESS_TROUGH: str
    SCROLLBAR: str
    INPUT_BG: str
    # 拖放区
    DROP_BG: str
    DROP_BG_HOVER: str
    DROP_BORDER: str
    DROP_DASH: str
    FOLDER_FRONT: str
    FOLDER_BACK: str
    FOLDER_BORDER: str
    # 滑杆
    SLIDER_TRACK: str
    SLIDER_HALO: str
    SLIDER_TICK: str
    SLIDER_DISABLED: str
    SLIDER_KNOB: str
    SLIDER_EDGE: str
    # 禁用与状态标签
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
                "SUCCESS_SOFT",
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
            "SUCCESS",
            "ON_SUCCESS_SOFT",
            "DISABLED_FG",
            "TAG_OK",
            "TAG_KEPT",
            "TAG_ERROR",
        ):
            result[key] = getattr(self, key)
        return result


# Material 3 · 浅色（Google Blue 主色）
LIGHT = Palette(
    mode="light",
    BG="#f0f4f9",
    CARD="#ffffff",
    CARD_ALT="#f4f7fc",
    CARD_SOFT="#eaf0f8",
    BORDER="#dbe2ec",
    DIVIDER="#e8edf5",
    SOFT="#e9eef7",
    TEXT="#1f1f1f",
    MUTED="#444746",
    FAINT="#747775",
    ACCENT="#0b57d0",
    ACCENT_HOVER="#1f68d5",
    ACCENT_DARK="#041e49",
    ACCENT_SOFT="#d3e3fd",
    ACCENT_TEXT="#0b57d0",
    ON_ACCENT="#ffffff",
    LINK="#0b57d0",
    AMBER="#8a4b00",
    AMBER_SOFT="#ffe9c7",
    RED="#b3261e",
    RED_HOVER="#8c1d18",
    RED_SOFT="#f9dedc",
    ON_DANGER="#ffffff",
    SUCCESS="#146c2e",
    SUCCESS_SOFT="#c4eed0",
    ON_SUCCESS_SOFT="#072711",
    TABLE_HEAD="#ffffff",
    TABLE_ALT="#fafcff",
    PROGRESS_TROUGH="#dde5f0",
    SCROLLBAR="#c4c7c5",
    INPUT_BG="#f4f7fc",
    DROP_BG="#f4f7fc",
    DROP_BG_HOVER="#e8f0fe",
    DROP_BORDER="#dbe2ec",
    DROP_DASH="#c4c7c5",
    FOLDER_FRONT="#d3e3fd",
    FOLDER_BACK="#b6d2fb",
    FOLDER_BORDER="#a4c7f8",
    SLIDER_TRACK="#dde5f0",
    SLIDER_HALO="#dbe8fd",
    SLIDER_TICK="#c4c7c5",
    SLIDER_DISABLED="#c3cbd6",
    SLIDER_KNOB="#0b57d0",
    SLIDER_EDGE="#ffffff",
    DISABLED_FILL="#e7e9ee",
    DISABLED_FG="#a2a7ad",
    TAG_OK="#146c2e",
    TAG_KEPT="#8a4b00",
    TAG_ERROR="#b3261e",
)

# Material 3 · 深色
DARK = Palette(
    mode="dark",
    BG="#131314",
    CARD="#1e1f20",
    CARD_ALT="#25262a",
    CARD_SOFT="#2c2e31",
    BORDER="#3c4043",
    DIVIDER="#2a2c2e",
    SOFT="#333537",
    TEXT="#e3e3e3",
    MUTED="#c4c7c5",
    FAINT="#9aa0a6",
    ACCENT="#a8c7fa",
    ACCENT_HOVER="#c2d7fb",
    ACCENT_DARK="#d3e3fd",
    ACCENT_SOFT="#0842a0",
    ACCENT_TEXT="#a8c7fa",
    ON_ACCENT="#062e6f",
    LINK="#8ab4f8",
    AMBER="#ffdf9e",
    AMBER_SOFT="#3f2e00",
    RED="#f2b8b5",
    RED_HOVER="#f9dedc",
    RED_SOFT="#5c1a17",
    ON_DANGER="#601410",
    SUCCESS="#6dd58c",
    SUCCESS_SOFT="#0f5223",
    ON_SUCCESS_SOFT="#c4eed0",
    TABLE_HEAD="#1e1f20",
    TABLE_ALT="#202124",
    PROGRESS_TROUGH="#3c4043",
    SCROLLBAR="#5f6368",
    INPUT_BG="#25262a",
    DROP_BG="#1e1f20",
    DROP_BG_HOVER="#1b2b44",
    DROP_BORDER="#3c4043",
    DROP_DASH="#5f6368",
    FOLDER_FRONT="#1a4a8f",
    FOLDER_BACK="#123a75",
    FOLDER_BORDER="#2f5f9e",
    SLIDER_TRACK="#444746",
    SLIDER_HALO="#1b2b44",
    SLIDER_TICK="#5f6368",
    SLIDER_DISABLED="#4a4e52",
    SLIDER_KNOB="#a8c7fa",
    SLIDER_EDGE="#131314",
    DISABLED_FILL="#2d2e30",
    DISABLED_FG="#7a7e83",
    TAG_OK="#6dd58c",
    TAG_KEPT="#ffdf9e",
    TAG_ERROR="#f2b8b5",
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
        # 窗口边框颜色（Windows 11）：与 Material 表面色保持一致
        border = ctypes.c_int(0x131314 if dark else 0xF0F4F9)
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
