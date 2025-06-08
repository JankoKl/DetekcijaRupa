# core/detection/severity.py
"""
Pothole severity analysis module.
"""
import cv2
import numpy as np
from typing import Dict, Any
from enum import Enum


class SeverityLevel(Enum):
    """Pothole severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class SeverityAnalyzer:
    """Analyzes pothole severity based on visual features."""

    def __init__(self):
        # Thresholds for severity classification
        self.area_thresholds = {
            'small': 1000,
            'medium': 5000,
            'large': 15000
        }

        self.depth_thresholds = {
            'shallow': 0.3,
            'medium': 0.6,
            'deep': 0.8
        }

    def analyze(self, roi: np.ndarray, area: float) -> Dict[str, Any]:
        """
        Analyze pothole severity.

        Args:
            roi: Region of interest containing the pothole
            area: Area of the pothole in pixels

        Returns:
            Dictionary containing severity analysis
        """
        try:
            # Estimate depth using shadow analysis
            depth_score = self._estimate_depth(roi)

            # Classify based on area
            area_category = self._classify_area(area)

            # Classify based on depth
            depth_category = self._classify_depth(depth_score)

            # Determine overall severity
            severity_level = self._determine_severity(area_category, depth_category)

            return {
                'level': severity_level.value,
                'area_category': area_category,
                'depth_category': depth_category,
                'depth_score': depth_score,
                'area_pixels': area,
                'risk_score': self._calculate_risk_score(severity_level, area, depth_score)
            }

        except Exception as e:
            # Return default severity on error
            return {
                'level': SeverityLevel.MEDIUM.value,
                'area_category': 'unknown',
                'depth_category': 'unknown',
                'depth_score': 0.5,
                'area_pixels': area,
                'risk_score': 0.5,
                'error': str(e)
            }

    def _estimate_depth(self, roi: np.ndarray) -> float:
        """Estimate pothole depth using shadow and texture analysis."""
        if roi.size == 0:
            return 0.0

        try:
            # Convert to grayscale
            gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY) if len(roi.shape) == 3 else roi

            # Calculate darkness (shadows indicate depth)
            darkness = 1.0 - (np.mean(gray) / 255.0)

            # Calculate texture variation (rough surfaces indicate depth)
            texture = np.std(gray) / 255.0

            # Combine metrics
            depth_score = (darkness * 0.7 + texture * 0.3)

            return min(max(depth_score, 0.0), 1.0)

        except Exception:
            return 0.5

    def _classify_area(self, area: float) -> str:
        """Classify pothole based on area."""
        if area < self.area_thresholds['small']:
            return 'small'
        elif area < self.area_thresholds['medium']:
            return 'medium'
        elif area < self.area_thresholds['large']:
            return 'large'
        else:
            return 'very_large'

    def _classify_depth(self, depth_score: float) -> str:
        """Classify pothole based on depth score."""
        if depth_score < self.depth_thresholds['shallow']:
            return 'shallow'
        elif depth_score < self.depth_thresholds['medium']:
            return 'medium'
        elif depth_score < self.depth_thresholds['deep']:
            return 'deep'
        else:
            return 'very_deep'

    def _determine_severity(self, area_category: str, depth_category: str) -> SeverityLevel:
        """Determine overall severity level."""
        # Severity matrix
        severity_matrix = {
            ('small', 'shallow'): SeverityLevel.LOW,
            ('small', 'medium'): SeverityLevel.LOW,
            ('small', 'deep'): SeverityLevel.MEDIUM,
            ('small', 'very_deep'): SeverityLevel.MEDIUM,

            ('medium', 'shallow'): SeverityLevel.LOW,
            ('medium', 'medium'): SeverityLevel.MEDIUM,
            ('medium', 'deep'): SeverityLevel.MEDIUM,
            ('medium', 'very_deep'): SeverityLevel.HIGH,

            ('large', 'shallow'): SeverityLevel.MEDIUM,
            ('large', 'medium'): SeverityLevel.MEDIUM,
            ('large', 'deep'): SeverityLevel.HIGH,
            ('large', 'very_deep'): SeverityLevel.HIGH,

            ('very_large', 'shallow'): SeverityLevel.MEDIUM,
            ('very_large', 'medium'): SeverityLevel.HIGH,
            ('very_large', 'deep'): SeverityLevel.HIGH,
            ('very_large', 'very_deep'): SeverityLevel.CRITICAL,
        }

        return severity_matrix.get((area_category, depth_category), SeverityLevel.MEDIUM)

    def _calculate_risk_score(self, severity: SeverityLevel, area: float, depth_score: float) -> float:
        """Calculate a numerical risk score (0-1)."""
        base_scores = {
            SeverityLevel.LOW: 0.2,
            SeverityLevel.MEDIUM: 0.5,
            SeverityLevel.HIGH: 0.8,
            SeverityLevel.CRITICAL: 1.0
        }

        base_score = base_scores[severity]

        # Adjust based on area and depth
        area_factor = min(area / 10000, 1.0)  # Normalize to 0-1
        depth_factor = depth_score

        # Weighted combination
        risk_score = (base_score * 0.6 + area_factor * 0.2 + depth_factor * 0.2)

        return min(max(risk_score, 0.0), 1.0)
