"""轻压 · 视觉无损批量压缩 —— 程序入口。

界面结构、布局与压缩流程在 app_window.py，
Material 3 自绘组件在 material.py，配色与系统主题在 theme.py。
"""

from __future__ import annotations

from app_window import main

if __name__ == "__main__":
    raise SystemExit(main())
