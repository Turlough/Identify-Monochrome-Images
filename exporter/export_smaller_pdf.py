import os
from pathlib import Path
from typing import List
import img2pdf
import logging

logging.basicConfig(level=logging.INFO)

def _save_pdf(output_path: Path, images: List[Path]) -> None:
    """Save a list of images as a single multipage PDF."""
    if not images:
        return
    logging.info(f"Saving PDF: {os.path.basename(output_path)}")
    with open(output_path, "wb") as fh:
        fh.write(img2pdf.convert([str(p) for p in images]))
