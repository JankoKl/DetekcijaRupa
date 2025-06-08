from pydantic import BaseModel
from datetime import datetime
from typing import Optional

from core.detection.severity import SeverityLevel


class GPSPoint(BaseModel):
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    speed: Optional[float] = None
    timestamp: datetime = datetime.now()

class Pothole(BaseModel):
    location: GPSPoint
    street: str
    city: str
    region: str
    severity_level: str  # Or use Enum if you have severity levels defined
    severity_score: float
    confidence: float
    detected_at: datetime

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            GPSPoint: lambda v: v.dict()
        }