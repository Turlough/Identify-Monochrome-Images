from exporter import export_from_import_file
from pathlib import Path
from PIL import Image
import os

import_file = r"C:\_PV\DAHG\EXPORT-small.TXT"

num_tiffs, num_pdfs = export_from_import_file(import_file)

print(f"Exported {num_tiffs} TIFFs and {num_pdfs} PDFs")


# Get base directory from import file path
base_dir = os.path.dirname(import_file)
mpt_dir = Path(base_dir + "_mpt") 

# Read the import file to get expected page counts
expected_pages = {}
with open(import_file, 'r', encoding='utf-8') as f:
    for line in f:
        parts = line.strip().split(',')
        if len(parts) > 1:
            tiff_name = parts[0].strip() + '.tif'
            # Count input files and build dictionary
            expected_count = sum(1 for p in parts[1:])
            expected_pages[tiff_name] = expected_count

# Check actual page counts in output TIFFs
print("\nVerifying page counts:")
for tiff_name, expected_count in expected_pages.items():
    tiff_path = mpt_dir / tiff_name
    if tiff_path.exists():
        with Image.open(tiff_path) as img:
            actual_count = 0
            try:
                while True:
                    actual_count += 1
                    img.seek(img.tell() + 1)
            except EOFError:
                pass
            
            if actual_count == expected_count:
                print(f"{tiff_name}: OK ({actual_count} pages)")
            else:
                print(f"{tiff_name}: MISMATCH - Expected {expected_count}, got {actual_count} pages")
    else:
        print(f"{tiff_name}: File not found")




