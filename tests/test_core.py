"""压缩引擎的无网络测试。"""

from __future__ import annotations

import csv
import shutil
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from compressor import (  # noqa: E402
    CompressionOptions,
    compress_folder,
    format_bytes,
    scan_folder,
)


def _font(size: int):
    for name in ("msyh.ttc", "segoeui.ttf", "arial.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def build_source(root: Path) -> None:
    root.mkdir(parents=True)
    (root / "sub").mkdir()

    width, height = 720, 480
    y, x = np.mgrid[0:height, 0:width]
    base = np.stack(
        [
            110 + 70 * np.sin(x / 90),
            130 + 55 * np.cos(y / 70),
            120 + 50 * np.sin((x + y) / 130),
        ],
        axis=-1,
    )
    noise = np.random.default_rng(7).normal(0, 6, base.shape)
    array = np.clip(base + noise, 0, 255).astype(np.uint8)
    Image.fromarray(array).save(root / "photo.jpg", quality=92)

    screen = Image.new("RGB", (960, 620), "white")
    draw = ImageDraw.Draw(screen)
    draw.rectangle((0, 0, 960, 70), fill=(26, 45, 38))
    draw.text((36, 20), "LightPress interface sample", font=_font(24), fill="white")
    for index in range(5):
        top = 110 + index * 90
        draw.rounded_rectangle(
            (36, top, 924, top + 62),
            radius=12,
            fill=(246, 250, 248),
            outline=(218, 230, 224),
        )
        draw.text((60, top + 20), f"Card row {index + 1}", font=_font(18), fill=(30, 50, 40))
    screen.save(root / "screenshot.png")

    transparent = Image.new("RGBA", (420, 300), (0, 0, 0, 0))
    draw = ImageDraw.Draw(transparent)
    draw.rounded_rectangle((30, 30, 390, 270), radius=28, fill=(15, 143, 118, 225))
    draw.ellipse((240, 130, 350, 240), fill=(255, 203, 89, 200))
    draw.text((55, 65), "alpha", font=_font(32), fill=(255, 255, 255, 255))
    transparent.save(root / "sub" / "transparent.png")

    # 两个同名不同后缀，测试目标名去重
    Image.new("RGB", (64, 64), (180, 30, 20)).save(root / "same.jpg", quality=90)
    Image.new("RGB", (64, 64), (20, 100, 180)).save(root / "same.png")

    frames = [
        Image.new("RGB", (120, 80), (20, 130, 110)),
        Image.new("RGB", (120, 80), (220, 160, 50)),
    ]
    frames[0].save(
        root / "animated.gif",
        save_all=True,
        append_images=frames[1:],
        duration=200,
        loop=0,
    )


def main() -> int:
    temp_root = ROOT / ".test-run"
    if temp_root.exists():
        shutil.rmtree(temp_root)
    temp_root.mkdir(parents=True)
    try:
        source = temp_root / "source"
        output = temp_root / "output"
        build_source(source)

        scanned = scan_folder(source)
        assert scanned.count == 6, scanned.count

        options = CompressionOptions(
            target_psnr=40,
            output_format="avif",
            workers=3,
            avif_speed=8,
        )
        report = compress_folder(source, output, options)
        assert len(report.results) == 6
        assert not report.errors, [r.message for r in report.errors]
        assert report.report_csv and report.report_csv.exists()

        statuses = {item.source.name: item.status for item in report.results}
        assert statuses["animated.gif"] == "animated", statuses
        assert (output / "animated.gif").exists()
        assert (output / "same_jpg.avif").exists() or (output / "same_jpg.jpg").exists()
        assert (output / "same_png.avif").exists() or (output / "same_png.png").exists()

        for item in report.compressed:
            assert item.output and item.output.exists()
            assert item.psnr is not None and item.psnr >= options.target_psnr - 1e-6, item
            assert item.ssim is not None and item.ssim >= options.min_ssim - 1e-9, item
            assert item.output_bytes < item.original_bytes

        with open(report.report_csv, encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.reader(handle))
        assert len(rows) == 7, len(rows)
        assert rows[0][0] == "文件"

        # 新增的极限档：30 dB 应能真正把文件继续压小
        low_options = CompressionOptions(
            target_psnr=30,
            output_format="avif",
            workers=3,
            avif_speed=8,
        )
        low_report = compress_folder(source, temp_root / "output30", low_options)
        assert not low_report.errors, [r.message for r in low_report.errors]
        assert low_report.compressed, "30 dB 档应至少压缩成功一张图"
        for item in low_report.compressed:
            assert item.psnr is not None and item.psnr >= 30 - 1e-6, item
            assert item.ssim is not None and item.ssim >= 0.85, item
        assert low_report.total_output_bytes < report.total_output_bytes

        # 输出目录不能与源目录相同
        try:
            compress_folder(source, source, options)
        except ValueError:
            pass
        else:
            raise AssertionError("应当拒绝覆盖源目录")

        for invalid_target in (29.0, 49.0):
            try:
                CompressionOptions(target_psnr=invalid_target)
            except ValueError:
                pass
            else:
                raise AssertionError(f"应当拒绝 {invalid_target} dB")

        print(
            "OK · "
            f"{len(report.compressed)} 张压缩，{len(report.kept)} 张保留，"
            f"节省 {format_bytes(report.savings_bytes)}，"
            f"平均 {report.average_psnr:.2f} dB；"
            f"30 dB 档节省 {format_bytes(low_report.savings_bytes)}"
        )
    finally:
        shutil.rmtree(temp_root, ignore_errors=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
