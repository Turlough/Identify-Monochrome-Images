import csv
from pathlib import Path
from typing import List, Tuple
import logging
import numpy as np
from PIL import Image
from .export_pdf import _save_pdf
from .export_mpt_imagemagick import _save_multipage_tiff

logging.basicConfig(level=logging.INFO)

def _read_import_list(import_file: str) -> List[List[str]]:
    """Read the import text/csv file into rows.

    Each row: [document_name, page1, page2, ...]
    Image references can be absolute or relative to the import file directory.
    """
    rows: List[List[str]] = []
    with open(import_file, 'r', encoding='utf-8') as f:
        reader = csv.reader(f)
        for row in reader:
            # skip empty/short rows
            if len(row) > 1:
                rows.append([cell.strip() for cell in row])
    return rows

def _resolve_images(import_file: str, page_cells: List[str]) -> List[Path]:
    """Resolve page image paths relative to the import file directory when needed."""
    base_dir = Path(import_file).parent
    resolved: List[Path] = []
    for cell in page_cells:
        if not cell:
            continue
        p = Path(cell)
        if not p.is_absolute():
            p = base_dir / cell
        resolved.append(p)
    return resolved

def _ensure_output_dirs(import_file: str) -> Tuple[Path, Path]:
    """Create sibling folders '<folder>_mpt' and '<folder>_pdf'."""
    images_folder = Path(import_file).parent
    parent = images_folder.parent
    suffix = images_folder.name
    mpt_dir = parent / f"{suffix}_mpt"
    pdf_dir = parent / f"{suffix}_pdf"
    mpt_dir.mkdir(parents=True, exist_ok=True)
    pdf_dir.mkdir(parents=True, exist_ok=True)
    return mpt_dir, pdf_dir



def export_from_import_file(import_file: str) -> Tuple[int, int]:
    """Create multipage TIFF and PDF per document row in the import file.

    Returns a tuple of (num_tiffs_created, num_pdfs_created).
    """
    rows = _read_import_list(import_file)
    mpt_dir, pdf_dir = _ensure_output_dirs(import_file)

    num_tiffs = 0
    num_pdfs = 0

    for row in rows:
        doc_name = Path(row[0]).stem  # Column 1 is the image/document name base
        page_cells = row[1:]
        images = _resolve_images(import_file, page_cells)
        images = [p for p in images if p.exists()]
        if not images:
            continue

        tiff_out = mpt_dir / f"{doc_name}.tif"
        pdf_out = pdf_dir / f"{doc_name}.pdf"

        try:
            _save_multipage_tiff(tiff_out, images)
            num_tiffs += 1 if tiff_out.exists() else 0
        except Exception as e:
            logging.error(f"Error saving TIFF: {e}")
            pass

        try:
            _save_pdf(pdf_out, images)
            num_pdfs += 1 if pdf_out.exists() else 0
        except Exception as e:
            logging.error(f"Error saving PDF: {e}")
            pass

    return num_tiffs, num_pdfs


