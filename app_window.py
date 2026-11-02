"""轻压 · 视觉无损批量压缩（Windows 桌面界面 · Material 3）。

窗口结构、界面布局和压缩流程都在这里；自绘 Material 组件见 material.py，
配色与系统主题见 theme.py。
"""

from __future__ import annotations

import ctypes
import math
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
from PIL import ImageTk

from screenshot import capture_client

from material import (  # noqa: E402
    Badge,
    Chip,
    IconTile,
    LinearProgress,
    MaterialButton,
    MaterialCard,
    MaterialSelect,
    MaterialSlider,
    SegmentedButton,
    ThemeToggle,
    TextButton,
    ThinScrollbar,
    round_rect,
    set_font_family,
)
from theme import (  # noqa: E402
    DARK,
    LIGHT,
    Palette,
    apply_titlebar_theme,
    load_theme_mode,
    save_theme_mode,
    system_is_dark,
)

APP_NAME = "轻压"
APP_VERSION = "1.2"
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
SUCCESS = LIGHT.SUCCESS
SUCCESS_SOFT = LIGHT.SUCCESS_SOFT
ON_SUCCESS_SOFT = LIGHT.ON_SUCCESS_SOFT
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

# Windows 上没有 Roboto，优先选择与 Material 字形接近的系统字体。
PREFERRED_FONTS = (
    "Google Sans",
    "Segoe UI Variable Display",
    "Segoe UI",
    "Microsoft YaHei UI",
    "Arial",
)
FONT_FAMILY = "Segoe UI"
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
    for candidate in PREFERRED_FONTS:
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
    tail_text = "\\".join(parts[-keep_parts:])
    if path.drive:
        return f"{path.drive}\\…\\{tail_text}"
    if path.anchor:
        return f"{path.anchor}…{tail_text}"
    return f"…\\{tail_text}"


