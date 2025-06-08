from typing import Union

from pydantic_settings import BaseSettings



class Settings(BaseSettings):
    # Detection
    model_path: str = "models/best.pt"  # Make sure this path exists
    video_source: str = "p.mp4"  # or 0 for webcam

    # GPS
    serial_port: str = "COM10"
    baud_rate: int = 9600
    simulate_gps: bool = True

    # Telegram
    telegram_token: str = ""

    # Data
    data_file: str = "data/potholes.db"

    #Video source
    video_source: Union[int, str] = 0  # Can be:

    # 0 - default webcam
    # "rtsp://url" for IP cameras
    # "/path/to/video.mp4"
    # "/path/to/images/"

    class Config:
        env_file = "token.env"
        env_file_encoding = "utf-8"


settings = Settings()