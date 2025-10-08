import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from PyQt6.QtCore import QThread, pyqtSignal
from PIL import Image, ImageOps
import cv2
import numpy as np



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
                    
                    # Convert PIL image to numpy array for OpenCV processing
                    gray_array = np.array(gray_img)
                    
                    # Apply adaptive thresholding
                    # ADAPTIVE_THRESH_GAUSSIAN_C uses Gaussian-weighted sum of neighborhood values
                    # THRESH_BINARY: pixel becomes 255 if greater than threshold, 0 otherwise
                    # Block size: 11 (size of neighborhood area)
                    # C: constant subtracted from mean (helps fine-tune threshold)
                    adaptive_thresh = cv2.adaptiveThreshold(
                        gray_array, 
                        255, 
                        cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                        cv2.THRESH_BINARY, 
                        11, 
                        15
                    )
                    
                    # Convert back to PIL Image
                    bw_img = Image.fromarray(adaptive_thresh, mode='L').convert('1')
                    
                    # Create output path with .tif extension
                    output_path = os.path.splitext(image_path)[0] + '.tif'
                    
                    # Save as G4 TIFF
                    # Save with original DPI if available, default to 300 DPI if not
                    dpi = img.info.get('dpi', (300, 300))
                    bw_img.save(output_path, 'TIFF', compression='group4', dpi=dpi)
                    
                    # Verify output file was created
                    if os.path.exists(output_path):
                        converted_files.append((image_path, output_path))
                        self.progress.emit(f"Successfully converted: {os.path.basename(output_path)}")
                    else:
                        self.progress.emit(f"Error: Output file was not created: {output_path}")
                    
            except Exception as e:
                self.progress.emit(f"Error converting {image_path}: {str(e)}")
        
        self.finished.emit(converted_files)

