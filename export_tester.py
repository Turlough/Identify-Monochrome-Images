from exporter import export_from_import_file
from pathlib import Path
from PIL import Image
import os
from dotenv import load_dotenv
import logging

# Load environment variables
load_dotenv()
NUM_DATA_COLUMNS = int(os.getenv('NUM_DATA_COLUMNS', '2'))
FILENAME_COLUMN = int(os.getenv('FILENAME_COLUMN', '1'))

logging.basicConfig(level=logging.DEBUG)

import_file = input("Enter the path to the import file:\n\t-> ").replace('&', '').replace('"', '').replace("'", "").strip()
if not import_file:
    logging.error("No import file provided")
    exit(1)
if not os.path.exists(import_file):
    logging.error(f"Import file does not exist: {import_file}")
    exit(1)

num_tiffs, num_pdfs = export_from_import_file(import_file)

logging.info(f"Exported {num_tiffs} TIFFs and {num_pdfs} PDFs")

# Get base directory from import file path
base_dir = os.path.dirname(import_file)
mpt_dir = Path(base_dir + "_mpt") 

# Read the import file to get expected page counts

failed_pages = check_page_counts(mpt_dir)
if failed_pages:
    logging.error(f"Failed page counts: {failed_pages}")
    exit(1)
else:
    logging.info("All page counts match")


