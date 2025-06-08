import time

import cv2
import logging
from typing import Optional, Union
from pathlib import Path
from enum import Enum

import numpy as np

from config import settings

logger = logging.getLogger(__name__)


class FrameSource(Enum):
    WEBCAM = 0
    RTSP = 1
    VIDEO_FILE = 2
    IMAGE_DIR = 3


class FrameCapture:
    def __init__(self, source: Union[int, str, Path]):
        """
        Initialize frame capture from various sources
        :param source: Can be:
            - 0 for default webcam
            - RTSP/HTTP URL (e.g., 'rtsp://192.168.1.64:554/stream')
            - Video file path (e.g., 'data/videos/potholes.mp4')
            - Directory path for image sequence
        """
        self.source = source
        self.cap = None
        self._init_capture()

    def _init_capture(self):
        """Initialize the appropriate capture method"""
        try:
            if isinstance(self.source, int):  # Webcam
                self.cap = cv2.VideoCapture(self.source)
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                logger.info(f"Initialized webcam capture (ID: {self.source})")
            elif str(self.source).startswith(('rtsp://', 'http://')):
                self.cap = cv2.VideoCapture(self.source)
                logger.info(f"Initialized RTSP stream: {self.source}")
            elif Path(self.source).is_dir():  # Image directory
                self.image_files = sorted(Path(self.source).glob("*.jpg"))
                self.frame_idx = 0
                logger.info(f"Initialized image sequence: {len(self.image_files)} frames")
            else:  # Video file
                self.cap = cv2.VideoCapture(str(self.source))
                logger.info(f"Initialized video file: {self.source}")
        except Exception as e:
            logger.error(f"Failed to initialize capture: {e}")
            raise

    def get_frame(self) -> Optional[tuple[bool, np.ndarray]]:
        """
        Get next frame from the source
        :return: Tuple of (success, frame) or None if source is invalid
        """
        try:
            if hasattr(self, 'image_files'):  # Image sequence mode
                if self.frame_idx >= len(self.image_files):
                    return False, None
                frame = cv2.imread(str(self.image_files[self.frame_idx]))
                self.frame_idx += 1
                return frame is not None, frame

            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret and str(self.source).startswith('rtsp://'):
                    logger.warning("RTSP stream disconnected, attempting reconnect...")
                    self._reconnect()
                    return self.get_frame()
                return ret, frame

            return False, None
        except Exception as e:
            logger.error(f"Frame capture error: {e}")
            return False, None

    def _reconnect(self, max_attempts=3, delay=2):
        """Attempt to reconnect to RTSP stream"""
        for attempt in range(max_attempts):
            self.cap.release()
            self._init_capture()
            if self.cap.isOpened():
                return True
            time.sleep(delay)
        return False

    def release(self):
        """Release capture resources"""
        if self.cap and self.cap.isOpened():
            self.cap.release()
        logger.info("Released frame capture resources")