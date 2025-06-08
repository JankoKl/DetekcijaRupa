from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import Optional, Dict, Any
from enum import Enum


class SeverityLevel(str, Enum):
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


class GPSPoint(BaseModel):
    latitude: float = Field(..., ge=-90, le=90, description="Latitude in decimal degrees")
    longitude: float = Field(..., ge=-180, le=180, description="Longitude in decimal degrees")
    altitude: Optional[float] = Field(None, description="Altitude in meters")
    speed: Optional[float] = Field(None, ge=0, description="Speed in km/h")
    timestamp: datetime = Field(default_factory=datetime.now)
    accuracy: Optional[float] = Field(None, ge=0, description="GPS accuracy in meters")

    @validator('latitude')
    def validate_latitude(cls, v):
        if not -90 <= v <= 90:
            raise ValueError('Latitude must be between -90 and 90 degrees')
        return v

    @validator('longitude')
    def validate_longitude(cls, v):
        if not -180 <= v <= 180:
            raise ValueError('Longitude must be between -180 and 180 degrees')
        return v

    def dict(self) -> Dict[str, Any]:
        """Convert to dictionary - overriding to handle datetime serialization"""
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "altitude": self.altitude,
            "speed": self.speed,
            "timestamp": self.timestamp.isoformat() if isinstance(self.timestamp, datetime) else self.timestamp,
            "accuracy": self.accuracy
        }

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class Detection(BaseModel):
    bbox: list[float] = Field(..., description="Bounding box coordinates [x1, y1, x2, y2]")
    contour: Optional[list] = Field(None, description="Contour points")
    severity: SeverityLevel
    severity_score: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    area_pixels: Optional[int] = Field(None, ge=0)
    diameter_cm: Optional[float] = Field(None, ge=0)


class Pothole(BaseModel):
    id: Optional[int] = None
    location: GPSPoint
    street: str = Field(default="Unknown Street")
    city: str = Field(default="Unknown City")
    region: str = Field(default="Unknown Region")
    country: str = Field(default="Unknown Country")
    severity_level: SeverityLevel
    severity_score: float = Field(..., ge=0, le=100)
    confidence: float = Field(..., ge=0, le=1)
    detected_at: datetime = Field(default_factory=datetime.now)
    image_path: Optional[str] = None
    processed: bool = Field(default=False)
    verified: bool = Field(default=False)

    @validator('severity_score')
    def validate_severity_score(cls, v):
        if not 0 <= v <= 100:
            raise ValueError('Severity score must be between 0 and 100')
        return v

    @validator('confidence')
    def validate_confidence(cls, v):
        if not 0 <= v <= 1:
            raise ValueError('Confidence must be between 0 and 1')
        return v

    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            SeverityLevel: lambda v: v.value
        }


class PotholeStats(BaseModel):
    total_detected: int = 0
    low_severity: int = 0
    medium_severity: int = 0
    high_severity: int = 0
    average_confidence: float = 0.0
    detection_rate_per_hour: float = 0.0
    last_detection: Optional[datetime] = None