from ultralytics import YOLO
import numpy as np
from .severity import SeverityEstimator, SeverityLevel
import cv2


class PotholeDetector:
    def __init__(self, model_path: str):
        self.model = YOLO(model_path)
        self.severity_estimator = SeverityEstimator(pixel_to_cm=0.15)

    def detect(self, frame: np.ndarray) -> list:
        """Detect potholes and estimate severity"""
        results = self.model.predict(frame)
        detections = []

        for r in results:
            if r.masks is None:
                continue

            for box, mask in zip(r.boxes, r.masks):
                # Process mask
                mask_np = mask.data.cpu().numpy().squeeze()
                if mask_np.size == 0:
                    continue

                mask_uint8 = (mask_np * 255).astype(np.uint8)

                # Find contours
                contours, _ = cv2.findContours(
                    mask_uint8, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE
                )

                if not contours:
                    continue

                # Take largest contour
                contour = max(contours, key=cv2.contourArea)

                # Estimate severity
                severity, score = self.severity_estimator.estimate_severity(
                    contour=contour,
                    detection_confidence=box.conf.item()
                )

                detections.append({
                    'bbox': box.xyxy[0].tolist(),
                    'contour': contour,
                    'severity': severity,
                    'score': score,
                    'confidence': box.conf.item()
                })

        return detections