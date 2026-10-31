"""轻压 · 视觉无损批量压缩（Windows 桌面界面）。"""

from __future__ import annotations

import ctypes
import os
import queue
import sys
import threading
import time
import traceback
from pathlib import Path
from tkinter import BOTH, END, LEFT, RIGHT, X, Y, filedialog, messagebox
import tkinter as tk
from tkinter import ttk
import tkinter.font as tkfont

BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR / "vendor"))
sys.path.insert(0, str(BASE_DIR))

try:
    from tkinterdnd2 import DND_FILES, TkinterDnD

    DND_AVAILABLE = True
except Exception:  # 拖拽组件缺失时仍可用“点击选择文件夹”
    DND_AVAILABLE = False

from compressor import (  # noqa: E402
    CompressionOptions,
    compress_folder,
    default_output_dir,
    format_bytes,
    scan_folder,
)
from compressor.core import MAX_TARGET_PSNR, MIN_TARGET_PSNR  # noqa: E402
from theme import (  # noqa: E402
    DARK,
    LIGHT,
    THEME_MODES,
    Palette,
    apply_titlebar_theme,
    current_palette,
    load_theme_mode,
    save_theme_mode,
    system_is_dark,
)

APP_NAME = "轻压"
APP_VERSION = "1.1"
ICON_ICO = BASE_DIR / "assets" / "logo.ico"
ICON_PNG = BASE_DIR / "assets" / "logo.png"
LOGO_LIGHT = BASE_DIR / "assets" / "logo_mark_light.png"
LOGO_DARK = BASE_DIR / "assets" / "logo_mark_dark.png"
SETTINGS_FILE = BASE_DIR / "settings.json"

# 构建时使用浅色配色；切换主题时会统一映射到 Palette。
BG = LIGHT.BG
CARD = LIGHT.CARD
CARD_ALT = LIGHT.CARD_ALT
CARD_SOFT = LIGHT.CARD_SOFT
BORDER = LIGHT.BORDER
DIVIDER = LIGHT.DIVIDER
SOFT = LIGHT.SOFT
TEXT = LIGHT.TEXT
MUTED = LIGHT.MUTED
FAINT = LIGHT.FAINT
ACCENT = LIGHT.ACCENT
ACCENT_HOVER = LIGHT.ACCENT_HOVER
ACCENT_DARK = LIGHT.ACCENT_DARK
ACCENT_SOFT = LIGHT.ACCENT_SOFT
ACCENT_TEXT = LIGHT.ACCENT_TEXT
ON_ACCENT = LIGHT.ON_ACCENT
LINK = LIGHT.LINK
AMBER = LIGHT.AMBER
AMBER_SOFT = LIGHT.AMBER_SOFT
RED = LIGHT.RED
RED_HOVER = LIGHT.RED_HOVER
RED_SOFT = LIGHT.RED_SOFT
ON_DANGER = LIGHT.ON_DANGER
TABLE_HEAD = LIGHT.TABLE_HEAD
TABLE_ALT = LIGHT.TABLE_ALT
PROGRESS_TROUGH = LIGHT.PROGRESS_TROUGH
SCROLLBAR = LIGHT.SCROLLBAR
INPUT_BG = LIGHT.INPUT_BG
DROP_BG = LIGHT.DROP_BG
DROP_BG_HOVER = LIGHT.DROP_BG_HOVER
DROP_BORDER = LIGHT.DROP_BORDER
DROP_DASH = LIGHT.DROP_DASH
FOLDER_FRONT = LIGHT.FOLDER_FRONT
FOLDER_BACK = LIGHT.FOLDER_BACK
FOLDER_BORDER = LIGHT.FOLDER_BORDER
SLIDER_TRACK = LIGHT.SLIDER_TRACK
SLIDER_HALO = LIGHT.SLIDER_HALO
SLIDER_TICK = LIGHT.SLIDER_TICK
SLIDER_DISABLED = LIGHT.SLIDER_DISABLED
SLIDER_KNOB = LIGHT.SLIDER_KNOB
SLIDER_EDGE = LIGHT.SLIDER_EDGE
DISABLED_FILL = LIGHT.DISABLED_FILL
DISABLED_FG = LIGHT.DISABLED_FG
RED_DARK = LIGHT.RED_HOVER

FONT_FAMILY = "Microsoft YaHei UI"
MAX_DIMENSIONS = {
    "保持原尺寸": 0,
    "3840 px": 3840,
    "2560 px": 2560,
    "1920 px": 1920,
    "1600 px": 1600,
    "1280 px": 1280,
}


def _choose_font(root: tk.Misc) -> str:
    families = set(tkfont.families(root))
    for candidate in (FONT_FAMILY, "Microsoft YaHei", "Segoe UI", "Arial"):
        if candidate in families:
            return candidate
    return "TkDefaultFont"


def _truncate_middle(text: str, limit: int = 62) -> str:
    if len(text) <= limit:
        return text
    keep = limit - 1
    left = keep // 2
    right = keep - left
    return f"{text[:left]}…{text[-right:]}"


def _compact_path(path: Path, keep_parts: int = 3) -> str:
    """保留盘符和最后几级目录，让长路径在卡片里仍然可读。"""
    text = str(path)
    if len(text) <= 48:
        return text
    parts = path.parts
    tail = "\\".join(parts[-keep_parts:])
    if path.drive:
        return f"{path.drive}\\…\\{tail}"
    if path.anchor:
        return f"{path.anchor}…{tail}"
    return f"…\\{tail}"


