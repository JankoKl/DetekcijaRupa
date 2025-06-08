"""
Frame capture module for video processing and camera input.
"""
import cv2
import logging
import threading
import time
from typing import Optional, Union
from pathlib import Path
import numpy as np

from config.config import VideoConfig
from config.logging import get_logger


class FrameCapture:
    """Handles video frame capture from various sources."""

    def __init__(self, config: VideoConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.cap: Optional[cv2.VideoCapture] = None
        self.current_frame: Optional[np.ndarray] = None
        self.running = False
        self._lock = threading.Lock()
        self._capture_thread: Optional[threading.Thread] = None

        # Video source (can be file path, camera index, or URL)
        self.source: Optional[Union[str, int]] = None

    def start_capture(self, source: Union[str, int, Path] = None):
        """
        Start frame capture from specified source.

        Args:
            source: Video source (file path, camera index, or URL)
        """
        if self.running:
            self.logger.warning("Capture already running")
            return

        # Determine source
        if source is not None:
            self.source = str(source) if isinstance(source, Path) else source
        else:
            # Try to find a video file in input directory
            input_dir = Path(self.config.input_path)
            video_files = list(input_dir.glob("*.mp4")) + list(input_dir.glob("*.avi"))
            if video_files:
                self.source = str(video_files[0])
                self.logger.info(f"Using video file: {self.source}")
            else:
                # Default to camera
                self.source = 0
                self.logger.info("Using default camera")

        try:
            # Initialize video capture
            self.cap = cv2.VideoCapture(self.source)

            if not self.cap.isOpened():
                raise RuntimeError(f"Failed to open video source: {self.source}")

            # Set capture properties for better performance
            if isinstance(self.source, int):  # Camera
                self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
                self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
                self.cap.set(cv2.CAP_PROP_FPS, 30)

            self.running = True

            # Start capture thread
            self._capture_thread = threading.Thread(target=self._capture_loop, daemon=True)
            self._capture_thread.start()

            self.logger.info(f"Started frame capture from: {self.source}")

        except Exception as e:
            self.logger.error(f"Failed to start capture: {e}")
            self.stop()
            raise

    def stop(self):
        """Stop frame capture."""
        self.running = False

        if self._capture_thread and self._capture_thread.is_alive():
            self._capture_thread.join(timeout=5.0)

        if self.cap:
            self.cap.release()
            self.cap = None

        with self._lock:
            self.current_frame = None

        self.logger.info("Frame capture stopped")

    def _capture_loop(self):
        """Main capture loop running in separate thread."""
        frame_count = 0

        while self.running and self.cap and self.cap.isOpened():
            try:
                ret, frame = self.cap.read()

                if not ret:
                    if isinstance(self.source, str):  # Video file ended
                        self.logger.info("Video file ended, restarting...")
                        self.cap.set(cv2.CAP_PROP_POS_FRAMES, 0)  # Restart video
                        continue
                    else:  # Camera error
                        self.logger.error("Failed to read frame from camera")
                        break

                frame_count += 1

                # Apply frame skip
                if frame_count % self.config.frame_skip != 0:
                    continue

                # Validate frame
                if frame is None or frame.size == 0:
                    continue

                # Store frame thread-safely
                with self._lock:
                    self.current_frame = frame.copy()

                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)

            except Exception as e:
                self.logger.error(f"Error in capture loop: {e}")
                time.sleep(1)  # Wait before retrying

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Get the latest captured frame.

        Returns:
            Latest frame or None if no frame available
        """
        with self._lock:
            return self.current_frame.copy() if self.current_frame is not None else None

    def get_frame_info(self) -> dict:
        """Get information about the current video source."""
        if not self.cap or not self.cap.isOpened():
            return {}

        try:
            info = {
                'source': self.source,
                'width': int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
                'height': int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
                'fps': self.cap.get(cv2.CAP_PROP_FPS),
                'frame_count': int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT)),
                'current_frame': int(self.cap.get(cv2.CAP_PROP_POS_FRAMES)),
                'running': self.running
            }
            return info
        except Exception as e:
            self.logger.error(f"Error getting frame info: {e}")
            return {}

    def save_frame(self, frame: np.ndarray, filename: str) -> bool:
        """
        Save a frame to file.

        Args:
            frame: Frame to save
            filename: Output filename

        Returns:
            True if successful, False otherwise
        """
        try:
            output_path = Path(self.config.output_path) / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            success = cv2.imwrite(str(output_path), frame)
            if success:
                self.logger.debug(f"Frame saved to: {output_path}")
            else:
                self.logger.error(f"Failed to save frame to: {output_path}")

            return success

        except Exception as e:
            self.logger.error(f"Error saving frame: {e}")
            return False

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.stop()
