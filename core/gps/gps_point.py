from pydantic import BaseModel
import time


class GPSPoint(BaseModel):
    latitude: float
    longitude: float
    timestamp: float = None

    def __init__(self, latitude: float, longitude: float, timestamp: float = None):
        super().__init__(
            latitude=latitude,
            longitude=longitude,
            timestamp=timestamp if timestamp is not None else time.time()
        )

    def dict(self):
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "timestamp": self.timestamp
        }

    def __repr__(self):
        return f"GPSPoint(lat={self.latitude:.6f}, lon={self.longitude:.6f}, ts={self.timestamp})"