"""轻压的核心压缩引擎。

设计目标：
- 每张图片自动搜索满足目标 PSNR / SSIM 的最低编码质量；
- 默认输出 WebP / AVIF，面向网站部署；
- 不覆盖源文件，保留目录结构和透明通道；
- 动图原样复制，异常单张隔离，不中断整批任务。
"""

from __future__ import annotations

import csv
import io
import math
import os
import shutil
import threading
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable

import numpy as np
from PIL import Image, ImageCms, ImageFile, ImageOps, UnidentifiedImageError

ImageFile.LOAD_TRUNCATED_IMAGES = False

_SRGB_PROFILE = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB"))
_SRGB_ICC = _SRGB_PROFILE.tobytes()

SUPPORTED_EXTENSIONS = frozenset(
    {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff", ".avif", ".gif"}
)
OUTPUT_FORMATS = ("webp", "avif")
MIN_TARGET_PSNR = 30.0
MAX_TARGET_PSNR = 48.0

STATUS_LABELS = {
    "compressed": "已压缩",
    "kept_quality": "保留原图",
    "kept_size": "保留原图",
    "animated": "动图复制",
    "error": "失败",
}


class CompressionCancelled(Exception):
    """内部使用：任务被用户取消。"""


@dataclass(frozen=True)
class CompressionOptions:
    """压缩参数。target_psnr 是搜索门槛，不是固定的编码质量。"""

    target_psnr: float = 44.0
    output_format: str = "avif"
    max_dimension: int = 0  # 0 表示不缩放
    min_ssim: float = 0.985
    quality_min: int = 10
    quality_max: int = 100
    workers: int = 4
    webp_method: int = 6
    avif_speed: int = 4

    def __post_init__(self) -> None:
        if not MIN_TARGET_PSNR <= float(self.target_psnr) <= MAX_TARGET_PSNR:
            raise ValueError(
                f"目标 PSNR 必须在 {MIN_TARGET_PSNR:.0f}–{MAX_TARGET_PSNR:.0f} dB 之间"
            )
        if self.output_format not in OUTPUT_FORMATS:
            raise ValueError("输出格式仅支持 webp 或 avif")
        if self.max_dimension < 0:
            raise ValueError("最大边长不能为负数")
        if not 0.0 < self.min_ssim <= 1.0:
            raise ValueError("SSIM 门槛必须在 0–1 之间")
        if not 1 <= self.quality_min <= self.quality_max <= 100:
            raise ValueError("编码质量范围无效")
        if self.workers < 1:
            raise ValueError("并发数至少为 1")


@dataclass
class CompressionResult:
    source: Path
    output: Path | None
    status: str
    original_bytes: int = 0
    output_bytes: int = 0
    source_width: int = 0
    source_height: int = 0
    output_width: int = 0
    output_height: int = 0
    psnr: float | None = None
    ssim: float | None = None
    quality: int | None = None
    message: str = ""
    duration: float = 0.0

    @property
    def display_status(self) -> str:
        return STATUS_LABELS.get(self.status, self.status)

    @property
    def savings_bytes(self) -> int:
        if self.status != "compressed" or self.output_bytes <= 0:
            return 0
        return max(0, self.original_bytes - self.output_bytes)

    @property
    def savings_ratio(self) -> float:
        if self.original_bytes <= 0:
            return 0.0
        return self.savings_bytes / self.original_bytes

    @property
    def ok(self) -> bool:
        return self.status != "error"


@dataclass
class BatchReport:
    source_dir: Path
    output_dir: Path
    results: list[CompressionResult] = field(default_factory=list)
    elapsed: float = 0.0
    cancelled: bool = False
    report_csv: Path | None = None

    @property
    def compressed(self) -> list[CompressionResult]:
        return [r for r in self.results if r.status == "compressed"]

    @property
    def kept(self) -> list[CompressionResult]:
        return [
            r
            for r in self.results
            if r.status in {"kept_quality", "kept_size", "animated"}
        ]

    @property
    def errors(self) -> list[CompressionResult]:
        return [r for r in self.results if r.status == "error"]

    @property
    def total_original_bytes(self) -> int:
        return sum(r.original_bytes for r in self.results if r.status != "error")

    @property
    def total_output_bytes(self) -> int:
        return sum(r.output_bytes for r in self.results if r.status != "error")

    @property
    def savings_bytes(self) -> int:
        return max(0, self.total_original_bytes - self.total_output_bytes)

    @property
    def savings_ratio(self) -> float:
        if self.total_original_bytes <= 0:
            return 0.0
        return self.savings_bytes / self.total_original_bytes

    @property
    def average_psnr(self) -> float | None:
        values = [r.psnr for r in self.compressed if r.psnr is not None]
        return sum(values) / len(values) if values else None

    @property
    def average_ssim(self) -> float | None:
        values = [r.ssim for r in self.compressed if r.ssim is not None]
        return sum(values) / len(values) if values else None


@dataclass(frozen=True)
class ScanSummary:
    count: int
    total_bytes: int
    images: tuple[Path, ...]


ProgressCallback = Callable[[int, int, CompressionResult], None]


def format_bytes(size: int | float) -> str:
    """生成适合界面显示的体积文本。"""
    value = float(max(0, size))
    units = ("B", "KB", "MB", "GB", "TB")
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} TB"


