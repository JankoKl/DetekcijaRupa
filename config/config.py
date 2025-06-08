import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database configuration settings."""
    url: str = "sqlite:///data/potholes.db"
    backup_enabled: bool = True
    backup_interval_hours: int = 24


@dataclass
class TelegramConfig:
    """Telegram bot configuration settings."""
    token: Optional[str] = None
    chat_id: Optional[str] = None
    enabled: bool = True


@dataclass
class ModelConfig:
    """AI model configuration settings."""
    yolo_model_path: str = "models/best.pt"
    confidence_threshold: float = 0.5
    device: str = "auto"  # auto, cpu, cuda


@dataclass
class GPSConfig:
    """GPS configuration settings."""
    serial_port: str = "/dev/ttyUSB0"
    baud_rate: int = 9600
    simulation_mode: bool = True
    cache_file: str = "data/geocoding_cache.json"


@dataclass
class LoggingConfig:
    """Logging configuration settings."""
    level: str = "INFO"
    file_path: str = "logs/pothole_detector.log"
    max_file_size_mb: int = 10
    backup_count: int = 5


@dataclass
class Config:
    """Main configuration class."""
    database: DatabaseConfig
    telegram: TelegramConfig
    model: ModelConfig
    gps: GPSConfig
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
            logging=LoggingConfig(
                level=os.getenv('LOG_LEVEL', 'INFO'),
                file_path=os.getenv('LOG_FILE', 'logs/pothole_detector.log'),
                max_file_size_mb=int(os.getenv('LOG_MAX_SIZE_MB', '10')),
                backup_count=int(os.getenv('LOG_BACKUP_COUNT', '5')),
            ),
        )


# Global configuration instance
config = Config.from_env()
