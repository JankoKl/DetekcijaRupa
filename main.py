import threading
import logging
import time
from config import settings, logging as config_logging
from core.detection.detector import PotholeDetector
from core.detection.processor import VideoProcessor
from core.gps.serial_receiver import SerialGPSReceiver
from core.gps.simulator import GPSSimulator
from core.data.repository import PotholeRepository
from core.services.pothole_service import PotholeService
from interfaces.telegram.bot import start_bot

def initialize_gps_provider(settings, logger):
    """Initialize the appropriate GPS provider based on settings"""
    if settings.simulate_gps:
        logger.info("Using GPS simulator")
        return GPSSimulator()
    else:
        logger.info(f"Using GPS receiver on {settings.serial_port}")
        return SerialGPSReceiver(settings.serial_port)

def initialize_telegram_bot(settings, logger):
    """Initialize Telegram bot in a separate thread if configured"""
    if settings.telegram_token:
        bot_thread = threading.Thread(
            target=start_bot,
            name="TelegramBot",
            daemon=True
        )
        bot_thread.start()
        logger.info("Telegram bot thread started")

def main():
    # Initialize logging
    logger = config_logging.setup_logging()
    logger.info("Starting Pothole Detection System")

    try:
        # Initialize core components
        detector = PotholeDetector(settings.model_path)
        repository = PotholeRepository(settings.data_file)
        gps_provider = initialize_gps_provider(settings, logger)
        service = PotholeService(detector, gps_provider, repository)

        # Start Telegram bot if configured
        initialize_telegram_bot(settings, logger)

        # Start video processing
        logger.info(f"Starting video processing from {settings.video_source}")
        processor = VideoProcessor(settings.video_source, service)
        processor.process_stream()

    except Exception as e:
        logger.error(f"Application error: {str(e)}", exc_info=True)
    finally:
        logger.info("Shutting down geocoding executor")
        service.geocoding_executor.shutdown(wait=False)
        logger.info("Application shutdown")

if __name__ == "__main__":
    main()