
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List
from PyQt6.QtCore import QThread, pyqtSignal
from color_detector import ColorDetector


class ColorAnalysisThread(QThread):
    """Thread for analyzing images to detect monochrome candidates"""
    progress = pyqtSignal(str)
    analysis_complete = pyqtSignal(list)  # List of image paths that are monochrome
    
    def __init__(self, image_paths: List[str]):
        super().__init__()
        self.image_paths = image_paths
        self.color_detector = ColorDetector()
    
    def run(self):
        """Analyze all images for monochrome characteristics"""
        monochrome_candidates = []

        def process_image(path: str):
            """Process a single image path and return summary for UI updates."""
            try:
                detector = ColorDetector()
                result = detector.analyze_image_color(path)
                if result.get('is_monochrome') and result.get('confidence', 0.0) >= 0.4:
                    return (path, True, result.get('confidence', 0.0), None, None)
                # Compute criteria count without re-reading image
                metrics = result.get('metrics', {})
                try:
                    low_color_variance = metrics.get('bgr_variance', float('inf')) < detector.color_variance_threshold
                    similar_channels = metrics.get('bgr_channel_diff', float('inf')) < 30
                    low_saturation = metrics.get('avg_saturation', float('inf')) < detector.saturation_threshold
                    low_hue_variance = metrics.get('hue_variance', float('inf')) < detector.hue_variance_threshold
                    high_hist_correlation = metrics.get('bgr_hist_correlation', -1.0) > 0.6
                    low_high_sat_ratio = metrics.get('high_saturation_ratio', float('inf')) < 0.03
                    criteria_passed = sum([
                        low_color_variance,
                        similar_channels,
                        low_saturation,
                        low_hue_variance,
                        high_hist_correlation,
                        low_high_sat_ratio
                    ])
                except Exception:
                    criteria_passed = None
                return (path, False, result.get('confidence', 0.0), criteria_passed, None)
            except Exception as e:
                return (path, None, 0.0, None, str(e))

        max_workers = max(1, min(8, (os.cpu_count() or 2)))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            future_to_path = {executor.submit(process_image, p): p for p in self.image_paths}
            for future in as_completed(future_to_path):
                image_path = future_to_path[future]
                try:
                    path, is_mono, confidence, criteria_passed, err = future.result()
                    if err:
                        self.progress.emit(f"Error analyzing {path}: {err}")
                        continue
                    if is_mono:
                        monochrome_candidates.append(path)
                        self.progress.emit(f"✓ {os.path.basename(path)} - Monochrome candidate (confidence: {confidence:.2f})")
                    else:
                        if criteria_passed is not None:
                            self.progress.emit(f"  {os.path.basename(path)} - Color image (confidence: {confidence:.2f}, criteria: {criteria_passed}/6)")
                        else:
                            self.progress.emit(f"  {os.path.basename(path)} - Color image (confidence: {confidence:.2f})")
                except Exception as e:
                    self.progress.emit(f"Error analyzing {image_path}: {str(e)}")

        self.progress.emit(f"Analysis complete. Found {len(monochrome_candidates)} monochrome candidates.")
        self.analysis_complete.emit(monochrome_candidates)

