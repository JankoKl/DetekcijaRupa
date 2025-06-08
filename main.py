import logging
import sys

from dotenv import load_dotenv

from config.config import config
from config.logging import setup_logging
from core.services.pothole_service import PotholeService


def main():
    """Main application entry point."""
    # Load environment variables
    load_dotenv()

    # Setup logging
    setup_logging(config.logging)
    logger = logging.getLogger(__name__)

    try:
        logger.info("Starting Pothole Detection System")

        # Initialize and start the service
        service = PotholeService(config)
        service.start()

    except KeyboardInterrupt:
        logger.info("Application stopped by user")
    except Exception as e:
        logger.error(f"Application error: {e}", exc_info=True)
        sys.exit(1)
    finally:
        logger.info("Application shutdown complete")


if __name__ == "__main__":
    main()