def iter_images(source: Path) -> list[Path]:
    """扫描目录下的静态/动态图片，不跟随符号链接。"""
    source = source.resolve()
    found: list[Path] = []
    for root, dirs, files in os.walk(source, followlinks=False):
        dirs[:] = [d for d in dirs if not d.startswith(".")]
        for name in files:
            if name.startswith("."):
                continue
            path = Path(root) / name
            if path.suffix.lower() in SUPPORTED_EXTENSIONS and path.is_file():
                found.append(path)
    return sorted(found, key=lambda p: str(p.relative_to(source)).casefold())


def scan_folder(source: Path, exclude: Path | None = None) -> ScanSummary:
    """快速统计待处理图片数量与体积，不读取像素。"""
    images = iter_images(source)
    if exclude is not None:
        try:
            excluded = exclude.resolve()
            images = [p for p in images if excluded not in p.resolve().parents]
        except OSError:
            pass
    total = 0
    for image in images:
        try:
            total += image.stat().st_size
        except OSError:
            pass
    return ScanSummary(len(images), total, tuple(images))


def _validate_paths(source: Path, output: Path) -> tuple[Path, Path]:
    source = source.expanduser().resolve()
    output = output.expanduser().resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"源文件夹不存在：{source}")
    if output == source:
        raise ValueError("输出目录不能与源文件夹相同，以免覆盖原图")
    if output in source.parents:
        raise ValueError("输出目录不能是源文件夹的上级目录")
    return source, output


def _base_plans(files: Iterable[Path], source: Path) -> dict[Path, Path]:
    """为每个源文件生成唯一的目标文件基名，避免 foo.jpg / foo.png 冲突。"""
    files = list(files)
    key_counts: dict[str, int] = {}
    for path in files:
        key = path.relative_to(source).with_suffix("").as_posix().casefold()
        key_counts[key] = key_counts.get(key, 0) + 1

    plans: dict[Path, Path] = {}
    used: set[str] = set()
    for path in files:
        rel_base = path.relative_to(source).with_suffix("")
        key = rel_base.as_posix().casefold()
        if key_counts.get(key, 0) > 1:
            suffix = path.suffix.lstrip(".").lower() or "img"
            rel_base = rel_base.with_name(f"{rel_base.name}_{suffix}")
        candidate = rel_base
        index = 2
        while candidate.as_posix().casefold() in used:
            candidate = rel_base.with_name(f"{rel_base.name}_{index}")
            index += 1
        used.add(candidate.as_posix().casefold())
        plans[path] = candidate
    return plans


def _flatten_for_metrics(image: Image.Image) -> Image.Image:
    """透明区域按白底合成后比较，符合网页上的实际呈现。"""
    if "A" in image.getbands() or "transparency" in image.info:
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        return Image.alpha_composite(background, rgba).convert("RGB")
    return image.convert("RGB")


