"""
Pothole Detection System
Main entry point for the application.

Usage:
    python main.py [--config CONFIG_FILE] [--video VIDEO_FILE] [--mode MODE]

Modes:
    - live: Process live video feed (default)
    - video: Process single video file
    - batch: Process multiple video files
    - test: Run system tests
"""

import sys
import argparse
import signal
import logging
from pathlib import Path
from dotenv import load_dotenv

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from config.config import config
from config.logging import setup_logging, get_logger
from core.services.pothole_service import PotholeService


class PotholeDetectionApp:
    """Main application class."""

    def __init__(self):
        self.logger = get_logger(__name__)
        self.service = None
        self.running = False

        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down gracefully...")
        self.running = False
        if self.service:
            self.service.stop()

    def run(self, mode: str = "live", video_path: str = None):
        """
        Run the application in specified mode.

        Args:
            mode: Mode of operation (live, video, batch, test)
            video_path: Path to video file if in video mode
        """
        if mode not in ["live", "video", "batch", "test"]:
            self.logger.error("Invalid mode specified. Use 'live', 'video', 'batch', or 'test'.")
            return

        self.logger.info(f"Running in {mode} mode")

        # Initialize the service
        self.service = PotholeService(config)

        try:
            self.service.start()
            self.running = True

            if mode == "live":
                self.service.run_live()
            elif mode == "video":
                if video_path:
                    self.service.run_video(video_path)
                else:
                    self.logger.error("Video path must be specified in video mode.")
            elif mode == "batch":
                self.service.run_batch()
            elif mode == "test":
                self.service.run_tests()

        except KeyboardInterrupt:
            self.logger.info("Application interrupted by user")
        except Exception as e:
            self.logger.error(f"Application error: {e}", exc_info=True)
        finally:
            self.stop()

    def stop(self):
        """Stop the application."""
        if self.service:
            self.service.stop()
        self.logger.info("Application stopped")


if __name__ == "__main__":
    load_dotenv()  # Load environment variables from .env file
    setup_logging(config.logging)  # Setup logging
    app = PotholeDetectionApp()

    # Argument parsing
    parser = argparse.ArgumentParser(description="Pothole Detection System")
    parser.add_argument("--mode", type=str, default="live", help="Mode of operation: live, video, batch, test")
    parser.add_argument("--video", type=str, help="Path to video file for video mode")
    args = parser.parse_args()

    app.run(mode=args.mode, video_path=args.video)
