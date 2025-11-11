"""
This script takes the Small_File_List.csv and Large_File_List.csv files and assembles the files into the final delivery.
These are produced by the console_delivery_size_splitter.py script.
The script will prompt the user for the folder to search for the 'File_List" files.

PDF and MPT files are handled differently. This script is for PDFs.

PDFs:
For each file path in the 'File_List' files, the script will copy the image files to the final delivery folders.
The script will also create a manifest.txt file in the final delivery folders.
The manifest.txt file will contain the list of files in the final delivery.
The script will also create a manifest.txt file in the final delivery folders.

No delivery folder may exceed max_bytes in size.

The final delivery folders will be named "PDFs_small_x" and "PDFs_large_x" 
where x increments from 1 each time a new delivery folder is created 
(i.e. The previous delivery folder is larger than max_bytes").

"""
import os
import shutil
from tqdm import tqdm


KB = 1024
MB = KB * KB
GB = MB * KB
max_bytes = 30 * GB

select_folder = input("Select the folder to search for the 'File_List' files: ")
small_file_list = os.path.join(select_folder, "Small_File_List.csv")
large_file_list = os.path.join(select_folder, "Large_File_List.csv")

small_files = []
small_files_count = 0
total_small_size = 0
small_delivery_folder_count = 1
small_delivery_folder = os.path.join(select_folder, f"PDFs_small_{small_delivery_folder_count}")
os.makedirs(small_delivery_folder, exist_ok=True)

large_files = []
large_files_count = 0
total_large_size = 0
large_delivery_folder_count = 1
large_delivery_folder = os.path.join(select_folder, f"PDFs_large_{large_delivery_folder_count}")
os.makedirs(large_delivery_folder, exist_ok=True)



with open(small_file_list, 'r') as file:
    for line in tqdm(file, desc="Processing Small Files"):
        # Skip header
        if line.startswith("Batch"):
            continue

        if total_small_size * KB > max_bytes:
            small_delivery_folder_count += 1
            small_delivery_folder = os.path.join(select_folder, f"PDFs_small_{small_delivery_folder_count}")
            os.makedirs(small_delivery_folder, exist_ok=True)
            small_files = []
            total_small_size = 0

        cells = line.strip().split(',')
        if len(cells) < 6:
            raise ValueError(f"Invalid line: {line} in Small_File_List.csv")

        box_name = cells[0].strip().split(' ')[-1][:6]
        customer_ref = cells[1].strip()
        filename = cells[2].strip()
        source_file = cells[3].strip()
        rel_filename = os.path.basename(source_file)
        dest_file = os.path.join(small_delivery_folder, rel_filename)
        mpt_size = float(cells[4].strip())
        pdf_size = float(cells[5].strip())

        if not os.path.exists(dest_file):
            shutil.copy(source_file, dest_file)

        small_files.append((box_name, customer_ref, rel_filename))
        total_small_size += pdf_size
        small_files_count += 1

# Write the manifest to the last folder
with open(os.path.join(small_delivery_folder, "_manifest.txt"), 'w') as file:
    file.write(f"BoxNo,RefCode,Filepath\n")
    for box_name, customer_ref, rel_filename in small_files:
        file.write(f"{box_name},{customer_ref},{rel_filename}\n")

print(f"""
_SMALL FILES REPORT_________________________________________________________
Num Folders: {small_delivery_folder_count}
Num Files:   {small_files_count}
_________________________________________________________
""")


with open(large_file_list, 'r') as file:
    for line in tqdm(file, desc="Processing Large Files"):
        # Skip header
        if line.startswith("Batch"):
            continue

        if total_large_size * KB > max_bytes:
            large_delivery_folder_count += 1
            large_delivery_folder = os.path.join(select_folder, f"PDFs_large_{large_delivery_folder_count}")
            os.makedirs(large_delivery_folder, exist_ok=True)
            large_files = []
            total_large_size = 0

        cells = line.strip().split(',')
        if len(cells) < 6:
            raise ValueError(f"Invalid line: {line} in Large_File_List.csv")

        box_name = cells[0].strip().split(' ')[-1][:6]
        customer_ref = cells[1].strip()
        filename = cells[2].strip()
        source_file = cells[3].strip()
        rel_filename = os.path.basename(source_file)
        dest_file = os.path.join(large_delivery_folder, rel_filename)   
        mpt_size = float(cells[4].strip())
        pdf_size = float(cells[5].strip())

        if not os.path.exists(dest_file):
            shutil.copy(source_file, dest_file)

        large_files.append((box_name, customer_ref, rel_filename))
        total_large_size += pdf_size
        large_files_count += 1

# Write the manifest to the last folder
with open(os.path.join(large_delivery_folder, "_manifest.txt"), 'w') as file:
    file.write(f"BoxNo,RefCode,Filepath\n")
    for box_name, customer_ref, rel_filename in large_files:
        file.write(f"{box_name},{customer_ref},{rel_filename}\n")

print(f"""
_LARGE FILES REPORT_________________________________________________________
Num Folders: {large_delivery_folder_count}
Num Files:   {large_files_count}
_________________________________________________________
""")



