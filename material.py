"""Material 3 自绘组件。

Tkinter 没有现成的 Material 组件，这里用 Canvas 手工绘制：
圆角表面卡片、填充/描边/文本按钮、分段按钮、过滤 Chip、状态徽标、
滑杆、线性进度条和描边下拉选择器。
"""

from __future__ import annotations

import math
import tkinter as tk
import tkinter.font as tkfont
from tkinter import BOTH, X

from theme import LIGHT, Palette, mix_hex

FONT_FAMILY = "Segoe UI"


def set_font_family(name: str) -> None:
    """由主窗口在启动时注入实际可用的界面字体。"""
    global FONT_FAMILY
    FONT_FAMILY = name


def _measure_text(font: tuple, text: str) -> int:
    family, size, *style = font
    weight = "bold" if "bold" in style else "normal"
    try:
        return tkfont.Font(family=family, size=size, weight=weight).measure(text)
    except tk.TclError:
        return int(len(text) * float(size) * 0.9)


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


def _rounded_points_corners(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    tl: float,
    tr: float,
    br: float,
    bl: float,
) -> list[float]:
    """四角半径可分别指定的圆角矩形，用于分段按钮等内嵌形状。"""
    return [
        x1 + tl, y1,
        x2 - tr, y1,
        x2, y1,
        x2, y1 + tr,
        x2, y2 - br,
        x2, y2,
        x2 - br, y2,
        x1 + bl, y2,
        x1, y2,
        x1, y2 - bl,
        x1, y1 + tl,
        x1, y1,
    ]


def _round_rect(
    canvas: tk.Canvas,
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    radius: float,
    fill: str,
    outline: str = "",
    width: int = 1,
    tags: str | tuple = (),
) -> int:
    points = _rounded_points(x1, y1, x2, y2, radius)
    return canvas.create_polygon(
        *points,
        smooth=True,
        splinesteps=28,
        fill=fill,
        outline=outline or fill,
        width=width,
        tags=tags,
    )


# 主窗口的拖放区也需要画圆角矩形，这里提供一个公开别名。
round_rect = _round_rect


# ---------------------------------------------------------------- Material 组件
class MaterialCard(tk.Canvas):
    """Material 3 卡片：圆角表面，内部 body 是普通的 Frame 容器。"""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        radius: int = 18,
        surface: str = "CARD",
        page: str = "BG",
        palette: Palette | None = None,
        fill_height: bool = False,
    ) -> None:
        self._palette = palette or LIGHT
        self._radius = radius
        self._surface_role = surface
        self._page_role = page
        self._fill_height = fill_height
        self._inset = max(4, int(round(radius * 0.34)))
        self._last_body_width = 0
        super().__init__(
            parent,
            bg=getattr(self._palette, page),
            height=1,
            bd=0,
            highlightthickness=0,
        )
        self.body = tk.Frame(
            self,
            bg=getattr(self._palette, surface),
            bd=0,
            highlightthickness=0,
        )
        self._window = self.create_window(
            self._inset,
            self._inset,
            window=self.body,
            anchor="nw",
            width=1,
            height=1,
        )
        self.bind("<Configure>", self._on_configure)
        self.body.bind("<Configure>", self._on_body_configure)
        self._draw_surface()

    # -- 绘制
    def _draw_surface(self) -> None:
        p = self._palette
        width = max(2, self.winfo_width())
        height = max(2, self.winfo_height())
        self.delete("card-surface")
        self.configure(bg=getattr(p, self._page_role))
        _round_rect(
            self,
            0.5,
            0.5,
            width - 0.5,
            height - 0.5,
            self._radius,
            getattr(p, self._surface_role),
            tags="card-surface",
        )
        self.tag_lower("card-surface")

    def _sync_size(self) -> None:
        width = max(1, self.winfo_width() - self._inset * 2)
        if self._fill_height:
            height = max(1, self.winfo_height() - self._inset * 2)
            self.itemconfigure(self._window, width=width, height=height)
        else:
            self.itemconfigure(self._window, width=width)

    def _fit_height(self) -> None:
        """按内容请求高度一次性贴合并固定卡片高度，避免几何循环。"""
        if self._fill_height:
            return
        required = self.body.winfo_reqheight()
        if required <= 1:
            return
        self.itemconfigure(self._window, height=required)
        target = required + self._inset * 2
        if abs(int(self.cget("height")) - target) > 1:
            self.configure(height=target)

    def _on_configure(self, _event=None) -> None:
        self._draw_surface()
        self._sync_size()

    def _on_body_configure(self, event=None) -> None:
        # 只有宽度变化（内容重排）才需要重新量高，高度变化来自我们自己的布局。
        if self._fill_height or event is None:
            return
        if abs(int(event.width) - self._last_body_width) <= 1:
            return
        self._last_body_width = int(event.width)
        self.after_idle(self._fit_height)

    def fit(self) -> None:
        """在容器尺寸稳定后调用，确保卡片高度贴合内容。"""
        self._fit_height()

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.body.configure(bg=getattr(palette, self._surface_role))
        self._sync_size()
        self._draw_surface()


