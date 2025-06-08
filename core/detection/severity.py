import cv2
import logging
from enum import Enum

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)

class SeverityLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"

class SeverityEstimator:
    def __init__(self, pixel_to_cm=0.1, depth_thresholds=(5, 10), size_thresholds=(20, 50)):
        self.pixel_to_cm = pixel_to_cm
        self.depth_thresholds = depth_thresholds
        self.size_thresholds = size_thresholds

    def estimate_severity(self, contour, depth_estimate=None, detection_confidence=1.0):
        (x, y, w, h) = cv2.boundingRect(contour)
        diameter_px = max(w, h)
        area_px = w * h

        diameter_cm = diameter_px * self.pixel_to_cm
        area_cm2 = area_px * (self.pixel_to_cm ** 2)

        if depth_estimate is None:
            logging.warning("No depth estimate provided, assuming 0 cm.")
            depth_estimate = 0

        # Compute severity score without confidence
        score = 0
        size_low, size_high = self.size_thresholds

        # Size contributes 50% of score
        if diameter_cm > size_high:
            score += 40
        elif diameter_cm > size_low:
            score += 25
        else:
            score += 10

        # Depth contributes 50% of score
        depth_low, depth_high = self.depth_thresholds
        if depth_estimate > depth_high:
            score += 40
        elif depth_estimate > depth_low:
            score += 25
        else:
            score += 10

        # Adjust thresholds for new max of 80
        if score >= 56:   # 70% of 80
            level = SeverityLevel.HIGH
        elif score >= 32:  # 40% of 80
            level = SeverityLevel.MEDIUM
        else:
            level = SeverityLevel.LOW

        return level, score