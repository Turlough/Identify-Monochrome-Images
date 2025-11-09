import csv
from pathlib import Path
from typing import List, Tuple
import logging
import numpy as np
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, as_completed
import time
import os
from dotenv import load_dotenv
from .export_smaller_pdf import _save_pdf
from .export_mpt_imagemagick import _save_multipage_tiff

logging.basicConfig(level=logging.INFO)

# Load environment variables
load_dotenv()
NUM_DATA_COLUMNS = int(os.getenv('NUM_DATA_COLUMNS', '2'))
FILENAME_COLUMN = int(os.getenv('FILENAME_COLUMN', '1'))
REPLACE_OUTPUT_FILES = os.getenv('REPLACE_OUTPUT_FILES', 'False').lower() == 'true'
CONCURRENT_EXPORT = os.getenv('CONCURRENT_EXPORT', 'False').lower() == 'true'

if REPLACE_OUTPUT_FILES:
    logging.info("REPLACE_OUTPUT_FILES is True, existing output files will be replaced")
else:
    logging.info("REPLACE_OUTPUT_FILES is False, existing output files will not be replaced")   

if CONCURRENT_EXPORT:
    logging.info("CONCURRENT_EXPORT is True, using concurrent export")
else:
    logging.info("CONCURRENT_EXPORT is False, using single-threaded export")

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



def _export_single_document(row: List[str], import_file: str, mpt_dir: Path, pdf_dir: Path) -> Tuple[str, bool, bool]:
    """Export a single document (both TIFF and PDF).
    
    Returns: (doc_name, tiff_success, pdf_success)
    """
    doc_name = Path(row[FILENAME_COLUMN]).stem
    page_cells = row[NUM_DATA_COLUMNS:]
    images = _resolve_images(import_file, page_cells)
    images = [p for p in images if p.exists()]
    
    if not images:
        return doc_name, False, False

    tiff_out = mpt_dir / f"{doc_name}.tif"
    pdf_out = pdf_dir / f"{doc_name}.pdf"
    
    tiff_success = False
    pdf_success = False

    try:
        if not REPLACE_OUTPUT_FILES and tiff_out.exists():
            logging.info(f"TIFF already exists: {tiff_out}")
            return doc_name, True, False
        _save_multipage_tiff(tiff_out, images)
        tiff_success = tiff_out.exists()
    except Exception as e:
        logging.error(f"Error saving TIFF for {doc_name}: {e}")

    try:
        if not REPLACE_OUTPUT_FILES and pdf_out.exists():
            logging.info(f"PDF already exists: {pdf_out}")
            return doc_name, True, False
        _save_pdf(pdf_out, images)
        pdf_success = pdf_out.exists()
    except Exception as e:
        logging.error(f"Error saving PDF for {doc_name}: {e}")

    return doc_name, tiff_success, pdf_success


def export_from_import_file(import_file: str) -> Tuple[int, int]:
    """Create multipage TIFF and PDF per document row in the import file.

    Returns a tuple of (num_tiffs_created, num_pdfs_created).
    """
    rows = _read_import_list(import_file)
    mpt_dir, pdf_dir = _ensure_output_dirs(import_file)

    num_tiffs = 0
    num_pdfs = 0

    for row in rows:
        doc_name = Path(row[FILENAME_COLUMN]).stem
        page_cells = row[NUM_DATA_COLUMNS:]
        images = _resolve_images(import_file, page_cells)
        images = [p for p in images if p.exists()]
        if not images:
            continue

        tiff_out = mpt_dir / f"{doc_name}.tif"
        pdf_out = pdf_dir / f"{doc_name}.pdf"

        try:
            if not REPLACE_OUTPUT_FILES and tiff_out.exists():
                logging.info(f"TIFF already exists: {tiff_out}")
                continue
            _save_multipage_tiff(tiff_out, images)
            num_tiffs += 1 if tiff_out.exists() else 0
        except Exception as e:
            logging.error(f"Error saving TIFF: {e}")
            pass

        try:
            if not REPLACE_OUTPUT_FILES and pdf_out.exists():
                logging.info(f"PDF already exists: {pdf_out}")
                continue
            _save_pdf(pdf_out, images)
            num_pdfs += 1 if pdf_out.exists() else 0
        except Exception as e:
            logging.error(f"Error saving PDF: {e}")
            pass

    return num_tiffs, num_pdfs


def export_from_import_file_concurrent(import_file: str, progress_callback=None) -> Tuple[int, int]:
    """Create multipage TIFF and PDF per document row in the import file using concurrent processing.

    Args:
        import_file: Path to the import file
        progress_callback: Optional callback function that receives (completed, total, doc_name, tiff_success, pdf_success)
        
    Returns a tuple of (num_tiffs_created, num_pdfs_created).
    """
    rows = _read_import_list(import_file)
    mpt_dir, pdf_dir = _ensure_output_dirs(import_file)
    
    # Filter out rows with no valid images
    valid_rows = []
    for row in rows:
        page_cells = row[NUM_DATA_COLUMNS:]
        images = _resolve_images(import_file, page_cells)
        images = [p for p in images if p.exists()]
        if images:
            valid_rows.append(row)
    
    if not valid_rows:
        return 0, 0
    
    num_tiffs = 0
    num_pdfs = 0
    completed = 0
    total = len(valid_rows)
    
    # If concurrent export is disabled, run single-threaded with progress updates
    if not CONCURRENT_EXPORT:
        for row in valid_rows:
            try:
                doc_name, tiff_success, pdf_success = _export_single_document(row, import_file, mpt_dir, pdf_dir)
                completed += 1
                if tiff_success:
                    num_tiffs += 1
                if pdf_success:
                    num_pdfs += 1
                if progress_callback:
                    progress_callback(completed, total, doc_name, tiff_success, pdf_success)
            except Exception as e:
                logging.error(f"Error processing document: {e}")
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, "Error", False, False)
        return num_tiffs, num_pdfs

    # Use ThreadPoolExecutor for concurrent processing
    max_workers = min(4, len(valid_rows))  # Limit to 4 concurrent exports

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_row = {
            executor.submit(_export_single_document, row, import_file, mpt_dir, pdf_dir): row 
            for row in valid_rows
        }
        
        # Process completed tasks
        for future in as_completed(future_to_row):
            try:
                doc_name, tiff_success, pdf_success = future.result()
                completed += 1
                
                if tiff_success:
                    num_tiffs += 1
                if pdf_success:
                    num_pdfs += 1
                
                # Call progress callback if provided
                if progress_callback:
                    progress_callback(completed, total, doc_name, tiff_success, pdf_success)
                    
            except Exception as e:
                logging.error(f"Error processing document: {e}")
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, "Error", False, False)
    
    return num_tiffs, num_pdfs


