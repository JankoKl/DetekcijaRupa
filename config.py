import os
from dataclasses import dataclass



@dataclass
class Config:
    # GPS Configuration
    USE_SIMULATION = True  # Set to False to use real GPS
    GPS_PORT: str = 'COM10'
    GPS_BAUDRATE: int = 9600

    # Model Paths
    YOLO_MODEL_PATH: str = 'best.pt'
   # MIDAS_MODEL_PATH: str = 'dpt_swin2_large_384.pt'  # downloaded model
   # MIDAS_MODEL_TYPE: str = 'dpt_swin2_large_384'  # or 'DPT_Hybrid' or 'MiDaS'

    #Input Video Configuration
    USE_LIVE_CAMERA = False  # Set to True to use live camera, false for video file
    VIDEO_WIDTH: int = 1020
    VIDEO_HEIGHT: int = 500
      # Video file config
    VIDEO_FILE: str = 'p.mp4'
    FRAME_SKIP: int = 3
      # Live camera config
    CAMERA_INDEX = 0  # Default webcam index (0 is usually the built-in or first connected camera)

    #Output Video Configuration
    SAVE_VIDEO = True  # Set to True only when you want to save a video
    VIDEO_OUTPUT_PATH = "output/demo_output.avi"  # Or .mp4 if supported
    VIDEO_FPS = 20  # Adjust FPS based on input video

    # Database Configuration
    DB_HOST: str = 'localhost'
    DB_PORT: int = 5432
    DB_PATH: str = 'pothole.db'
    DB_NAME: str = 'pothole_db'
    DB_USER: str = 'sqlite'
    DB_PASSWORD: str = '555333'

    # Telegram Bot
    BOT_TOKEN: str = 'Your_Bot_Token'

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
