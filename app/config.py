import os
import sys
from dataclasses import dataclass
from dotenv import load_dotenv

# Ensure local imports work regardless of working directory
APP_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(APP_DIR)

sys.path.insert(0, APP_DIR)

load_dotenv()


def _env_bool(name: str, default: bool = False) -> bool:
    """Read boolean environment variables safely."""
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ("1", "true", "yes", "y", "on")


def _resolve_path(path: str, base_dir: str = PROJECT_ROOT) -> str:
    """
    Resolve a path safely.

    - Absolute paths are returned unchanged.
    - Relative paths are resolved against PROJECT_ROOT.
    """
    if not path:
        return path

    if os.path.isabs(path):
        return path

    return os.path.abspath(os.path.join(base_dir, path))


def _resolve_existing_or_default(path: str, default_path: str) -> str:
    """
    Resolve paths that may be provided relative to either:
    - project root
    - app directory

    Useful for model/video paths where users often write "best.pt" or "p.mp4".
    """
    if not path:
        return default_path

    if os.path.isabs(path):
        return path

    candidates = [
        os.path.abspath(os.path.join(PROJECT_ROOT, path)),
        os.path.abspath(os.path.join(APP_DIR, path)),
    ]

    for candidate in candidates:
        if os.path.exists(candidate):
            return candidate

    # If the file does not exist yet, prefer project-root-relative path.
    return candidates[0]


@dataclass
class Config:
    # Runtime
    BOT_ONLY: bool = _env_bool("BOT_ONLY", False)
    HEADLESS: bool = _env_bool("HEADLESS", False)

    # GPS
    USE_SIMULATION: bool = _env_bool("USE_SIMULATION", True)
    GPS_PORT: str = os.getenv("GPS_PORT", "COM10")
    GPS_BAUDRATE: int = int(os.getenv("GPS_BAUDRATE", 9600))

    # Model
    YOLO_MODEL_PATH: str = os.getenv("YOLO_MODEL_PATH", "best.pt")

    # Input
    USE_LIVE_CAMERA: bool = _env_bool("USE_LIVE_CAMERA", False)
    VIDEO_WIDTH: int = int(os.getenv("VIDEO_WIDTH", 1020))
    VIDEO_HEIGHT: int = int(os.getenv("VIDEO_HEIGHT", 500))
    VIDEO_FILE: str = os.getenv("VIDEO_FILE", "p.mp4")
    FRAME_SKIP: int = int(os.getenv("FRAME_SKIP", 3))
    CAMERA_INDEX: int = int(os.getenv("CAMERA_INDEX", 0))

    # Output
    SAVE_VIDEO: bool = _env_bool("SAVE_VIDEO", False)
    VIDEO_OUTPUT_PATH: str = os.getenv("VIDEO_OUTPUT_PATH", ".output/demo_output.avi")
    VIDEO_FPS: int = int(os.getenv("VIDEO_FPS", 20))

    # Database
    DB_PATH: str = os.getenv("DB_PATH", "data/pothole.db")

    # Telegram
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
    ADMIN_CHAT_ID: str = os.getenv("ADMIN_CHAT_ID", "")

    # Paths
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    OFFLINE_LOG_DIR: str = ""
    EXPORT_DIR: str = ""

    # Detection
    DUPLICATE_RADIUS_METERS: float = float(os.getenv("DUPLICATE_RADIUS_METERS", 5.0))
    SEVERITY_THRESHOLDS: dict = None

    def __post_init__(self):
        # Resolve runtime directories
        self.DATA_DIR = _resolve_path(self.DATA_DIR)
        self.DB_PATH = _resolve_path(self.DB_PATH)
        self.VIDEO_OUTPUT_PATH = _resolve_path(self.VIDEO_OUTPUT_PATH)

        # Resolve input/model paths
        default_model_path = os.path.join(APP_DIR, "best.pt")
        self.YOLO_MODEL_PATH = _resolve_existing_or_default(
            self.YOLO_MODEL_PATH,
            default_model_path
        )

        default_video_path = os.path.join(PROJECT_ROOT, "p.mp4")
        self.VIDEO_FILE = _resolve_existing_or_default(
            self.VIDEO_FILE,
            default_video_path
        )

        # Derived directories
        self.OFFLINE_LOG_DIR = os.path.join(self.DATA_DIR, "offline_logs")
        self.EXPORT_DIR = os.path.join(self.DATA_DIR, "exports")

        os.makedirs(self.DATA_DIR, exist_ok=True)
        os.makedirs(self.OFFLINE_LOG_DIR, exist_ok=True)
        os.makedirs(self.EXPORT_DIR, exist_ok=True)

        video_output_dir = os.path.dirname(self.VIDEO_OUTPUT_PATH)
        if video_output_dir:
            os.makedirs(video_output_dir, exist_ok=True)

        db_dir = os.path.dirname(self.DB_PATH)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.SEVERITY_THRESHOLDS = {
            "low": {"area": 100, "depth": 0.05},
            "medium": {"area": 500, "depth": 0.10},
            "high": {"area": 1000, "depth": 0.15},
            "critical": {"area": float("inf"), "depth": float("inf")},
        }


config = Config()