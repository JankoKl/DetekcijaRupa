import sqlite3
import logging
from pathlib import Path
from typing import List
from .models import Pothole, GPSPoint
from datetime import datetime

logger = logging.getLogger(__name__)

class PotholeRepository:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """Initialize database schema with proper SQL syntax"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS potholes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    city TEXT NOT NULL,
                    region TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    detected_at TEXT NOT NULL,
                    image_path TEXT,
                    UNIQUE(latitude, longitude)
                )
            ''')  # Closing parenthesis was missing
            conn.commit()
            logger.info("Database initialized")

    def save_pothole(self, pothole: Pothole) -> bool:
        """Save pothole to database with proper error handling"""
        with sqlite3.connect(self.db_path) as conn:
            try:
                conn.execute('''
                             INSERT
                             OR IGNORE INTO potholes 
                    (latitude, longitude, street, city, region, severity_level, severity_score, confidence, detected_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                             ''', (
                                 pothole.location.latitude,
                                 pothole.location.longitude,
                                 pothole.street,
                                 pothole.city,
                                 pothole.region,
                                 pothole.severity_level.value,  # Store enum value
                                 pothole.severity_score,
                                 pothole.confidence,
                                 pothole.detected_at.isoformat()
                             ))
                conn.commit()
                return True
            except sqlite3.Error as e:
                logger.error(f"Database error: {e}")
                return False

    def get_all_potholes(self) -> List[Pothole]:
        """Retrieve all potholes with proper type conversion"""
        potholes = []
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute('''
                SELECT latitude, longitude, city, region, confidence, detected_at, image_path
                FROM potholes
                ORDER BY detected_at DESC
            ''')
            for row in cursor.fetchall():
                try:
                    potholes.append(Pothole(
                        location=GPSPoint(
                            latitude=row[0],
                            longitude=row[1],
                            timestamp=datetime.fromisoformat(row[5])
                        ),
                        city=row[2],
                        region=row[3],
                        confidence=row[4],
                        detected_at=datetime.fromisoformat(row[5]),
                        image_path=row[6]
                    ))
                except (ValueError, IndexError) as e:
                    logger.warning(f"Skipping invalid pothole record: {e}")
        return potholes