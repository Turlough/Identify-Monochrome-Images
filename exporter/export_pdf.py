import os
from pathlib import Path
from typing import List
from PIL import Image

def _save_pdf(output_path: Path, images: List[Path]) -> None:
    """Save a list of images as a single multipage PDF."""
    pil_images: List[Image.Image] = []
    try:
        for p in images:
            img = Image.open(str(p))

            if img.mode == "1":
                processed = img
            elif img.mode in ("L", "RGB"):
                processed = img
            elif img.mode == "P":
                try:
                    palette_mode = img.palette.mode if img.palette else None
                except Exception:
                    palette_mode = None
                if palette_mode in ("RGB", "RGBA", "CMYK"):
                    processed = img.convert("RGB")
                else:
                    processed = img.convert("L")
            else:
                processed = img.convert("RGB")

            pil_images.append(processed)

        first, *rest = pil_images
        first.save(str(output_path), save_all=True, append_images=rest)
    finally:
        for img in pil_images:
            try:
                img.close()
            except Exception:
                pass