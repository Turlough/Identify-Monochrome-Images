import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image, ImageOps



class ImageConverter(QThread):
    """Thread for converting images to G4 TIFF format"""
    progress = pyqtSignal(str)
    finished = pyqtSignal(list)
    
    def __init__(self, image_paths: List[str]):
        super().__init__()
        self.image_paths = image_paths
    
    def run(self):
        converted_files = []
        for i, image_path in enumerate(self.image_paths):
            try:
                self.progress.emit(f"Converting {os.path.basename(image_path)}...")
                
                # Check if input file exists
                if not os.path.exists(image_path):
                    self.progress.emit(f"Error: Input file does not exist: {image_path}")
                    continue
                
                # Open image and convert to grayscale
                with Image.open(image_path) as img:
                    # Convert to grayscale
                    gray_img = ImageOps.grayscale(img)
                    
                    # Convert to 1-bit (bilevel) using a fixed threshold so Group 4 is valid
                    # Group 4 requires 1-bit images (BitsPerSample == 1)
                    bw_img = gray_img.point(lambda x: 255 if x >= 128 else 0, mode='1')
                    
                    # Create output path with .tif extension
                    output_path = os.path.splitext(image_path)[0] + '.tif'
                    
                    # Save as G4 TIFF
                    bw_img.save(output_path, 'TIFF', compression='group4')
                    
                    # Verify output file was created
                    if os.path.exists(output_path):
                        converted_files.append((image_path, output_path))
                        self.progress.emit(f"Successfully converted: {os.path.basename(output_path)}")
                    else:
                        self.progress.emit(f"Error: Output file was not created: {output_path}")
                    
            except Exception as e:
                self.progress.emit(f"Error converting {image_path}: {str(e)}")
        
        self.finished.emit(converted_files)

