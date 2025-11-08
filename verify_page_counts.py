from exporter import PdfCounter, TifCounter
import logging
import os
from tqdm import tqdm
from tabulate import tabulate

from exporter.counters.page_counter import PageCountResult
from exporter.counters.page_counter import PageCounter

def count_all_pages_concurrently(counter: PageCounter):

    # Process with progress bar
    pbar = tqdm(total=len(counter.counting_results), 
                    desc=f"TIF {counter.batch_name}")
    for _ in counter.count_batch_pages_concurrently(lambda _: pbar.update(1)):
        pass
    pbar.close()

    return list(counter.counting_results.values()) # return a list of PageCount objects


def main():
    import_file = input("Enter the path to the import file:\n\t-> ").replace('&', '').replace('"', '').replace("'", "").strip()
    tif_counter = TifCounter(import_file)
    pdf_counter = PdfCounter(import_file)
    counters = [tif_counter]
    for counter in counters:

        all_counts = count_all_pages_concurrently(counter)
        
        failed_files = counter.get_failed_files()


        if failed_files:
            print(f"Failed files: {failed_files}")

            counter.tabulate_results(failed_files)
            print(f"Failed files: {len(failed_files)}/{len(counter.counting_results)}")
            response = input("Do you want to create a rework file? (y/n): ")

            if response.lower()[0] == "y":
                counter.create_rework_file(failed_files)
                print(f"Rework file created: {counter.rework_file}")
            else:
                logging.info("No failed files found")
        else:
            logging.info("No failed files found")


if __name__ == "__main__":
    main()