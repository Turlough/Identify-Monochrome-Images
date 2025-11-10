# EXPORT.TXT is the filename we are searching for. 
# Each EXPORT.TXT file will have a list image files.
# We are searching for the term "EXPORT.TXT" in the current directory and all subdirectories.
# We are then going to split the files into two groups based on the size of the file.
# The first group will be the files that are less than 50MB.
# The second group will be the files that are greater than 50MB.
# We are then going to print the filenames of the files in each group.


import glob
import os

class MissingFileException(Exception):
    def __init__(self, message):
        self.message = message
        super().__init__(self.message)

search_term = "EXPORT.TXT"
max_size = 50 * 1024 * 1024

search_folder = input("Enter the folder to search for EXPORT.TXT files: \n\t-> ")
search_folder = search_folder.replace('&', '').replace('"', '').replace("'", "").strip()

export_files = glob.glob(os.path.join(search_folder, "**", search_term), recursive=True)

less_than_50mb_pdf_group = []
greater_than_50mb_pdf_group = []
less_than_50mb_mpt_group = []
greater_than_50mb_mpt_group = []

less_than_50mb_group = []
greater_than_50mb_group = []

less_than_50mb_pdf_file = os.path.join(search_folder, "less_than_50mb_pdf.csv")
less_than_50mb_mpt_file = os.path.join(search_folder, "less_than_50mb_mpt.csv")
greater_than_50mb_pdf_file = os.path.join(search_folder, "greater_than_50mb_pdf.csv")
greater_than_50mb_mpt_file = os.path.join(search_folder, "greater_than_50mb_mpt.csv")

# Clear the output files
with open(less_than_50mb_pdf_file, 'w') as file:
    file.write("")
with open(less_than_50mb_mpt_file, 'w') as file:
    file.write("")
with open(greater_than_50mb_pdf_file, 'w') as file:
    file.write("")
with open(greater_than_50mb_mpt_file, 'w') as file:
    file.write("")

print(f"Cleared output files")

for export_file in export_files:

    parent_folder = os.path.dirname(export_file)
    
    mpt_folder = parent_folder + "_mpt"
    pdf_folder = parent_folder + "_pdf"

    batch_name = os.path.basename(parent_folder)

    print(f"Processing batch: {batch_name}")

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
                    # If either the MPT or PDF file is greater than 50MB, add it to the greater than 50MB group.
                    # include: batch_name, ref, name, file, mpt_size, pdf_size
                    if mpt_size > max_size or pdf_size > max_size:
                        greater_than_50mb_pdf_group.append((batch_name, ref, name, pdf_file, mpt_size, pdf_size))
                        greater_than_50mb_mpt_group.append((batch_name, ref, name, mpt_file, mpt_size, pdf_size))
                    else:
                        less_than_50mb_pdf_group.append((batch_name, ref, name, pdf_file, mpt_size, pdf_size))
                        less_than_50mb_mpt_group.append((batch_name, ref, name, mpt_file, mpt_size, pdf_size))
    print(f"Less than 50MB PDF group: {len(less_than_50mb_pdf_group)}")
    print(f"Less than 50MB MPT group: {len(less_than_50mb_mpt_group)}")
    print(f"Greater than 50MB PDF group: {len(greater_than_50mb_pdf_group)}")
    print(f"Greater than 50MB MPT group: {len(greater_than_50mb_mpt_group)}")


    with open(less_than_50mb_pdf_file, 'a') as out_file:
        print(f"Writing less than 50MB PDF group to file: {less_than_50mb_pdf_file}")
        for batch_name, ref, name, pdf_path, mpt_size, pdf_size in less_than_50mb_pdf_group:
            out_file.write(f"{batch_name},{ref},{name},{pdf_path},{pdf_size},{mpt_size}\n")
    with open(less_than_50mb_mpt_file, 'a') as out_file:
        print(f"Writing less than 50MB MPT group to file: {less_than_50mb_mpt_file}")
        for batch_name, ref, name, mpt_path, mpt_size, pdf_size in less_than_50mb_mpt_group:
            out_file.write(f"{batch_name},{ref},{name},{mpt_path},{pdf_size},{mpt_size}\n")
    with open(greater_than_50mb_pdf_file, 'a') as out_file:
        print(f"Writing greater than 50MB PDF group to file: {greater_than_50mb_pdf_file}")
        for batch_name, ref, name, pdf_path, mpt_size, pdf_size in greater_than_50mb_pdf_group:
            out_file.write(f"{batch_name},{ref},{name},{pdf_path},{pdf_size},{mpt_size}\n")
    with open(greater_than_50mb_mpt_file, 'a') as out_file:
        print(f"Writing greater than 50MB MPT group to file: {greater_than_50mb_mpt_file}")
        for batch_name, ref, name, mpt_path, mpt_size, pdf_size in greater_than_50mb_mpt_group:
            out_file.write(f"{batch_name},{ref},{name},{mpt_path},{pdf_size},{mpt_size}\n")

    print(f"Done processing batch: {batch_name}")
print(f"Done processing all batches")