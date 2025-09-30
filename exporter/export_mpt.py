from pathlib import Path
from typing import List
from PIL import Image



def _save_multipage_tiff(output_path: Path, images: List[Path]) -> None:
    """Save a list of images as a multipage TIFF.

    Preserves original image modes - only applies Group 4 compression to 1-bit images.
    Color images are kept in their original format.
    """
    pil_images: List[Image.Image] = []
    try:
        for p in images:
            img = Image.open(str(p))
            # Keep original mode - don't force conversion to 1-bit
            # Only convert palette images to RGB for better compatibility
            if img.mode == 'P':
                img = img.convert('RGB')
            pil_images.append(img)

        if not pil_images:
            return

        first, rest = pil_images[0], pil_images[1:]
        save_kwargs = {'save_all': True, 'append_images': rest}
        
        # Only use Group 4 compression if ALL pages are 1-bit
        if all(img.mode == '1' for img in pil_images):
            save_kwargs.update({'compression': 'group4'})
        # For mixed or color images, use LZW compression (good for both color and grayscale)
        else:
            save_kwargs.update({'compression': 'tiff_lzw'})
            
        first.save(str(output_path), format='TIFF', **save_kwargs)
    finally:
        for img in pil_images:
            try:
                img.close()
            except Exception:
                pass


