"""轻压 · 视觉无损批量压缩。"""

from .core import (
    MAX_TARGET_PSNR,
    MIN_TARGET_PSNR,
    STATUS_LABELS,
    SUPPORTED_EXTENSIONS,
    BatchReport,
    CompressionOptions,
    CompressionResult,
    ScanSummary,
    compress_folder,
    default_output_dir,
    format_bytes,
    scan_folder,
    write_report_csv,
)

__all__ = [
    "BatchReport",
    "CompressionOptions",
    "CompressionResult",
    "MAX_TARGET_PSNR",
    "MIN_TARGET_PSNR",
    "STATUS_LABELS",
    "SUPPORTED_EXTENSIONS",
    "ScanSummary",
    "compress_folder",
    "default_output_dir",
    "format_bytes",
    "scan_folder",
    "write_report_csv",
]
