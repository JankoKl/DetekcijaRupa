import os
import logging
from pathlib import Path
from typing import Optional
from pydantic import BaseSettings, validator


class Settings(BaseSettings):
    # Model Configuration
    model_path: str = "models/pothole_model.pt"

    # Video Source Configuration
    video_source: str = "0"  # Default to webcam
    frame_width: int = 1280
    frame_height: int = 720
    process_every_nth_frame: int = 3

    # GPS Configuration
    simulate_gps: bool = True
    serial_port: str = "/dev/ttyUSB0"
    gps_baudrate: int = 9600
    gps_center_lat: float = 40.7128
    gps_center_lon: float = -74.0060
    gps_radius: float = 0.01

    # Database Configuration
    database_path: str = "data/potholes.db"
    database_pool_size: int = 5

    # Detection Configuration
    confidence_threshold: float = 0.5
    duplicate_threshold_meters: float = 15.0
    time_window_seconds: int = 300

    # Severity Configuration
    pixel_to_cm: float = 0.15
    depth_thresholds: tuple = (5, 10)
    size_thresholds: tuple = (20, 50)

    # Geocoding Configuration
    geocoding_timeout: int = 5
    geocoding_cache_file: str = "data/geocoding_cache.json"
    geocoding_max_workers: int = 2

    # Telegram Configuration
    telegram_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None

    # Logging Configuration
    log_level: str = "INFO"
    log_file: str = "logs/pothole_detector.log"

    @validator('model_path')
    def validate_model_path(cls, v):
        if not Path(v).exists():
            raise ValueError(f"Model file not found: {v}")
        return v

    @validator('log_level')
    def validate_log_level(cls, v):
        valid_levels = ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']
        if v.upper() not in valid_levels:
            raise ValueError(f"Invalid log level: {v}")
        return v.upper()

    class Config:
        env_prefix = "POTHOLE_"
        case_sensitive = False


# config/logging.py
import logging
import logging.handlers
from pathlib import Path


def setup_logging(settings) -> logging.Logger:
    """Setup logging configuration"""
    # Create logs directory
    log_dir = Path(settings.log_file).parent
    log_dir.mkdir(parents=True, exist_ok=True)

    # Configure root logger
    logger = logging.getLogger()
    logger.setLevel(getattr(logging, settings.log_level))

    # Clear existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
    )
    console_handler.setFormatter(console_format)
    logger.addHandler(console_handler)

    # File handler with rotation
    file_handler = logging.handlers.RotatingFileHandler(
        settings.log_file,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=5
    )
    file_handler.setLevel(getattr(logging, settings.log_level))
    file_format = logging.Formatter(
        '%(asctime)s [%(levelname)s] %(name)s:%(lineno)d - %(message)s'
    )
    file_handler.setFormatter(file_format)
    logger.addHandler(file_handler)

    return logger


# Create global settings instance
settings = Settings()