import json

import cv2
from core.detection.severity import SeverityEstimator

# Take image with known object (e.g., 20cm marker)
image = cv2.imread("calibration.jpg")
marker_pixels = 150  # Measure this in the image
estimator = SeverityEstimator()
estimator.pixel_to_cm = 20.0 / marker_pixels
print(f"Calibrated pixel_to_cm: {estimator.pixel_to_cm}")