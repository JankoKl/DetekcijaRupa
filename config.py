import os
from dataclasses import dataclass



@dataclass
class Config:
    # GPS Configuration
    GPS_PORT: str = 'COM10'
    GPS_BAUDRATE: int = 9600

    # Model Paths
    YOLO_MODEL_PATH: str = 'best.pt'
    MIDAS_MODEL_PATH: str = 'dpt_swin2_large_384.pt'  # Your downloaded model
    MIDAS_MODEL_TYPE: str = 'dpt_swin2_large_384'  # or 'DPT_Hybrid' or 'MiDaS'

    # Video Configuration
    VIDEO_FILE: str = 'p.mp4'
    FRAME_SKIP: int = 3
    VIDEO_WIDTH: int = 1020
    VIDEO_HEIGHT: int = 500

    # Database Configuration
    DB_HOST: str = 'localhost'
    DB_PORT: int = 5432
    DB_PATH: str = 'pothole.db'
    DB_NAME: str = 'pothole_db'
    DB_USER: str = 'sqlite'
    DB_PASSWORD: str = '555333'

    # Telegram Bot
    BOT_TOKEN: str = '7040394124:AAGKEPB8LHwdSQw__w-LMpMsaHrHvtdiB1s'

    # Paths
    DATA_DIR: str = 'data'
    OFFLINE_LOG_DIR: str = os.path.join(DATA_DIR, 'offline_logs')
    EXPORT_DIR: str = os.path.join(DATA_DIR, 'exports')

    # Detection Parameters
    DUPLICATE_RADIUS_METERS: float = 5.0  # Consider same pothole if within 5 meters
    SEVERITY_THRESHOLDS: dict = None

    def __post_init__(self):
        # Create directories if they don't exist
        os.makedirs(self.OFFLINE_LOG_DIR, exist_ok=True)
        os.makedirs(self.EXPORT_DIR, exist_ok=True)

        # Define severity thresholds
        self.SEVERITY_THRESHOLDS = {
            'low': {'area': 100, 'depth': 0.05},
            'medium': {'area': 500, 'depth': 0.10},
            'high': {'area': 1000, 'depth': 0.15},
            'critical': {'area': float('inf'), 'depth': float('inf')}
        }


config = Config()