def _psnr(reference: Image.Image, decoded: Image.Image) -> float:
    """分块计算 RGB PSNR，避免高分辨率图片产生过大临时数组。"""
    reference = _flatten_for_metrics(reference)
    decoded = _flatten_for_metrics(decoded)
    if decoded.size != reference.size:
        return 0.0
    width, height = reference.size
    mse_sum = 0.0
    tile_rows = 128
    for top in range(0, height, tile_rows):
        bottom = min(top + tile_rows, height)
        box = (0, top, width, bottom)
        a = np.asarray(reference.crop(box), dtype=np.float32)
        b = np.asarray(decoded.crop(box), dtype=np.float32)
        diff = a - b
        mse_sum += float(np.square(diff).sum(dtype=np.float64))
    mse = mse_sum / float(width * height * 3)
    if mse <= 1e-12:
        return 100.0
    return 20.0 * math.log10(255.0 / math.sqrt(mse))


def _box_mean(values: np.ndarray, window: int = 7) -> np.ndarray:
    """用积分图求局部均值，返回与输入同尺寸的数组。"""
    pad = window // 2
    padded = np.pad(values, ((pad, pad), (pad, pad)), mode="reflect")
    integral = np.pad(
        padded.cumsum(axis=0).cumsum(axis=1), ((1, 0), (1, 0)), mode="constant"
    )
    height, width = values.shape
    total = (
        integral[window : window + height, window : window + width]
        - integral[:height, window : window + width]
        - integral[window : window + height, :width]
        + integral[:height, :width]
    )
    return total / float(window * window)


def _alpha_psnr(reference: Image.Image, decoded: Image.Image) -> float:
    """透明图额外检查 alpha 边缘，避免换背景后出现光晕。"""
    ref_has_alpha = "A" in reference.getbands() or "transparency" in reference.info
    if not ref_has_alpha:
        return 100.0
    dec_has_alpha = "A" in decoded.getbands() or "transparency" in decoded.info
    if not dec_has_alpha:
        return 0.0
    a = np.asarray(reference.convert("RGBA").getchannel("A"), dtype=np.float32)
    b = np.asarray(decoded.convert("RGBA").getchannel("A"), dtype=np.float32)
    if a.shape != b.shape:
        return 0.0
    mse = float(np.mean((a - b) ** 2, dtype=np.float64))
    if mse <= 1e-12:
        return 100.0
    return 20.0 * math.log10(255.0 / math.sqrt(mse))


def _ssim(reference: Image.Image, decoded: Image.Image, max_side: int = 1280) -> float:
    """计算灰度全局 SSIM；大图先缩放，避免逐张比较过慢。"""
    ref_gray = _flatten_for_metrics(reference).convert("L")
    out_gray = _flatten_for_metrics(decoded).convert("L")
    if out_gray.size != ref_gray.size:
        return 0.0
    if max(ref_gray.size) > max_side:
        ratio = max_side / max(ref_gray.size)
        new_size = (
            max(1, round(ref_gray.width * ratio)),
            max(1, round(ref_gray.height * ratio)),
        )
        ref_gray = ref_gray.resize(new_size, Image.Resampling.LANCZOS)
        out_gray = out_gray.resize(new_size, Image.Resampling.LANCZOS)
    a = np.asarray(ref_gray, dtype=np.float64)
    b = np.asarray(out_gray, dtype=np.float64)

    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    mu_a = _box_mean(a)
    mu_b = _box_mean(b)
    mu_a_sq = mu_a * mu_a
    mu_b_sq = mu_b * mu_b
    mu_ab = mu_a * mu_b
    sigma_a_sq = _box_mean(a * a) - mu_a_sq
    sigma_b_sq = _box_mean(b * b) - mu_b_sq
    sigma_ab = _box_mean(a * b) - mu_ab

    numerator = (2.0 * mu_ab + c1) * (2.0 * sigma_ab + c2)
    denominator = (mu_a_sq + mu_b_sq + c1) * (sigma_a_sq + sigma_b_sq + c2)
    score = float(np.mean(numerator / denominator))
    return max(0.0, min(1.0, score))


def _icc_description(profile: ImageCms.ImageCmsProfile) -> str:
    try:
        return str(ImageCms.getProfileDescription(profile)).strip()
    except Exception:
        return ""


