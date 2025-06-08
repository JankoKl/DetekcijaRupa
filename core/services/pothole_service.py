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

            # Main detection loop
            self._detection_loop()

        except KeyboardInterrupt:
            self.logger.info("Service interrupted by user")
        except Exception as e:
            self.logger.error(f"Service error: {e}", exc_info=True)
        finally:
            self.stop()

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

    def _detection_loop(self):
        """Main detection loop."""
        frame_count = 0

        while self.running and not self._stop_event.is_set():
            try:
                # Capture frame
                frame = self.frame_capture.get_frame()
                if frame is None:
                    time.sleep(0.1)
                    continue

                # Skip frames based on configuration
                frame_count += 1
                if frame_count % self.config.video.frame_skip != 0:
                    continue

                # Get current GPS position
                gps_position = self.gps_simulator.get_current_position()

                # Detect potholes
                detections = self.detector.detect(frame)

                # Process detections
                if detections:
                    self._process_detections(detections, gps_position, frame)

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
                    self.telegram_bot.send_pothole_notification(
                        pothole_id=pothole_id,
                        detection=detection,
                        gps_position=gps_position
                    )

                self.logger.info(f"Processed pothole detection: {pothole_id}")

            except Exception as e:
                self.logger.error(f"Error processing detection: {e}", exc_info=True)
