import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Optional
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image, ImageOps
import cv2
import numpy as np


def convert_image_to_g4_tiff(image_path: str) -> Optional[str]:
    """Convert a single image to G4 TIFF format.
    
    Args:
        image_path: Path to the input image file
        
    Returns:
        Path to the created TIFF file if successful, None if failed
    """
    try:

        with Image.open(image_path) as img:
            gray_img = ImageOps.grayscale(img)
            gray_array = np.array(gray_img)

            adaptive_thresh = cv2.adaptiveThreshold(
                gray_array,
                255,
                cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                cv2.THRESH_BINARY,
                11,
                15,
            )

            bw_img = Image.fromarray(adaptive_thresh, mode='L').convert('1')

            output_path = os.path.splitext(image_path)[0] + '.tif'

            dpi = img.info.get('dpi', (300, 300))
            bw_img.save(output_path, 'TIFF', compression='group4', dpi=dpi)

            if os.path.exists(output_path):
                return output_path
            else:
                return None
                
    except Exception as e:
        print(f"Error converting {image_path}: {str(e)}")
        return None


class ImageConverter(QThread):
    """Thread for converting images to G4 TIFF format"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)
    
    def __init__(self, image_paths: List[str]):
        super().__init__()
        self.image_paths = image_paths
    
    def run(self):
        converted_files = []
        max_workers = max(1, min(len(self.image_paths), (os.cpu_count() or 1)))

        def convert_one(image_path: str):
            try:
                self.progress.emit(f"Converting {os.path.basename(image_path)}...")

                output_path = convert_image_to_g4_tiff(image_path)
                
                if output_path:
                    self.progress.emit(f"Successfully converted: {os.path.basename(output_path)}")
                    return (image_path, output_path)
                else:
                    self.progress.emit(f"Error: Failed to convert {image_path}")
                    return None
            except Exception as e:
                self.progress.emit(f"Error converting {image_path}: {str(e)}")
                return None

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(convert_one, path) for path in self.image_paths]
            for future in as_completed(futures):
                result = future.result()
                if result:
                    converted_files.append(result)

        self.finished.emit(converted_files)