def _rounded_points(x1: float, y1: float, x2: float, y2: float, r: float) -> list[float]:
    r = max(0.0, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    return [
        x1 + r, y1,
        x2 - r, y1,
        x2, y1,
        x2, y1 + r,
        x2, y2 - r,
        x2, y2,
        x2 - r, y2,
        x1 + r, y2,
        x1, y2,
        x1, y2 - r,
        x1, y1 + r,
        x1, y1,
    ]


class RoundedButton(tk.Canvas):
    """Canvas 绘制的圆角主按钮，支持禁用、换色和动态宽度。"""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        height: int = 50,
        radius: int = 12,
        bg: str = CARD,
        fill: str = ACCENT,
        hover: str = ACCENT_DARK,
        fg: str = "#ffffff",
        disabled_fill: str = "#dfe8e3",
        disabled_fg: str = "#93a69c",
        font: tuple | None = None,
    ) -> None:
        super().__init__(
            parent,
            height=height,
            bg=bg,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._text = text
        self._command = command
        self._radius = radius
        self._fill = fill
        self._hover = hover
        self._fg = fg
        self._disabled_fill = disabled_fill
        self._disabled_fg = disabled_fg
        self._font = font or (FONT_FAMILY, 11, "bold")
        self._enabled = True
        self._hovered = False
        self._mode = "normal"
        self._palette = LIGHT
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        width = max(10, self.winfo_width())
        height = max(10, self.winfo_height())
        fill = self._fill if self._enabled else self._disabled_fill
        if self._hovered and self._enabled:
            fill = self._hover
        points = _rounded_points(1, 1, width - 1, height - 1, self._radius)
        self.create_polygon(
            *points, smooth=True, splinesteps=32, fill=fill, outline=fill
        )
        self.create_text(
            width / 2,
            height / 2 + 1,
            text=self._text,
            fill=self._fg if self._enabled else self._disabled_fg,
            font=self._font,
        )

    def _on_enter(self, _event=None) -> None:
        if self._enabled:
            self._hovered = True
            self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._draw()

    def _on_click(self, _event=None) -> None:
        if self._enabled and self._command:
            self._command()

    def set_text(self, text: str) -> None:
        self._text = text
        self._draw()

    def set_state(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_palette(self, fill: str, hover: str, fg: str = "#ffffff") -> None:
        self._fill = fill
        self._hover = hover
        self._fg = fg
        self._draw()

    def set_mode(self, mode: str) -> None:
        self._mode = mode if mode in {"normal", "danger"} else "normal"
        self.apply_palette(self._palette)

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.configure(bg=palette.BG)
        self._disabled_fill = palette.DISABLED_FILL
        self._disabled_fg = palette.DISABLED_FG
        if self._mode == "danger":
            self._fill = palette.RED
            self._hover = palette.RED_HOVER
            self._fg = palette.ON_DANGER
        else:
            self._fill = palette.ACCENT
            self._hover = palette.ACCENT_HOVER
            self._fg = palette.ON_ACCENT
        self._draw()


class FlatTextButton(tk.Label):
    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        bg: str = CARD,
        fg: str = ACCENT,
        font: tuple | None = None,
        disabled_fg: str = FAINT,
    ) -> None:
        super().__init__(
            parent,
            text=text,
            bg=bg,
            fg=disabled_fg,
            font=font or (FONT_FAMILY, 9, "bold"),
            cursor="arrow",
            bd=0,
            padx=2,
            pady=1,
        )
        self._command = command
        self._fg = fg
        self._pressed_fg = ACCENT_DARK
        self._disabled_fg = disabled_fg
        self._enabled = False
        self._palette = LIGHT
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)

    def _on_enter(self, _event=None) -> None:
        if self._enabled:
            self.configure(fg=self._pressed_fg)

    def _on_leave(self, _event=None) -> None:
        self.configure(fg=self._fg if self._enabled else self._disabled_fg)

    def _on_click(self, _event=None) -> None:
        if self._enabled and self._command:
            self._command()

    def set_state(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.configure(
            fg=self._fg if enabled else self._disabled_fg,
            cursor="hand2" if enabled else "arrow",
        )

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._fg = palette.LINK
        self._pressed_fg = palette.ACCENT_DARK
        self._disabled_fg = palette.FAINT
        self.configure(fg=self._fg if self._enabled else self._disabled_fg)


class SegmentedControl(tk.Canvas):
    """多段式选择器，用于格式和外观主题。"""

    def __init__(
        self,
        parent: tk.Misc,
        options: list[tuple[str, str]],
        value: str,
        command=None,
        *,
        bg: str = CARD,
        height: int = 40,
        width: int | None = None,
        font_size: int = 9,
        palette: Palette = LIGHT,
    ) -> None:
        kwargs = {
            "height": height,
            "bg": bg,
            "bd": 0,
            "highlightthickness": 0,
            "cursor": "hand2",
        }
        if width is not None:
            kwargs["width"] = width
        super().__init__(parent, **kwargs)
        self._segments = options
        self._value = value
        self._command = command
        self._enabled = True
        self._hover_index = -1
        self._font_size = font_size
        self._palette = palette
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Button-1>", self._on_click)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _event: self._set_hover(-1))
        self._draw()

    @property
    def value(self) -> str:
        return self._value

    def _segment_width(self) -> float:
        gap = 4
        return (max(10, self.winfo_width()) - gap * (len(self._segments) + 1)) / max(
            1, len(self._segments)
        )

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        width = max(10, self.winfo_width())
        height = max(10, self.winfo_height())
        self.create_polygon(
            *_rounded_points(1, 1, width - 1, height - 1, 10),
            smooth=True,
            fill=p.SOFT,
            outline=p.SOFT,
        )
        gap = 4
        segment_width = self._segment_width()
        for index, (option_value, label) in enumerate(self._segments):
            x1 = gap * 2 + index * (segment_width + gap)
            x2 = x1 + segment_width
            selected = option_value == self._value
            fill = (
                p.ACCENT
                if selected
                else (p.CARD if index == self._hover_index else p.SOFT)
            )
            fg = (
                p.ON_ACCENT
                if selected
                else (p.TEXT if index == self._hover_index else p.MUTED)
            )
            self.create_polygon(
                *_rounded_points(x1, 4, x2, height - 4, 8),
                smooth=True,
                fill=fill,
                outline=fill,
            )
            self.create_text(
                (x1 + x2) / 2,
                height / 2,
                text=label,
                fill=fg,
                font=(FONT_FAMILY, self._font_size, "bold"),
            )

    def _index_from_x(self, x: int) -> int:
        count = len(self._segments)
        gap = 4
        segment_width = self._segment_width()
        index = int((x - gap * 2) // max(1.0, segment_width + gap))
        return min(count - 1, max(0, index))

    def _set_value_from_x(self, x: int) -> None:
        if not self._enabled:
            return
        new_value = self._segments[self._index_from_x(x)][0]
        if new_value != self._value:
            self._value = new_value
            self._draw()
            if self._command:
                self._command(new_value)

    def _on_click(self, event) -> None:
        self._set_value_from_x(event.x)

    def _on_motion(self, event) -> None:
        if not self._enabled:
            return
        self._set_hover(self._index_from_x(event.x))

    def _set_hover(self, index: int) -> None:
        if index != self._hover_index:
            self._hover_index = index
            self._draw()

    def set_value(self, value: str, notify: bool = False) -> None:
        if value in {v for v, _ in self._segments}:
            self._value = value
            self._draw()
            if notify and self._command:
                self._command(value)

    def set_state(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.configure(bg=palette.CARD)
        self._draw()


class QualitySlider(tk.Canvas):
    """轻量画质滑杆，避免系统 Scale 在白色卡片上不够清晰。"""

    def __init__(
        self,
        parent: tk.Misc,
        value: int = 44,
        minimum: int = 40,
        maximum: int = 48,
        command=None,
        *,
        bg: str = CARD,
        height: int = 32,
        palette: Palette = LIGHT,
    ) -> None:
        super().__init__(
            parent, bg=bg, height=height, bd=0, highlightthickness=0, cursor="hand2"
        )
        self._minimum = int(minimum)
        self._maximum = int(maximum)
        self._value = int(value)
        self._command = command
        self._enabled = True
        self._hovered = False
        self._palette = palette
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Button-1>", self._on_pointer)
        self.bind("<B1-Motion>", self._on_pointer)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._draw()

    @property
    def value(self) -> int:
        return self._value

    def _track_bounds(self) -> tuple[float, float, float]:
        width = max(20, self.winfo_width())
        return 11.0, width - 11.0, 14.0

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        left, right, y = self._track_bounds()
        self.create_line(
            left, y, right, y, fill=p.SLIDER_TRACK, width=6, capstyle="round"
        )
        ratio = (self._value - self._minimum) / max(1, self._maximum - self._minimum)
        knob_x = left + (right - left) * ratio
        if knob_x > left + 1:
            self.create_line(
                left,
                y,
                knob_x,
                y,
                fill=p.ACCENT if self._enabled else p.SLIDER_DISABLED,
                width=6,
                capstyle="round",
            )
        for tick in range(self._minimum, self._maximum + 1, 2):
            tick_ratio = (tick - self._minimum) / max(1, self._maximum - self._minimum)
            tick_x = left + (right - left) * tick_ratio
            self.create_line(
                tick_x, y + 8, tick_x, y + 10, fill=p.SLIDER_TICK, width=1
            )
        self.create_oval(
            knob_x - 9, y - 9, knob_x + 9, y + 9, fill=p.SLIDER_HALO, outline=""
        )
        radius = 7 if self._hovered and self._enabled else 6
        self.create_oval(
            knob_x - radius,
            y - radius,
            knob_x + radius,
            y + radius,
            fill=p.SLIDER_KNOB,
            outline=p.ACCENT if self._enabled else p.SLIDER_EDGE,
            width=2,
        )

    def _set_from_x(self, x: float) -> None:
        if not self._enabled:
            return
        left, right, _ = self._track_bounds()
        ratio = min(1.0, max(0.0, (x - left) / max(1.0, right - left)))
        new_value = int(
            round(self._minimum + ratio * (self._maximum - self._minimum))
        )
        if new_value != self._value:
            self._value = new_value
            self._draw()
            if self._command:
                self._command(new_value)

    def _on_pointer(self, event) -> None:
        self._set_from_x(event.x)

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._draw()

    def set_state(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def set_value(self, value: int, notify: bool = False) -> None:
        value = max(self._minimum, min(self._maximum, int(value)))
        if value != self._value:
            self._value = value
            self._draw()
            if notify and self._command:
                self._command(value)

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.configure(bg=palette.CARD)
        self._draw()


class Card(tk.Frame):
    def __init__(self, parent: tk.Misc, **kwargs) -> None:
        kwargs.setdefault("bg", CARD)
        kwargs.setdefault("highlightbackground", BORDER)
        kwargs.setdefault("highlightthickness", 1)
        kwargs.setdefault("bd", 0)
        super().__init__(parent, **kwargs)


class LightPressApp:
    def __init__(self, root: tk.Tk, initial_folder: Path | None = None) -> None:
        self.root = root
        self.font_family = _choose_font(root)
        self.source: Path | None = None
        self.output_path: Path | None = None
        self.default_output: Path | None = None
        self.scan = None
        self.scan_token = 0
        self.running = False
        self.cancelling = False
        self.cancel_event: threading.Event | None = None
        self.report = None
        self.events: queue.Queue = queue.Queue()
        self.results_received = 0
        self.compressed_count = 0
        self.kept_count = 0
        self.error_count = 0
        self.psnr_sum = 0.0
        self.psnr_count = 0
        self.saved_bytes = 0
        self._row_counter = 0
        self._detail_by_iid: dict[str, str] = {}
        self._progress_started = False
        self._closing = False
        self.theme_mode = load_theme_mode(SETTINGS_FILE)
        self._system_dark = system_is_dark()
        self.is_dark = self.theme_mode == "dark" or (
            self.theme_mode == "system" and self._system_dark
        )
        self.palette = LIGHT
        self._logo_images: dict[str, tk.PhotoImage] = {}

        self.root.withdraw()
        self._configure_window()
        self._load_logo_images()
        self._configure_styles(self.palette)
        self._build_ui()
        self._setup_dnd()
        self._bind_shortcuts()
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self.root.after(80, self._poll_events)
        self._apply_theme(self.is_dark, initial=True)
        self.root.update_idletasks()
        self.root.deiconify()
        self.root.after(120, lambda: apply_titlebar_theme(self.root, self.is_dark))
        self.root.after(1500, self._watch_system_theme)
        if initial_folder:
            self.root.after(200, lambda: self.select_folder(initial_folder))

    # ------------------------------------------------------------------ 窗口
    def _configure_window(self) -> None:
        self.root.title(f"{APP_NAME} · 视觉无损批量压缩")
        self.root.configure(bg=BG)
        self.root.minsize(1020, 650)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1200, max(1020, screen_w - 140))
        height = min(800, max(640, screen_h - 110))
        x = max(20, (screen_w - width) // 2)
        y = max(20, (screen_h - height) // 2 - 10)
        self.root.geometry(f"{width}x{height}+{x}+{y}")
        if ICON_PNG.exists():
            try:
                self._icon_photo = tk.PhotoImage(file=str(ICON_PNG))
                self.root.iconphoto(True, self._icon_photo)
            except tk.TclError:
                pass
        if ICON_ICO.exists():
            try:
                self.root.iconbitmap(str(ICON_ICO))
            except tk.TclError:
                pass

    def _load_logo_images(self) -> None:
        for key, path in (("light", LOGO_LIGHT), ("dark", LOGO_DARK)):
            if not path.exists():
                continue
            try:
                image = tk.PhotoImage(file=str(path))
                # 384px 原图 → 48px 显示，缩放后有足够的抗锯齿细节
                image = image.subsample(8, 8)
                self._logo_images[key] = image
            except tk.TclError:
                pass

    def _configure_styles(self, palette: Palette | None = None) -> None:
        p = palette or self.palette
        style = ttk.Style(self.root)
        try:
            style.theme_use("clam")
        except tk.TclError:
            pass
        family = self.font_family
        style.configure(
            "Log.Treeview",
            background=p.CARD,
            fieldbackground=p.CARD,
            foreground=p.TEXT,
            borderwidth=0,
            relief="flat",
            rowheight=31,
            font=(family, 9),
        )
        style.configure(
            "Log.Treeview.Heading",
            background=p.TABLE_HEAD,
            foreground=p.MUTED,
            borderwidth=0,
            relief="flat",
            font=(family, 8, "bold"),
            padding=(8, 8),
        )
        style.map(
            "Log.Treeview",
            background=[("selected", p.ACCENT_SOFT)],
            foreground=[("selected", p.TEXT)],
        )
        style.map(
            "Log.Treeview.Heading",
            background=[("active", p.SOFT)],
        )
        style.configure(
            "Accent.Horizontal.TProgressbar",
            troughcolor=p.PROGRESS_TROUGH,
            background=p.ACCENT,
            bordercolor=p.PROGRESS_TROUGH,
            lightcolor=p.ACCENT,
            darkcolor=p.ACCENT,
            thickness=7,
        )
        style.configure(
            "Thin.Vertical.TScrollbar",
            background=p.SCROLLBAR,
            troughcolor=p.CARD,
            bordercolor=p.CARD,
            arrowcolor=p.MUTED,
            width=9,
        )
        style.configure(
            "TCombobox",
            fieldbackground=p.INPUT_BG,
            background=p.CARD,
            foreground=p.TEXT,
            bordercolor=p.BORDER,
            lightcolor=p.BORDER,
            darkcolor=p.BORDER,
            arrowcolor=p.MUTED,
            arrowsize=12,
            padding=5,
            font=(family, 9),
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", p.INPUT_BG)],
            foreground=[("readonly", p.TEXT)],
            selectbackground=[("readonly", p.INPUT_BG)],
            selectforeground=[("readonly", p.TEXT)],
        )

    # -------------------------------------------------------------- 主题切换
    def _on_theme_mode_change(self, mode: str) -> None:
        if mode not in THEME_MODES:
            return
        self.theme_mode = mode
        self._system_dark = system_is_dark()
        dark = mode == "dark" or (mode == "system" and self._system_dark)
        save_theme_mode(SETTINGS_FILE, mode)
        if hasattr(self, "theme_control"):
            self.theme_control.set_value(mode)
        self._apply_theme(dark)

    def _watch_system_theme(self) -> None:
        if self._closing:
            return
        try:
            dark = system_is_dark()
        except Exception:
            dark = self._system_dark
        changed = dark != self._system_dark
        self._system_dark = dark
        if changed and self.theme_mode == "system" and dark != self.is_dark:
            self._apply_theme(dark)
        self.root.after(2000, self._watch_system_theme)

    def _apply_theme(self, dark: bool, initial: bool = False) -> None:
        self.is_dark = bool(dark)
        target = DARK if dark else LIGHT
        old = LIGHT if initial else self.palette
        self.palette = target
        # 运行时的状态颜色会继续读取这些常量，必须一并同步。
        for field in target.__dataclass_fields__:
            if field != "mode":
                globals()[field] = getattr(target, field)
        self._recolor_widget_tree(self.root, old, target)
        self.root.configure(bg=target.BG)
        # 下拉框的弹出列表由 Tk 单独创建，需要单独同步配色
        self.root.option_add("*TCombobox*Listbox.background", target.INPUT_BG)
        self.root.option_add("*TCombobox*Listbox.foreground", target.TEXT)
        self.root.option_add("*TCombobox*Listbox.selectBackground", target.ACCENT_SOFT)
        self.root.option_add("*TCombobox*Listbox.selectForeground", target.TEXT)
        self._configure_styles(target)
        self._update_tree_tags(target)
        self._update_logo()
        # 自定义 Canvas 需要在统一映射之后，按新配色重画
        self.primary.apply_palette(target)
        self.format_control.apply_palette(target)
        self.theme_control.apply_palette(target)
        self.quality_slider.apply_palette(target)
        for widget in self._flat_text_buttons():
            widget.apply_palette(target)
        self._sync_quality_ui(self.quality_slider.value)
        self._draw_drop_zone()
        self.root.after(30, lambda: apply_titlebar_theme(self.root, self.is_dark))

    def _flat_text_buttons(self) -> list[FlatTextButton]:
        return [
            self.output_change_btn,
            self.output_reset_btn,
            self.open_btn,
            self.report_btn,
        ]

    def _update_logo(self) -> None:
        image = self._logo_images.get("dark" if self.is_dark else "light")
        if image is not None:
            self.logo_label.configure(image=image)
            self.logo_label.image = image

    def _update_tree_tags(self, palette: Palette) -> None:
        if not hasattr(self, "tree"):
            return
        for parity, background in (
            ("even", palette.CARD),
            ("odd", palette.TABLE_ALT),
        ):
            for state, foreground in (
                ("ok", palette.TAG_OK),
                ("kept", palette.TAG_KEPT),
                ("error", palette.TAG_ERROR),
                ("normal", palette.TEXT),
            ):
                self.tree.tag_configure(
                    f"{parity}_{state}", background=background, foreground=foreground
                )

    def _normalize_color(self, value: str) -> str | None:
        if not value:
            return None
        try:
            red, green, blue = self.root.winfo_rgb(str(value))
            return f"#{red // 256:02x}{green // 256:02x}{blue // 256:02x}"
        except tk.TclError:
            return str(value).lower()

    def _mapped_color(self, value: str, mapping: dict[str, str]) -> str | None:
        normalized = self._normalize_color(value)
        return mapping.get(normalized) if normalized else None

    def _recolor_widget_tree(
        self, widget: tk.Misc, old: Palette, target: Palette
    ) -> None:
        """把已经构建好的浅色控件，按语义映射到当前主题。"""
        bg_map: dict[str, str] = {}
        fg_map: dict[str, str] = {}
        for key, old_value in old.backgrounds_for_mapping().items():
            # CARD 等主背景先注册，不能让同色的滑块圆点等辅助色覆盖。
            bg_map.setdefault(str(old_value).lower(), getattr(target, key))
        for key, old_value in old.foregrounds_for_mapping().items():
            fg_map.setdefault(str(old_value).lower(), getattr(target, key))
        # 常见辅助色（个别 Tk 控件会返回小写颜色）
        for old_value, new_value in (
            ("#ffffff", target.CARD),
            ("#fbfdfc", target.CARD_ALT),
            ("#f8fbf9", target.CARD_SOFT),
            ("#edf3ef", target.DIVIDER),
            ("#eef5f0", target.SOFT),
            ("#f5f9f6", target.TABLE_HEAD),
            ("#f7faf8", target.INPUT_BG),
            ("#e9f0ec", target.PROGRESS_TROUGH),
            ("#cfddd6", target.SCROLLBAR),
            ("#dfe8e3", target.DISABLED_FILL),
            ("#93a69c", target.DISABLED_FG),
        ):
            bg_map.setdefault(old_value, new_value)

        bg_options = (
            "background",
            "bg",
            "activebackground",
            "highlightbackground",
            "highlightcolor",
            "troughcolor",
            "selectbackground",
            "readonlybackground",
        )
        fg_options = (
            "foreground",
            "fg",
            "activeforeground",
            "disabledforeground",
            "selectforeground",
            "insertbackground",
        )

        def recolor(current: tk.Misc) -> None:
            if not isinstance(current, ttk.Widget):
                for option in bg_options:
                    try:
                        value = str(current.cget(option))
                    except (tk.TclError, AttributeError):
                        continue
                    replacement = self._mapped_color(value, bg_map)
                    if replacement and replacement != value:
                        try:
                            current.configure(**{option: replacement})
                        except tk.TclError:
                            pass
                for option in fg_options:
                    try:
                        value = str(current.cget(option))
                    except (tk.TclError, AttributeError):
                        continue
                    replacement = self._mapped_color(value, fg_map)
                    if replacement and replacement != value:
                        try:
                            current.configure(**{option: replacement})
                        except tk.TclError:
                            pass
            if isinstance(current, tk.Canvas):
                for item in current.find_all():
                    kind = current.type(item)
                    for option in ("fill", "outline"):
                        try:
                            value = current.itemcget(item, option)
                        except tk.TclError:
                            continue
                        if not value or str(value).lower() == "#ffffff":
                            continue
                        mapping = fg_map if kind == "text" else {**bg_map, **fg_map}
                        replacement = self._mapped_color(value, mapping)
                        if replacement and replacement != value:
                            try:
                                current.itemconfigure(item, **{option: replacement})
                            except tk.TclError:
                                pass
            for child in current.winfo_children():
                recolor(child)

        recolor(widget)

    # ------------------------------------------------------------------- UI
    def _label(
        self,
        parent,
        text,
        *,
        size=9,
        bold=False,
        fg=TEXT,
        bg=None,
        **kwargs,
    ):
        return tk.Label(
            parent,
            text=text,
            bg=bg or parent.cget("bg"),
            fg=fg,
            font=(self.font_family, size, "bold" if bold else "normal"),
            **kwargs,
        )

    def _build_ui(self) -> None:
        self._build_header()
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill=BOTH, expand=True, padx=24, pady=(17, 15))
        body.grid_columnconfigure(0, minsize=420, weight=0)
        body.grid_columnconfigure(1, minsize=500, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.left = tk.Frame(body, bg=BG, width=420)
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 14))
        self.left.pack_propagate(False)

        self.right = tk.Frame(body, bg=BG)
        self.right.grid(row=0, column=1, sticky="nsew")

        self._build_drop_zone()
        self._build_selected_card()
        self._build_settings_card()
        self._build_primary()
        self._build_side_note()

        self._build_overview()
        self._build_log_card()

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=CARD, height=72)
        header.pack(fill=X)
        header.pack_propagate(False)
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=X)

        inner = tk.Frame(header, bg=CARD)
        inner.pack(fill=BOTH, expand=True, padx=26)
        self.logo_label = tk.Label(
            inner,
            bg=CARD,
            bd=0,
            image=self._logo_images.get("light"),
        )
        self.logo_label.pack(side=LEFT, pady=(12, 0))

        brand = tk.Frame(inner, bg=CARD)
        brand.pack(side=LEFT, padx=(12, 0), pady=(13, 0))
        self._label(brand, APP_NAME, size=15, bold=True).pack(anchor="w")
        self._label(
            brand,
            "批量视觉无损压缩 · 为网页提速",
            size=8,
            fg=MUTED,
        ).pack(anchor="w", pady=(1, 0))

        right = tk.Frame(inner, bg=CARD)
        right.pack(side=RIGHT)
        self._label(right, f"v{APP_VERSION}", size=8, fg=FAINT).pack(
            side=RIGHT, padx=(10, 0)
        )
        badge = tk.Label(
            right,
            text="  本地处理 · 不上传  ",
            bg=ACCENT_SOFT,
            fg=ACCENT_DARK,
            font=(self.font_family, 8, "bold"),
            padx=7,
            pady=6,
        )
        badge.pack(side=RIGHT, padx=(0, 10))
        appearance = tk.Frame(right, bg=CARD)
        appearance.pack(side=RIGHT, padx=(0, 14))
        self._label(appearance, "外观", size=7, fg=FAINT).pack(
            side=LEFT, padx=(0, 6)
        )
        self.theme_control = SegmentedControl(
            appearance,
            [(mode, label) for mode, label in THEME_MODES.items()],
            self.theme_mode,
            command=self._on_theme_mode_change,
            bg=CARD,
            height=30,
            width=214,
            font_size=8,
            palette=self.palette,
        )
        self.theme_control.pack(side=LEFT, pady=(0, 1))

    def _build_drop_zone(self) -> None:
        self.drop_zone = tk.Canvas(
            self.left,
            height=136,
            bg=BG,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self.drop_zone.pack(fill=X)
        self.drop_zone.bind("<Configure>", lambda _event: self._draw_drop_zone())
        self.drop_zone.bind("<Button-1>", lambda _event: self.choose_folder())
        self.drop_zone.bind("<Enter>", lambda _event: self._set_drop_hover(True))
        self.drop_zone.bind("<Leave>", lambda _event: self._set_drop_hover(False))
        self._drop_hover = False
        self._draw_drop_zone()

    def _draw_drop_zone(self) -> None:
        canvas = self.drop_zone
        canvas.delete("all")
        width = max(50, canvas.winfo_width())
        height = max(50, canvas.winfo_height())
        p = self.palette
        fill = p.DROP_BG if not self._drop_hover else p.DROP_BG_HOVER
        outline = p.ACCENT if self._drop_hover else p.DROP_BORDER
        points = _rounded_points(1, 1, width - 1, height - 1, 16)
        canvas.create_polygon(
            *points, smooth=True, splinesteps=36, fill=fill, outline=outline, width=1
        )
        canvas.create_line(
            *(points + [points[0], points[1]]),
            smooth=True,
            splinesteps=36,
            fill=p.DROP_DASH,
            width=1,
            dash=(5, 5),
        )

        # 文件夹图标
        cx = width / 2
        cy = 36
        canvas.create_polygon(
            *_rounded_points(cx - 22, cy - 13, cx - 2, cy - 5, 4),
            smooth=True,
            fill=p.FOLDER_BACK,
            outline=p.FOLDER_BACK,
        )
        canvas.create_polygon(
            *_rounded_points(cx - 24, cy - 8, cx + 24, cy + 23, 6),
            smooth=True,
            fill=p.FOLDER_FRONT,
            outline=p.FOLDER_BORDER,
            width=1,
        )
        canvas.create_line(
            cx, cy + 2, cx, cy + 13, fill=p.ACCENT, width=2, capstyle="round"
        )
        canvas.create_line(
            cx - 5, cy + 8, cx, cy + 13, cx + 5, cy + 8, fill=p.ACCENT, width=2,
            capstyle="round", joinstyle="round"
        )

        canvas.create_text(
            cx,
            78,
            text="把文件夹拖到这里" if DND_AVAILABLE else "点击选择文件夹",
            fill=p.TEXT,
            font=(self.font_family, 12, "bold"),
        )
        sub = "或点击选择文件夹，整批图片一次压完" if DND_AVAILABLE else "拖拽组件未加载，点击选择文件夹"
        canvas.create_text(
            cx,
            100,
            text=sub,
            fill=p.MUTED,
            font=(self.font_family, 8),
        )
        canvas.create_text(
            cx,
            119,
            text="JPG · PNG · WebP · AVIF · TIFF · BMP · GIF",
            fill=p.FAINT,
            font=(self.font_family, 7),
        )

    def _set_drop_hover(self, hovered: bool) -> None:
        if self._drop_hover == hovered:
            return
        self._drop_hover = hovered
        self._draw_drop_zone()

    def _build_selected_card(self) -> None:
        self.selected_card = Card(self.left)
        self.selected_card.pack(fill=X, pady=(10, 0))
        inner = tk.Frame(self.selected_card, bg=CARD)
        inner.pack(fill=X, padx=14, pady=9)

        badge = tk.Canvas(inner, width=34, height=34, bg=CARD, bd=0, highlightthickness=0)
        badge.pack(side=LEFT, padx=(0, 10))
        badge.create_oval(1, 1, 33, 33, fill=SOFT, outline=SOFT)
        badge.create_text(17, 17, text="▣", fill=ACCENT, font=(self.font_family, 12, "bold"))

        text_box = tk.Frame(inner, bg=CARD)
        text_box.pack(side=LEFT, fill=X, expand=True)
        self.folder_name_label = self._label(
            text_box, "尚未选择文件夹", size=10, bold=True
        )
        self.folder_name_label.pack(anchor="w")
        self.folder_path_label = self._label(
            text_box,
            "拖入文件夹后会自动统计图片数量",
            size=8,
            fg=MUTED,
            anchor="w",
            justify="left",
        )
        self.folder_path_label.pack(anchor="w", pady=(2, 0))

        self.scan_badge = tk.Label(
            inner,
            text="待选择",
            bg=SOFT,
            fg=MUTED,
            font=(self.font_family, 8, "bold"),
            padx=8,
            pady=5,
        )
        self.scan_badge.pack(side=RIGHT, before=text_box, anchor="n", padx=(8, 0))

        output_row = tk.Frame(self.selected_card, bg="#fbfdfc")
        output_row.pack(fill=X, side="bottom")
        tk.Frame(output_row, bg=BORDER, height=1).pack(fill=X)
        output_inner = tk.Frame(output_row, bg="#fbfdfc")
        output_inner.pack(fill=X, padx=14, pady=6)
        self._label(output_inner, "输出", size=7, fg=FAINT, bold=True, bg="#fbfdfc").pack(side=LEFT)
        self.output_change_btn = FlatTextButton(
            output_inner,
            "更改",
            self._change_output,
            bg="#fbfdfc",
            font=(self.font_family, 7, "bold"),
        )
        self.output_change_btn.pack(side=RIGHT)
        self.output_reset_btn = FlatTextButton(
            output_inner,
            "恢复默认",
            self._reset_output,
            bg="#fbfdfc",
            font=(self.font_family, 7, "bold"),
        )
        self.output_reset_btn.pack(side=RIGHT, padx=(4, 0))
        self.output_label = self._label(
            output_inner,
            "选择文件夹后自动创建 _web 文件夹",
            size=8,
            fg=MUTED,
            bg="#fbfdfc",
            anchor="w",
        )
        self.output_label.pack(side=LEFT, padx=(7, 8), fill=X, expand=True)

    def _build_settings_card(self) -> None:
        card = Card(self.left)
        card.pack(fill=X, pady=(10, 0))
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill=X, padx=16, pady=10)

        top = tk.Frame(inner, bg=CARD)
        top.pack(fill=X)
        self._label(top, "压缩设置", size=10, bold=True).pack(side=LEFT)
        self._label(top, "自动寻找达标的最低质量", size=7, fg=FAINT).pack(side=RIGHT)

        quality_head = tk.Frame(inner, bg=CARD)
        quality_head.pack(fill=X, pady=(8, 0))
        self._label(quality_head, "画质目标", size=8, fg=MUTED).pack(side=LEFT)
        self.quality_value_label = tk.Label(
            quality_head,
            text="44 dB",
            bg=ACCENT_SOFT,
            fg=ACCENT_DARK,
            font=(self.font_family, 9, "bold"),
            padx=8,
            pady=2,
        )
        self.quality_value_label.pack(side=RIGHT)

        self.quality_slider = QualitySlider(
            inner,
            value=44,
            minimum=int(MIN_TARGET_PSNR),
            maximum=int(MAX_TARGET_PSNR),
            command=self._on_quality_change,
            bg=CARD,
            height=28,
        )
        self.quality_slider.pack(fill=X, pady=(1, 0))

        preset_row = tk.Frame(inner, bg=CARD)
        preset_row.pack(fill=X, pady=(0, 1))
        self._label(preset_row, "快捷", size=7, fg=FAINT).pack(
            side=LEFT, padx=(0, 5)
        )
        self.preset_chips: dict[int, tk.Label] = {}
        for preset in (30, 36, 40, 44, 48):
            chip = tk.Label(
                preset_row,
                text=str(preset),
                bg=SOFT,
                fg=MUTED,
                font=(self.font_family, 8, "bold"),
                padx=7,
                pady=2,
                cursor="hand2",
            )
            chip.pack(side=LEFT, padx=(0, 4))
            chip.bind(
                "<Button-1>",
                lambda _event, value=preset: self._set_quality(value),
            )
            self.preset_chips[preset] = chip

        self.quality_hint = self._label(
            inner,
            "推荐 · 视觉上接近原图，网页加载明显更快",
            size=7,
            fg=MUTED,
        )
        self.quality_hint.pack(anchor="w", pady=(0, 4))

        tk.Frame(inner, bg="#edf3ef", height=1).pack(fill=X, pady=(1, 6))

        format_head = tk.Frame(inner, bg=CARD)
        format_head.pack(fill=X)
        self._label(format_head, "输出格式", size=8, fg=MUTED).pack(side=LEFT)
        self.format_hint = self._label(
            format_head,
            "同画质体积最小 · 现代浏览器首选",
            size=7,
            fg=FAINT,
        )
        self.format_hint.pack(side=RIGHT)
        self.format_control = SegmentedControl(
            inner,
            [("avif", "AVIF · 更小体积"), ("webp", "WebP · 兼容优先")],
            "avif",
            command=self._on_format_change,
            bg=CARD,
            height=36,
        )
        self.format_control.pack(fill=X, pady=(6, 0))

        size_row = tk.Frame(inner, bg=CARD)
        size_row.pack(fill=X, pady=(8, 0))
        size_text = tk.Frame(size_row, bg=CARD)
        size_text.pack(side=LEFT)
        self._label(size_text, "最大边长", size=8, fg=MUTED).pack(anchor="w")
        self._label(
            size_text, "默认保持原始分辨率", size=7, fg=FAINT
        ).pack(anchor="w", pady=(1, 0))
        self.size_var = tk.StringVar(value="保持原尺寸")
        self.size_combo = ttk.Combobox(
            size_row,
            textvariable=self.size_var,
            values=list(MAX_DIMENSIONS.keys()),
            state="readonly",
            width=12,
        )
        self.size_combo.pack(side=RIGHT, pady=(2, 0))
        self._sync_quality_ui(44)
        self._refresh_output_links()

    def _build_primary(self) -> None:
        self.primary = RoundedButton(
            self.left,
            "开始压缩",
            self._on_primary,
            height=50,
            bg=BG,
            font=(self.font_family, 11, "bold"),
        )
        self.primary.pack(fill=X, pady=(10, 0))
        self.primary.set_state(False)

        note = self._label(
            self.left,
            "本地处理 · 不覆盖原图 · 自动生成压缩报告",
            size=7,
            fg=FAINT,
        )
        note.pack(anchor="center", pady=(5, 0))

    def _build_side_note(self) -> None:
        self.side_note = self._label(
            self.left,
            "",
            size=7,
            fg=FAINT,
        )

    def _build_overview(self) -> None:
        card = Card(self.right)
        card.pack(fill=X)
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill=X, padx=18, pady=14)

        top = tk.Frame(inner, bg=CARD)
        top.pack(fill=X)
        self._label(top, "批次概览", size=11, bold=True).pack(side=LEFT)
        self.overview_badge = tk.Label(
            top,
            text="等待开始",
            bg=SOFT,
            fg=MUTED,
            font=(self.font_family, 7, "bold"),
            padx=8,
            pady=4,
        )
        self.overview_badge.pack(side=RIGHT)

        stats = tk.Frame(inner, bg=CARD)
        stats.pack(fill=X, pady=(12, 0))
        self.stat_labels: dict[str, tk.Label] = {}
        self.stat_captions: dict[str, tk.Label] = {}
        specs = [
            ("images", "图片总数", "—"),
            ("compressed", "压缩成功", "0"),
            ("psnr", "平均画质", "—"),
            ("saved", "已节省", "—"),
        ]
        for index, (key, caption, initial) in enumerate(specs):
            cell = tk.Frame(stats, bg="#f8fbf9")
            cell.grid(row=0, column=index, sticky="nsew", padx=(0 if index == 0 else 6, 0))
            stats.grid_columnconfigure(index, weight=1)
            value = tk.Label(
                cell,
                text=initial,
                bg="#f8fbf9",
                fg=TEXT,
                font=(self.font_family, 14, "bold"),
                anchor="w",
            )
            value.pack(fill=X, padx=11, pady=(9, 0))
            caption_label = self._label(
                cell, caption, size=7, fg=MUTED, bg="#f8fbf9", anchor="w"
            )
            caption_label.pack(fill=X, padx=11, pady=(0, 9))
            self.stat_labels[key] = value
            self.stat_captions[key] = caption_label

        progress_head = tk.Frame(inner, bg=CARD)
        progress_head.pack(fill=X, pady=(13, 6))
        self.status_label = self._label(
            progress_head, "准备就绪", size=8, bold=True
        )
        self.status_label.pack(side=LEFT)
        self.progress_percent = self._label(
            progress_head, "0%", size=8, fg=MUTED
        )
        self.progress_percent.pack(side=RIGHT)
        self.progress = ttk.Progressbar(
            inner,
            style="Accent.Horizontal.TProgressbar",
            mode="determinate",
            maximum=100,
            value=0,
        )
        self.progress.pack(fill=X)
        self.status_detail = self._label(
            inner,
            "选择一个文件夹，开始为网站减负。",
            size=7,
            fg=FAINT,
        )
        self.status_detail.pack(anchor="w", pady=(5, 0))

    def _build_log_card(self) -> None:
        card = Card(self.right)
        card.pack(fill=BOTH, expand=True, pady=(12, 0))
        inner = tk.Frame(card, bg=CARD)
        inner.pack(fill=BOTH, expand=True, padx=0, pady=0)

        head = tk.Frame(inner, bg=CARD)
        head.pack(fill=X, padx=16, pady=(12, 9))
        title_box = tk.Frame(head, bg=CARD)
        title_box.pack(side=LEFT)
        self._label(title_box, "处理明细", size=10, bold=True).pack(side=LEFT)
        self.log_count = self._label(title_box, "0 张", size=8, fg=FAINT)
        self.log_count.pack(side=LEFT, padx=(8, 0), pady=(2, 0))

        self.report_btn = FlatTextButton(
            head, "报告", self._open_report, bg=CARD, font=(self.font_family, 8, "bold")
        )
        self.report_btn.pack(side=RIGHT)
        self.open_btn = FlatTextButton(
            head, "打开输出文件夹", self._open_output, bg=CARD, font=(self.font_family, 8, "bold")
        )
        self.open_btn.pack(side=RIGHT, padx=(0, 12))

        table_wrap = tk.Frame(inner, bg=CARD)
        table_wrap.pack(fill=BOTH, expand=True)
        columns = ("file", "status", "size", "psnr", "saved")
        self.tree = ttk.Treeview(
            table_wrap,
            columns=columns,
            show="headings",
            style="Log.Treeview",
            selectmode="browse",
        )
        headings = {
            "file": "文件",
            "status": "状态",
            "size": "体积",
            "psnr": "PSNR",
            "saved": "节省",
        }
        widths = {"file": 215, "status": 80, "size": 181, "psnr": 70, "saved": 56}
        for column in columns:
            self.tree.heading(column, text=headings[column], anchor="w")
            self.tree.column(
                column,
                width=widths[column],
                minwidth=55,
                anchor="w" if column in {"file", "size"} else "center",
                stretch=column == "file",
            )
        scrollbar = ttk.Scrollbar(
            table_wrap,
            orient="vertical",
            command=self.tree.yview,
            style="Thin.Vertical.TScrollbar",
        )
        self.tree.configure(yscrollcommand=scrollbar.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        scrollbar.pack(side=RIGHT, fill=Y, padx=(0, 7))
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

        for tag, background in (("even", "#ffffff"), ("odd", "#fbfdfc")):
            for state, foreground in (
                ("ok", "#1b5b4b"),
                ("kept", AMBER),
                ("error", RED),
                ("normal", TEXT),
            ):
                self.tree.tag_configure(
                    f"{tag}_{state}", background=background, foreground=foreground
                )

        detail_wrap = tk.Frame(inner, bg="#fbfdfc")
        detail_wrap.pack(fill=X, side="bottom")
        tk.Frame(detail_wrap, bg="#edf3ef", height=1).pack(fill=X)
        detail_inner = tk.Frame(detail_wrap, bg="#fbfdfc")
        detail_inner.pack(fill=X, padx=16, pady=7)
        self.detail_label = self._label(
            detail_inner,
            "选择一条记录查看处理说明。",
            size=7,
            fg=MUTED,
            bg="#fbfdfc",
            anchor="w",
        )
        self.detail_label.pack(fill=X)

    # --------------------------------------------------------------- 拖拽/选择
    def _setup_dnd(self) -> None:
        if not DND_AVAILABLE:
            return
        try:
            self.drop_zone.drop_target_register(DND_FILES)
            self.drop_zone.dnd_bind("<<Drop>>", self._on_drop)
            self.drop_zone.dnd_bind("<<DropEnter>>", lambda _event: self._set_drop_hover(True))
            self.drop_zone.dnd_bind("<<DropLeave>>", lambda _event: self._set_drop_hover(False))
        except Exception:
            self._set_drop_hover(False)

    def _on_drop(self, event) -> None:
        self._set_drop_hover(False)
        if self.running:
            return
        try:
            paths = self.root.tk.splitlist(event.data)
        except Exception:
            paths = []
        folders = [Path(path) for path in paths if Path(path).is_dir()]
        if not folders:
            messagebox.showinfo(
                APP_NAME,
                "请拖入一个文件夹，而不是单个图片文件。\n\n"
                "工具会递归处理文件夹中的所有图片，并保留子目录结构。",
                parent=self.root,
            )
            return
        if len(folders) > 1:
            messagebox.showinfo(
                APP_NAME,
                "一次处理一个文件夹。\n\n已选择拖入列表中的第一个文件夹。",
                parent=self.root,
            )
        self.select_folder(folders[0])

    def choose_folder(self) -> None:
        if self.running:
            return
        selected = filedialog.askdirectory(
            title="选择要压缩的图片文件夹",
            parent=self.root,
            mustexist=True,
        )
        if selected:
            self.select_folder(Path(selected))

    def select_folder(self, folder: Path) -> None:
        if self.running:
            return
        try:
            folder = folder.expanduser().resolve()
        except OSError:
            messagebox.showerror(APP_NAME, "无法访问这个文件夹。", parent=self.root)
            return
        if not folder.is_dir():
            messagebox.showerror(APP_NAME, "请选择一个有效的文件夹。", parent=self.root)
            return

        self.source = folder
        self.default_output = default_output_dir(folder)
        self.output_path = self.default_output
        self.scan = None
        self.scan_token += 1
        token = self.scan_token
        self.report = None

        self.folder_name_label.configure(text=folder.name or str(folder))
        self.folder_path_label.configure(text=_compact_path(folder))
        self.scan_badge.configure(text="扫描中…", bg=AMBER_SOFT, fg=AMBER)
        self._refresh_output_label()
        self._refresh_output_links()
        self._clear_results()

        self.overview_badge.configure(text="正在扫描", bg=AMBER_SOFT, fg=AMBER)
        self.status_label.configure(text="正在扫描图片…")
        self.status_detail.configure(text="统计图片数量和体积")
        self.progress.configure(mode="indeterminate")
        self.progress.start(12)
        self.progress_percent.configure(text="")
        self.primary.set_state(False)
        self.primary.set_text("开始压缩")
        self._set_controls_enabled(True)

        def worker() -> None:
            try:
                summary = scan_folder(folder)
            except Exception as exc:
                self.events.put(("scan_error", token, str(exc)))
            else:
                self.events.put(("scan_ok", token, summary))

        threading.Thread(target=worker, daemon=True, name="scan-images").start()

    def _on_scan_ok(self, token: int, summary) -> None:
        if token != self.scan_token:
            return
        self.scan = summary
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=100, value=0)
        self.progress_percent.configure(text="0%")
        self.scan_badge.configure(
            text=f"{summary.count} 张",
            bg=ACCENT_SOFT if summary.count else SOFT,
            fg=ACCENT_DARK if summary.count else MUTED,
        )
        self.stat_labels["images"].configure(text=str(summary.count))
        if summary.count:
            self.status_label.configure(text="准备就绪")
            self.status_detail.configure(
                text=f"共 {summary.count} 张图片，约 {format_bytes(summary.total_bytes)}，可以开始压缩。"
            )
            self.overview_badge.configure(text="待压缩", bg=SOFT, fg=MUTED)
            self.primary.set_state(True)
            self.primary.set_text("开始压缩")
            self.primary.set_mode("normal")
        else:
            self.status_label.configure(text="没有找到可压缩的图片")
            self.status_detail.configure(
                text="支持 JPG、PNG、WebP、AVIF、TIFF、BMP 和 GIF。"
            )
            self.overview_badge.configure(text="暂无图片", bg=SOFT, fg=MUTED)
            self.primary.set_state(False)
            self.primary.set_text("没有可压缩的图片")

    def _on_scan_error(self, token: int, message: str) -> None:
        if token != self.scan_token:
            return
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self.scan_badge.configure(text="无法读取", bg=RED_SOFT, fg=RED)
        self.status_label.configure(text="无法读取文件夹")
        self.status_detail.configure(text=message)
        self.overview_badge.configure(text="扫描失败", bg=RED_SOFT, fg=RED)
        self.primary.set_state(False)

    # ---------------------------------------------------------------- 配置变化
    def _on_quality_change(self, value) -> None:
        self._sync_quality_ui(int(round(float(value))))

    def _set_quality(self, value: int) -> None:
        self.quality_slider.set_value(int(value), notify=True)

    def _sync_quality_ui(self, target: int) -> None:
        target = max(int(MIN_TARGET_PSNR), min(int(MAX_TARGET_PSNR), int(target)))
        self.quality_value_label.configure(text=f"{target} dB")
        if target <= 31:
            hint = "极限压缩 · 细节明显减少，仅建议缩略图 / 背景图"
        elif target <= 35:
            hint = "高压缩 · 页面小图可用，不建议用于重点展示图"
        elif target <= 39:
            hint = "体积优先 · 适合非重点配图，注意文字边缘"
        elif target <= 41:
            hint = "轻量 · 体积优先，主体依然清晰"
        elif target <= 43:
            hint = "均衡 · 日常网页图片的轻量选择"
        elif target <= 45:
            hint = "推荐 · 视觉上接近原图，网页加载明显更快"
        elif target <= 47:
            hint = "高保真 · 细节更完整，体积也会增加"
        else:
            hint = "极致 · 接近像素级保留，适合重点展示图"
        self.quality_hint.configure(
            text=hint, fg=AMBER if target < 40 else MUTED
        )
        for value, chip in self.preset_chips.items():
            active = value == target
            chip.configure(
                bg=ACCENT_SOFT if active else SOFT,
                fg=ACCENT_DARK if active else MUTED,
            )

    def _on_format_change(self, value: str) -> None:
        if value == "avif":
            self.format_hint.configure(text="同画质体积最小 · 现代浏览器首选")
        else:
            self.format_hint.configure(text="兼容性最好 · 高纹理照片可能达不到目标")

    def _refresh_output_label(self) -> None:
        if not self.output_path:
            self.output_label.configure(text="选择文件夹后自动创建 _web 文件夹")
            return
        if self.source and self.output_path == self.default_output:
            text = f"{self.output_path.name}  ·  自动创建在源文件夹旁"
        else:
            text = _compact_path(self.output_path, keep_parts=2)
        self.output_label.configure(text=text)
        self.output_reset_btn.set_state(
            bool(self.source and self.output_path != self.default_output)
        )
        self.output_change_btn.set_state(bool(self.source) and not self.running)

    def _refresh_output_links(self) -> None:
        enabled = bool(self.source) and not self.running
        self.output_change_btn.set_state(enabled)
        self.output_reset_btn.set_state(
            enabled and self.output_path != self.default_output
        )

    def _change_output(self) -> None:
        if self.running or not self.source:
            return
        initial = self.output_path.parent if self.output_path else self.source.parent
        selected = filedialog.askdirectory(
            title="选择输出文件夹",
            parent=self.root,
            initialdir=str(initial),
            mustexist=False,
        )
        if not selected:
            return
        target = Path(selected).resolve()
        if target == self.source:
            messagebox.showwarning(
                APP_NAME,
                "输出目录不能与源文件夹相同，以免覆盖原图。",
                parent=self.root,
            )
            return
        self.output_path = target
        self._refresh_output_label()
        self._refresh_output_links()

    def _reset_output(self) -> None:
        if self.running or not self.source:
            return
        self.output_path = self.default_output
        self._refresh_output_label()
        self._refresh_output_links()

    # ---------------------------------------------------------------- 压缩流程
    def _on_primary(self) -> None:
        if self.running:
            if not self.cancelling:
                self._cancel_compression()
            return
        self._start_compression()

    def _start_compression(self) -> None:
        if not self.source or not self.scan or self.scan.count == 0:
            return
        output = self.output_path or self.default_output
        if output is None:
            return
        output = output.resolve()
        if output == self.source:
            messagebox.showerror(
                APP_NAME, "输出目录不能与源文件夹相同。", parent=self.root
            )
            return
        if output in self.source.parents:
            messagebox.showerror(
                APP_NAME, "输出目录不能是源文件夹的上级目录。", parent=self.root
            )
            return
        if output.exists() and any(output.iterdir()):
            proceed = messagebox.askyesno(
                APP_NAME,
                f"输出文件夹已存在：\n{output}\n\n"
                "继续会覆盖其中同名的旧输出文件，源文件夹不会被修改。\n是否继续？",
                parent=self.root,
            )
            if not proceed:
                return

        try:
            target_psnr = float(self.quality_slider.value)
            fmt = self.format_control.value
            max_dimension = MAX_DIMENSIONS.get(self.size_var.get(), 0)
            cpu = os.cpu_count() or 4
            workers = max(2, min(4, cpu // 2))
            options = CompressionOptions(
                target_psnr=target_psnr,
                output_format=fmt,
                max_dimension=max_dimension,
                workers=workers,
            )
        except Exception as exc:
            messagebox.showerror(APP_NAME, f"参数有误：{exc}", parent=self.root)
            return

        self._clear_results()
        self.output_path = output
        self._refresh_output_label()
        self.running = True
        self.cancelling = False
        self.cancel_event = threading.Event()
        self.overview_badge.configure(text="压缩中", bg=ACCENT_SOFT, fg=ACCENT_DARK)
        self.status_label.configure(text="正在压缩…")
        self.status_detail.configure(
            text=f"目标 {int(round(target_psnr))} dB · {fmt.upper()} · {options.workers} 个并行任务"
        )
        self.progress.stop()
        self._progress_started = False
        self.progress.configure(mode="indeterminate", maximum=100, value=0)
        self.progress.start(12)
        self.progress_percent.configure(text="处理中")
        self.primary.set_text("取消任务")
        self.primary.set_mode("danger")
        self.primary.set_state(True)
        self._set_controls_enabled(False)

        def progress_callback(done: int, total: int, result) -> None:
            self.events.put(("progress", done, total, result))

        def worker() -> None:
            try:
                report = compress_folder(
                    self.source,
                    output,
                    options,
                    progress=progress_callback,
                    cancel_event=self.cancel_event,
                )
            except Exception as exc:
                self.events.put(("fatal", str(exc), traceback.format_exc()))
            else:
                self.events.put(("done", report))

        threading.Thread(target=worker, daemon=True, name="compress-batch").start()

    def _cancel_compression(self) -> None:
        if not self.running or self.cancelling:
            return
        self.cancelling = True
        if self.cancel_event:
            self.cancel_event.set()
        self.primary.set_state(False)
        self.primary.set_text("正在取消…")
        self.status_label.configure(text="正在取消…")
        self.status_detail.configure(text="等待当前图片安全地结束，不会留下半个文件。")

    def _on_progress(self, done: int, total: int, result) -> None:
        if not self._progress_started:
            self.progress.stop()
            self.progress.configure(mode="determinate", maximum=100, value=0)
            self._progress_started = True
        self.results_received += 1
        if result.status == "compressed":
            self.compressed_count += 1
            self.saved_bytes += result.savings_bytes
            if result.psnr is not None:
                self.psnr_sum += result.psnr
                self.psnr_count += 1
            state = "ok"
            status_text = "已压缩"
        elif result.status == "error":
            self.error_count += 1
            state = "error"
            status_text = "失败"
        else:
            self.kept_count += 1
            state = "kept"
            status_text = result.display_status

        self._insert_row(result, state, status_text)
        percent = int(round(done / total * 100)) if total else 0
        self.progress.configure(mode="determinate", maximum=100, value=percent)
        self.progress_percent.configure(text=f"{percent}%")
        self.status_label.configure(text="正在压缩…")
        detail = f"已处理 {done}/{total} 张 · 保留 {self.kept_count} · 失败 {self.error_count}"
        self.status_detail.configure(text=detail)
        self.stat_labels["images"].configure(text=str(total))
        self.stat_labels["compressed"].configure(text=str(self.compressed_count))
        if self.psnr_count:
            self.stat_labels["psnr"].configure(
                text=f"{self.psnr_sum / self.psnr_count:.1f} dB"
            )
        if self.saved_bytes:
            base = self.scan.total_bytes if self.scan else 0
            ratio = (self.saved_bytes / base * 100) if base else 0
            self.stat_labels["saved"].configure(text=format_bytes(self.saved_bytes))
            self.stat_captions["saved"].configure(text=f"已节省 · {ratio:.0f}%")
        else:
            self.stat_labels["saved"].configure(text="—")
            self.stat_captions["saved"].configure(text="已节省")
        self.log_count.configure(text=f"{done} 张")
        self.overview_badge.configure(text="压缩中", bg=ACCENT_SOFT, fg=ACCENT_DARK)

    def _insert_row(self, result, state: str, status_text: str) -> None:
        try:
            relative = result.source.relative_to(self.source).as_posix()
        except Exception:
            relative = result.source.name
        if result.output_bytes:
            size_text = f"{format_bytes(result.original_bytes)} → {format_bytes(result.output_bytes)}"
        else:
            size_text = "—"
        psnr_text = f"{result.psnr:.1f} dB" if result.psnr is not None else "—"
        saved_text = (
            f"-{result.savings_ratio * 100:.0f}%"
            if result.status == "compressed" and result.savings_ratio > 0
            else "—"
        )
        tag = f"{'even' if self._row_counter % 2 == 0 else 'odd'}_{state}"
        iid = f"row-{self._row_counter}"
        self._row_counter += 1
        self.tree.insert(
            "",
            END,
            iid=iid,
            values=(relative, status_text, size_text, psnr_text, saved_text),
            tags=(tag,),
        )
        self._detail_by_iid[iid] = (
            f"{result.display_status} · {result.message}"
            + (f" · 输出：{result.output}" if result.output else "")
        )
        self.tree.yview_moveto(1.0)

    def _on_done(self, report) -> None:
        self.running = False
        self.cancelling = False
        self.report = report
        self.cancel_event = None
        self._set_controls_enabled(True)
        self._refresh_output_links()
        self.primary.set_mode("normal")
        if report.cancelled:
            self.overview_badge.configure(text="已取消", bg=AMBER_SOFT, fg=AMBER)
            self.status_label.configure(text="任务已取消")
            self.status_detail.configure(
                text=f"已完成 {len(report.results)} 张，输出文件已保留。"
            )
            self.primary.set_text("继续压缩")
            self.primary.set_state(True)
        else:
            self.overview_badge.configure(
                text="已完成" if not report.errors else "部分完成",
                bg=ACCENT_SOFT if not report.errors else AMBER_SOFT,
                fg=ACCENT_DARK if not report.errors else AMBER,
            )
            self.status_label.configure(
                text="压缩完成" if not report.errors else "压缩完成，但有图片失败"
            )
            fail_text = f" · {len(report.errors)} 张失败" if report.errors else ""
            self.status_detail.configure(
                text=(
                    f"共处理 {len(report.results)} 张{fail_text} · "
                    f"用时 {report.elapsed:.1f} 秒"
                )
            )
            self.primary.set_text("再次压缩")
            self.primary.set_state(True)
        self.progress.stop()
        self.progress.configure(mode="determinate", maximum=100)
        if report.results:
            self.progress["value"] = (
                100
                if not report.cancelled
                else min(99, len(report.results) / max(1, self.scan.count) * 100)
            )
            self.progress_percent.configure(text=f"{int(self.progress['value'])}%")
        self.stat_labels["images"].configure(text=str(len(report.results)))
        self.stat_labels["compressed"].configure(text=str(len(report.compressed)))
        if report.average_psnr is not None:
            self.stat_labels["psnr"].configure(text=f"{report.average_psnr:.1f} dB")
        self.stat_labels["saved"].configure(text=format_bytes(report.savings_bytes))
        self.stat_captions["saved"].configure(
            text=f"已节省 · {report.savings_ratio * 100:.0f}%"
        )
        self.open_btn.set_state(True)
        self.report_btn.set_state(report.report_csv is not None)
        self.log_count.configure(text=f"{len(report.results)} 张")
        self._refresh_output_label()

    def _on_fatal(self, message: str, trace: str) -> None:
        self.running = False
        self.cancelling = False
        self.cancel_event = None
        self._set_controls_enabled(True)
        self.primary.set_text("开始压缩")
        self.primary.set_state(bool(self.scan and self.scan.count))
        self.primary.set_mode("normal")
        self.overview_badge.configure(text="出错", bg=RED_SOFT, fg=RED)
        self.status_label.configure(text="压缩任务出错")
        self.status_detail.configure(text=message[:160])
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self._append_error_log(message, trace)
        messagebox.showerror(
            APP_NAME,
            f"压缩任务出错：\n{message}\n\n详细日志已保存到 error.log。",
            parent=self.root,
        )

    def _set_controls_enabled(self, enabled: bool) -> None:
        state = "readonly" if enabled else "disabled"
        self.quality_slider.set_state(enabled)
        self.size_combo.configure(state=state)
        self.format_control.set_state(enabled)
        self._refresh_output_links()
        if not enabled:
            self.output_change_btn.set_state(False)
            self.output_reset_btn.set_state(False)

    def _clear_results(self) -> None:
        for iid in self.tree.get_children():
            self.tree.delete(iid)
        self._detail_by_iid.clear()
        self._row_counter = 0
        self.results_received = 0
        self.compressed_count = 0
        self.kept_count = 0
        self.error_count = 0
        self.psnr_sum = 0.0
        self.psnr_count = 0
        self.saved_bytes = 0
        self.report = None
        self.stat_labels["compressed"].configure(text="0")
        self.stat_labels["psnr"].configure(text="—")
        self.stat_labels["saved"].configure(text="—")
        self.stat_captions["saved"].configure(text="已节省")
        self.stat_labels["images"].configure(
            text=str(self.scan.count) if self.scan else "—"
        )
        self.log_count.configure(text="0 张")
        self.open_btn.set_state(False)
        self.report_btn.set_state(False)
        self.detail_label.configure(text="选择一条记录查看处理说明。")
        if hasattr(self, "progress"):
            self.progress.configure(value=0)

    def _on_row_select(self, _event=None) -> None:
        selection = self.tree.selection()
        if not selection:
            return
        self.detail_label.configure(
            text=_truncate_middle(self._detail_by_iid.get(selection[0], ""), 140)
        )

    # ---------------------------------------------------------------- 结果操作
    def _open_output(self) -> None:
        if not self.output_path or not self.output_path.exists():
            return
        try:
            os.startfile(str(self.output_path))
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"无法打开输出文件夹：{exc}", parent=self.root)

    def _open_report(self) -> None:
        if not self.report or not self.report.report_csv:
            return
        try:
            os.startfile(str(self.report.report_csv))
        except OSError as exc:
            messagebox.showerror(APP_NAME, f"无法打开报告：{exc}", parent=self.root)

    def _append_error_log(self, message: str, trace: str) -> None:
        try:
            with open(BASE_DIR / "error.log", "a", encoding="utf-8") as handle:
                handle.write(f"\n[{time.strftime('%Y-%m-%d %H:%M:%S')}] {message}\n{trace}\n")
        except OSError:
            pass

    # ------------------------------------------------------------------ 事件循环
    def _poll_events(self) -> None:
        if self._closing:
            return
        while True:
            try:
                event = self.events.get_nowait()
            except queue.Empty:
                break
            kind = event[0]
            if kind == "scan_ok":
                self._on_scan_ok(event[1], event[2])
            elif kind == "scan_error":
                self._on_scan_error(event[1], event[2])
            elif kind == "progress":
                self._on_progress(event[1], event[2], event[3])
            elif kind == "done":
                self._on_done(event[1])
            elif kind == "fatal":
                self._on_fatal(event[1], event[2])
        self.root.after(80, self._poll_events)

    def _bind_shortcuts(self) -> None:
        self.root.bind("<Control-o>", lambda _event: self.choose_folder())
        self.root.bind("<Escape>", lambda _event: self._cancel_compression() if self.running else None)

    def _on_close(self) -> None:
        if self.running:
            proceed = messagebox.askyesno(
                APP_NAME,
                "压缩任务还在进行。\n确定退出吗？当前未完成的图片会被取消。",
                parent=self.root,
            )
            if not proceed:
                return
            if self.cancel_event:
                self.cancel_event.set()
        self._closing = True
        self.root.destroy()


def main() -> None:
    if sys.platform == "win32":
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    initial_folder = None
    if len(sys.argv) > 1:
        candidate = Path(sys.argv[1]).expanduser()
        if candidate.is_dir():
            initial_folder = candidate

    try:
        root = TkinterDnD.Tk() if DND_AVAILABLE else tk.Tk()
    except Exception:
        root = tk.Tk()
    root.option_add("*tearOff", False)
    app = LightPressApp(root, initial_folder=initial_folder)
    try:
        root.mainloop()
    except Exception:
        with open(BASE_DIR / "error.log", "a", encoding="utf-8") as handle:
            handle.write(traceback.format_exc())
        raise
    _ = app


if __name__ == "__main__":
    main()
