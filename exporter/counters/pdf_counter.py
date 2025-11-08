from concurrent.futures import ThreadPoolExecutor, as_completed
from ..counters.page_counter import PageCounter
from pathlib import Path
from pypdf import PdfReader
import logging


class PdfCounter(PageCounter):
    def __init__(self, import_file: str):
        super().__init__(import_file, "PDF", ".pdf")
        self.output_dir = Path(str(self.base_dir) + "_pdf")

    def count_document_pages(self, filename, path):
        if not path.exists():
            self.counting_results[filename].actual_count = 0
            return

        try:
            reader = PdfReader(path)
            actual_count = reader.get_num_pages()
            self.counting_results[filename].actual_count = actual_count
            return actual_count
        except Exception as e:
            self.counting_results[filename].actual_count = 0
            return 0


    def count_batch_pages_concurrently(self, progress_callback=None):
        logging.debug(f"Checking page counts for {self.batch_name} in pdf directory: {self.output_dir}")
        future_to_filename = {}
        with ThreadPoolExecutor() as executor:
            for filename in self.counting_results.keys():
                path = self.output_dir / f"{filename}"
                future = executor.submit(self.count_document_pages, filename, path)
                future_to_filename[future] = filename

            for future in as_completed(future_to_filename.keys()):
                actual_count = future.result()
                filename = future_to_filename[future]
                if progress_callback:
                    progress_callback(actual_count)
                yield actual_count