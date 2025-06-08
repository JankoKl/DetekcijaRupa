"""
Configuration management for the Pothole Detection System.
Handles environment variables and provides type-safe configuration.
"""
import os
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Union
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    url: str = "sqlite:///data/potholes.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24

    def __post_init__(self):
        """Ensure database directory exists."""
        if self.url.startswith('sqlite:///'):
            db_path = Path(self.url.replace('sqlite:///', ''))
            db_path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class TelegramConfig:
    """Telegram bot configuration settings."""
    token: Optional[str] = None
    chat_id: Optional[str] = None
    enabled: bool = True

    def __post_init__(self):
        """Validate telegram configuration."""
        if self.enabled and not self.token:
            logging.warning("Telegram is enabled but no token provided. Disabling Telegram notifications.")
            self.enabled = False


@dataclass
class ModelConfig:
    """AI model configuration settings."""
    yolo_model_path: str = "models/best.pt"
    confidence_threshold: float = 0.5
    device: str = "auto"  # auto, cpu, cuda

    def __post_init__(self):
        """Validate model configuration."""
        if not Path(self.yolo_model_path).exists():
            logging.warning(f"Model file not found: {self.yolo_model_path}")

        if not 0.0 <= self.confidence_threshold <= 1.0:
            logging.warning(f"Invalid confidence threshold: {self.confidence_threshold}. Using 0.5")
            self.confidence_threshold = 0.5


@dataclass
class GPSConfig:
    """GPS configuration settings."""
    serial_port: str = "/dev/ttyUSB0"
    baud_rate: int = 9600
    simulation_mode: bool = True
    cache_file: str = "data/geocoding_cache.json"

    def __post_init__(self):
        """Ensure cache directory exists."""
        cache_path = Path(self.cache_file)
        cache_path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class VideoConfig:
    """Video processing configuration."""
    input_path: str = "data/videos/"
    output_path: str = "data/output/"
    frame_skip: int = 1
    max_video_size_mb: int = 100

    def __post_init__(self):
        """Ensure video directories exist."""
        Path(self.input_path).mkdir(parents=True, exist_ok=True)
        Path(self.output_path).mkdir(parents=True, exist_ok=True)


@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    level: str = "INFO"
    file_path: str = "logs/pothole_detector.log"
    max_file_size_mb: int = 10
    backup_count: int = 5
    format: str = "%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s"

    def __post_init__(self):
        """Ensure log directory exists."""
        log_path = Path(self.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)


@dataclass
class Config:
    """Main configuration class."""
    database: DatabaseConfig
    telegram: TelegramConfig
    model: ModelConfig
    gps: GPSConfig
    video: VideoConfig
    logging: LoggingConfig

    @classmethod
    def from_env(cls) -> 'Config':
        """Create configuration from environment variables."""
        return cls(
            database=DatabaseConfig(
                url=os.getenv('DATABASE_URL', 'sqlite:///data/potholes.db'),
                backup_enabled=os.getenv('DB_BACKUP_ENABLED', 'true').lower() == 'true',
                backup_interval_hours=int(os.getenv('DB_BACKUP_INTERVAL_HOURS', '24')),
            ),
            telegram=TelegramConfig(
                token=os.getenv('TELEGRAM_TOKEN'),
                chat_id=os.getenv('TELEGRAM_CHAT_ID'),
                enabled=os.getenv('TELEGRAM_ENABLED', 'true').lower() == 'true',
            ),
            model=ModelConfig(
                yolo_model_path=os.getenv('YOLO_MODEL_PATH', 'models/best.pt'),
                confidence_threshold=float(os.getenv('MODEL_CONFIDENCE', '0.5')),
                device=os.getenv('MODEL_DEVICE', 'auto'),
            ),
            gps=GPSConfig(
                serial_port=os.getenv('GPS_SERIAL_PORT', '/dev/ttyUSB0'),
                baud_rate=int(os.getenv('GPS_BAUD_RATE', '9600')),
                simulation_mode=os.getenv('GPS_SIMULATION', 'true').lower() == 'true',
                cache_file=os.getenv('GPS_CACHE_FILE', 'data/geocoding_cache.json'),
            ),
            video=VideoConfig(
                input_path=os.getenv('VIDEO_INPUT_PATH', 'data/videos/'),
                output_path=os.getenv('VIDEO_OUTPUT_PATH', 'data/output/'),
                frame_skip=int(os.getenv('FRAME_SKIP', '1')),
                max_video_size_mb=int(os.getenv('MAX_VIDEO_SIZE_MB', '100')),
            ),
            logging=LoggingConfig(
                level=os.getenv('LOG_LEVEL', 'INFO'),
                file_path=os.getenv('LOG_FILE', 'logs/pothole_detector.log'),
                max_file_size_mb=int(os.getenv('LOG_MAX_SIZE_MB', '10')),
                backup_count=int(os.getenv('LOG_BACKUP_COUNT', '5')),
            ),
        )

    def validate(self) -> bool:
        """Validate the entire configuration."""
        try:
            # Check critical paths
            if not Path(self.model.yolo_model_path).exists():
                logging.error(f"Critical: Model file not found: {self.model.yolo_model_path}")
                return False

            # Validate numeric ranges
            if not 0.0 <= self.model.confidence_threshold <= 1.0:
                logging.error(f"Invalid confidence threshold: {self.model.confidence_threshold}")
                return False

            if self.video.frame_skip < 1:
                logging.error(f"Invalid frame skip: {self.video.frame_skip}")
                return False

            return True
        except Exception as e:
            logging.error(f"Configuration validation failed: {e}")
            return False


# Global configuration instance
config = Config.from_env()
