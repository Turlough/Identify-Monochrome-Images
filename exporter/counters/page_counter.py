from dataclasses import dataclass
import logging
from pathlib import Path
import os
from dotenv import load_dotenv
from concurrent.futures import as_completed as futures_as_completed
from tabulate import tabulate

logging.basicConfig(level=logging.INFO)

env_file = os.path.join(os.path.dirname(__file__), '..', '.env')
load_dotenv(env_file)

NUM_DATA_COLUMNS = int(os.getenv('NUM_DATA_COLUMNS', '2'))
FILENAME_COLUMN = int(os.getenv('FILENAME_COLUMN', '1')) 

@dataclass
class PageCountResult:
    title: str
    extension: str
    filename: str
    expected_count: int
    actual_count: int = 0

    def failed(self):
        return self.expected_count != self.actual_count

    def as_row(self):
        return [self.title, self.filename, self.expected_count, self.actual_count, self.failed()]

class PageCounter:
    def __init__(self, import_file: str, title: str, extension: str):
        self.title = title
        self.extension = extension
        self.output_dir = None
        self.base_dir = Path(os.path.dirname(import_file))
        self.batch_name = self.base_dir.name.strip()
        self.import_file = import_file
        self.rework_file = self.base_dir / f"{self.batch_name}_{self.title.lower()}_rework.txt"
        self.counting_results: dict[str, PageCountResult] = {}

        with open(import_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) > 1:
                    tiff_name = parts[FILENAME_COLUMN].strip() + self.extension
                    # Count input files and build dictionary (starting after data columns)
                    expected_count = sum(1 for p in parts[NUM_DATA_COLUMNS:])
                    self.counting_results[tiff_name] = PageCountResult( self.title, self.extension, tiff_name, expected_count)

    def count_batch_pages_concurrently(self, progress_callback=None):
        """
        Counts the number of pages for each document in the batch concurrently using ThreadPoolExecutor.
        Updates self.counter with actual page counts. Accepts an optional progress_callback to be called after each file is processed.
        Yields after each file is processed.
        """
        pass

    def count_document_pages(self, filename, path, expected_count):
        pass

    def get_failed_files(self):
        return [c for c in self.counting_results.values() if c.failed()]

    def tabulate_results(self,counter_results: list[PageCountResult]):
        rows = [page_count.as_row() for page_count in counter_results]
        print(tabulate(rows, headers=["Type", "Filename", "Expected Count", "Actual Count", "Failed"], tablefmt="grid"))

    def create_rework_file(self, failed_files: list[PageCountResult]):
        """
        Having mismatched page counts, find the rows in the import file that have mismatched page counts
        in the mpt and pdf directories and create a new file with a copy of each row that has mismatched page counts in either the mpt or pdf directories.
         and create a new file with a copy of each row that has mismatched page counts.
         The new file will be named <import_file_rework.txt
         The new file will have the same content as the original file, but with the rows do not have mismatched page counts.
         This file is to be used to rework the documents that have mismatched page counts.
        """
        target_files = [
            os.path.splitext(page_count.filename)[0]
            for page_count in self.counting_results.values()
            if page_count.failed()
        ]
        rework_lines = []
        with open(self.import_file, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(',')
                doc_name = parts[FILENAME_COLUMN].strip()
                if doc_name in target_files:
                    rework_lines.append(line)

        with open(self.rework_file, 'w', encoding='utf-8') as f:
            for line in rework_lines:
                f.write(line)

        logging.info(f"Created {len(rework_lines)} rework lines in file: {self.rework_file}")