def _convert_to_srgb(
    image: Image.Image, icc_profile: bytes | None
) -> tuple[Image.Image, bytes | None, bool]:
    """把带 ICC 的图统一转换到 sRGB，避免不同查看器忽略 ICC 后偏色。

    返回 (处理后的图, 输出应嵌入的 ICC, 是否发生过转换)。
    """
    if not icc_profile:
        # 无 ICC 时按 Web 最常见的约定视为 sRGB。
        return image, None, False
    try:
        source_profile = ImageCms.ImageCmsProfile(io.BytesIO(icc_profile))
    except Exception:
        return image.convert("RGB"), None, False
    if "srgb" in _icc_description(source_profile).lower():
        return image, icc_profile, False

    has_alpha = "A" in image.getbands() or "transparency" in image.info
    try:
        base = image
        alpha = None
        if has_alpha:
            rgba = image.convert("RGBA")
            alpha = rgba.getchannel("A")
            base = rgba.convert("RGB")
        elif base.mode not in ("RGB", "CMYK", "L", "LAB"):
            base = base.convert("RGB")
        converted = ImageCms.profileToProfile(
            base,
            source_profile,
            _SRGB_PROFILE,
            renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
            outputMode="RGB",
        )
        if alpha is not None:
            converted = converted.convert("RGBA")
            converted.putalpha(alpha)
        return converted, _SRGB_ICC, True
    except Exception:
        # 损坏或不受支持的 profile：去掉有色 profile 的错误标记，
        # 以网页默认 sRGB 语义输出，避免把错误色彩继续传播。
        working = image.convert("RGBA" if has_alpha else "RGB")
        return working, None, False


def _encode(
    image: Image.Image,
    quality: int,
    options: CompressionOptions,
    icc_profile: bytes | None,
) -> tuple[bytes, Image.Image]:
    buffer = io.BytesIO()
    save_kwargs: dict = {"format": options.output_format.upper(), "quality": quality}
    if icc_profile:
        save_kwargs["icc_profile"] = icc_profile
    if options.output_format == "webp":
        save_kwargs.update(method=options.webp_method, alpha_quality=100)
    else:
        save_kwargs.update(speed=options.avif_speed, subsampling="4:4:4")
    image.save(buffer, **save_kwargs)
    data = buffer.getvalue()
    with Image.open(io.BytesIO(data)) as check:
        check.load()
        decoded = check.copy()
    return data, decoded


def _effective_ssim_floor(target_psnr: float, configured: float) -> float:
    """低 PSNR 目标通常对应更激进的压缩，SSIM 门槛也要相应放宽。

    保持 40 dB 以上原有行为不变；30–39 dB 用一档平滑下滑的下限，
    防止局部严重崩坏，但不会把极限压缩重新拉回高画质。
    """
    if target_psnr >= 40:
        return configured
    derived = max(0.85, 0.985 - (40.0 - target_psnr) * 0.013)
    return min(configured, derived)


def _choose_quality(
    image: Image.Image,
    icc_profile: bytes | None,
    options: CompressionOptions,
    cancel_event: threading.Event | None,
) -> tuple[bytes, int, float, float] | None:
    """二分搜索满足画质门槛的最低质量；最低质量 = 同画质下最小体积。"""
    low, high = options.quality_min, options.quality_max
    best: tuple[bytes, int, float, float] | None = None
    ssim_floor = _effective_ssim_floor(options.target_psnr, options.min_ssim)
    best_psnr = 0.0
    best_ssim = 0.0

    while low <= high:
        if cancel_event is not None and cancel_event.is_set():
            raise CompressionCancelled()
        quality = (low + high) // 2
        data, decoded = _encode(image, quality, options, icc_profile)
        psnr = _psnr(image, decoded)
        passes = psnr >= options.target_psnr
        ssim = _ssim(image, decoded) if passes else 0.0
        alpha_psnr = _alpha_psnr(image, decoded) if passes else 0.0
        passes = passes and ssim >= ssim_floor and alpha_psnr >= 48.0
        if passes:
            best = (data, quality, psnr, ssim)
            high = quality - 1
        else:
            low = quality + 1
        if quality == options.quality_max:
            best_psnr, best_ssim = psnr, ssim
    if best is None:
        # 记录最高质量的实际得分，方便告诉用户为何保留原图。
        _ = best_psnr, best_ssim
        return None
    return best


