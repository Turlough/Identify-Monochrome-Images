import cv2
import numpy as np
from typing import List, Tuple, Dict
import os


class ColorDetector:
    """
    OpenCV-based color detector for identifying monochrome images
    that should be converted to black and white.
    """
    
    def __init__(self):
        # Thresholds for monochrome detection (balanced for red line detection)
        self.color_variance_threshold = 0.4  # Maximum color variance for monochrome
        self.saturation_threshold = 50  # Maximum average saturation for monochrome
        self.hue_variance_threshold = 0.10  # Maximum hue variance for monochrome (stricter for color detection)
        
    def analyze_image_color(self, image_path: str) -> Dict:
        """
        Analyze an image to determine if it should be converted to monochrome.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with analysis results including 'is_monochrome' boolean
        """
        try:
            # Load image
            img = cv2.imread(image_path)
            if img is None:
                return {
                    'is_monochrome': False,
                    'error': f'Could not load image: {image_path}',
                    'confidence': 0.0,
                    'metrics': {}
                }
            
            # Convert to different color spaces for analysis
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)
            lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
            
            # Calculate various metrics
            metrics = self._calculate_color_metrics(img, hsv, lab)
            
            # Determine if image should be considered monochrome
            is_monochrome = self._is_monochrome_image(metrics)
            
            # Calculate confidence score
            confidence = self._calculate_confidence(metrics)
            
            return {
                'is_monochrome': is_monochrome,
                'confidence': confidence,
                'metrics': metrics,
                'image_path': image_path
            }
            
        except Exception as e:
            return {
                'is_monochrome': False,
                'error': f'Error analyzing image: {str(e)}',
                'confidence': 0.0,
                'metrics': {}
            }
    
    def _calculate_color_metrics(self, bgr_img: np.ndarray, hsv_img: np.ndarray, lab_img: np.ndarray) -> Dict:
        """Calculate various color metrics for monochrome detection."""
        metrics = {}
        
        # 1. Color variance in BGR channels
        bgr_mean = np.mean(bgr_img, axis=(0, 1))
        bgr_variance = np.var(bgr_img, axis=(0, 1))
        metrics['bgr_variance'] = np.mean(bgr_variance)
        metrics['bgr_channel_diff'] = np.std(bgr_mean)  # Difference between B, G, R channels
        
        # 2. Saturation analysis (HSV)
        saturation = hsv_img[:, :, 1]
        metrics['avg_saturation'] = np.mean(saturation)
        metrics['saturation_variance'] = np.var(saturation)
        metrics['high_saturation_ratio'] = np.sum(saturation > 50) / saturation.size
        
        # 3. Hue analysis (HSV)
        hue = hsv_img[:, :, 0]
        # Remove black pixels (saturation = 0) from hue analysis
        valid_hue_mask = saturation > 10
        if np.any(valid_hue_mask):
            valid_hue = hue[valid_hue_mask]
            metrics['hue_variance'] = np.var(valid_hue) / 180.0  # Normalize to 0-1
            metrics['hue_range'] = (np.max(valid_hue) - np.min(valid_hue)) / 180.0
        else:
            metrics['hue_variance'] = 0.0
            metrics['hue_range'] = 0.0
        
        # 4. Lightness analysis (LAB)
        lightness = lab_img[:, :, 0]
        metrics['lightness_variance'] = np.var(lightness)
        metrics['lightness_range'] = np.max(lightness) - np.min(lightness)
        
        # 5. Edge detection for text/graphics analysis
        gray = cv2.cvtColor(bgr_img, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 50, 150)
        metrics['edge_density'] = np.sum(edges > 0) / edges.size
        
        # 6. Histogram analysis
        hist_b = cv2.calcHist([bgr_img], [0], None, [256], [0, 256])
        hist_g = cv2.calcHist([bgr_img], [1], None, [256], [0, 256])
        hist_r = cv2.calcHist([bgr_img], [2], None, [256], [0, 256])
        
        # Normalize histograms
        hist_b = hist_b.flatten() / np.sum(hist_b)
        hist_g = hist_g.flatten() / np.sum(hist_g)
        hist_r = hist_r.flatten() / np.sum(hist_r)
        
        # Calculate histogram correlation
        metrics['bgr_hist_correlation'] = (
            np.corrcoef(hist_b, hist_g)[0, 1] + 
            np.corrcoef(hist_b, hist_r)[0, 1] + 
            np.corrcoef(hist_g, hist_r)[0, 1]
        ) / 3.0
        
        return metrics
    
    def _is_monochrome_image(self, metrics: Dict) -> bool:
        """
        Determine if an image should be considered monochrome based on calculated metrics.
        """
        # Multiple criteria for monochrome detection
        
        # 1. Low color variance and channel similarity
        low_color_variance = metrics['bgr_variance'] < self.color_variance_threshold
        similar_channels = metrics['bgr_channel_diff'] < 30  # More lenient
        
        # 2. Low saturation
        low_saturation = metrics['avg_saturation'] < self.saturation_threshold
        low_saturation_variance = metrics['saturation_variance'] < 800  # More lenient
        
        # 3. Low hue variance (indicating mostly grayscale or single hue)
        low_hue_variance = metrics['hue_variance'] < self.hue_variance_threshold
        
        # 4. High correlation between BGR histograms
        high_hist_correlation = metrics['bgr_hist_correlation'] > 0.6  # More lenient
        
        # 5. Low ratio of highly saturated pixels
        low_high_sat_ratio = metrics['high_saturation_ratio'] < 0.03  # Stricter to catch small colored elements
        
        # Combine criteria (image is monochrome if most criteria are met)
        criteria = [
            low_color_variance,
            similar_channels,
            low_saturation,
            low_hue_variance,
            high_hist_correlation,
            low_high_sat_ratio
        ]
        
        # Require at least 4 out of 7 criteria to be true (balanced for red line detection)
        return sum(criteria) >= 4
    
    def _calculate_confidence(self, metrics: Dict) -> float:
        """Calculate confidence score for monochrome classification."""
        confidence_factors = []
        
        # Factor 1: Color variance (use a more generous scaling)
        # Scale based on a much higher threshold since variance can be large
        color_var_threshold = 2000  # Much higher threshold for scaling
        color_var_score = max(0, 1 - metrics['bgr_variance'] / color_var_threshold)
        confidence_factors.append(color_var_score)
        
        # Factor 2: Saturation (lower is better)
        sat_score = max(0, 1 - metrics['avg_saturation'] / self.saturation_threshold)
        confidence_factors.append(sat_score)
        
        # Factor 3: Hue variance (use a more generous scaling)
        hue_var_threshold = 10  # Much higher threshold for scaling
        hue_var_score = max(0, 1 - metrics['hue_variance'] / hue_var_threshold)
        confidence_factors.append(hue_var_score)
        
        # Factor 4: Histogram correlation (higher is better)
        hist_score = max(0, metrics['bgr_hist_correlation'])
        confidence_factors.append(hist_score)
        
        # Factor 5: High saturation ratio (lower is better)
        high_sat_score = max(0, 1 - metrics['high_saturation_ratio'] / 0.2)
        confidence_factors.append(high_sat_score)
        
        # Factor 6: Channel similarity (lower is better)
        channel_sim_score = max(0, 1 - metrics['bgr_channel_diff'] / 30)
        confidence_factors.append(channel_sim_score)
        
        # Factor 7: Saturation variance (lower is better)
        sat_var_score = max(0, 1 - metrics['saturation_variance'] / 800)
        confidence_factors.append(sat_var_score)
        
        return np.mean(confidence_factors)
    
    def analyze_multiple_images(self, image_paths: List[str]) -> List[Dict]:
        """
        Analyze multiple images and return results for each.
        
        Args:
            image_paths: List of image file paths
            
        Returns:
            List of analysis results for each image
        """
        results = []
        for image_path in image_paths:
            if os.path.exists(image_path):
                result = self.analyze_image_color(image_path)
                results.append(result)
            else:
                results.append({
                    'is_monochrome': False,
                    'error': f'File not found: {image_path}',
                    'confidence': 0.0,
                    'metrics': {}
                })
        
        return results
    
    def get_monochrome_candidates(self, image_paths: List[str], min_confidence: float = 0.4) -> List[str]:
        """
        Get list of image paths that are likely candidates for monochrome conversion.
        
        Args:
            image_paths: List of image file paths
            min_confidence: Minimum confidence threshold for classification
            
        Returns:
            List of image paths that should be converted to monochrome
        """
        results = self.analyze_multiple_images(image_paths)
        candidates = []
        
        for result in results:
            if (result['is_monochrome'] and 
                result['confidence'] >= min_confidence and 
                'error' not in result):
                candidates.append(result['image_path'])
        
        return candidates
    
    def debug_analysis(self, image_path: str) -> Dict:
        """
        Debug method to show detailed analysis results for troubleshooting.
        
        Args:
            image_path: Path to the image file
            
        Returns:
            Dictionary with detailed analysis including all criteria results
        """
        result = self.analyze_image_color(image_path)
        if 'error' in result:
            return result
        
        metrics = result['metrics']
        
        # Calculate all criteria for debugging
        low_color_variance = metrics['bgr_variance'] < self.color_variance_threshold
        similar_channels = metrics['bgr_channel_diff'] < 30
        low_saturation = metrics['avg_saturation'] < self.saturation_threshold
        low_saturation_variance = metrics['saturation_variance'] < 800
        low_hue_variance = metrics['hue_variance'] < self.hue_variance_threshold
        high_hist_correlation = metrics['bgr_hist_correlation'] > 0.6
        low_high_sat_ratio = metrics['high_saturation_ratio'] < 0.03
        
        criteria_results = {
            'low_color_variance': (low_color_variance, metrics['bgr_variance'], self.color_variance_threshold),
            'similar_channels': (similar_channels, metrics['bgr_channel_diff'], 30),
            'low_saturation': (low_saturation, metrics['avg_saturation'], self.saturation_threshold),
            'low_saturation_variance': (low_saturation_variance, metrics['saturation_variance'], 800),
            'low_hue_variance': (low_hue_variance, metrics['hue_variance'], self.hue_variance_threshold),
            'high_hist_correlation': (high_hist_correlation, metrics['bgr_hist_correlation'], 0.6),
            'low_high_sat_ratio': (low_high_sat_ratio, metrics['high_saturation_ratio'], 0.03)
        }
        
        criteria_passed = sum([result[0] for result in criteria_results.values()])
        
        result['debug_info'] = {
            'criteria_results': criteria_results,
            'criteria_passed': criteria_passed,
            'required_criteria': 4,
            'thresholds': {
                'color_variance_threshold': self.color_variance_threshold,
                'saturation_threshold': self.saturation_threshold,
                'hue_variance_threshold': self.hue_variance_threshold
            }
        }
        
        return result


# Example usage and testing
if __name__ == "__main__":
    # Test the color detector
    detector = ColorDetector()
    
    # Example with a single image
    test_image = "test_image.jpg"  # Replace with actual image path
    if os.path.exists(test_image):
        result = detector.analyze_image_color(test_image)
        print(f"Analysis result: {result}")
        print(f"Is monochrome: {result['is_monochrome']}")
        print(f"Confidence: {result['confidence']:.2f}")
        if 'metrics' in result:
            print("Metrics:")
            for key, value in result['metrics'].items():
                print(f"  {key}: {value:.4f}")
