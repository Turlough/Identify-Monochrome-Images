from pathlib import Path
from typing import List
import img2pdf

def _save_pdf(output_path: Path, images: List[Path]) -> None:
    """Save a list of images as a single multipage PDF."""
    if not images:
        return

    with open(output_path, "wb") as fh:
        fh.write(img2pdf.convert([str(p) for p in images]))
