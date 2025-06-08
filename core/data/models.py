"""
Data models for the pothole detection system.
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class SeverityLevel(Enum):
    """Pothole severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class GPSPoint:
    """GPS point data model."""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    address: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'accuracy': self.accuracy,
            'timestamp': self.timestamp.isoformat(),
            'address': self.address
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GPSPoint':
        """Create from dictionary."""
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        return cls(
            latitude=data['latitude'],
            longitude=data['longitude'],
            altitude=data.get('altitude'),
            accuracy=data.get('accuracy'),
            timestamp=timestamp,
            address=data.get('address')
        )


@dataclass
class GPSLocation:
    """GPS location data model (alias for GPSPoint for backward compatibility)."""
    latitude: float
    longitude: float
    altitude: Optional[float] = None
    accuracy: Optional[float] = None
    timestamp: datetime = field(default_factory=datetime.now)
    address: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'latitude': self.latitude,
            'longitude': self.longitude,
            'altitude': self.altitude,
            'accuracy': self.accuracy,
            'timestamp': self.timestamp.isoformat(),
            'address': self.address
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'GPSLocation':
        """Create from dictionary."""
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        return cls(
            latitude=data['latitude'],
            longitude=data['longitude'],
            altitude=data.get('altitude'),
            accuracy=data.get('accuracy'),
            timestamp=timestamp,
            address=data.get('address')
        )


@dataclass
class Detection:
    """Pothole detection data model."""
    bbox: List[int]  # [x1, y1, x2, y2]
    confidence: float
    area: float
    width: float
    height: float
    severity_level: str
    severity_score: float
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'bbox': self.bbox,
            'confidence': self.confidence,
            'area': self.area,
            'width': self.width,
            'height': self.height,
            'severity_level': self.severity_level,
            'severity_score': self.severity_score,
            'timestamp': self.timestamp.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Detection':
        """Create from dictionary."""
        timestamp = data.get('timestamp')
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        elif timestamp is None:
            timestamp = datetime.now()

        return cls(
            bbox=data['bbox'],
            confidence=data['confidence'],
            area=data['area'],
            width=data['width'],
            height=data['height'],
            severity_level=data['severity_level'],
            severity_score=data['severity_score'],
            timestamp=timestamp
        )


@dataclass
class Pothole:
    """Main pothole data model."""
    id: Optional[int] = None
    detection: Optional[Detection] = None
    gps_location: Optional[GPSLocation] = None
    image_path: Optional[str] = None
    image_data: Optional[str] = None  # Base64 encoded thumbnail
    processed: bool = False
    notification_sent: bool = False
    notes: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'detection': self.detection.to_dict() if self.detection else None,
            'gps_location': self.gps_location.to_dict() if self.gps_location else None,
            'image_path': self.image_path,
            'image_data': self.image_data,
            'processed': self.processed,
            'notification_sent': self.notification_sent,
            'notes': self.notes,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Pothole':
        """Create from dictionary."""
        created_at = data.get('created_at')
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        elif created_at is None:
            created_at = datetime.now()

        updated_at = data.get('updated_at')
        if isinstance(updated_at, str):
            updated_at = datetime.fromisoformat(updated_at)
        elif updated_at is None:
            updated_at = datetime.now()

        detection = None
        if data.get('detection'):
            detection = Detection.from_dict(data['detection'])

        gps_location = None
        if data.get('gps_location'):
            gps_location = GPSLocation.from_dict(data['gps_location'])

        return cls(
            id=data.get('id'),
            detection=detection,
            gps_location=gps_location,
            image_path=data.get('image_path'),
            image_data=data.get('image_data'),
            processed=data.get('processed', False),
            notification_sent=data.get('notification_sent', False),
            notes=data.get('notes'),
            created_at=created_at,
            updated_at=updated_at
        )
