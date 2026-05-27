import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # GPS
    USE_SIMULATION: bool = os.getenv('USE_SIMULATION', 'True') == 'True'
    GPS_PORT: str = os.getenv('GPS_PORT', 'COM10')
    GPS_BAUDRATE: int = int(os.getenv('GPS_BAUDRATE', 9600))

    # Model
    YOLO_MODEL_PATH: str = os.getenv('YOLO_MODEL_PATH', 'best.pt')

    # Input
    USE_LIVE_CAMERA: bool = os.getenv('USE_LIVE_CAMERA', 'False') == 'True'
    VIDEO_WIDTH: int = int(os.getenv('VIDEO_WIDTH', 1020))
    VIDEO_HEIGHT: int = int(os.getenv('VIDEO_HEIGHT', 500))
    VIDEO_FILE: str = os.getenv('VIDEO_FILE', 'p.mp4')
    FRAME_SKIP: int = int(os.getenv('FRAME_SKIP', 3))
    CAMERA_INDEX: int = int(os.getenv('CAMERA_INDEX', 0))

    # Output
    SAVE_VIDEO: bool = os.getenv('SAVE_VIDEO', 'True') == 'True'
    VIDEO_OUTPUT_PATH: str = os.getenv('VIDEO_OUTPUT_PATH', '.output/demo_output.avi')
    VIDEO_FPS: int = int(os.getenv('VIDEO_FPS', 20))

    # Database
    DB_PATH: str = os.getenv('DB_PATH', 'pothole.db')

    # Telegram
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')
    # Chat ID admina — ko god ima ovaj ID dobija admin ulogu automatski
    # Kako pronaci svoj chat ID: posalji /start botu @userinfobot na Telegramu
    ADMIN_CHAT_ID: str = os.getenv('ADMIN_CHAT_ID', '')

    # Paths
    DATA_DIR: str = os.getenv('DATA_DIR', 'data')
    OFFLINE_LOG_DIR: str = ''
    EXPORT_DIR: str = ''

    # Detection
    DUPLICATE_RADIUS_METERS: float = float(os.getenv('DUPLICATE_RADIUS_METERS', 5.0))
    SEVERITY_THRESHOLDS: dict = None

    def __post_init__(self):
        self.OFFLINE_LOG_DIR = os.path.join(self.DATA_DIR, 'offline_logs')
        self.EXPORT_DIR = os.path.join(self.DATA_DIR, 'exports')

        os.makedirs(self.OFFLINE_LOG_DIR, exist_ok=True)
        os.makedirs(self.EXPORT_DIR, exist_ok=True)

        self.SEVERITY_THRESHOLDS = {
            'low':      {'area': 100,          'depth': 0.05},
            'medium':   {'area': 500,          'depth': 0.10},
            'high':     {'area': 1000,         'depth': 0.15},
            'critical': {'area': float('inf'), 'depth': float('inf')}
        }


config = Config()