import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv('token.env')


class Settings:
    def __init__(self):
        # Model configuration
        self.model_path = os.getenv('MODEL_PATH', 'models/best.pt')

        # Video source
        self.video_source = os.getenv('VIDEO_SOURCE', 'p.mp4')

        # Database
        self.data_file = os.getenv('DATA_FILE', 'data/potholes.db')

        # GPS configuration
        self.simulate_gps = os.getenv('SIMULATE_GPS', 'True').lower() == 'true'
        self.serial_port = os.getenv('SERIAL_PORT', '/dev/ttyUSB0')

        # Telegram bot
        self.telegram_token = os.getenv('TELEGRAM_TOKEN')

        # Processing settings
        self.process_every_n_frames = int(os.getenv('PROCESS_EVERY_N_FRAMES', '3'))
        self.detection_confidence_threshold = float(os.getenv('DETECTION_CONFIDENCE_THRESHOLD', '0.5'))

        # Validate critical paths
        self._validate_paths()

    def _validate_paths(self):
        """Validate that critical files and directories exist"""
        if not Path(self.model_path).exists():
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        # Create data directory if it doesn't exist
        Path(self.data_file).parent.mkdir(parents=True, exist_ok=True)


settings = Settings()