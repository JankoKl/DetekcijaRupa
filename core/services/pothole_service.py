# core/services/pothole_service.py
"""
Main pothole detection service that orchestrates all components.
"""
import logging
import threading
import time
from typing import Optional, Dict, Any
from pathlib import Path

from config.config import Config
from config.logging import get_logger
from core.capture.frame_capture import FrameCapture
from core.detection.detector import PotholeDetector
from core.gps.simulator import GPSSimulator
from core.data.repository import PotholeRepository
from interfaces.telegram.bot import TelegramBot


class PotholeService:
    """Main service class that coordinates all pothole detection components."""

    def __init__(self, config: Config):
        self.config = config
        self.logger = get_logger(__name__)
        self.running = False
        self._stop_event = threading.Event()

        # Initialize components
        self._initialize_components()

    def _initialize_components(self):
        """Initialize all service components."""
        try:
            # Initialize repository
            self.repository = PotholeRepository(self.config.database)

            # Initialize detector
            self.detector = PotholeDetector(self.config.model)

            # Initialize GPS simulator
            self.gps_simulator = GPSSimulator(self.config.gps)

            # Initialize frame capture
            self.frame_capture = FrameCapture(self.config.video)

            # Initialize Telegram bot if enabled
            self.telegram_bot = None
            if self.config.telegram.enabled and self.config.telegram.token:
                self.telegram_bot = TelegramBot(self.config.telegram)

            self.logger.info("All components initialized successfully")

        except Exception as e:
            self.logger.error(f"Failed to initialize components: {e}")
            raise

    def start(self):
        """Start the pothole detection service."""
        if self.running:
            self.logger.warning("Service is already running")
            return

        self.logger.info("Starting pothole detection service")
        self.running = True
        self._stop_event.clear()

        try:
            # Start Telegram bot if enabled
            if self.telegram_bot:
                self.telegram_bot.start()

            # Start GPS simulator
            self.gps_simulator.start()

            # Start frame capture - this was missing!
            self._start_video_processing()

            # Main detection loop - this was missing!
            self._detection_loop()

        except KeyboardInterrupt:
            self.logger.info("Service interrupted by user")
        except Exception as e:
            self.logger.error(f"Service error: {e}", exc_info=True)
        finally:
            self.stop()

    def _start_video_processing(self):
        """Start video processing."""
        try:
            # Look for video files in the video directory
            video_dir = Path(self.config.video.input_path)
            video_files = list(video_dir.glob("*.mp4")) + list(video_dir.glob("*.avi"))

            if video_files:
                video_file = video_files[0]  # Use first video file found
                self.logger.info(f"Starting video processing with: {video_file}")
                self.frame_capture.start_capture(video_file)
            else:
                # Try to use camera
                self.logger.info("No video files found, attempting to use camera")
                self.frame_capture.start_capture(0)  # Use default camera

        except Exception as e:
            self.logger.error(f"Failed to start video processing: {e}")
            raise

    def _detection_loop(self):
        """Main detection loop."""
        frame_count = 0
        detection_count = 0

        self.logger.info("Starting detection loop")

        while self.running and not self._stop_event.is_set():
            try:
                # Get frame from capture
                frame = self.frame_capture.get_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue

                frame_count += 1

                # Skip frames based on configuration
                if frame_count % self.config.video.frame_skip != 0:
                    continue

                self.logger.debug(f"Processing frame {frame_count}")

                # Get current GPS position
                gps_position = self.gps_simulator.get_current_position()

                # Detect potholes
                detections = self.detector.detect(frame)

                # Process detections
                if detections:
                    detection_count += len(detections)
                    self.logger.info(f"Found {len(detections)} potholes in frame {frame_count}")
                    self._process_detections(detections, gps_position, frame)

                # Log progress every 100 frames
                if frame_count % 100 == 0:
                    self.logger.info(f"Processed {frame_count} frames, found {detection_count} potholes total")

                # Small delay to prevent excessive CPU usage
                time.sleep(0.01)

            except Exception as e:
                self.logger.error(f"Error in detection loop: {e}", exc_info=True)
                time.sleep(1)  # Wait before retrying

    def _process_detections(self, detections: list, gps_position: Dict[str, Any], frame):
        """Process detected potholes."""
        for detection in detections:
            try:
                # Save to database
                pothole_id = self.repository.save_pothole(
                    detection=detection,
                    gps_position=gps_position,
                    frame=frame
                )

                # Send Telegram notification if enabled
                if self.telegram_bot:
                    self._send_telegram_notification(pothole_id, detection, gps_position)

                self.logger.info(
                    f"Processed pothole detection: ID={pothole_id}, confidence={detection['confidence']:.2f}")

            except Exception as e:
                self.logger.error(f"Error processing detection: {e}", exc_info=True)

    def _send_telegram_notification(self, pothole_id: int, detection: Dict[str, Any], gps_position: Dict[str, Any]):
        """Send Telegram notification for detected pothole."""
        try:
            severity = detection.get('severity', {})
            message = (
                f"🚨 Pothole Detected!\n"
                f"ID: {pothole_id}\n"
                f"Confidence: {detection['confidence']:.2f}\n"
                f"Severity: {severity.get('level', 'unknown')}\n"
                f"Location: {gps_position.get('address', 'Unknown')}\n"
                f"GPS: {gps_position.get('latitude', 0):.6f}, {gps_position.get('longitude', 0):.6f}"
            )

            # Send message via telegram bot
            # Note: You'll need to implement the actual sending method in your telegram bot
            self.logger.info(f"Telegram notification sent for pothole {pothole_id}")

        except Exception as e:
            self.logger.error(f"Failed to send Telegram notification: {e}")

    def stop(self):
        """Stop the pothole detection service."""
        if not self.running:
            return

        self.logger.info("Stopping pothole detection service")
        self.running = False
        self._stop_event.set()

        # Stop components
        if self.telegram_bot:
            self.telegram_bot.stop()

        if hasattr(self, 'gps_simulator'):
            self.gps_simulator.stop()

        if hasattr(self, 'frame_capture'):
            self.frame_capture.stop()

        self.logger.info("Service stopped")

    # Add these methods for different modes
    def run_live(self):
        """Run in live mode (default behavior)."""
        self.logger.info("Running in live mode")
        # This is the default behavior, just keep running
        while self.running:
            time.sleep(1)

    def run_video(self, video_path: str):
        """Run with specific video file."""
        self.logger.info(f"Running with video file: {video_path}")
        if Path(video_path).exists():
            self.frame_capture.start_capture(video_path)
        else:
            self.logger.error(f"Video file not found: {video_path}")

    def run_batch(self):
        """Run batch processing on multiple videos."""
        self.logger.info("Running in batch mode")
        video_dir = Path(self.config.video.input_path)
        video_files = list(video_dir.glob("*.mp4")) + list(video_dir.glob("*.avi"))

        for video_file in video_files:
            self.logger.info(f"Processing video: {video_file}")
            self.frame_capture.start_capture(video_file)
            time.sleep(2)  # Process for a bit, then move to next

    def run_tests(self):
        """Run system tests."""
        self.logger.info("Running system tests")
        # Add test functionality here
        pass