class MaterialButton(tk.Canvas):
    """Material 3 按钮：filled / tonal / outlined / text 四种形态。"""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        height: int = 52,
        radius: int | None = None,
        page: str = "CARD",
        variant: str = "filled",
        font: tuple | None = None,
        palette: Palette | None = None,
        autosize: bool = False,
    ) -> None:
        self._palette = palette or LIGHT
        self._page_role = page
        super().__init__(
            parent,
            height=height,
            bg=getattr(self._palette, page),
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._text = text
        self._command = command
        self._variant = variant
        self._height = height
        self._radius = radius if radius is not None else height / 2
        self._font = font or (FONT_FAMILY, 10, "bold")
        self._enabled = True
        self._hovered = False
        self._pressed = False
        self._danger = False
        self._autosize = autosize
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<ButtonRelease-1>", self._on_release)
        if autosize:
            self._fit_width()
        self._draw()

    # -- 尺寸与配色
    def _fit_width(self) -> None:
        width = _measure_text(self._font, self._text) + 26
        self.configure(width=max(46, width))

    def _page_color(self) -> str:
        return getattr(self._palette, self._page_role)

    def _colors(self) -> tuple[str, str, str]:
        p = self._palette
        page = self._page_color()
        if self._variant == "text":
            if not self._enabled:
                return page, p.DISABLED_FG, ""
            fill = page
            if self._pressed:
                fill = mix_hex(page, p.ACCENT, 0.12)
            elif self._hovered:
                fill = mix_hex(page, p.ACCENT, 0.08)
            return fill, p.ACCENT, ""
        if self._variant == "outlined":
            if not self._enabled:
                return page, p.DISABLED_FG, mix_hex(page, p.BORDER, 0.55)
            fill = page
            if self._pressed:
                fill = mix_hex(page, p.ACCENT, 0.12)
            elif self._hovered:
                fill = mix_hex(page, p.ACCENT, 0.06)
            return fill, p.ACCENT, p.BORDER
        if not self._enabled:
            return p.DISABLED_FILL, p.DISABLED_FG, ""
        if self._danger:
            base, on = (p.RED, p.ON_DANGER) if self._variant == "filled" else (
                p.RED_SOFT,
                p.RED,
            )
        elif self._variant == "filled":
            base, on = p.ACCENT, p.ON_ACCENT
        else:  # tonal
            base, on = p.ACCENT_SOFT, p.ACCENT_DARK
        if self._pressed:
            base = mix_hex(base, on, 0.12)
        elif self._hovered:
            base = mix_hex(base, on, 0.08)
        return base, on, ""

    def _draw(self) -> None:
        self.delete("all")
        width = max(10, self.winfo_width())
        height = max(10, self.winfo_height())
        fill, fg, outline = self._colors()
        self.configure(bg=self._page_color())
        _round_rect(
            self,
            1,
            1,
            width - 1,
            height - 1,
            self._radius,
            fill,
            outline,
            1,
        )
        self.create_text(
            width / 2,
            height / 2 + 0.5,
            text=self._text,
            fill=fg,
            font=self._font,
        )

    # -- 交互
    def _on_enter(self, _event=None) -> None:
        if self._enabled:
            self._hovered = True
            self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._pressed = False
        self._draw()

    def _on_press(self, _event=None) -> None:
        if self._enabled:
            self._pressed = True
            self._draw()

    def _on_release(self, event=None) -> None:
        was_pressed = self._pressed
        self._pressed = False
        inside = True
        if event is not None:
            inside = 0 <= event.x <= self.winfo_width() and 0 <= event.y <= self.winfo_height()
        self._draw()
        if was_pressed and inside and self._enabled and self._command:
            self._command()

    # -- 对外接口
    def set_text(self, text: str) -> None:
        self._text = text
        if self._autosize:
            self._fit_width()
        self._draw()

    def set_state(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow")
        if not enabled:
            self._hovered = False
            self._pressed = False
        self._draw()

    def set_mode(self, mode: str) -> None:
        self._danger = mode == "danger"
        self._draw()

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.configure(bg=self._page_color())
        self._draw()


class TextButton(MaterialButton):
    """Material 文本按钮，用于卡片内的轻量操作。"""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command,
        *,
        page: str = "CARD",
        font: tuple | None = None,
        height: int = 30,
    ) -> None:
        super().__init__(
            parent,
            text,
            command,
            height=height,
            radius=10,
            page=page,
            variant="text",
            font=font or (FONT_FAMILY, 8, "bold"),
            autosize=True,
        )


class SegmentedButton(tk.Canvas):
    """Material 3 分段按钮，用于格式与外观主题选择。"""

    def __init__(
        self,
        parent: tk.Misc,
        options: list[tuple[str, str]],
        value: str,
        command=None,
        *,
        page: str = "CARD",
        height: int = 40,
        width: int | None = None,
        font_size: int = 9,
        palette: Palette | None = None,
    ) -> None:
        self._palette = palette or LIGHT
        self._page_role = page
        kwargs = {
            "height": height,
            "bg": getattr(self._palette, page),
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
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Button-1>", self._on_click)
        self.bind("<Motion>", self._on_motion)
        self.bind("<Leave>", lambda _event: self._set_hover(-1))
        self._draw()

    @property
    def value(self) -> str:
        return self._value

    def _segment_width(self) -> float:
        return (max(10, self.winfo_width()) - 2) / max(1, len(self._segments))

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        width = max(10, self.winfo_width())
        height = max(10, self.winfo_height())
        page = getattr(p, self._page_role)
        self.configure(bg=page)
        _round_rect(self, 1, 1, width - 1, height - 1, height / 2, page, p.BORDER, 1)
        count = len(self._segments)
        segment = self._segment_width()
        font = (FONT_FAMILY, self._font_size, "bold")
        for index, (option_value, label) in enumerate(self._segments):
            x1 = 1 + index * segment
            x2 = x1 + segment
            selected = option_value == self._value
            hovered = self._enabled and index == self._hover_index
            fill = None
            if selected:
                fill = p.ACCENT_SOFT
            elif hovered:
                fill = mix_hex(page, p.TEXT, 0.05)
            if fill:
                left = index == 0
                right = index == count - 1
                corner = height / 2
                points = _rounded_points_corners(
                    x1,
                    1,
                    x2,
                    height - 1,
                    corner if left else 0,
                    corner if right else 0,
                    corner if right else 0,
                    corner if left else 0,
                )
                self.create_polygon(
                    *points,
                    smooth=True,
                    splinesteps=28,
                    fill=fill,
                    outline=fill,
                )
            if not self._enabled:
                fg = p.DISABLED_FG
            elif selected:
                fg = p.ACCENT_DARK
            elif hovered:
                fg = p.TEXT
            else:
                fg = p.MUTED
            text_width = _measure_text(font, label)
            center = (x1 + x2) / 2
            if selected:
                check_x = max(x1 + 12, center - text_width / 2 - 10)
                self._draw_check(check_x, height / 2, fg)
            self.create_text(
                center,
                height / 2,
                text=label,
                fill=fg,
                font=font,
            )
            if index > 0 and not selected:
                previous = self._segments[index - 1][0]
                if previous != self._value:
                    self.create_line(
                        x1,
                        height * 0.3,
                        x1,
                        height * 0.7,
                        fill=p.BORDER,
                        width=1,
                    )

    def _draw_check(self, cx: float, cy: float, color: str) -> None:
        self.create_line(
            cx - 4,
            cy,
            cx - 1,
            cy + 3.5,
            cx + 4.5,
            cy - 3.5,
            fill=color,
            width=1.8,
            capstyle="round",
            joinstyle="round",
        )

    def _index_from_x(self, x: int) -> int:
        count = len(self._segments)
        segment = self._segment_width()
        index = int((x - 1) // max(1.0, segment))
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
        self._hover_index = -1
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.configure(bg=getattr(palette, self._page_role))
        self._draw()


class ThemeToggle(tk.Canvas):
    """圆形主题开关：浅色时显示月亮，深色时显示太阳。"""

    def __init__(
        self,
        parent: tk.Misc,
        command,
        *,
        size: int = 40,
        page: str = "CARD",
        surface: str = "CARD_ALT",
        palette: Palette | None = None,
    ) -> None:
        self._palette = palette or LIGHT
        self._page_role = page
        self._surface_role = surface
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=getattr(self._palette, page),
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._size = size
        self._command = command
        self._dark = False
        self._hovered = False
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._draw()

    def _on_click(self, _event=None) -> None:
        if self._command:
            self._command()

    def set_dark(self, dark: bool) -> None:
        dark = bool(dark)
        if self._dark != dark:
            self._dark = dark
            self._draw()

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        page = getattr(p, self._page_role)
        self.configure(bg=page)
        size = max(20, min(self._size, self.winfo_width() or self._size))
        fill = getattr(p, self._surface_role)
        if self._hovered:
            fill = mix_hex(fill, p.ACCENT, 0.10)
        self.create_oval(0.5, 0.5, size - 0.5, size - 0.5, fill=fill, outline=p.BORDER)
        cx = cy = size / 2
        color = p.ACCENT
        if self._dark:
            # 太阳
            radius = size * 0.13
            self.create_oval(
                cx - radius, cy - radius, cx + radius, cy + radius,
                fill=color, outline="",
            )
            for index in range(8):
                angle = index * math.pi / 4
                inner = radius + 3.0
                outer = radius + 6.5
                self.create_line(
                    cx + math.cos(angle) * inner,
                    cy + math.sin(angle) * inner,
                    cx + math.cos(angle) * outer,
                    cy + math.sin(angle) * outer,
                    fill=color,
                    width=1.8,
                    capstyle="round",
                )
        else:
            # 月亮：先画圆，再用按钮底色挖出月牙
            radius = size * 0.22
            self.create_oval(
                cx - radius, cy - radius, cx + radius, cy + radius,
                fill=color, outline="",
            )
            self.create_oval(
                cx - radius * 0.35, cy - radius * 1.18,
                cx + radius * 1.35, cy + radius * 0.62,
                fill=fill, outline="",
            )

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.configure(bg=getattr(palette, self._page_role))
        self._draw()


class MaterialSlider(tk.Canvas):
    """Material 3 滑杆：细轨道 + 圆形手柄 + 悬停光晕。"""

    def __init__(
        self,
        parent: tk.Misc,
        value: int = 44,
        minimum: int = 40,
        maximum: int = 48,
        command=None,
        *,
        page: str = "CARD",
        height: int = 44,
        palette: Palette | None = None,
    ) -> None:
        self._palette = palette or LIGHT
        self._page_role = page
        super().__init__(
            parent,
            bg=getattr(self._palette, page),
            height=height,
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._minimum = int(minimum)
        self._maximum = int(maximum)
        self._value = int(value)
        self._command = command
        self._enabled = True
        self._hovered = False
        self._dragging = False
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Button-1>", self._on_pointer)
        self.bind("<B1-Motion>", self._on_pointer)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self._draw()

    @property
    def value(self) -> int:
        return self._value

    def _track_bounds(self) -> tuple[float, float, float]:
        width = max(40, self.winfo_width())
        return 12.0, width - 12.0, max(10, self.winfo_height()) / 2

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        self.configure(bg=getattr(p, self._page_role))
        left, right, y = self._track_bounds()
        active = p.ACCENT if self._enabled else p.SLIDER_DISABLED
        ratio = (self._value - self._minimum) / max(1, self._maximum - self._minimum)
        knob_x = left + (right - left) * ratio
        self.create_line(left, y, right, y, fill=p.SLIDER_TRACK, width=4, capstyle="round")
        if knob_x - 10 > left:
            self.create_line(
                left, y, knob_x - 10, y, fill=active, width=4, capstyle="round"
            )
        if self._hovered or self._dragging:
            self.create_oval(
                knob_x - 18,
                y - 18,
                knob_x + 18,
                y + 18,
                fill=p.SLIDER_HALO,
                outline="",
            )
        radius = 8.5 if (self._hovered or self._dragging) else 7.5
        self.create_oval(
            knob_x - radius,
            y - radius,
            knob_x + radius,
            y + radius,
            fill=active,
            outline=active,
        )

    def _set_from_x(self, x: float) -> None:
        if not self._enabled:
            return
        left, right, _ = self._track_bounds()
        ratio = min(1.0, max(0.0, (x - left) / max(1.0, right - left)))
        new_value = int(round(self._minimum + ratio * (self._maximum - self._minimum)))
        if new_value != self._value:
            self._value = new_value
            self._draw()
            if self._command:
                self._command(new_value)

    def _on_pointer(self, event) -> None:
        self._dragging = True
        self._set_from_x(event.x)

    def _on_release(self, _event=None) -> None:
        self._dragging = False
        self._draw()

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._dragging = False
        self._draw()

    def set_state(self, enabled: bool) -> None:
        self._enabled = bool(enabled)
        self._hovered = False
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
        self.configure(bg=getattr(palette, self._page_role))
        self._draw()


class Badge(tk.Canvas):
    """Material 状态徽标（tonal pill）。"""

    TONES = ("neutral", "primary", "success", "warn", "error")

    def __init__(
        self,
        parent: tk.Misc,
        text: str = "",
        tone: str = "neutral",
        *,
        page: str = "CARD",
        height: int = 26,
        font_size: int = 8,
        palette: Palette | None = None,
    ) -> None:
        self._palette = palette or LIGHT
        self._page_role = page
        super().__init__(
            parent,
            height=height,
            bg=getattr(self._palette, page),
            bd=0,
            highlightthickness=0,
            width=1,
        )
        self._text = text
        self._tone = tone if tone in self.TONES else "neutral"
        self._height = height
        self._font = (FONT_FAMILY, font_size, "bold")
        self._fit()
        self.bind("<Configure>", lambda _event: self._draw())
        self._draw()

    def _fit(self) -> None:
        width = _measure_text(self._font, self._text) + 22
        self.configure(width=max(34, width))

    def _tone_colors(self) -> tuple[str, str]:
        p = self._palette
        if self._tone == "primary":
            return p.ACCENT_SOFT, p.ACCENT_DARK
        if self._tone == "success":
            return p.SUCCESS_SOFT, p.ON_SUCCESS_SOFT
        if self._tone == "warn":
            return p.AMBER_SOFT, p.AMBER
        if self._tone == "error":
            return p.RED_SOFT, p.RED
        return p.CARD_ALT, p.MUTED

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        width = max(10, self.winfo_width())
        height = max(8, self.winfo_height())
        self.configure(bg=getattr(p, self._page_role))
        fill, fg = self._tone_colors()
        _round_rect(self, 0.5, 0.5, width - 0.5, height - 0.5, height / 2, fill)
        self.create_text(
            width / 2,
            height / 2 + 0.5,
            text=self._text,
            fill=fg,
            font=self._font,
        )

    def set(self, text: str | None = None, tone: str | None = None) -> None:
        if text is not None:
            self._text = text
        if tone is not None:
            self._tone = tone if tone in self.TONES else "neutral"
        self._fit()
        self._draw()

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.configure(bg=getattr(palette, self._page_role))
        self._draw()


class Chip(tk.Canvas):
    """Material 过滤 Chip，用于画质快捷档位。"""

    def __init__(
        self,
        parent: tk.Misc,
        text: str,
        command=None,
        *,
        page: str = "CARD",
        height: int = 30,
        font_size: int = 8,
        selected: bool = False,
        palette: Palette | None = None,
    ) -> None:
        self._palette = palette or LIGHT
        self._page_role = page
        super().__init__(
            parent,
            height=height,
            bg=getattr(self._palette, page),
            bd=0,
            highlightthickness=0,
            cursor="hand2",
            width=1,
        )
        self._text = text
        self._command = command
        self._selected = bool(selected)
        self._hovered = False
        self._height = height
        self._font = (FONT_FAMILY, font_size, "bold")
        self._fit()
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", self._on_click)
        self._draw()

    def _fit(self) -> None:
        width = _measure_text(self._font, self._text) + (46 if self._selected else 26)
        self.configure(width=max(46, width))

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        width = max(10, self.winfo_width())
        height = max(8, self.winfo_height())
        page = getattr(p, self._page_role)
        self.configure(bg=page)
        if self._selected:
            fill, fg, outline = p.ACCENT_SOFT, p.ACCENT_DARK, ""
        else:
            fill = mix_hex(page, p.TEXT, 0.05) if self._hovered else page
            fg, outline = p.MUTED, p.BORDER
        _round_rect(self, 1, 1, width - 1, height - 1, 8, fill, outline, 1)
        text_width = _measure_text(self._font, self._text)
        center = width / 2
        if self._selected:
            check_x = max(10.0, center - text_width / 2 - 9)
            self.create_line(
                check_x - 4, height / 2,
                check_x - 1, height / 2 + 3,
                check_x + 4.5, height / 2 - 3.5,
                fill=fg,
                width=1.8,
                capstyle="round",
                joinstyle="round",
            )
        self.create_text(
            center,
            height / 2 + 0.5,
            text=self._text,
            fill=fg,
            font=self._font,
        )

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._draw()

    def _on_click(self, _event=None) -> None:
        if self._command:
            self._command()

    def set_selected(self, selected: bool) -> None:
        if self._selected != bool(selected):
            self._selected = bool(selected)
            self._fit()
            self._draw()

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.configure(bg=getattr(palette, self._page_role))
        self._draw()


class IconTile(tk.Canvas):
    """卡片里的小圆角图标块。"""

    def __init__(
        self,
        parent: tk.Misc,
        kind: str = "folder",
        *,
        size: int = 44,
        page: str = "CARD",
        palette: Palette | None = None,
    ) -> None:
        self._palette = palette or LIGHT
        self._page_role = page
        super().__init__(
            parent,
            width=size,
            height=size,
            bg=getattr(self._palette, page),
            bd=0,
            highlightthickness=0,
        )
        self._kind = kind
        self._size = size
        self._draw()

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        size = self._size
        self.configure(bg=getattr(p, self._page_role))
        _round_rect(self, 0, 0, size, size, size * 0.32, p.ACCENT_SOFT)
        if self._kind == "folder":
            self.create_polygon(
                *_rounded_points(
                    size * 0.24, size * 0.30, size * 0.50, size * 0.40, 3
                ),
                smooth=True,
                splinesteps=18,
                fill=p.ACCENT,
                outline=p.ACCENT,
            )
            _round_rect(
                self,
                size * 0.22,
                size * 0.36,
                size * 0.78,
                size * 0.70,
                size * 0.10,
                p.ACCENT,
            )
        elif self._kind == "image":
            _round_rect(
                self,
                size * 0.28,
                size * 0.30,
                size * 0.72,
                size * 0.70,
                size * 0.08,
                p.ACCENT,
            )
            self.create_oval(
                size * 0.34,
                size * 0.38,
                size * 0.44,
                size * 0.48,
                fill=p.ACCENT_SOFT,
                outline="",
            )

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self._draw()


class ThinScrollbar(tk.Canvas):
    """Material 风格的窄滚动条，可拖动，内容放得下时自动隐藏。"""

    def __init__(
        self,
        parent: tk.Misc,
        command,
        *,
        page: str = "CARD",
        width: int = 10,
        palette: Palette | None = None,
    ) -> None:
        self._palette = palette or LIGHT
        self._page_role = page
        super().__init__(
            parent,
            width=width,
            bg=getattr(self._palette, page),
            bd=0,
            highlightthickness=0,
        )
        self._command = command
        self._first = 0.0
        self._last = 1.0
        self._drag_origin: float | None = None
        self._drag_first = 0.0
        self._hovered = False
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<ButtonPress-1>", self._on_press)
        self.bind("<B1-Motion>", self._on_motion)
        self.bind("<ButtonRelease-1>", self._on_release)
        self.bind("<Enter>", lambda _event: self._set_hover(True))
        self.bind("<Leave>", lambda _event: self._set_hover(False))
        self._draw()

    # ttk.Scrollbar 兼容接口
    def set(self, first, last) -> None:
        try:
            self._first = float(first)
            self._last = float(last)
        except (TypeError, ValueError):
            return
        self._draw()

    def _visible(self) -> bool:
        return (self._last - self._first) < 0.995

    def _thumb_bounds(self) -> tuple[float, float]:
        height = max(10, self.winfo_height())
        top = self._first * height
        bottom = self._last * height
        if bottom - top < 24:
            middle = (top + bottom) / 2
            top = middle - 12
            bottom = middle + 12
        return max(2.0, top), min(height - 2.0, bottom)

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        self.configure(bg=getattr(p, self._page_role))
        if not self._visible():
            return
        width = max(6, self.winfo_width())
        top, bottom = self._thumb_bounds()
        color = mix_hex(p.SCROLLBAR, p.TEXT, 0.18) if self._hovered else p.SCROLLBAR
        _round_rect(self, 2, top, width - 2, bottom, (width - 4) / 2, color)

    def _set_hover(self, hovered: bool) -> None:
        if self._hovered != hovered:
            self._hovered = hovered
            self._draw()

    def _on_press(self, event) -> None:
        if not self._visible():
            return
        self._drag_origin = float(event.y)
        self._drag_first = self._first

    def _on_motion(self, event) -> None:
        if self._drag_origin is None or not self._visible():
            return
        height = max(10, self.winfo_height())
        delta = (event.y - self._drag_origin) / height
        target = max(0.0, min(1.0, self._drag_first + delta))
        if self._command:
            self._command("moveto", target)

    def _on_release(self, _event=None) -> None:
        self._drag_origin = None

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.configure(bg=getattr(palette, self._page_role))
        self._draw()


class LinearProgress(tk.Canvas):
    """Material 3 线性进度条，兼容 ttk.Progressbar 的常用调用。"""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        page: str = "CARD",
        height: int = 6,
        palette: Palette | None = None,
    ) -> None:
        self._palette = palette or LIGHT
        self._page_role = page
        super().__init__(
            parent,
            height=height,
            bg=getattr(self._palette, page),
            bd=0,
            highlightthickness=0,
        )
        self._mode = "determinate"
        self._value = 0.0
        self._maximum = 100.0
        self._phase = 0.0
        self._after_id = None
        self.bind("<Configure>", lambda _event: self._draw())
        self._draw()

    # -- ttk 兼容层
    def configure(self, cnf=None, **kwargs):
        if isinstance(cnf, dict):
            kwargs = {**cnf, **kwargs}
        handled = False
        if "value" in kwargs:
            try:
                self._value = float(kwargs.pop("value"))
            except (TypeError, ValueError):
                self._value = 0.0
            handled = True
        if "maximum" in kwargs:
            try:
                self._maximum = float(kwargs.pop("maximum")) or 100.0
            except (TypeError, ValueError):
                self._maximum = 100.0
            handled = True
        if "mode" in kwargs:
            self._mode = str(kwargs.pop("mode"))
            if self._mode == "determinate":
                self.stop()
            handled = True
        if kwargs:
            tk.Canvas.configure(self, **kwargs)
        if handled:
            self._draw()
        return None

    def __setitem__(self, key, value) -> None:
        self.configure({key: value})

    def __getitem__(self, key):
        if key == "value":
            return self._value
        if key == "maximum":
            return self._maximum
        if key == "mode":
            return self._mode
        return tk.Canvas.__getitem__(self, key)

    def start(self, interval: int = 16) -> None:
        if self._after_id is not None:
            return
        self._mode = "indeterminate"
        self._phase = 0.0
        self._animate(max(16, int(interval)))

    def stop(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:
                pass
            self._after_id = None

    def _animate(self, interval: int) -> None:
        if self._mode != "indeterminate":
            self._after_id = None
            return
        self._phase = (self._phase + 0.018) % 1.0
        self._draw()
        self._after_id = self.after(interval, lambda: self._animate(interval))

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        self.configure(bg=getattr(p, self._page_role))
        width = max(20, self.winfo_width())
        height = max(4, self.winfo_height())
        y = height / 2
        self.create_line(
            6, y, width - 6, y, fill=p.PROGRESS_TROUGH, width=height, capstyle="round"
        )
        if self._mode == "indeterminate":
            t = self._phase
            length = 0.16 + 0.24 * math.sin(math.pi * t)
            start = -0.35 + 1.7 * t
            x1 = max(6.0, start * width)
            x2 = min(width - 6.0, (start + length) * width)
            if x2 - x1 > 2:
                self.create_line(
                    x1, y, x2, y, fill=p.ACCENT, width=height, capstyle="round"
                )
            return
        fraction = 0.0 if self._maximum <= 0 else self._value / self._maximum
        fraction = max(0.0, min(1.0, fraction))
        if fraction > 0:
            x2 = 6 + (width - 12) * fraction
            self.create_line(
                6, y, max(8.0, x2), y, fill=p.ACCENT, width=height, capstyle="round"
            )

    def apply_palette(self, palette: Palette) -> None:
        self._palette = palette
        self.configure(bg=getattr(palette, self._page_role))
        self._draw()


class MaterialSelect(tk.Canvas):
    """Material 描边下拉选择器，弹层用自绘列表代替系统菜单。"""

    def __init__(
        self,
        parent: tk.Misc,
        options: list[str],
        value: str,
        command=None,
        *,
        page: str = "CARD",
        width: int = 158,
        height: int = 42,
        font_size: int = 9,
        palette: Palette | None = None,
    ) -> None:
        self._palette = palette or LIGHT
        self._page_role = page
        super().__init__(
            parent,
            width=width,
            height=height,
            bg=getattr(self._palette, page),
            bd=0,
            highlightthickness=0,
            cursor="hand2",
        )
        self._choices = list(options)
        self._value = value if value in self._choices else (self._choices[0] if self._choices else "")
        self._command = command
        self._enabled = True
        self._hovered = False
        self._font_size = font_size
        self._popup: tk.Toplevel | None = None
        self.bind("<Configure>", lambda _event: self._draw())
        self.bind("<Enter>", self._on_enter)
        self.bind("<Leave>", self._on_leave)
        self.bind("<Button-1>", lambda _event: self._open())
        self._draw()

    @property
    def value(self) -> str:
        return self._value

    def _draw(self) -> None:
        self.delete("all")
        p = self._palette
        page = getattr(p, self._page_role)
        self.configure(bg=page)
        width = max(40, self.winfo_width())
        height = max(20, self.winfo_height())
        active = self._enabled and self._hovered
        outline = p.ACCENT if active else p.BORDER
        if not self._enabled:
            outline = mix_hex(page, p.BORDER, 0.55)
        _round_rect(self, 1, 1, width - 1, height - 1, 8, page, outline, 1)
        fg = p.TEXT if self._enabled else p.DISABLED_FG
        self.create_text(
            14,
            height / 2,
            text=self._value,
            fill=fg,
            font=(FONT_FAMILY, self._font_size),
            anchor="w",
        )
        cx = width - 18
        cy = height / 2
        self.create_line(
            cx - 4, cy - 2.5, cx, cy + 1.5, cx + 4, cy - 2.5,
            fill=p.MUTED if self._enabled else p.DISABLED_FG,
            width=1.6,
            capstyle="round",
            joinstyle="round",
        )

    def _on_enter(self, _event=None) -> None:
        self._hovered = True
        self._draw()

    def _on_leave(self, _event=None) -> None:
        self._hovered = False
        self._draw()

    def _open(self) -> None:
        if not self._enabled or self._popup is not None:
            return
        p = self._palette
        top = tk.Toplevel(self.winfo_toplevel())
        top.withdraw()
        top.overrideredirect(True)
        wrapper = tk.Frame(top, bg=p.BORDER)
        wrapper.pack(fill=BOTH, expand=True)
        panel = tk.Frame(wrapper, bg=p.CARD, padx=6, pady=6)
        panel.pack(fill=BOTH, expand=True, padx=1, pady=1)
        for option in self._choices:
            selected = option == self._value
            row = tk.Label(
                panel,
                text=option,
                bg=p.ACCENT_SOFT if selected else p.CARD,
                fg=p.ACCENT_DARK if selected else p.TEXT,
                anchor="w",
                padx=12,
                pady=6,
                font=(FONT_FAMILY, self._font_size),
                cursor="hand2",
            )
            row.pack(fill=X)
            if not selected:
                row.bind(
                    "<Enter>",
                    lambda _event, widget=row: widget.configure(bg=p.CARD_ALT),
                )
                row.bind(
                    "<Leave>",
                    lambda _event, widget=row: widget.configure(bg=p.CARD),
                )
            row.bind("<Button-1>", lambda _event, value=option: self._choose(value))
        top.bind("<Escape>", lambda _event: self._close())
        top.bind("<FocusOut>", lambda _event: self._close())
        top.update_idletasks()
        width = max(self.winfo_width(), 150)
        height = wrapper.winfo_reqheight()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height() + 6
        if y + height > self.winfo_screenheight() - 24:
            y = max(24, self.winfo_rooty() - height - 6)
        top.geometry(f"{width}x{height}+{x}+{y}")
        top.deiconify()
        try:
            top.attributes("-topmost", True)
            top.focus_force()
        except tk.TclError:
            pass
        self._popup = top

    def _close(self) -> None:
        if self._popup is not None:
            try:
                self._popup.destroy()
            except tk.TclError:
                pass
            self._popup = None
        self._hovered = False
        self._draw()

    def _choose(self, value: str) -> None:
        changed = value != self._value
        self._value = value
        self._close()
        self._draw()
        if changed and self._command:
            self._command(value)

    def set_state(self, enabled: bool) -> None:
        if not enabled:
            self._close()
        self._enabled = bool(enabled)
        self.configure(cursor="hand2" if enabled else "arrow")
        self._draw()

    def apply_palette(self, palette: Palette) -> None:
        self._close()
        self._palette = palette
        self.configure(bg=getattr(palette, self._page_role))
        self._draw()
