import os
import csv
from pathlib import Path
from typing import List, Tuple
from PIL import Image


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


def _save_multipage_tiff(output_path: Path, images: List[Path]) -> None:
    """Save a list of images as a multipage TIFF.

    Preserves original image modes - only applies Group 4 compression to 1-bit images.
    Color images are kept in their original format.
    """
    pil_images: List[Image.Image] = []
    try:
        for p in images:
            img = Image.open(str(p))
            # Keep original mode - don't force conversion to 1-bit
            # Only convert palette images to RGB for better compatibility
            if img.mode == 'P':
                img = img.convert('RGB')
            pil_images.append(img)

        if not pil_images:
            return

        first, rest = pil_images[0], pil_images[1:]
        save_kwargs = {'save_all': True, 'append_images': rest}
        
        # Only use Group 4 compression if ALL pages are 1-bit
        if all(img.mode == '1' for img in pil_images):
            save_kwargs.update({'compression': 'group4'})
        # For mixed or color images, use LZW compression (good for both color and grayscale)
        else:
            save_kwargs.update({'compression': 'tiff_lzw'})
            
        first.save(str(output_path), format='TIFF', **save_kwargs)
    finally:
        for img in pil_images:
            try:
                img.close()
            except Exception:
                pass


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
        except Exception:
            pass

        try:
            _save_pdf(pdf_out, images)
            num_pdfs += 1 if pdf_out.exists() else 0
        except Exception:
            pass

    return num_tiffs, num_pdfs


