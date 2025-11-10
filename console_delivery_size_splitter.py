"""
This script is used to split the files into two groups based on the size of the file.

The user is prompted to enter the folder to search for EXPORT.TXT files.
The script will then search for the term "EXPORT.TXT" in the current directory and all subdirectories.
The script will then split the files into two groups based on the size of the file.
The first group will be the files that are less than 50MB.
The second group will be the files that are greater than 50MB.
We are then going to print the filenames of the files in each group.
"""


from tqdm import tqdm
import os
from exceptions import MissingFileException
from exporter.export_common import get_all_export_files


 # 50 MB
KB = 1024
MB = KB * KB
max_bytes = 50 * MB
total_pdf_size = 0
total_mpt_size = 0

header = "Batch,CustomerRef,Filename,Filepath,MPT_KB,PDF_KB\n"

search_folder, export_files = get_all_export_files()

small_files = []
large_files = []
small_files_count = 0
large_files_count = 0


small_files_output = os.path.join(search_folder, "Small_File_List.csv")
large_files_output = os.path.join(search_folder, "Large_File_List.csv")


# Clear the output files
with open(small_files_output, 'w') as file:
    file.write(header)
with open(large_files_output, 'w') as file:
    file.write(header)

print(f"Cleared output files")
print(f"Reading {len(export_files)} EXPORT.TXT files")

for export_file in tqdm(export_files): 

    parent_folder = os.path.dirname(export_file)
    
    mpt_folder = parent_folder + "_mpt"
    pdf_folder = parent_folder + "_pdf"

    batch_name = os.path.basename(parent_folder)


    with open(export_file, 'r') as file:
        for line in file:
            if line.strip():
                cells = line.strip().split(',') 
                if len(cells) > 2:
                    ref = cells[0].strip()
                    name = cells[1].strip()
                    mpt_file = os.path.join(mpt_folder, name + ".tif")  
                    pdf_file = os.path.join(pdf_folder, name + ".pdf")

                    if not os.path.exists(mpt_file):
                        raise MissingFileException(f"Missing MPT file: {mpt_file}")
                    if not os.path.exists(pdf_file):
                        raise MissingFileException(f"Missing PDF file: {pdf_file}")

                    mpt_size = os.path.getsize(mpt_file)
                    pdf_size = os.path.getsize(pdf_file)
                    total_pdf_size += pdf_size
                    total_mpt_size += mpt_size
                    mpt_kb = round(mpt_size / KB, 0)
                    pdf_kb = round(pdf_size / KB, 0)

                    # If either the MPT or PDF file is greater than max_size, add it to the greater than max_size group.
                    # include: batch_name, ref, name, file, mpt_size, pdf_size
                    if mpt_size > max_bytes or pdf_size > max_bytes:
                        large_files.append((batch_name, ref, name, pdf_file, mpt_kb, pdf_kb))
                        large_files_count += 1
                    else:
                        small_files_count += 1
                        small_files.append((batch_name, ref, name, pdf_file, mpt_kb, pdf_kb))

print(f"""
_REPORT_________________________________________________________
Small: {small_files_count}
Large: {large_files_count}
Total: {small_files_count + large_files_count}
Large Percentage: {large_files_count / (small_files_count + large_files_count) * 100:.1f}%
PDFs: {total_pdf_size / MB:.1f} MB
MPTs: {total_mpt_size / MB:.1f} MB
_________________________________________________________
""")


if input("Create the output files (large and small)? (y/n): ") != "y":
    exit()

print(f"Sorting by filename")
small_files.sort(key=lambda x: x[1])
large_files.sort(key=lambda x: x[1])

print(f"Writing small files to {small_files_output}")
with open(small_files_output, 'a') as out_file:
    for batch_name, ref, name, pdf_path, mpt_size, pdf_size in small_files:
        out_file.write(f"{batch_name},{ref},{name},{pdf_path},{mpt_size},{pdf_size}\n")

print(f"Writing large files to {large_files_output}")
with open(large_files_output, 'a') as out_file:
    for batch_name, ref, name, pdf_path, mpt_size, pdf_size in large_files:
        out_file.write(f"{batch_name},{ref},{name},{pdf_path},{pdf_size},{mpt_size}\n")