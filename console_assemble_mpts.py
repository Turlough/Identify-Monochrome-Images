"""
This script takes the Small_File_List.csv and Large_File_List.csv files and assembles the files into the final delivery.
These are produced by the console_delivery_size_splitter.py script.
The script will prompt the user for the folder to search for the 'File_List" files.

PDF and MPT files are handled differently. This script is for MPTs.

MPTs:
See the examples_and_samples/MPT_Structure.TXT file for the output folder structure
and the CDDOC.DAT file structure.
"""

import os
import shutil
from tqdm import tqdm

KB = 1024
MB = KB * KB
GB = MB * KB
max_bytes = 30 * GB


def create_mpt_delivery_folder_structure(base_folder: str, delivery_folder_count: int) -> tuple[str, str]:
    base_folder = os.path.join(select_folder, f"{base_folder}_{delivery_folder_count}")

    # IMAGES/0001 directory holds the delivery TIFF files.
    images_folder = os.path.join(base_folder, "IMAGES", "0001")
    os.makedirs(images_folder, exist_ok=True)

    # APP_SPEC/XFERDATA contains the manifest; ensure the folder and file exist.
    manifest_folder = os.path.join(base_folder, "APP_SPEC", "XFERDATA")
    os.makedirs(manifest_folder, exist_ok=True)
    cddoc_path = os.path.join(manifest_folder, "CDDOC.DAT")
    if not os.path.exists(cddoc_path):
        with open(cddoc_path, "w", encoding="utf-8"):
            pass

    return images_folder, cddoc_path

select_folder = input("Select the folder to search for the 'File_List' files: ")
small_file_list = os.path.join(select_folder, "Small_File_List.csv")
large_file_list = os.path.join(select_folder, "Large_File_List.csv")

small_files = []
small_files_count = 0
total_small_size = 0
small_delivery_folder_count = 1
small_delivery_folder = "MPTs_small"
create_mpt_delivery_folder_structure(small_delivery_folder, small_delivery_folder_count)

large_files = []
large_files_count = 0
total_large_size = 0
large_delivery_folder_count = 1
large_delivery_folder = "MPTs_large"


with open(small_file_list, 'r') as file:

    images_folder, cddoc_path = create_mpt_delivery_folder_structure(small_delivery_folder, small_delivery_folder_count)

    for line in tqdm(file, desc="Processing Small Files"):
        # Skip header
        if line.startswith("Batch"):
            continue

        if total_small_size * KB > max_bytes:
            with open(cddoc_path, "w", encoding="utf-8") as file:
                for customer_ref, rel_filename in small_files:
                    file.write(f"0001;{customer_ref}; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ;\\IMAGES\\0001\\{rel_filename};TIFF;0;0;0;0;\n")
            small_delivery_folder_count += 1
            images_folder, cddoc_path = create_mpt_delivery_folder_structure(small_delivery_folder, small_delivery_folder_count)
            total_small_size = 0

        cells = line.strip().split(',')
        if len(cells) < 6:
            raise ValueError(f"Invalid line: {line} in Small_File_List.csv")

        customer_ref = cells[1].strip()
        source_file = cells[3].strip().replace(".pdf", ".tif").replace("_pdf", "_mpt")
        rel_filename = os.path.basename(source_file)
        dest_file = os.path.join(images_folder, rel_filename)
        mpt_size = float(cells[4].strip())

        if not os.path.exists(dest_file):
            shutil.copy(source_file, dest_file)

        small_files.append((customer_ref, rel_filename))
        total_small_size += mpt_size
        small_files_count += 1
    

    with open(cddoc_path, "w", encoding="utf-8") as file:
        for customer_ref, rel_filename in small_files:
            file.write(f"0001;{customer_ref}; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ;\\IMAGES\\0001\\{rel_filename};TIFF;0;0;0;0;\n")

print(f"""
_SMALL FILES REPORT_________________________________________________________
Num Folders: {small_delivery_folder_count}
Num Files:   {small_files_count}
_________________________________________________________
""")

with open(large_file_list, 'r') as file:
    images_folder, cddoc_path = create_mpt_delivery_folder_structure(large_delivery_folder, large_delivery_folder_count)

    for line in tqdm(file, desc="Processing Large Files"):
        # Skip header
        if line.startswith("Batch"):
            continue

        if total_large_size * KB > max_bytes:
            with open(cddoc_path, "w", encoding="utf-8") as file:
                for customer_ref, rel_filename in large_files:
                    file.write(f"0001;{customer_ref}; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ;\\IMAGES\\0001\\{rel_filename};TIFF;0;0;0;0;\n")

            large_delivery_folder_count += 1
            images_folder, cddoc_path = create_mpt_delivery_folder_structure(large_delivery_folder, large_delivery_folder_count)
            total_large_size = 0

        cells = line.strip().split(',')
        if len(cells) < 6:
            raise ValueError(f"Invalid line: {line} in Large_File_List.csv")

        customer_ref = cells[1].strip()
        source_file = cells[3].strip().replace(".pdf", ".tif").replace("_pdf", "_mpt")
        rel_filename = os.path.basename(source_file)
        dest_file = os.path.join(images_folder, rel_filename)
        mpt_size = float(cells[4].strip())

        if not os.path.exists(dest_file):
            shutil.copy(source_file, dest_file)

        large_files.append((customer_ref, rel_filename))
        total_large_size += mpt_size
        large_files_count += 1
    

    with open(cddoc_path, "w", encoding="utf-8") as file:
        for customer_ref, rel_filename in large_files:
            file.write(f"0001;{customer_ref}; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ; ;\\IMAGES\\0001\\{rel_filename};TIFF;0;0;0;0;\n")

print(f"""
_LARGE FILES REPORT_________________________________________________________
Num Folders: {large_delivery_folder_count}
Num Files:   {large_files_count}
_________________________________________________________
""")