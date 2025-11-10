"""
Due to user error, some tiffs were not created.

This script is used to create missing tiffs in the source directory.
The user is prompted to enter the path to the import file.  
The script will check that all the tiffs in the import file are present in the source directory.    
If a tiff is missing, the script will create it by converting the corresponding jpg file to a tiff file.    
The script will NOT update the import file with the new tiff filenames.
"""

import os
import sys
import csv
import logging
from pathlib import Path
from image_converter import convert_image_to_g4_tiff
from exporter.export_common import _read_import_list, _resolve_images
from dotenv import load_dotenv

load_dotenv()
NUM_DATA_COLUMNS = int(os.getenv('NUM_DATA_COLUMNS', '2'))
FILENAME_COLUMN = int(os.getenv('FILENAME_COLUMN', '1'))


logging.basicConfig(level=logging.DEBUG)

import_file = input("Enter the path to the import file:\n\t-> ").replace('&', '').replace('"', '').replace("'", "").strip()


rows = _read_import_list(import_file)

for row in rows:
    fix_list = []
    doc_name = Path(row[FILENAME_COLUMN]).stem
    page_cells = row[NUM_DATA_COLUMNS:]
    images = _resolve_images(import_file, page_cells)
    missing_images = [p for p in images if not p.exists()]
    if not images:
        continue

    for item in missing_images:
        jpg_path = item.with_suffix('.jpg')
        if not jpg_path.exists():
            logging.error(f"JPEG file not found: {jpg_path}")
            continue
        tiff_out = item.with_suffix('.tif')
        if not tiff_out.exists():
            fix_list.append(jpg_path)

logging.info(f"{len(fix_list)} missing tiffs found")
# for item in fix_list:
#     convert_image_to_g4_tiff(item)