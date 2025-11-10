import glob
from exporter import TifCounter, PdfCounter
from exporter.export_common import export_from_import_file_concurrent
from verify_page_counts import verify_page_counts
import os


search_term = "EXPORT.TXT"
max_size = 50 * 1024 * 1024

search_folder = input("Enter the folder to search for EXPORT.TXT files: \n\t-> ")
search_folder = search_folder.replace('&', '').replace('"', '').replace("'", "").strip()
export_files = glob.glob(os.path.join(search_folder, "**", search_term), recursive=True)

for export_file in export_files:
    print(f"Exporting {export_file}")
    num_tiffs, num_pdfs = export_from_import_file_concurrent(export_file)
    print(f"Exported {num_tiffs} TIFFs and {num_pdfs} PDFs")

    # Read the import file to get expected page counts
    tif_counter = TifCounter(export_file)
    pdf_counter = PdfCounter(export_file)
    counters = [pdf_counter]
    verify_page_counts(counters)

    print(f"--------------------------------")
print(f"Done exporting all files")