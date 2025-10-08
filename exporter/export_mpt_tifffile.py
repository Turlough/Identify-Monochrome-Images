import logging
from pathlib import Path
from typing import List

import numpy as np
from PIL import Image
import tifffile

logging.basicConfig(level=logging.INFO)


def _normalize_resolution(pil_img: Image.Image) -> tuple[float, float]:
    """Return (xres, yres) as floats in DPI, defaulting to 300.0 if missing.

    Coerces any IFDRational or non-float types to float to satisfy tifffile.
    """
    dpi = pil_img.info.get('dpi')
    if isinstance(dpi, (tuple, list)) and len(dpi) >= 2:
        try:
            return float(dpi[0]), float(dpi[1])
        except Exception:
            pass
    return 300.0, 300.0


def _is_bilevel_pil(pil_img: Image.Image) -> bool:
    """Return True if image is effectively bilevel (1-bit).

    Treat mode '1' as bilevel. For 'L' images with only 0/255 values, also treat as bilevel.
    """
    if pil_img.mode == '1':
        return True
    if pil_img.mode in ('L', 'LA'):
        # Quick heuristics: check unique values on a small subsample to avoid full scan
        arr = np.asarray(pil_img)
        if arr.ndim == 2:
            # Sample a grid
            sample = arr[::64, ::64]
            u = np.unique(sample)
            if u.size <= 2 and set(u.tolist()).issubset({0, 255}):
                return True
    return False


def _to_bilevel_array(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL image to bool array suitable for Group4 compression."""
    if pil_img.mode != '1':
        # Convert to bilevel using default threshold
        pil_img = pil_img.convert('1')
    # Convert to boolean where True=foreground (255)
    arr = np.asarray(pil_img, dtype=np.uint8)
    return arr > 0


def _to_color_array(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL image to uint8 RGB array for JPEG-in-TIFF."""
    if pil_img.mode not in ('RGB', 'RGBA'):
        pil_img = pil_img.convert('RGB')
    else:
        # Drop alpha if present
        pil_img = pil_img.convert('RGB')
    return np.asarray(pil_img, dtype=np.uint8)


def _save_multipage_tiff(output_path: Path, images: List[Path]) -> None:
    """Create a multipage TIFF using tifffile with per-page compression.

    - Bilevel pages use compression='group4' with photometric='miniswhite'.
    - Color pages use compression='jpeg' with photometric='rgb'.
    """
    if not images:
        raise ValueError("No input images provided")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Opena tifffile.TiffWriter to append pages
    with tifffile.TiffWriter(str(output_path), bigtiff=False, append=False) as tif:
        for img_path in images:
            p = Path(img_path)
            if not p.exists():
                logging.warning(f"Image not found: {p}")
                continue

            logging.info(f"Writing page from: {p}")

            with Image.open(p) as pil_img:
                try:
                    xres, yres = _normalize_resolution(pil_img)
                    if _is_bilevel_pil(pil_img):
                        # Bilevel page (1-bit)
                        data = _to_bilevel_array(pil_img)
                        tif.write(
                            data,
                            photometric='miniswhite',  # common for scanned docs
                            compression='ccitt_t6',
                            contiguous=False,
                            metadata=None,
                            predictor=None,
                            resolution=(xres, yres),
                            resolutionunit='inch',
                        )
                    else:
                        # Color/gray page -> store as RGB JPEG-in-TIFF
                        data = _to_color_array(pil_img)
                        tif.write(
                            data,
                            photometric='rgb',
                            compression='jpeg',
                            compressionargs={
                                # quality (1..100), subsampling factors
                                'level': 38,
                                'subsampling': (2, 2),
                            },
                            contiguous=False,
                            metadata=None,
                            resolution=(xres, yres),
                            resolutionunit='inch',
                        )
                except Exception as exc:
                    logging.error(f"Failed to write page for {p}: {exc}")
                    raise