def _copy_file(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}-{threading.get_ident()}")
    try:
        shutil.copy2(source, temp)
        os.replace(temp, target)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def _write_bytes(target: Path, data: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp = target.with_name(f".{target.name}.tmp-{os.getpid()}-{threading.get_ident()}")
    try:
        with open(temp, "wb") as handle:
            handle.write(data)
        os.replace(temp, target)
    finally:
        if temp.exists():
            try:
                temp.unlink()
            except OSError:
                pass


def _friendly_error(exc: BaseException) -> str:
    if isinstance(exc, UnidentifiedImageError):
        return "无法识别的图片格式"
    if isinstance(exc, PermissionError):
        return "没有读写权限"
    if isinstance(exc, OSError) and "cannot identify" in str(exc).lower():
        return "图片已损坏或格式不受支持"
    text = str(exc).strip()
    return text[:180] if text else exc.__class__.__name__


def _process_one(
    source: Path,
    source_root: Path,
    target_base: Path,
    output_root: Path,
    options: CompressionOptions,
    cancel_event: threading.Event | None,
) -> CompressionResult:
    started = time.perf_counter()
    original_bytes = source.stat().st_size
    result = CompressionResult(
        source=source,
        output=None,
        status="error",
        original_bytes=original_bytes,
        duration=0.0,
    )
    suffix = source.suffix.lower()

    try:
        with Image.open(source) as opened:
            source_width, source_height = opened.size
            result.source_width, result.source_height = source_width, source_height
            is_animated = bool(
                getattr(opened, "is_animated", False) and getattr(opened, "n_frames", 1) > 1
            )
            if is_animated:
                target = output_root / target_base.parent / f"{target_base.name}{suffix}"
                _copy_file(source, target)
                result.output = target
                result.status = "animated"
                result.output_bytes = target.stat().st_size
                result.output_width, result.output_height = source_width, source_height
                result.message = "动图保持原样复制，避免丢失动画"
                return result

            opened.load()
            icc_profile = opened.info.get("icc_profile")
            image = ImageOps.exif_transpose(opened)
            image.load()
            if source_width != image.width or source_height != image.height:
                result.source_width, result.source_height = image.size

        image, icc_profile, color_converted = _convert_to_srgb(image, icc_profile)
        color_note = " · 已转 sRGB" if color_converted else ""

        has_alpha = "A" in image.getbands() or "transparency" in image.info
        working = image.convert("RGBA" if has_alpha else "RGB")
        if options.max_dimension and max(working.size) > options.max_dimension:
            working.thumbnail(
                (options.max_dimension, options.max_dimension),
                Image.Resampling.LANCZOS,
            )
        result.output_width, result.output_height = working.size

        chosen = _choose_quality(working, icc_profile, options, cancel_event)
        if chosen is None:
            target = output_root / target_base.parent / f"{target_base.name}{suffix}"
            _copy_file(source, target)
            result.output = target
            result.status = "kept_quality"
            result.output_bytes = target.stat().st_size
            result.message = (
                f"最高质量仍未达到 {options.target_psnr:.0f} dB，已保留原图"
            )
            return result

        data, quality, psnr, ssim = chosen
        extension = options.output_format
        target = output_root / target_base.parent / f"{target_base.name}.{extension}"

        # 转换收益过小（<2%）时不改变格式，避免多一次有损转码。
        if len(data) >= original_bytes * 0.98:
            fallback = output_root / target_base.parent / f"{target_base.name}{suffix}"
            _copy_file(source, fallback)
            result.output = fallback
            result.status = "kept_size"
            result.output_bytes = fallback.stat().st_size
            result.psnr = psnr
            result.ssim = ssim
            result.quality = quality
            result.message = "压缩收益不足 2%，已保留原图"
            return result

        if cancel_event is not None and cancel_event.is_set():
            raise CompressionCancelled()
        _write_bytes(target, data)
        result.output = target
        result.status = "compressed"
        result.output_bytes = len(data)
        result.psnr = psnr
        result.ssim = ssim
        result.quality = quality
        result.message = f"质量 {quality} · SSIM {ssim:.4f}{color_note}"
        return result
    except CompressionCancelled:
        raise
    except Exception as exc:  # 单张失败不拖垮整批任务
        result.status = "error"
        result.message = _friendly_error(exc)
        return result
    finally:
        result.duration = time.perf_counter() - started


def write_report_csv(report: BatchReport) -> Path:
    path = report.output_dir / "压缩报告.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "文件",
                "状态",
                "源文件",
                "输出文件",
                "原始字节",
                "输出字节",
                "节省比例",
                "PSNR(dB)",
                "SSIM",
                "编码质量",
                "原始尺寸",
                "输出尺寸",
                "耗时(秒)",
                "说明",
            ]
        )
        for item in report.results:
            writer.writerow(
                [
                    item.source.relative_to(report.source_dir).as_posix(),
                    item.display_status,
                    str(item.source),
                    str(item.output or ""),
                    item.original_bytes,
                    item.output_bytes,
                    f"{item.savings_ratio * 100:.1f}%",
                    f"{item.psnr:.2f}" if item.psnr is not None else "",
                    f"{item.ssim:.5f}" if item.ssim is not None else "",
                    item.quality or "",
                    f"{item.source_width}×{item.source_height}",
                    (
                        f"{item.output_width}×{item.output_height}"
                        if item.output_width
                        else ""
                    ),
                    f"{item.duration:.2f}",
                    item.message,
                ]
            )
    report.report_csv = path
    return path


