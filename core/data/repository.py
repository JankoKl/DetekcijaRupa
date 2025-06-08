# core/data/repository.py
"""
Database repository for pothole data management.
"""
import sqlite3
import json
import logging
import time
import threading
from typing import Dict, Any, List, Optional, Tuple
from pathlib import Path
from datetime import datetime
import base64

from config.config import DatabaseConfig
from config.logging import get_logger
from core.data.models import Pothole, GPSLocation, Detection


class PotholeRepository:
    """Repository for managing pothole data in SQLite database."""

    def __init__(self, config: DatabaseConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self._lock = threading.Lock()
        self._connection = None

        self._initialize_database()

    def _initialize_database(self):
        """Initialize database and create tables if they don't exist."""
        try:
            with self._get_connection() as conn:
                self._create_tables(conn)
                self.logger.info("Database initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize database: {e}")
            raise

    def _get_connection(self) -> sqlite3.Connection:
        """Get database connection with proper configuration."""
        db_path = self.config.url.replace('sqlite:///', '')

        conn = sqlite3.Connection(
            db_path,
            timeout=30.0,
            check_same_thread=False
        )

        # Enable foreign keys and WAL mode for better performance
        conn.execute("PRAGMA foreign_keys = ON")
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
        conn.execute("PRAGMA cache_size = -64000")  # 64MB cache

        # Set row factory for easier data access
        conn.row_factory = sqlite3.Row

        return conn

    def _create_tables(self, conn: sqlite3.Connection):
        """Create database tables."""

        # GPS locations table
        conn.execute("""
                     CREATE TABLE IF NOT EXISTS gps_locations
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
                         accuracy
                         REAL,
                         timestamp
                         DATETIME
                         NOT
                         NULL,
                         address
                         TEXT,
                         created_at
                         DATETIME
                         DEFAULT
                         CURRENT_TIMESTAMP
                     )
                     """)

        # Detections table
        conn.execute("""
                     CREATE TABLE IF NOT EXISTS detections
                     (
                         id
                         INTEGER
                         PRIMARY
                         KEY
                         AUTOINCREMENT,
                         bbox_x1
                         INTEGER
                         NOT
                         NULL,
                         bbox_y1
                         INTEGER
                         NOT
                         NULL,
                         bbox_x2
                         INTEGER
                         NOT
                         NULL,
                         bbox_y2
                         INTEGER
                         NOT
                         NULL,
                         confidence
                         REAL
                         NOT
                         NULL,
                         area
                         REAL
                         NOT
                         NULL,
                         width
                         REAL
                         NOT
                         NULL,
                         height
                         REAL
                         NOT
                         NULL,
                         severity_level
                         TEXT
                         NOT
                         NULL,
                         severity_score
                         REAL
                         NOT
                         NULL,
                         timestamp
                         DATETIME
                         NOT
                         NULL,
                         created_at
                         DATETIME
                         DEFAULT
                         CURRENT_TIMESTAMP
                     )
                     """)

        # Potholes table (main table)
        conn.execute("""
                     CREATE TABLE IF NOT EXISTS potholes
                     (
                         id
                         INTEGER
                         PRIMARY
                         KEY
                         AUTOINCREMENT,
                         detection_id
                         INTEGER
                         NOT
                         NULL,
                         gps_location_id
                         INTEGER
                         NOT
                         NULL,
                         image_data
                         BLOB,
                         image_path
                         TEXT,
                         processed
                         BOOLEAN
                         DEFAULT
                         FALSE,
                         notification_sent
                         BOOLEAN
                         DEFAULT
                         FALSE,
                         notes
                         TEXT,
                         created_at
                         DATETIME
                         DEFAULT
                         CURRENT_TIMESTAMP,
                         updated_at
                         DATETIME
                         DEFAULT
                         CURRENT_TIMESTAMP,
                         FOREIGN
                         KEY
                     (
                         detection_id
                     ) REFERENCES detections
                     (
                         id
                     ),
                         FOREIGN KEY
                     (
                         gps_location_id
                     ) REFERENCES gps_locations
                     (
                         id
                     )
                         )
                     """)

        # Create indexes for better performance
        conn.execute("CREATE INDEX IF NOT EXISTS idx_potholes_created_at ON potholes (created_at)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_potholes_severity ON detections (severity_level)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_gps_timestamp ON gps_locations (timestamp)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_potholes_processed ON potholes (processed)")

        conn.commit()

    def save_pothole(self, detection: Dict[str, Any], gps_position: Dict[str, Any],
                     frame=None) -> int:
        """
        Save a pothole detection to the database.

        Args:
            detection: Detection data from YOLO
            gps_position: GPS position data
            frame: Optional image frame (numpy array)

        Returns:
            Pothole ID
        """
        try:
            with self._lock:
                with self._get_connection() as conn:
                    # Save GPS location
                    gps_id = self._save_gps_location(conn, gps_position)

                    # Save detection
                    detection_id = self._save_detection(conn, detection)

                    # Save image if provided
                    image_data = None
                    image_path = None
                    if frame is not None:
                        image_data, image_path = self._save_image(frame, detection_id)

                    # Save pothole record
                    cursor = conn.execute("""
                                          INSERT INTO potholes
                                              (detection_id, gps_location_id, image_data, image_path)
                                          VALUES (?, ?, ?, ?)
                                          """, (detection_id, gps_id, image_data, image_path))

                    pothole_id = cursor.lastrowid
                    conn.commit()

                    self.logger.info(f"Saved pothole {pothole_id} with detection {detection_id}")
                    return pothole_id

        except Exception as e:
            self.logger.error(f"Error saving pothole: {e}", exc_info=True)
            raise

    def _save_gps_location(self, conn: sqlite3.Connection, gps_data: Dict[str, Any]) -> int:
        """Save GPS location and return ID."""
        cursor = conn.execute("""
                              INSERT INTO gps_locations
                                  (latitude, longitude, altitude, accuracy, timestamp, address)
                              VALUES (?, ?, ?, ?, ?, ?)
                              """, (
                                  gps_data.get('latitude', 0.0),
                                  gps_data.get('longitude', 0.0),
                                  gps_data.get('altitude'),
                                  gps_data.get('accuracy'),
                                  gps_data.get('timestamp', datetime.now()),
                                  gps_data.get('address')
                              ))
        return cursor.lastrowid

    def _save_detection(self, conn: sqlite3.Connection, detection: Dict[str, Any]) -> int:
        """Save detection data and return ID."""
        bbox = detection['bbox']
        severity = detection.get('severity', {})

        cursor = conn.execute("""
                              INSERT INTO detections
                              (bbox_x1, bbox_y1, bbox_x2, bbox_y2, confidence, area, width, height,
                               severity_level, severity_score, timestamp)
                              VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                              """, (
                                  bbox[0], bbox[1], bbox[2], bbox[3],
                                  detection['confidence'],
                                  detection['area'],
                                  detection['width'],
                                  detection['height'],
                                  severity.get('level', 'medium'),
                                  severity.get('risk_score', 0.5),
                                  detection.get('timestamp', datetime.now())
                              ))
        return cursor.lastrowid

    def _save_image(self, frame, detection_id: int) -> Tuple[Optional[bytes], Optional[str]]:
        """Save image frame and return data and path."""
        try:
            import cv2

            # Create images directory
            images_dir = Path("data/images")
            images_dir.mkdir(parents=True, exist_ok=True)

            # Save image file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_path = images_dir / f"pothole_{detection_id}_{timestamp}.jpg"

            cv2.imwrite(str(image_path), frame)

            # Optionally store small thumbnail in database
            thumbnail = cv2.resize(frame, (200, 150))
            _, buffer = cv2.imencode('.jpg', thumbnail, [cv2.IMWRITE_JPEG_QUALITY, 70])
            image_data = base64.b64encode(buffer).decode('utf-8')

            return image_data, str(image_path)

        except Exception as e:
            self.logger.error(f"Error saving image: {e}")
            return None, None

    def get_potholes(self, limit: int = 100, offset: int = 0,
                     severity_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get potholes with optional filtering."""
        try:
            with self._get_connection() as conn:
                query = """
                        SELECT p.id, \
                               p.created_at, \
                               p.processed, \
                               p.notification_sent, \
                               d.confidence, \
                               d.area, \
                               d.severity_level, \
                               d.severity_score, \
                               d.bbox_x1, \
                               d.bbox_y1, \
                               d.bbox_x2, \
                               d.bbox_y2, \
                               g.latitude, \
                               g.longitude, \
                               g.address, \
                               g.timestamp as gps_timestamp
                        FROM potholes p
                                 JOIN detections d ON p.detection_id = d.id
                                 JOIN gps_locations g ON p.gps_location_id = g.id \
                        """

                params = []
                if severity_filter:
                    query += " WHERE d.severity_level = ?"
                    params.append(severity_filter)

                query += " ORDER BY p.created_at DESC LIMIT ? OFFSET ?"
                params.extend([limit, offset])

                cursor = conn.execute(query, params)
                return [dict(row) for row in cursor.fetchall()]

        except Exception as e:
            self.logger.error(f"Error getting potholes: {e}")
            return []

    def get_pothole_by_id(self, pothole_id: int) -> Optional[Dict[str, Any]]:
        """Get a specific pothole by ID."""
        try:
            with self._get_connection() as conn:
                cursor = conn.execute("""
                                      SELECT p.*,
                                             d.*,
                                             g.*,
                                             p.id as pothole_id,
                                             d.id as detection_id,
                                             g.id as gps_id
                                      FROM potholes p
                                               JOIN detections d ON p.detection_id = d.id
                                               JOIN gps_locations g ON p.gps_location_id = g.id
                                      WHERE p.id = ?
                                      """, (pothole_id,))

                row = cursor.fetchone()
                return dict(row) if row else None

        except Exception as e:
            self.logger.error(f"Error getting pothole {pothole_id}: {e}")
            return None

    def mark_processed(self, pothole_id: int, processed: bool = True):
        """Mark a pothole as processed."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                             UPDATE potholes
                             SET processed  = ?,
                                 updated_at = CURRENT_TIMESTAMP
                             WHERE id = ?
                             """, (processed, pothole_id))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error marking pothole {pothole_id} as processed: {e}")

    def mark_notification_sent(self, pothole_id: int, sent: bool = True):
        """Mark notification as sent for a pothole."""
        try:
            with self._get_connection() as conn:
                conn.execute("""
                             UPDATE potholes
                             SET notification_sent = ?,
                                 updated_at        = CURRENT_TIMESTAMP
                             WHERE id = ?
                             """, (sent, pothole_id))
                conn.commit()

        except Exception as e:
            self.logger.error(f"Error marking notification sent for pothole {pothole_id}: {e}")

    def get_statistics(self) -> Dict[str, Any]:
        """Get database statistics."""
        try:
            with self._get_connection() as conn:
                stats = {}

                # Total potholes
                cursor = conn.execute("SELECT COUNT(*) FROM potholes")
                stats['total_potholes'] = cursor.fetchone()[0]

                # Potholes by severity
                cursor = conn.execute("""
                                      SELECT d.severity_level, COUNT(*)
                                      FROM potholes p
                                               JOIN detections d ON p.detection_id = d.id
                                      GROUP BY d.severity_level
                                      """)
                stats['by_severity'] = dict(cursor.fetchall())

                # Processed vs unprocessed
                cursor = conn.execute("""
                                      SELECT processed, COUNT(*)
                                      FROM potholes
                                      GROUP BY processed
                                      """)
                stats['by_processed'] = dict(cursor.fetchall())

                # Recent activity (last 24 hours)
                cursor = conn.execute("""
                                      SELECT COUNT(*)
                                      FROM potholes
                                      WHERE created_at > datetime('now', '-1 day')
                                      """)
                stats['recent_24h'] = cursor.fetchone()[0]

                return stats

        except Exception as e:
            self.logger.error(f"Error getting statistics: {e}")
            return {}

    def cleanup_old_data(self, days_old: int = 30):
        """Clean up old data to prevent database bloat."""
        try:
            with self._get_connection() as conn:
                # Delete old processed potholes
                cursor = conn.execute("""
                    DELETE FROM potholes 
                    WHERE processed = 1 
                    AND created_at < datetime('now', '-{} days')
                """.format(days_old))

                deleted_count = cursor.rowcount
                conn.commit()

                self.logger.info(f"Cleaned up {deleted_count} old pothole records")

        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {e}")

    def backup_database(self, backup_path: Optional[str] = None):
        """Create a backup of the database."""
        try:
            if not backup_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                backup_path = f"data/backups/potholes_backup_{timestamp}.db"

            backup_dir = Path(backup_path).parent
            backup_dir.mkdir(parents=True, exist_ok=True)

            with self._get_connection() as source:
                backup = sqlite3.connect(backup_path)
                source.backup(backup)
                backup.close()

            self.logger.info(f"Database backed up to {backup_path}")

        except Exception as e:
            self.logger.error(f"Error backing up database: {e}")

    def close(self):
        """Close database connection."""
        if self._connection:
            self._connection.close()
            self._connection = None
