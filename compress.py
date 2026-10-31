"""轻压命令行入口。

示例：
    python compress.py "D:\\网站图片"
    python compress.py "D:\\网站图片" --target 42 --format webp
    python compress.py "D:\\相册" -o "D:\\网站\\assets"
"""

from __future__ import annotations

import argparse
import sys
import threading
from pathlib import Path

from compressor import (
    MAX_TARGET_PSNR,
    MIN_TARGET_PSNR,
    CompressionOptions,
    compress_folder,
    default_output_dir,
    format_bytes,
)


def _positive_int(value: str) -> int:
    try:
        number = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是整数") from exc
    if number < 1:
        raise argparse.ArgumentTypeError("必须大于 0")
    return number


def _target_psnr(value: str) -> float:
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("必须是数字") from exc
    if not MIN_TARGET_PSNR <= number <= MAX_TARGET_PSNR:
        raise argparse.ArgumentTypeError(
            f"必须在 {MIN_TARGET_PSNR:.0f}–{MAX_TARGET_PSNR:.0f} dB 之间"
        )
    return number


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="lightpress",
        description="批量视觉无损压缩图片，面向网站部署。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "示例：\n"
            "  python compress.py 图片文件夹\n"
            "  python compress.py 图片文件夹 --target 42 --format webp\n"
            "  python compress.py 图片文件夹 --target 30 --format avif\n"
            "  python compress.py 相册 -o D:\\网站\\assets\n"
        ),
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="一个或多个图片文件夹")
    parser.add_argument(
        "-o", "--output", type=Path, help="输出目录（仅处理单个输入文件夹时可用）"
    )
    parser.add_argument(
        "--target",
        type=_target_psnr,
        default=44.0,
        help="目标 PSNR，范围 30–48，默认 44 dB；30–39 为明显有损压缩",
    )
    parser.add_argument(
        "--format",
        choices=("avif", "webp"),
        default="avif",
        help="输出格式，默认 avif",
    )
    parser.add_argument(
        "--max-dimension",
        type=_positive_int,
        default=0,
        help="可选：图片最大边长（像素），默认保持原尺寸",
    )
    parser.add_argument(
        "--workers", type=_positive_int, default=4, help="并行任务数，默认 4"
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="逐张显示压缩结果"
    )
    parser.add_argument("--version", action="version", version="轻压 1.0")
    return parser


def main(argv: list[str] | None = None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.output is not None and len(args.inputs) != 1:
        parser.error("-o/--output 只能和单个输入文件夹一起使用")

    options = CompressionOptions(
        target_psnr=args.target,
        output_format=args.format,
        max_dimension=args.max_dimension,
        workers=args.workers,
    )

    failures = 0
    for index, source in enumerate(args.inputs, 1):
        source = source.expanduser().resolve()
        if not source.is_dir():
            print(f"[跳过] 不是文件夹：{source}")
            failures += 1
            continue
        output = (
            args.output.expanduser().resolve()
            if args.output is not None
            else default_output_dir(source)
        )
        print()
        print(f"[{index}/{len(args.inputs)}] {source}")
        print(f"  输出：{output}")
        print(
            f"  参数：{int(args.target)} dB · {args.format.upper()} · "
            f"{options.workers} 并行 · "
            + (
                f"最长边 {args.max_dimension}px"
                if args.max_dimension
                else "保持原尺寸"
            )
        )

        verbose = args.verbose

        def progress(done: int, total: int, result) -> None:
            if verbose:
                if result.status == "compressed":
                    print(
                        f"  [{done}/{total}] {result.source.name}  "
                        f"{format_bytes(result.original_bytes)} → "
                        f"{format_bytes(result.output_bytes)}  "
                        f"{result.psnr:.1f} dB  "
                        f"-{result.savings_ratio * 100:.0f}%"
                    )
                elif result.status == "error":
                    print(f"  [{done}/{total}] [失败] {result.source.name}：{result.message}")
                else:
                    print(f"  [{done}/{total}] [保留] {result.source.name}：{result.message}")
            else:
                print(f"\r  处理中 {done}/{total}…", end="", flush=True)

        cancel_event = threading.Event()
        try:
            report = compress_folder(
                source, output, options, progress=progress, cancel_event=cancel_event
            )
        except KeyboardInterrupt:
            cancel_event.set()
            print("\n已取消。")
            return 130
        except Exception as exc:
            print(f"\n[失败] {source}：{exc}")
            failures += 1
            continue

        if not verbose:
            print()
        print(
            f"  完成：{len(report.compressed)} 张已压缩，"
            f"{len(report.kept)} 张保留原图，{len(report.errors)} 张失败"
        )
        savings_line = (
            f"  节省：{format_bytes(report.savings_bytes)}"
            f"（{report.savings_ratio * 100:.1f}%）"
        )
        if report.average_psnr is not None:
            savings_line += f"，平均 {report.average_psnr:.1f} dB"
        print(savings_line)
        print(f"  报告：{report.report_csv}")
        if report.errors:
            failures += len(report.errors)
            for item in report.errors:
                print(f"  [失败] {item.source.relative_to(source)}：{item.message}")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