def compress_folder(
    source: Path,
    output: Path | None = None,
    options: CompressionOptions | None = None,
    progress: ProgressCallback | None = None,
    cancel_event: threading.Event | None = None,
) -> BatchReport:
    """压缩一个文件夹，并返回完整报告。

    progress(已完成数, 总数, 单张结果) 在工作线程中调用；
    界面层应把回调内容放入队列，再回到 Tk 主线程更新 UI。
    """
    options = options or CompressionOptions()
    source, output = _validate_paths(
        source, output if output is not None else source.parent / f"{source.name}_web"
    )
    if cancel_event is None:
        cancel_event = threading.Event()

    started = time.perf_counter()
    report = BatchReport(source_dir=source, output_dir=output)
    output.mkdir(parents=True, exist_ok=True)
    files = [
        path
        for path in iter_images(source)
        if output not in path.resolve().parents and path.resolve() != output
    ]
    if not files:
        report.elapsed = time.perf_counter() - started
        write_report_csv(report)
        return report

    plans = _base_plans(files, source)
    total = len(files)
    processed = 0
    workers = max(1, min(int(options.workers), 16))

    executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="lightpress")
    futures: dict[Future, Path] = {}
    try:
        for path in files:
            if cancel_event.is_set():
                report.cancelled = True
                break
            future = executor.submit(
                _process_one,
                path,
                source,
                plans[path],
                output,
                options,
                cancel_event,
            )
            futures[future] = path

        for future in as_completed(futures):
            if future.cancelled():
                continue
            try:
                item = future.result()
            except CompressionCancelled:
                report.cancelled = True
                continue
            except Exception as exc:  # 理论上 _process_one 已捕获
                source_path = futures[future]
                item = CompressionResult(
                    source=source_path,
                    output=None,
                    status="error",
                    original_bytes=source_path.stat().st_size
                    if source_path.exists()
                    else 0,
                    message=_friendly_error(exc),
                )
            report.results.append(item)
            processed += 1
            if progress is not None:
                progress(processed, total, item)
            if cancel_event.is_set():
                report.cancelled = True
                for pending in futures:
                    if not pending.done():
                        pending.cancel()
    finally:
        for pending in futures:
            if not pending.done():
                pending.cancel()
        executor.shutdown(wait=True, cancel_futures=True)

    report.results.sort(key=lambda r: str(r.source.relative_to(source)).casefold())
    report.elapsed = time.perf_counter() - started
    write_report_csv(report)
    return report


def default_output_dir(source: Path) -> Path:
    """与源文件夹同级的 _web 文件夹。"""
    source = source.expanduser().resolve()
    return source.parent / f"{source.name}_web"