class LightPressApp:
    def __init__(self, root: tk.Tk, initial_folder: Path | None = None) -> None:
        self.root = root
        self.font_family = _choose_font(root)
        set_font_family(self.font_family)
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
        self._resize_job = None
        self._rippling = False
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
        self.root.bind("<Configure>", self._on_root_configure)
        self.root.after(80, self._poll_events)
        self._apply_theme(self.is_dark, initial=True)
        self.root.update_idletasks()
        self._fit_cards()
        self.root.deiconify()
        self.root.after(120, lambda: apply_titlebar_theme(self.root, self.is_dark))
        self.root.after(1500, self._watch_system_theme)
        if initial_folder:
            self.root.after(200, lambda: self.select_folder(initial_folder))

    # ------------------------------------------------------------------ 窗口
    def _configure_window(self) -> None:
        self.root.title(f"{APP_NAME} · 视觉无损批量压缩")
        self.root.configure(bg=BG)
        self.root.minsize(1040, 720)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        width = min(1260, max(1040, screen_w - 160))
        height = min(880, max(720, screen_h - 120))
        x = max(20, (screen_w - width) // 2)
        y = max(20, (screen_h - height) // 2 - 12)
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
                # 384px 原图 → 32px 显示，整数倍缩放边缘更干净
                image = image.subsample(12, 12)
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
            rowheight=36,
            font=(family, 9),
        )
        style.layout("Log.Treeview", [("Log.Treeview.treearea", {"sticky": "nswe"})])
        style.configure(
            "Log.Treeview.Heading",
            background=p.CARD,
            foreground=p.MUTED,
            borderwidth=0,
            relief="flat",
            font=(family, 8, "bold"),
            padding=(4, 10),
        )
        style.map(
            "Log.Treeview",
            background=[("selected", p.ACCENT_SOFT)],
            foreground=[("selected", p.TEXT)],
        )
        style.map(
            "Log.Treeview.Heading",
            background=[("active", p.CARD)],
            foreground=[("active", p.MUTED)],
        )

    # -------------------------------------------------------------- 主题切换
    def _toggle_theme(self) -> None:
        if self._rippling or self._closing:
            return
        target_dark = not self.is_dark
        self.theme_mode = "dark" if target_dark else "light"
        self._system_dark = system_is_dark()
        save_theme_mode(SETTINGS_FILE, self.theme_mode)
        self._play_theme_ripple(target_dark)

    def _play_theme_ripple(self, target_dark: bool) -> None:
        """用旧界面截图盖住窗口，再以按钮为圆心挖洞露出新主题。"""
        button = getattr(self, "theme_button", None)
        if button is None or sys.platform != "win32":
            self._apply_theme(target_dark)
            return
        snapshot = capture_client(self.root)
        if snapshot is None:
            self._apply_theme(target_dark)
            return

        width = max(1, self.root.winfo_width())
        height = max(1, self.root.winfo_height())
        origin_x = (
            button.winfo_rootx() - self.root.winfo_rootx() + button.winfo_width() / 2
        )
        origin_y = (
            button.winfo_rooty() - self.root.winfo_rooty() + button.winfo_height() / 2
        )
        radius = max(
            math.hypot(origin_x, origin_y),
            math.hypot(width - origin_x, origin_y),
            math.hypot(origin_x, height - origin_y),
            math.hypot(width - origin_x, height - origin_y),
        )

        overlay = tk.Toplevel(self.root)
        overlay.overrideredirect(True)
        overlay.geometry(
            f"{width}x{height}+{self.root.winfo_rootx()}+{self.root.winfo_rooty()}"
        )
        try:
            overlay.attributes("-topmost", True)
        except tk.TclError:
            pass
        try:
            photo = ImageTk.PhotoImage(snapshot)
        except Exception:
            overlay.destroy()
            self._apply_theme(target_dark)
            return
        label = tk.Label(overlay, image=photo, bd=0, highlightthickness=0)
        label.image = photo
        label.pack(fill=BOTH, expand=True)
        overlay.update_idletasks()
        overlay.update()

        # 先换成新主题，新界面在遮罩下面，随后靠圆形镂空一点点露出来
        self._apply_theme(target_dark)
        self.root.update_idletasks()

        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hwnd = user32.GetParent(overlay.winfo_id()) or overlay.winfo_id()
        steps = 15
        self._rippling = True

        def apply_region(current: float) -> None:
            region = gdi32.CreateRectRgn(0, 0, width, height)
            hole = gdi32.CreateEllipticRgn(
                int(origin_x - current),
                int(origin_y - current),
                int(origin_x + current),
                int(origin_y + current),
            )
            # RGN_DIFF：整块遮罩减去圆形区域，形成镂空
            gdi32.CombineRgn(region, region, hole, 4)
            gdi32.DeleteObject(hole)
            user32.SetWindowRgn(hwnd, region, True)

        def frame(index: int) -> None:
            if self._closing:
                self._close_overlay(overlay)
                return
            progress = index / steps
            eased = 1 - (1 - progress) ** 3
            apply_region(radius * eased)
            if index < steps:
                overlay.after(16, lambda: frame(index + 1))
            else:
                overlay.after(30, lambda: self._close_overlay(overlay))

        frame(0)

    def _close_overlay(self, overlay: tk.Toplevel) -> None:
        self._rippling = False
        try:
            overlay.destroy()
        except tk.TclError:
            pass

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
        # 自绘组件按新配色重画
        for widget in self._themeable_widgets(self.root):
            try:
                widget.apply_palette(target)
            except tk.TclError:
                pass
        if hasattr(self, "theme_button"):
            self.theme_button.set_dark(self.is_dark)
        self._sync_quality_ui(self.quality_slider.value)
        self._draw_drop_zone()
        self.root.after(60, self._fit_cards)
        self.root.after(30, lambda: apply_titlebar_theme(self.root, self.is_dark))

    def _themeable_widgets(self, widget: tk.Misc):
        for child in widget.winfo_children():
            if hasattr(child, "apply_palette"):
                yield child
            yield from self._themeable_widgets(child)

    def _fit_cards(self) -> None:
        if self._closing:
            return
        self.root.update_idletasks()
        for widget in self._themeable_widgets(self.root):
            if isinstance(widget, MaterialCard):
                try:
                    widget.fit()
                except tk.TclError:
                    pass
        self.root.update_idletasks()

    def _on_root_configure(self, event) -> None:
        """窗口尺寸变化后重新贴合卡片高度（防抖）。"""
        if event.widget is not self.root:
            return
        if self._resize_job is not None:
            try:
                self.root.after_cancel(self._resize_job)
            except tk.TclError:
                pass
        self._resize_job = self.root.after(120, self._resize_cards)

    def _resize_cards(self) -> None:
        self._resize_job = None
        self._rippling = False
        if self._closing:
            return
        self._fit_cards()

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
            ("#f4f7fc", target.CARD_ALT),
            ("#eaf0f8", target.CARD_SOFT),
            ("#e8edf5", target.DIVIDER),
            ("#e9eef7", target.SOFT),
            ("#ffffff", target.TABLE_HEAD),
            ("#dde5f0", target.PROGRESS_TROUGH),
            ("#c4c7c5", target.SCROLLBAR),
            ("#e7e9ee", target.DISABLED_FILL),
            ("#a2a7ad", target.DISABLED_FG),
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
        body.pack(fill=BOTH, expand=True, padx=22, pady=(18, 18))
        body.grid_columnconfigure(0, minsize=400, weight=0)
        body.grid_columnconfigure(1, minsize=520, weight=1)
        body.grid_rowconfigure(0, weight=1)

        self.left = tk.Frame(body, bg=BG, width=400)
        self.left.grid(row=0, column=0, sticky="nsew", padx=(0, 18))
        self.left.pack_propagate(False)

        self.right = tk.Frame(body, bg=BG)
        self.right.grid(row=0, column=1, sticky="nsew")

        # 窗口变矮时，左侧卡片可以滚动，主操作按钮始终固定在底部。
        self._build_primary()
        self._build_left_scroller()
        self._build_drop_zone()
        self._build_selected_card()
        self._build_settings_card()

        self._build_overview()
        self._build_log_card()
        self._build_theme_toggle()

    def _build_left_scroller(self) -> None:
        wrap = tk.Frame(self.left, bg=BG)
        wrap.pack(fill=BOTH, expand=True, pady=(2, 0))

        self.left_canvas = tk.Canvas(
            wrap,
            bg=BG,
            bd=0,
            highlightthickness=0,
            yscrollincrement=48,
        )
        self.left_scrollbar = ThinScrollbar(
            wrap, self.left_canvas.yview, page="BG", width=8
        )
        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)
        self.left_scrollbar.pack(side=RIGHT, fill=Y, padx=(4, 0))
        self.left_canvas.pack(side=LEFT, fill=BOTH, expand=True)

        self.left_inner = tk.Frame(self.left_canvas, bg=BG)
        self._left_window = self.left_canvas.create_window(
            (0, 0), window=self.left_inner, anchor="nw"
        )
        self.left_inner.bind("<Configure>", self._on_left_inner_configure)
        self.left_canvas.bind("<Configure>", self._on_left_canvas_configure)
        self.root.bind("<MouseWheel>", self._on_mousewheel, add="+")

    def _on_left_inner_configure(self, _event=None) -> None:
        self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))
        self._update_left_scrollbar()

    def _on_left_canvas_configure(self, event) -> None:
        self.left_canvas.itemconfigure(self._left_window, width=event.width)
        self._update_left_scrollbar()

    def _update_left_scrollbar(self) -> None:
        """内容放得下时隐藏滚动条，避免无谓的留白。"""
        try:
            needed = (
                self.left_inner.winfo_reqheight()
                > self.left_canvas.winfo_height() + 2
            )
            mapped = bool(self.left_scrollbar.winfo_ismapped())
            if needed and not mapped:
                self.left_scrollbar.pack(
                    side=RIGHT, fill=Y, padx=(4, 0), before=self.left_canvas
                )
            elif not needed and mapped:
                self.left_scrollbar.pack_forget()
                self.left_canvas.yview_moveto(0.0)
        except tk.TclError:
            pass

    def _on_mousewheel(self, event) -> None:
        widget = self.root.winfo_containing(event.x_root, event.y_root)
        while widget is not None and widget is not self.left_inner:
            widget = getattr(widget, "master", None)
        if widget is None:
            return
        if self.left_inner.winfo_reqheight() <= self.left_canvas.winfo_height():
            return
        self.left_canvas.yview_scroll(-int(event.delta / 120), "units")

    def _build_header(self) -> None:
        header = tk.Frame(self.root, bg=CARD, height=70)
        header.pack(fill=X)
        header.pack_propagate(False)
        tk.Frame(self.root, bg=BORDER, height=1).pack(fill=X)

        inner = tk.Frame(header, bg=CARD)
        inner.pack(fill=BOTH, expand=True, padx=24)
        self.logo_label = tk.Label(
            inner,
            bg=CARD,
            bd=0,
            image=self._logo_images.get("light"),
        )
        self.logo_label.pack(side=LEFT, pady=(19, 0))

        brand = tk.Frame(inner, bg=CARD)
        brand.pack(side=LEFT, padx=(12, 0), pady=(13, 0))
        title_row = tk.Frame(brand, bg=CARD)
        title_row.pack(anchor="w")
        self._label(title_row, APP_NAME, size=15, bold=True).pack(side=LEFT)
        self._label(
            title_row, "批量图片压缩", size=8, fg=MUTED
        ).pack(side=LEFT, padx=(8, 0), pady=(10, 0))
        self._label(
            brand,
            "视觉无损 · 为网页提速",
            size=8,
            fg=MUTED,
        ).pack(anchor="w", pady=(0, 0))

        right = tk.Frame(inner, bg=CARD)
        right.pack(side=RIGHT)
        self._label(right, f"v{APP_VERSION}", size=8, fg=FAINT).pack(side=RIGHT)

    def _build_drop_zone(self) -> None:
        self.drop_zone = tk.Canvas(
            self.left_inner,
            height=148,
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
        width = max(80, canvas.winfo_width())
        height = max(80, canvas.winfo_height())
        p = self.palette
        hover = self._drop_hover
        fill = p.DROP_BG_HOVER if hover else p.DROP_BG
        outline = p.ACCENT if hover else p.DROP_BORDER
        round_rect(canvas, 1, 1, width - 1, height - 1, 26, fill, outline, 1)

        cx = width / 2
        # 图标：Material “下载到本地”箭头，放在主色容器圆里
        canvas.create_oval(cx - 24, 12, cx + 24, 60, fill=p.ACCENT_SOFT, outline="")
        canvas.create_line(cx, 24, cx, 44, fill=p.ACCENT, width=3, capstyle="round")
        canvas.create_line(
            cx - 6,
            38,
            cx,
            44,
            cx + 6,
            38,
            fill=p.ACCENT,
            width=3,
            capstyle="round",
            joinstyle="round",
        )
        canvas.create_line(
            cx - 8, 52, cx + 8, 52, fill=p.ACCENT, width=3, capstyle="round"
        )

        canvas.create_text(
            cx,
            88,
            text="把文件夹拖到这里" if DND_AVAILABLE else "点击选择文件夹",
            fill=p.TEXT,
            font=(self.font_family, 13, "bold"),
        )
        sub = (
            "或点击选择文件夹，整批图片一次压完"
            if DND_AVAILABLE
            else "拖拽组件未加载，点击选择文件夹"
        )
        canvas.create_text(
            cx,
            112,
            text=sub,
            fill=p.MUTED,
            font=(self.font_family, 8),
        )
        canvas.create_text(
            cx,
            133,
            text="JPG · PNG · WebP · AVIF · TIFF · BMP · GIF",
            fill=p.FAINT,
            font=(self.font_family, 8),
        )

    def _set_drop_hover(self, hovered: bool) -> None:
        if self._drop_hover == hovered:
            return
        self._drop_hover = hovered
        self._draw_drop_zone()

    def _build_selected_card(self) -> None:
        card = MaterialCard(self.left_inner, radius=18, page="BG")
        card.pack(fill=X, pady=(10, 0))
        self.selected_card = card

        inner = tk.Frame(card.body, bg=CARD)
        inner.pack(fill=X, padx=16, pady=(12, 10))

        row = tk.Frame(inner, bg=CARD)
        row.pack(fill=X)
        self.folder_tile = IconTile(row, "folder", size=40, page="CARD")
        self.folder_tile.pack(side=LEFT, padx=(0, 12))

        text_box = tk.Frame(row, bg=CARD)
        text_box.pack(side=LEFT, fill=X, expand=True)
        self.folder_name_label = self._label(
            text_box, "尚未选择文件夹", size=11, bold=True, anchor="w"
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
        self.folder_path_label.pack(anchor="w", pady=(3, 0))

        self.scan_badge = Badge(
            row, "待选择", "neutral", page="CARD", height=26, font_size=8
        )
        self.scan_badge.pack(side=RIGHT, padx=(8, 0))

        tk.Frame(inner, bg=DIVIDER, height=1).pack(fill=X, pady=(11, 0))

        output_row = tk.Frame(inner, bg=CARD)
        output_row.pack(fill=X, pady=(8, 0))
        self._label(output_row, "输出", size=8, fg=MUTED).pack(side=LEFT)
        self.output_change_btn = TextButton(
            output_row, "更改", self._change_output, page="CARD"
        )
        self.output_change_btn.pack(side=RIGHT)
        self.output_reset_btn = TextButton(
            output_row, "恢复默认", self._reset_output, page="CARD"
        )
        self.output_reset_btn.pack(side=RIGHT, padx=(2, 0))
        self.output_label = self._label(
            output_row,
            "选择文件夹后自动创建 _web 文件夹",
            size=8,
            fg=MUTED,
            anchor="w",
        )
        self.output_label.pack(side=LEFT, padx=(10, 8), fill=X, expand=True)

    def _build_settings_card(self) -> None:
        card = MaterialCard(self.left_inner, radius=18, page="BG")
        card.pack(fill=X, pady=(10, 0))
        self.settings_card = card
        inner = tk.Frame(card.body, bg=CARD)
        inner.pack(fill=X, padx=16, pady=(12, 12))

        top = tk.Frame(inner, bg=CARD)
        top.pack(fill=X)
        self._label(top, "压缩设置", size=11, bold=True).pack(side=LEFT)
        self._label(top, "自动寻找达标的最低质量", size=8, fg=FAINT).pack(
            side=RIGHT, pady=(4, 0)
        )

        quality_head = tk.Frame(inner, bg=CARD)
        quality_head.pack(fill=X, pady=(10, 0))
        self._label(quality_head, "画质目标", size=9, fg=MUTED).pack(side=LEFT)
        self.quality_badge = Badge(
            quality_head, "44 dB", "primary", page="CARD", height=24, font_size=8
        )
        self.quality_badge.pack(side=RIGHT)

        self.quality_slider = MaterialSlider(
            inner,
            value=44,
            minimum=int(MIN_TARGET_PSNR),
            maximum=int(MAX_TARGET_PSNR),
            command=self._on_quality_change,
            page="CARD",
            height=36,
        )
        self.quality_slider.pack(fill=X, pady=(2, 0))

        preset_row = tk.Frame(inner, bg=CARD)
        preset_row.pack(fill=X)
        self._label(preset_row, "快捷", size=8, fg=FAINT).pack(
            side=LEFT, padx=(0, 8)
        )
        self.preset_chips: dict[int, Chip] = {}
        for preset in (30, 36, 40, 44, 48):
            chip = Chip(
                preset_row,
                str(preset),
                command=lambda value=preset: self._set_quality(value),
                page="CARD",
                height=30,
                font_size=8,
            )
            chip.pack(side=LEFT, padx=(0, 6))
            self.preset_chips[preset] = chip

        self.quality_hint = self._label(
            inner,
            "推荐 · 视觉上接近原图，网页加载明显更快",
            size=8,
            fg=MUTED,
        )
        self.quality_hint.pack(anchor="w", pady=(6, 0))

        tk.Frame(inner, bg=DIVIDER, height=1).pack(fill=X, pady=(10, 8))

        format_head = tk.Frame(inner, bg=CARD)
        format_head.pack(fill=X)
        self._label(format_head, "输出格式", size=9, fg=MUTED).pack(side=LEFT)
        self.format_hint = self._label(
            format_head,
            "同画质体积最小 · 现代浏览器首选",
            size=8,
            fg=FAINT,
        )
        self.format_hint.pack(side=RIGHT)
        self.format_control = SegmentedButton(
            inner,
            [("avif", "AVIF · 更小体积"), ("webp", "WebP · 兼容优先")],
            "avif",
            command=self._on_format_change,
            page="CARD",
            height=38,
            font_size=9,
        )
        self.format_control.pack(fill=X, pady=(6, 0))

        size_row = tk.Frame(inner, bg=CARD)
        size_row.pack(fill=X, pady=(10, 0))
        size_text = tk.Frame(size_row, bg=CARD)
        size_text.pack(side=LEFT)
        self._label(size_text, "最大边长", size=9, fg=MUTED).pack(anchor="w")
        self._label(
            size_text, "默认保持原始分辨率", size=8, fg=FAINT
        ).pack(anchor="w", pady=(1, 0))
        self.size_select = MaterialSelect(
            size_row,
            list(MAX_DIMENSIONS.keys()),
            "保持原尺寸",
            command=self._on_size_change,
            page="CARD",
            width=158,
            height=40,
        )
        self.size_select.pack(side=RIGHT, pady=(2, 0))
        self._sync_quality_ui(44)

    def _build_primary(self) -> None:
        self._label(
            self.left,
            "本地处理 · 不覆盖原图 · 自动生成压缩报告",
            size=8,
            fg=FAINT,
        ).pack(side="bottom", anchor="center", pady=(6, 0))

        self.primary = MaterialButton(
            self.left,
            "开始压缩",
            self._on_primary,
            height=52,
            page="BG",
            variant="filled",
            font=(self.font_family, 11, "bold"),
        )
        self.primary.pack(side="bottom", fill=X, pady=(10, 0))
        self.primary.set_state(False)

    def _build_theme_toggle(self) -> None:
        """右下角悬浮的圆形主题开关。"""
        self.theme_button = ThemeToggle(
            self.root,
            self._toggle_theme,
            size=36,
            page="CARD",
            palette=self.palette,
        )
        self.theme_button.place(relx=1.0, rely=1.0, anchor="se", x=-30, y=-24)

    def _build_overview(self) -> None:
        card = MaterialCard(self.right, radius=18, page="BG")
        card.pack(fill=X)
        self.overview_card = card
        inner = tk.Frame(card.body, bg=CARD)
        inner.pack(fill=X, padx=18, pady=(16, 16))

        top = tk.Frame(inner, bg=CARD)
        top.pack(fill=X)
        self._label(top, "批次概览", size=12, bold=True).pack(side=LEFT)
        self.overview_badge = Badge(
            top, "等待开始", "neutral", page="CARD", height=26, font_size=8
        )
        self.overview_badge.pack(side=RIGHT)

        stats = tk.Frame(inner, bg=CARD)
        stats.pack(fill=X, pady=(14, 0))
        self.stat_labels: dict[str, tk.Label] = {}
        self.stat_captions: dict[str, tk.Label] = {}
        specs = [
            ("images", "图片总数", "—"),
            ("compressed", "压缩成功", "0"),
            ("psnr", "平均画质", "—"),
            ("saved", "已节省", "—"),
        ]
        for index, (key, caption, initial) in enumerate(specs):
            tile = MaterialCard(stats, radius=12, surface="CARD_ALT", page="CARD")
            tile.grid(
                row=0,
                column=index,
                sticky="nsew",
                padx=(0 if index == 0 else 8, 0),
            )
            stats.grid_columnconfigure(index, weight=1, uniform="stat")
            body = tk.Frame(tile.body, bg=CARD_ALT)
            body.pack(fill=X, padx=12, pady=(10, 10))
            value = tk.Label(
                body,
                text=initial,
                bg=CARD_ALT,
                fg=TEXT,
                font=(self.font_family, 16, "bold"),
                anchor="w",
            )
            value.pack(fill=X)
            caption_label = self._label(
                body, caption, size=8, fg=MUTED, bg=CARD_ALT, anchor="w"
            )
            caption_label.pack(fill=X, pady=(2, 0))
            self.stat_labels[key] = value
            self.stat_captions[key] = caption_label

        progress_head = tk.Frame(inner, bg=CARD)
        progress_head.pack(fill=X, pady=(16, 0))
        self.status_label = self._label(
            progress_head, "准备就绪", size=9, bold=True
        )
        self.status_label.pack(side=LEFT)
        self.progress_percent = self._label(
            progress_head, "0%", size=9, fg=MUTED
        )
        self.progress_percent.pack(side=RIGHT)
        self.progress = LinearProgress(inner, page="CARD", height=6)
        self.progress.pack(fill=X, pady=(9, 0))
        self.status_detail = self._label(
            inner,
            "选择一个文件夹，开始为网站减负。",
            size=8,
            fg=MUTED,
        )
        self.status_detail.pack(anchor="w", pady=(9, 0))

    def _build_log_card(self) -> None:
        card = MaterialCard(self.right, radius=18, page="BG", fill_height=True)
        card.pack(fill=BOTH, expand=True, pady=(14, 0))
        self.log_card = card
        inner = tk.Frame(card.body, bg=CARD)
        inner.pack(fill=BOTH, expand=True)

        head = tk.Frame(inner, bg=CARD)
        head.pack(fill=X, padx=18, pady=(14, 10))
        title_box = tk.Frame(head, bg=CARD)
        title_box.pack(side=LEFT)
        self._label(title_box, "处理明细", size=11, bold=True).pack(side=LEFT)
        self.log_count = self._label(title_box, "0 张", size=8, fg=FAINT)
        self.log_count.pack(side=LEFT, padx=(8, 0), pady=(2, 0))

        self.report_btn = TextButton(
            head, "报告", self._open_report, page="CARD"
        )
        self.report_btn.pack(side=RIGHT)
        self.open_btn = TextButton(
            head, "打开输出文件夹", self._open_output, page="CARD"
        )
        self.open_btn.pack(side=RIGHT, padx=(0, 4))

        # 先固定底部说明栏，再让表格占用剩余空间，避免窗口变矮时说明被裁掉
        detail_wrap = tk.Frame(inner, bg=CARD)
        detail_wrap.pack(fill=X, side="bottom")
        tk.Frame(detail_wrap, bg=DIVIDER, height=1).pack(fill=X)
        self.detail_label = self._label(
            detail_wrap,
            "选择一条记录查看处理说明。",
            size=8,
            fg=MUTED,
            bg=CARD,
            anchor="w",
        )
        self.detail_label.pack(fill=X, padx=18, pady=9)

        table_wrap = tk.Frame(inner, bg=CARD)
        table_wrap.pack(fill=BOTH, expand=True, padx=(10, 6), pady=0)
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
            anchor = "w" if column in {"file", "size"} else "center"
            self.tree.heading(column, text=headings[column], anchor=anchor)
            self.tree.column(
                column,
                width=widths[column],
                minwidth=55,
                anchor=anchor,
                stretch=column == "file",
            )
        self.log_scroll = ThinScrollbar(table_wrap, self.tree.yview, page="CARD")
        self.tree.configure(yscrollcommand=self.log_scroll.set)
        self.tree.pack(side=LEFT, fill=BOTH, expand=True)
        self.log_scroll.pack(side=RIGHT, fill=Y, padx=(2, 0))
        self.tree.bind("<<TreeviewSelect>>", self._on_row_select)

        # 空状态提示：盖在表格上，出现第一条结果后隐藏
        self.empty_state = tk.Label(
            table_wrap,
            text="压缩完成后，这里会列出每张图片的体积与画质结果",
            bg=CARD,
            fg=FAINT,
            font=(self.font_family, 9),
        )
        self.empty_state.place(relx=0.5, rely=0.52, anchor="center")

        self._update_tree_tags(LIGHT)

    def _on_size_change(self, _value: str) -> None:
        """最大边长在开始压缩时读取，这里只保留回调占位。"""


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
        self.scan_badge.set("扫描中…", "warn")
        self._refresh_output_label()
        self._refresh_output_links()
        self._clear_results()

        self.overview_badge.set("正在扫描", "warn")
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
        self.scan_badge.set(
            f"{summary.count} 张", "primary" if summary.count else "neutral"
        )
        self.stat_labels["images"].configure(text=str(summary.count))
        if summary.count:
            self.status_label.configure(text="准备就绪")
            self.status_detail.configure(
                text=f"共 {summary.count} 张图片，约 {format_bytes(summary.total_bytes)}，可以开始压缩。"
            )
            self.overview_badge.set("待压缩", "primary")
            self.primary.set_state(True)
            self.primary.set_text("开始压缩")
            self.primary.set_mode("normal")
        else:
            self.status_label.configure(text="没有找到可压缩的图片")
            self.status_detail.configure(
                text="支持 JPG、PNG、WebP、AVIF、TIFF、BMP 和 GIF。"
            )
            self.overview_badge.set("暂无图片", "neutral")
            self.primary.set_state(False)
            self.primary.set_text("没有可压缩的图片")

    def _on_scan_error(self, token: int, message: str) -> None:
        if token != self.scan_token:
            return
        self.progress.stop()
        self.progress.configure(mode="determinate", value=0)
        self.scan_badge.set("无法读取", "error")
        self.status_label.configure(text="无法读取文件夹")
        self.status_detail.configure(text=message)
        self.overview_badge.set("扫描失败", "error")
        self.primary.set_state(False)

    # ---------------------------------------------------------------- 配置变化
    def _on_quality_change(self, value) -> None:
        self._sync_quality_ui(int(round(float(value))))

    def _set_quality(self, value: int) -> None:
        self.quality_slider.set_value(int(value), notify=True)

    def _sync_quality_ui(self, target: int) -> None:
        target = max(int(MIN_TARGET_PSNR), min(int(MAX_TARGET_PSNR), int(target)))
        self.quality_badge.set(f"{target} dB")
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
            chip.set_selected(value == target)

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
            name = self.output_path.name
            text = f"{name} · 源文件夹旁" if len(name) <= 15 else _truncate_middle(name, 24)
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
            max_dimension = MAX_DIMENSIONS.get(self.size_select.value, 0)
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
        self.overview_badge.set("压缩中", "primary")
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
        self.overview_badge.set("压缩中", "primary")

    def _insert_row(self, result, state: str, status_text: str) -> None:
        self.empty_state.place_forget()
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
            self.overview_badge.set("已取消", "warn")
            self.status_label.configure(text="任务已取消")
            self.status_detail.configure(
                text=f"已完成 {len(report.results)} 张，输出文件已保留。"
            )
            self.primary.set_text("继续压缩")
            self.primary.set_state(True)
        else:
            self.overview_badge.set(
                "已完成" if not report.errors else "部分完成",
                "success" if not report.errors else "warn",
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
        self.overview_badge.set("出错", "error")
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
        self.quality_slider.set_state(enabled)
        self.size_select.set_state(enabled)
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
        self.empty_state.place(relx=0.5, rely=0.52, anchor="center")
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
