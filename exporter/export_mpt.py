import subprocess
from pathlib import Path
from typing import List
import logging
import os

logging.basicConfig(level=logging.INFO)

def _identify_type_and_colorspace(image_path: Path) -> str:
    """Return ImageMagick identify string like 'Bilevel:Gray' or 'TrueColor:RGB'."""
    identify_cmd = [
        'magick', 'identify', '-quiet', '-format', '%[type]:%[colorspace]', str(image_path)
    ]
    proc = subprocess.run(identify_cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        logging.warning(
            f"identify failed for {image_path}: {proc.stderr.strip()} — falling back to extension"
        )
        return ''
    return proc.stdout.strip()


def _save_multipage_tiff(output_path: Path, images: List[Path]) -> None:
    """Create multipage TIFF with per-image settings using ImageMagick (IM7).

    Key points:
    - Use parentheses to scope settings to each input so compress/type do not leak.
    - Preserve existing compression on TIFF inputs where possible.
    - Force color inputs to remain color; bilevel inputs to remain bilevel.
    """

    if not images:
        raise ValueError("No input images provided")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Start IM7 command. Avoid global -compress so settings don't leak across pages.
    cmd: List[str] = [
        'magick',
    ]

    for img_path in images:
        img_path = Path(img_path)
        if not img_path.exists():
            logging.warning(f"Image not found: {img_path}")
            continue

        identify = _identify_type_and_colorspace(img_path)
        img_ext = img_path.suffix.lower()

        # Open a per-image parenthesis group so settings are scoped to this image only
        cmd.append('(')

        # Always read the image first inside the group
        cmd.append(str(img_path))

        if identify:
            img_type, colorspace = (identify.split(':') + [''])[:2]
        else:
            img_type, colorspace = '', ''

        # Decide how to treat the image
        is_tiff = img_ext in ['.tif', '.tiff']
        is_bilevel = img_type.lower() == 'bilevel' or colorspace.lower() == 'gray'

        if is_tiff and is_bilevel:
            # Keep bilevel as G4 and ensure it's really 1-bit
            logging.info(f"Adding bilevel TIFF with G4: {img_path}")
            cmd.extend([
                '-alpha', 'off',
                '-type', 'bilevel',
                '-compress', 'Group4',
            ])
        else:
            # Treat as color/continuous-tone page
            logging.info(f"Adding color page with JPEG compression: {img_path}")
            cmd.extend([
                '-alpha', 'off',
                '-colorspace', 'sRGB',
                '-type', 'TrueColor',
                '-depth', '8',                         # ensure 8 bits per sample
                # Explicit TIFF JPEG parameters to prevent grayscale/None compression
                '-define', 'tiff:bits-per-sample=8',
                '-define', 'tiff:samples-per-pixel=3',
                '-define', 'tiff:photometric=ycbcr',   # YCbCr is standard for JPEG-in-TIFF
                '-sampling-factor', '4:2:0',
                '-compress', 'JPEG',
                '-define', 'tiff:compression=jpeg',
                '-define', 'tiff:jpeg:subsampling-factor=2x2',
                # JPEG quality
                '-quality', '38',
            ])

        # Close per-image group
        cmd.append(')')

    # Remove output file if it exists
    if os.path.exists(output_path):
        os.remove(output_path)

    # Finally, write the multi-page TIFF. Avoid global -compress here.
    cmd.append(str(output_path))
    logging.info(f"Cmd: {cmd}\n")
    logging.info("Executing ImageMagick command for MPT TIFF")

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"ImageMagick failed (code {result.returncode}): {result.stderr}")