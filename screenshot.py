"""窗口截图工具。

只截取本程序窗口的客户区，不读取桌面其它内容；
Windows 上使用 PrintWindow，避免被其它窗口遮挡时拍到别人。
"""

from __future__ import annotations

import ctypes
import sys
from ctypes import wintypes
from typing import Any

from PIL import Image


class _BitmapInfoHeader(ctypes.Structure):
    _fields_ = [
        ("biSize", wintypes.DWORD),
        ("biWidth", wintypes.LONG),
        ("biHeight", wintypes.LONG),
        ("biPlanes", wintypes.WORD),
        ("biBitCount", wintypes.WORD),
        ("biCompression", wintypes.DWORD),
        ("biSizeImage", wintypes.DWORD),
        ("biXPelsPerMeter", wintypes.LONG),
        ("biYPelsPerMeter", wintypes.LONG),
        ("biClrUsed", wintypes.DWORD),
        ("biClrImportant", wintypes.DWORD),
    ]


class _BitmapInfo(ctypes.Structure):
    _fields_ = [("bmiHeader", _BitmapInfoHeader), ("bmiColors", wintypes.DWORD * 3)]


def capture_client(root: Any) -> Image.Image | None:
    """截取 Tk 窗口的客户区，失败时返回 None。"""
    if sys.platform != "win32":
        return None
    try:
        user32 = ctypes.windll.user32
        gdi32 = ctypes.windll.gdi32
        hwnd = user32.GetParent(root.winfo_id()) or root.winfo_id()
        rect = wintypes.RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        full_width = rect.right - rect.left
        full_height = rect.bottom - rect.top
        if full_width <= 0 or full_height <= 0:
            return None

        window_dc = user32.GetWindowDC(hwnd)
        memory_dc = gdi32.CreateCompatibleDC(window_dc)
        bitmap = gdi32.CreateCompatibleBitmap(window_dc, full_width, full_height)
        gdi32.SelectObject(memory_dc, bitmap)
        user32.PrintWindow(hwnd, memory_dc, 2)

        info = _BitmapInfo()
        info.bmiHeader.biSize = ctypes.sizeof(_BitmapInfoHeader)
        info.bmiHeader.biWidth = full_width
        info.bmiHeader.biHeight = -full_height
        info.bmiHeader.biPlanes = 1
        info.bmiHeader.biBitCount = 32
        info.bmiHeader.biCompression = 0
        buffer = ctypes.create_string_buffer(full_width * full_height * 4)
        gdi32.GetDIBits(
            memory_dc, bitmap, 0, full_height, buffer, ctypes.byref(info), 0
        )
        image = Image.frombuffer(
            "RGBA", (full_width, full_height), buffer, "raw", "BGRA", 0, 1
        ).convert("RGB")

        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory_dc)
        user32.ReleaseDC(hwnd, window_dc)

        left = root.winfo_rootx() - rect.left
        top = root.winfo_rooty() - rect.top
        width = max(1, root.winfo_width())
        height = max(1, root.winfo_height())
        return image.crop((left, top, left + width, top + height))
    except Exception:
        return None
