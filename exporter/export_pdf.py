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
            if img.mode in ('1', 'P'):
                img = img.convert('RGB')
            elif img.mode != 'RGB':
                img = img.convert('RGB')
            pil_images.append(img)

        if not pil_images:
            return
        first, rest = pil_images[0], pil_images[1:]
        first.save(str(output_path), save_all=True, append_images=rest)
    finally:
        for img in pil_images:
            try:
                img.close()
            except Exception:
                pass