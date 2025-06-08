# core/data/repository.py
import sqlite3
import logging
import threading
from pathlib import Path
from typing import List, Optional, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager
from queue import Queue

from .models import Pothole, GPSPoint, SeverityLevel, PotholeStats

logger = logging.getLogger(__name__)


class DatabasePool:
    """Simple database connection pool for SQLite"""

    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self.pool_size = pool_size
        self._pool = Queue(maxsize=pool_size)
        self._lock = threading.Lock()
        self._initialize_pool()

    def _initialize_pool(self):
        """Initialize the connection pool"""
        for _ in range(self.pool_size):
            conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0
            )
            conn.row_factory = sqlite3.Row
            self._pool.put(conn)

    @contextmanager
    def get_connection(self):
        """Get a connection from the pool"""
        conn = self._pool.get()
        try:
            yield conn
        finally:
            self._pool.put(conn)

    def close_all(self):
        """Close all connections in the pool"""
        while not self._pool.empty():
            conn = self._pool.get()
            conn.close()


class PotholeRepository:
    """Enhanced repository with connection pooling and better error handling"""

    def __init__(self, db_path: str, pool_size: int = 5):
        self.db_path = db_path
        self._ensure_directory()
        self.pool = DatabasePool(db_path, pool_size)
        self._init_db()
        logger.info(f"Repository initialized with database: {db_path}")

    def _ensure_directory(self):
        """Ensure database directory exists"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _init_db(self):
        """Initialize database schema"""
        with self.pool.get_connection() as conn:
            try:
                # Create potholes table
                conn.execute('''
                             CREATE TABLE IF NOT EXISTS potholes
                             (
                                 id
                                 INTEGER
                                 PRIMARY
                                 KEY
                                 AUTOINCREMENT,
                                 latitude
                                 REAL
                                 NOT
                                 NULL,
                                 longitude
                                 REAL
                                 NOT
                                 NULL,
                                 altitude
                                 REAL,
                                 gps_accuracy
                                 REAL,
                                 street
                                 TEXT
                                 NOT
                                 NULL
                                 DEFAULT
                                 'Unknown Street',
                                 city
                                 TEXT
                                 NOT
                                 NULL
                                 DEFAULT
                                 'Unknown City',
                                 region
                                 TEXT
                                 NOT
                                 NULL
                                 DEFAULT
                                 'Unknown Region',
                                 country
                                 TEXT
                                 NOT
                                 NULL
                                 DEFAULT
                                 'Unknown Country',
                                 severity_level
                                 TEXT
                                 NOT
                                 NULL,
                                 severity_score
                                 REAL
                                 NOT
                                 NULL,
                                 confidence
                                 REAL
                                 NOT
                                 NULL,
                                 detected_at
                                 TEXT
                                 NOT
                                 NULL,
                                 image_path
                                 TEXT,
                                 processed
                                 BOOLEAN
                                 DEFAULT
                                 FALSE,
                                 verified
                                 BOOLEAN
                                 DEFAULT
                                 FALSE,
                                 created_at
                                 TEXT
                                 DEFAULT
                                 CURRENT_TIMESTAMP,
                                 UNIQUE
                             (
                                 latitude,
                                 longitude,
                                 detected_at
                             )
                                 )
                             ''')

                # Create indexes for better query performance
                conn.execute('''
                             CREATE INDEX IF NOT EXISTS idx_potholes_location
                                 ON potholes(latitude, longitude)
                             ''')

                conn.execute('''
                             CREATE INDEX IF NOT EXISTS idx_potholes_detected_at
                                 ON potholes(detected_at)
                             ''')

                conn.execute('''
                             CREATE INDEX IF NOT EXISTS idx_potholes_severity
                                 ON potholes(severity_level)
                             ''')

                conn.commit()
                logger.info("Database schema initialized successfully")

            except sqlite3.Error as e:
                logger.error(f"Database initialization error: {e}")
                raise

    def save_pothole(self, pothole: Pothole) -> bool:
        """Save pothole with better error handling and validation"""
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.execute('''
                                      INSERT
                                      OR IGNORE INTO potholes 
                    (latitude, longitude, altitude, gps_accuracy, street, city, region, country,
                     severity_level, severity_score, confidence, detected_at, image_path, processed, verified)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                                      ''', (
                                          pothole.location.latitude,
                                          pothole.location.longitude,
                                          pothole.location.altitude,
                                          pothole.location.accuracy,
                                          pothole.street,
                                          pothole.city,
                                          pothole.region,
                                          pothole.country,
                                          pothole.severity_level.value,
                                          pothole.severity_score,
                                          pothole.confidence,
                                          pothole.detected_at.isoformat(),
                                          pothole.image_path,
                                          pothole.processed,
                                          pothole.verified
                                      ))

                if cursor.rowcount > 0:
                    conn.commit()
                    logger.info(f"Saved pothole at ({pothole.location.latitude:.6f}, {pothole.location.longitude:.6f})")
                    return True
                else:
                    logger.debug("Pothole already exists, skipping duplicate")
                    return False

        except sqlite3.Error as e:
            logger.error(f"Database save error: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error saving pothole: {e}")
            return False

    def get_all_potholes(self, limit: Optional[int] = None) -> List[Pothole]:
        """Retrieve potholes with optional limit"""
        potholes = []
        try:
            with self.pool.get_connection() as conn:
                query = '''
                        SELECT * \
                        FROM potholes
                        ORDER BY detected_at DESC \
                        '''
                if limit:
                    query += f' LIMIT {limit}'

                cursor = conn.execute(query)
                for row in cursor.fetchall():
                    try:
                        pothole = self._row_to_pothole(row)
                        potholes.append(pothole)
                    except Exception as e:
                        logger.warning(f"Skipping invalid pothole record: {e}")

        except sqlite3.Error as e:
            logger.error(f"Database query error: {e}")

        return potholes

    def get_potholes_by_area(self, lat: float, lon: float, radius_km: float) -> List[Pothole]:
        """Get potholes within a specific radius (approximate)"""
        # Simple bounding box approximation (not exact but fast)
        lat_delta = radius_km / 111.0  # Rough km to degrees conversion
        lon_delta = radius_km / (111.0 * abs(lat))

        potholes = []
        try:
            with self.pool.get_connection() as conn:
                cursor = conn.execute('''
                                      SELECT *
                                      FROM potholes
                                      WHERE latitude BETWEEN ? AND ?
                                        AND longitude BETWEEN ? AND ?
                                      ORDER BY detected_at DESC
                                      ''', (
                                          lat - lat_delta, lat + lat_delta,
                                          lon - lon_delta, lon + lon_delta
                                      ))

                for row in cursor.fetchall():
                    try:
                        pothole = self._row_to_pothole(row)
                        potholes.append(pothole)
                    except Exception as e:
                        logger.warning(f"Skipping invalid pothole record: {e}")

        except sqlite3.Error as e:
            logger.error(f"Database area query error: {e}")

        return potholes

    def get_statistics(self, days: int = 30) -> PotholeStats:
        """Get pothole detection statistics"""
        stats = PotholeStats()

        try:
            with self.pool.get_connection() as conn:
                # Get date threshold
                threshold = (datetime.now() - timedelta(days=days)).isoformat()

                # Total count
                cursor = conn.execute('''
                                      SELECT COUNT(*)
                                      FROM potholes
                                      WHERE detected_at >= ?
                                      ''', (threshold,))
                stats.total_detected = cursor.fetchone()[0]

                # Severity breakdown
                cursor = conn.execute('''
                                      SELECT severity_level, COUNT(*)
                                      FROM potholes
                                      WHERE detected_at >= ?
                                      GROUP BY severity_level
                                      ''', (threshold,))

                for row in cursor.fetchall():
                    severity, count = row
                    if severity == 'Low':
                        stats.low_severity = count
                    elif severity == 'Medium':
                        stats.medium_severity = count
                    elif severity == 'High':
                        stats.high_severity = count

                # Average confidence
                cursor = conn.execute('''
                                      SELECT AVG(confidence)
                                      FROM potholes
                                      WHERE detected_at >= ?
                                      ''', (threshold,))
                result = cursor.fetchone()[0]
                stats.average_confidence = float(result) if result else 0.0

                # Detection rate per hour
                if stats.total_detected > 0:
                    stats.detection_rate_per_hour = stats.total_detected / (days * 24)

                # Last detection
                cursor = conn.execute('''
                                      SELECT MAX(detected_at)
                                      FROM potholes
                                      ''')
                last_detection = cursor.fetchone()[0]
                if last_detection:
                    stats.last_detection = datetime.fromisoformat(last_detection)

        except sqlite3.Error as e:
            logger.error(f"Statistics query error: {e}")

        return stats

    def _row_to_pothole(self, row) -> Pothole:
        """Convert database row to Pothole object"""
        return Pothole(
            id=row['id'],
            location=GPSPoint(
                latitude=row['latitude'],
                longitude=row['longitude'],
                altitude=row['altitude'],
                accuracy=row['gps_accuracy'],
                timestamp=datetime.fromisoformat(row['detected_at'])
            ),
            street=row['street'],
            city=row['city'],
            region=row['region'],
            country=row['country'],
            severity_level=SeverityLevel(row['severity_level']),
            severity_score=row['severity_score'],
            confidence=row['confidence'],
            detected_at=datetime.fromisoformat(row['detected_at']),
            image_path=row['image_path'],
            processed=bool(row['processed']),
            verified=bool(row['verified'])
        )

    def close(self):
        """Close all database connections"""
        self.pool.close_all()
        logger.info("Database connections closed")