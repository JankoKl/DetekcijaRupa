import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()  # Load variables from .env

@dataclass
class Config:
    # GPS Configuration
    USE_SIMULATION: bool = os.getenv('USE_SIMULATION', 'True') == 'True'  # Set to False to use real GPS
    GPS_PORT: str = os.getenv('GPS_PORT', 'COM10')
    GPS_BAUDRATE: int = int(os.getenv('GPS_BAUDRATE', 9600))

    # Model Paths
    YOLO_MODEL_PATH: str = os.getenv('YOLO_MODEL_PATH', 'best.pt')
   # MIDAS_MODEL_PATH: str = 'dpt_swin2_large_384.pt'  # downloaded model
   # MIDAS_MODEL_TYPE: str = 'dpt_swin2_large_384'  # or 'DPT_Hybrid' or 'MiDaS'

    #Input Video Configuration
    USE_LIVE_CAMERA: bool = os.getenv('USE_LIVE_CAMERA', 'False') == 'True'  # Set to True to use live camera, false for video file
    VIDEO_WIDTH: int = int(os.getenv('VIDEO_WIDTH', 1020))
    VIDEO_HEIGHT: int = int(os.getenv('VIDEO_HEIGHT', 500))
      # Video file config
    VIDEO_FILE: str = os.getenv('VIDEO_FILE', 'p.mp4')
    FRAME_SKIP: int = int(os.getenv('FRAME_SKIP', 3))
      # Live camera config
    CAMERA_INDEX: int = int(os.getenv('CAMERA_INDEX', 0))  # Default webcam index (0 is usually the built-in or first connected camera)

    #Output Video Configuration
    SAVE_VIDEO: bool = os.getenv('SAVE_VIDEO', 'True') == 'True'  # Set to True only when you want to save a video
    VIDEO_OUTPUT_PATH: str = os.getenv('VIDEO_OUTPUT_PATH', '.output/demo_output.avi')  # Or .mp4 if supported
    VIDEO_FPS: int = int(os.getenv('VIDEO_FPS', 20))  # Adjust FPS based on input video

    # Database Configuration
    DB_HOST: str = os.getenv('DB_HOST', 'localhost')
    DB_PORT: int = int(os.getenv('DB_PORT', 5432))
    DB_PATH: str = os.getenv('DB_PATH', 'pothole.db')
    DB_NAME: str = os.getenv('DB_NAME', 'pothole_db')
    DB_USER: str = os.getenv('DB_USER', 'sqlite')
    DB_PASSWORD: str = os.getenv('DB_PASSWORD', '555333')

    # Telegram Bot
    BOT_TOKEN: str = os.getenv('BOT_TOKEN', '')

    # Paths
    DATA_DIR: str = os.getenv('DATA_DIR', 'data')
    OFFLINE_LOG_DIR: str = ''
    EXPORT_DIR: str = ''

    # Detection Parameters
    DUPLICATE_RADIUS_METERS: float = float(os.getenv('DUPLICATE_RADIUS_METERS', 5.0))  
    SEVERITY_THRESHOLDS: dict = None

    def __post_init__(self):
        self.OFFLINE_LOG_DIR = os.path.join(self.DATA_DIR, 'offline_logs')
        self.EXPORT_DIR = os.path.join(self.DATA_DIR, 'exports')

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
