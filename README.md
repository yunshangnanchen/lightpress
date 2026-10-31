# 轻压 · 批量网页图片压缩

<p align="center">
  <img src="assets/logo.png" width="96" height="96" alt="Pixel Matrix logo">
</p>

<p align="center">
  <img alt="Windows" src="https://img.shields.io/badge/platform-Windows-0f8f76">
  <img alt="Python 3.10+" src="https://img.shields.io/badge/Python-3.10%2B-0f8f76">
  <img alt="License MIT" src="https://img.shields.io/badge/license-MIT-0f8f76">
</p>

轻压是一个面向网站素材的 Windows 桌面批量图片压缩工具：**把一个文件夹拖进窗口，整批输出 AVIF / WebP**。它会对每张图单独搜索「刚好达到画质目标」的最低编码质量，在 30–48 dB 范围内尽量压缩体积，同时保留透明通道和目录结构。

- 默认 **44 dB + AVIF**：优先保证网页上的视觉清晰度。
- 提供 **30 dB 极限压缩档**：用于缩略图、背景图和非重点配图。
- 原图不会被修改，结果写入旁边的 `_web` 文件夹。
- 纯本地离线运行，**不需要账号、API Key，也不会上传图片**。

![轻压深色模式](docs/preview.png)

*浅色模式：[docs/preview-light.png](docs/preview-light.png)*

## 核心特性

- **文件夹直接拖入**：递归处理所有子文件夹，保留相对目录结构。
- **逐张自适应压缩**：对每张图二分搜索最低编码质量，而不是全局套用一个质量值。
- **画质双门槛**：以 PSNR 为目标，SSIM 作为辅助保护；透明图额外检查 alpha 边缘。
- **色彩统一到 sRGB**：Display P3、Adobe RGB 等广色域图片先做色彩管理转换，再编码，避免不同浏览器/查看器忽略 ICC 造成偏色。
- **30–48 dB 可调**：界面滑杆 + `30 / 36 / 40 / 44 / 48` 快捷档位。
- **AVIF / WebP 可选**：默认 AVIF，同画质通常更小；WebP 兼容范围更广。
- **深色 / 浅色 / 跟随系统**：默认跟随 Windows 应用主题，并能在系统切换时自动刷新。
- **安全输出**：不覆盖源文件，输出目录可自定义。
- **自动报告**：每批输出 `压缩报告.csv`，包含体积、PSNR、SSIM、质量值和说明。
- **稳健批处理**：单张失败不影响整批，动图原样复制，可随时取消。

## 画质目标

| 目标 | 适用场景 | 体积趋势 |
| --- | --- | --- |
| 30–34 dB | 极限压缩：缩略图、背景、预加载占位 | 极小；细节明显减少 |
| 35–39 dB | 高压缩：非重点配图、画廊缩略图 | 更小 |
| 40–42 dB | 轻量：背景图、内容配图 | 小 |
| 43–44 dB | 日常网页配图（默认 44） | 均衡 |
| 45–46 dB | 首屏大图、商品图 | 偏大 |
| 47–48 dB | 接近像素级保留的重点图 | 最大 |

工具追求的是：**在不低于目标值的前提下，找到体积最小的编码质量**。最终 PSNR 通常在目标附近，简单图形可能高于 48 dB。

> 30–39 dB 属于明显有损压缩，可能出现色块、文字发虚和细节丢失，不适合重要商品图或带文字的界面截图。
>
> 默认 44 dB 是「工程意义上的视觉高保真」，不是数学无损。真正逐像素无损请保留原始 PNG，或使用专门的 WebP lossless 工作流。

## 快速开始

### 直接运行（Windows）

1. 安装 **Python 3.10+**（推荐 3.11+），安装时勾选 **Add Python to PATH**。
2. 双击 `安装依赖.bat`。Pillow 和 NumPy 会安装到项目内的 `.deps`，不会污染其他 Python 环境。
3. 双击 `启动工具.bat`。
4. 把图片文件夹拖入虚线区域，选择画质和格式，点击「开始压缩」。

如果启动失败，双击 `调试启动.bat`，命令行窗口会保留并显示错误信息。

### 从源码运行

```powershell
# 下载或克隆本项目后，在项目根目录运行
python -m pip install -r requirements.txt
python app.py
```

拖拽组件已经放在 `vendor/tkinterdnd2`，不需要额外安装。

Windows 10/11、Python 3.10+、Tk 8.6、Pillow 12+、NumPy 1.26+。主要面向 Windows；拖拽依赖为 Windows 预编译组件。

## 使用说明

1. 拖入文件夹（不是单个文件），工具会递归扫描子目录。
2. 选择画质目标和输出格式：
   - **AVIF**：默认，同画质体积通常最小，现代浏览器推荐。
   - **WebP**：兼容范围更广；高纹理照片在 44 dB 附近可能达到编码器上限，此时会保留原图。
3. 需要限制网页展示尺寸时，可选「最大边长」；默认保持原始分辨率。
4. 点击开始，完成后可直接打开输出文件夹或 CSV 报告。

支持格式：

```
JPG / JPEG / PNG / WebP / AVIF / TIFF / TIF / BMP / GIF
```

动图 GIF / WebP / AVIF 原样复制，避免丢帧；不支持 SVG、HEIC/HEIF。

## 输出规则

以源文件夹 `D:\相册` 为例：

```text
D:\相册\                       ← 原图，始终不改动
D:\相册_web\                   ← 输出目录
├─ photo.avif
├─ screenshot.avif
├─ nested\
│  └─ art.avif
├─ already-small.jpg           ← 收益不足 2% 时保留原图
└─ 压缩报告.csv
```

