# core/detection/detector.py
"""
YOLO-based pothole detection module.
"""
import logging
import time

import cv2
import numpy as np
from typing import List, Dict, Any, Optional
from pathlib import Path

try:
    from ultralytics import YOLO
except ImportError:
    YOLO = None

from config.config import ModelConfig
from config.logging import get_logger
from core.detection.severity import SeverityAnalyzer


class PotholeDetector:
    """YOLO-based pothole detector."""

    def __init__(self, config: ModelConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.model = None
        self.severity_analyzer = SeverityAnalyzer()

        self._load_model()

    def _load_model(self):
        """Load the YOLO model."""
        if YOLO is None:
            raise ImportError("ultralytics package is required for YOLO detection")

        model_path = Path(self.config.yolo_model_path)
        if not model_path.exists():
            raise FileNotFoundError(f"Model file not found: {model_path}")

        try:
            self.model = YOLO(str(model_path))
            self.logger.info(f"YOLO model loaded from {model_path}")
        except Exception as e:
            self.logger.error(f"Failed to load YOLO model: {e}")
            raise

    def detect(self, frame: np.ndarray) -> List[Dict[str, Any]]:
        """
        Detect potholes in the given frame.

        Args:
            frame: Input image frame

        Returns:
            List of detection dictionaries
        """
        if self.model is None:
            self.logger.error("Model not loaded")
            return []

        try:
            # Run YOLO detection
            results = self.model(frame, conf=self.config.confidence_threshold)

            detections = []
            for result in results:
                if result.boxes is not None:
                    for box in result.boxes:
                        detection = self._process_detection(box, frame)
                        if detection:
                            detections.append(detection)

            return detections

        except Exception as e:
            self.logger.error(f"Detection error: {e}", exc_info=True)
            return []

    def _process_detection(self, box, frame: np.ndarray) -> Optional[Dict[str, Any]]:
        """Process a single detection box."""
        try:
            # Extract box coordinates
            x1, y1, x2, y2 = box.xyxy[0].cpu().numpy()
            confidence = float(box.conf[0].cpu().numpy())

            # Calculate box properties
            width = x2 - x1
            height = y2 - y1
            area = width * height

            # Extract region of interest
            roi = frame[int(y1):int(y2), int(x1):int(x2)]

            # Analyze severity
            severity = self.severity_analyzer.analyze(roi, area)

            detection = {
                'bbox': [int(x1), int(y1), int(x2), int(y2)],
                'confidence': confidence,
                'area': float(area),
                'width': float(width),
                'height': float(height),
                'severity': severity,
                'timestamp': time.time()
            }

            return detection

        except Exception as e:
            self.logger.error(f"Error processing detection: {e}")
            return None
