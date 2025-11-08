"""
ImageMagick-based multipage TIFF exporter.

This module provides functionality to create multipage TIFF files using ImageMagick
via the Wand Python binding. It automatically applies appropriate compression:
- G4 (Group 4) compression for monochrome TIFF images
- JPEG compression for color images (JPG, RGB TIFFs, etc.)

Supports mixing different image types in a single multipage TIFF.
"""

from pathlib import Path
from typing import List
import logging

from wand.image import Image

logging.basicConfig(level=logging.INFO)


def _save_multipage_tiff(output_path: Path, images: List[Path]) -> None:
    """Create a multipage TIFF using ImageMagick.
    
    Applies G4 compression to monochrome TIFF images and JPEG compression to color images.
    Supports mixing JPG and single-page G4 TIFF inputs.
    """
    if not images:
        raise ValueError("No input images provided")
    
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    logging.debug(f"Creating multipage TIFF with ImageMagick: {output_path}")
    
    # Create a list to hold all converted images
    converted_images = []
    
    try:
        for img_path in images:
            img_path = Path(img_path)
            if not img_path.exists():
                logging.warning(f"Image not found: {img_path}")
                continue
                
            logging.info(f"Processing {img_path}")
            
            with Image(filename=str(img_path)) as img:
                # Get image format and properties
                img_format = img.format.lower()
                img_extension = img_path.suffix.lower()
                
                # Check if this is a G4 TIFF based on file extension and image properties
                is_g4_tiff = (img_extension in ['.tif', '.tiff']) and (img.type == 'bilevel' or img.colorspace == 'gray')
                
                # Clone the image to avoid closing the original
                with img.clone() as processed_img:
                    if is_g4_tiff:
                        # For G4 TIFFs, maintain monochrome with G4 compression
                        processed_img.compression = 'group4'
                        processed_img.type = 'bilevel'  # Ensure 1-bit
                        processed_img.colorspace = 'gray'
                        logging.debug(f"Applied G4 compression to {img_path}")
                        processed_img.resolution = 300
                        
                    else:
                        # For color images (JPG, other TIFFs), use JPEG compression
                        processed_img.compression = 'jpeg'
                        processed_img.compression_quality = 20  # Good quality/size balance
                        # Convert to RGB if not already
                        if processed_img.colorspace != 'rgb':
                            processed_img.colorspace = 'rgb'
                        logging.debug(f"Applied JPEG compression to {img_path}")
                    
                    # Add to list (this creates a copy)
                    converted_images.append(processed_img.clone())
        
        if not converted_images:
            raise ValueError("No valid images to process")
        
        # Create multipage TIFF using the first image as base
        if len(converted_images) == 1:
            # Single page - just save directly
            converted_images[0].save(filename=str(output_path))
        else:
            # Multiple pages - use sequence approach
            with converted_images[0] as first_img:
                # Create a sequence from all images
                first_img.sequence.extend(converted_images[1:])
                first_img.save(filename=str(output_path))
            
        logging.info(f"Successfully created multipage TIFF: {output_path}")
        
    except Exception as e:
        logging.error(f"Error creating multipage TIFF: {e}")
        raise
    finally:
        # Clean up converted images
        for img in converted_images:
            try:
                img.close()
            except Exception:
                pass