- 保留子目录结构；同名不同后缀会自动生成不冲突的文件名。
- 输出收益不足 **2%** 时保留原图，避免额外有损转码。
- 达到不了画质门槛时保留原图，并在报告中说明。
- 如果输出目录已存在，工具会询问是否继续，只覆盖同名输出，不碰源文件。
- 网站引用后缀会变化（如 `.jpg` → `.avif`），上线时需要同步更新图片路径；建议用 `<picture>` 给 AVIF 配置 WebP / JPEG 回退。

## 工作原理

1. 递归扫描图片，应用 EXIF 方向信息。
2. 将广色域图片通过 LittleCMS（Pillow ImageCms）统一转换到 sRGB。
3. 在编码质量范围内二分搜索：
   - 每次编码后立即解码，并按白底合成透明区域计算；
   - 检查整图 PSNR、缩小到 ≤1280 px 的灰度 SSIM；
   - 透明图额外要求 alpha 通道 PSNR ≥ 48 dB；
   - 40 dB 以上使用严格的 SSIM ≥ 0.985；30–39 dB 按目标自动放宽 SSIM 下限，避免局部崩坏。
4. 保留能达标的最低质量，写入输出目录并生成 CSV。

AVIF 使用 Pillow 的编码器，4:4:4 色度采样；WebP 使用 method 6。

## 命令行

```powershell
# 默认 44 dB、AVIF，输出到 相册_web
python compress.py "D:\相册"

# 极限压缩，适合缩略图 / 背景
python compress.py "D:\缩略图" --target 30

# WebP + 较高压缩
python compress.py "D:\相册" --target 42 --format webp

# 指定输出目录，并限制最长边
python compress.py "D:\相册" -o "D:\网站\assets" --max-dimension 2560

# 多个文件夹会分别输出到各自的 _web
python compress.py "D:\文章图" "D:\商品图" --target 44
```

参数：

```text
inputs                 一个或多个图片文件夹
-o, --output           输出目录（仅单输入时可用）
--target               目标 PSNR，30–48，默认 44；30–39 为明显有损
--format               avif 或 webp，默认 avif
--max-dimension        最大边长，默认 0（不缩放）
--workers              并行数，默认 4
-v, --verbose          逐张输出结果
```

退出码：`0` 全部成功；`1` 有失败图片；`130` 手动取消。

## 项目结构

```text
visual-compressor/
├─ 启动工具.bat
├─ 安装依赖.bat
├─ 调试启动.bat
├─ app.py                 # 图形界面
├─ theme.py               # 深浅色、系统主题、标题栏
├─ compress.py            # 命令行入口
├─ compressor/
│  ├─ core.py             # 扫描、色彩管理、PSNR/SSIM、编码、报告
│  └─ __init__.py
├─ vendor/
│  └─ tkinterdnd2/        # 拖拽组件及第三方许可证
├─ assets/                # Logo、深浅色标记、应用图标
├─ docs/                  # README 截图
├─ tests/
│  └─ test_core.py
├─ requirements.txt
├─ LICENSE
├─ THIRD_PARTY_NOTICES.md
├─ .gitignore
└─ .gitattributes
```

`settings.json`、日志、`.deps`、测试输出和 `_web` 结果都是本地生成的，已加入 `.gitignore`。

## 安全与隐私

- 所有图片处理都在本机完成，运行时不发起网络请求，也没有遥测。
- **不需要任何 API Key、账号、Cookie 或云端服务**；仓库中不包含 `.env`、Token 或密钥文件。
- 默认移除 EXIF、XMP 等元数据，只保留必要的图像数据；色彩会被转换并标记为 sRGB。
- 工具只在本地写入输出目录和报告，源目录只读。
- 唯一保存的本地偏好是项目目录下的 `settings.json`，记录外观模式，已被 `.gitignore` 排除。
- 上传 GitHub 时，请把仓库根目录设为本 `visual-compressor` 文件夹，不要把上级工作区、原始图片、`压缩` 输出、`压缩_色彩修复备份`、`.deps`、日志或任何 `api-key` / `.env` 文件一起提交。

## 常见问题

**拖拽没反应？**

确认拖的是文件夹；可以点击虚线区域选择文件夹。若拖拽组件加载失败，双击 `调试启动.bat` 查看错误。

**为什么有的图片提示「保留原图」？**

原图本身已经很小，输出收益不足 2%；或者当前格式在最高质量下也无法达到目标 dB（WebP 更常见）。改用 AVIF 或降低目标值。

**会影响原图吗？**

不会。源目录只读，只写输出目录。首次处理重要相册仍建议备份。

**为什么统一转成 sRGB？**

P3 等广色域原图如果直接将 ICC 嵌入 AVIF，不同浏览器和图片查看器对 ICC 的支持不一致，可能明显偏色。统一色彩管理到 sRGB 后，网页端显示更稳定。

**图片能压多少？**

取决于源图。未优化的大图或 PNG 截屏通常可节省 50%–90%；已经过 CDN 优化的 JPEG 可能节省很少，甚至保留原图。

**为什么 30 dB 看起来不够清晰？**

30 dB 是极限压缩档，设计目标是缩略图/背景图。带文字、商品细节或人物面部的图片建议使用 42 dB 以上；默认 44 dB 更安全。

## 开发与测试

```powershell
python -m py_compile app.py theme.py compress.py compressor/core.py

# 生成测试图，验证扫描、压缩、sRGB、透明度、30 dB 档和报告
python tests/test_core.py
```

## 许可证

本项目代码以 [MIT License](LICENSE) 发布。随附的 `vendor/tkinterdnd2` 采用 MIT License，TkDND 使用其原始许可条款，详见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。
