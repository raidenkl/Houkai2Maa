"""准备 OCR 模型到 assets/resource/model/ocr/。

优先使用 MaaCommonAssets 子模块；子模块未初始化时回落到官方下载地址，
保证「克隆即可构建」。
"""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
import zipfile
from pathlib import Path

assets_dir = Path(__file__).parent.parent.resolve() / "assets"
ocr_dir = assets_dir / "resource" / "model" / "ocr"
submodule_ocr = assets_dir / "MaaCommonAssets" / "OCR" / "ppocr_v5" / "zh_cn"
OCR_URL = "https://download.maafw.xyz/MaaCommonAssets/OCR/ppocr_v5/ppocr_v5-zh_cn.zip"
OCR_FILES = ("det.onnx", "rec.onnx", "keys.txt")


def copy_ocr_from(source: Path) -> bool:
    if not all((source / name).is_file() for name in OCR_FILES):
        return False
    ocr_dir.mkdir(parents=True, exist_ok=True)
    for name in OCR_FILES:
        shutil.copy2(source / name, ocr_dir / name)
    print(f"OCR model copied from {source}")
    return True


def download_ocr_model() -> bool:
    """子模块缺失时直接从官方下载（与文档中的下载地址一致）。"""

    print(f"OCR submodule not found, downloading {OCR_URL} ...")
    with tempfile.TemporaryDirectory() as temp_dir:
        archive = Path(temp_dir) / "ppocr.zip"
        try:
            with urllib.request.urlopen(OCR_URL, timeout=120) as response, archive.open("wb") as handle:
                shutil.copyfileobj(response, handle)
        except OSError as error:
            print(f"Download failed: {error}")
            return False
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(temp_dir)
        return copy_ocr_from(Path(temp_dir))


def configure_ocr_model():
    if ocr_dir.exists():
        print("Found existing OCR directory, skipping default OCR model import.")
        return

    if copy_ocr_from(submodule_ocr):
        return

    if download_ocr_model():
        return

    raise SystemExit(
        "OCR model is missing. Run `git submodule update --init` or download "
        f"{OCR_URL} and place det.onnx / rec.onnx / keys.txt into {ocr_dir}"
    )


if __name__ == "__main__":
    configure_ocr_model()
    print("OCR model configured.")
