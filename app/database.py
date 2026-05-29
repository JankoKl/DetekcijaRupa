import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import sqlite3
from contextlib import contextmanager
import json
import math
from datetime import datetime
from typing import List, Optional, Dict
import logging

from config import config
from models import Pothole, Severity
from utils import calculate_distance

logger = logging.getLogger(__name__)


class PotholeDatabase:
    def __init__(self):
        self.db_path = config.DB_PATH

        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.init_database()

    @contextmanager
    def get_connection(self):
        """
        Create a new SQLite connection per operation.

        timeout=30 reduces immediate "database is locked" errors when bot,
        sync thread and video thread access SQLite concurrently.
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.row_factory = sqlite3.Row

        try:
            conn.execute("PRAGMA foreign_keys = ON")
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def init_database(self):
        with self.get_connection() as conn:
            cur = conn.cursor()

            # Better behavior for concurrent reads/writes.
            cur.execute("PRAGMA journal_mode = WAL")
            cur.execute("PRAGMA synchronous = NORMAL")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS potholes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    latitude REAL NOT NULL,
                    longitude REAL NOT NULL,
                    city TEXT,
                    region TEXT,
                    severity TEXT,
                    area REAL,
                    depth REAL,
                    confidence REAL,
                    timestamp TEXT NOT NULL,
                    image_path TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            """)

            cur.execute("CREATE INDEX IF NOT EXISTS idx_location ON potholes(latitude, longitude)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_region ON potholes(region)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_severity ON potholes(severity)")
            cur.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON potholes(timestamp)")

            cur.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    chat_id INTEGER PRIMARY KEY,
                    username TEXT,
                    first_name TEXT,
                    role TEXT DEFAULT 'viewer',
                    joined_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    last_seen TEXT
                )
            """)

    # ------------------------------------------------------------------ #
    # Users                                                               #
    # ------------------------------------------------------------------ #

    def register_user(self, chat_id: int, username: str, first_name: str) -> str:
        """
        Register user if it does not exist.

        Admin is the user whose chat_id matches ADMIN_CHAT_ID from environment.
        Returns role: 'admin' or 'viewer'.
        """
        role = "admin" if str(chat_id) == str(config.ADMIN_CHAT_ID) else "viewer"
        now = datetime.now().isoformat()

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO users (chat_id, username, first_name, role, joined_at, last_seen)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    username = excluded.username,
                    first_name = excluded.first_name,
                    role = excluded.role,
                    last_seen = excluded.last_seen
            """, (chat_id, username, first_name, role, now, now))

        return role

    def get_user_role(self, chat_id: int) -> Optional[str]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT role FROM users WHERE chat_id = ?", (chat_id,))
            row = cur.fetchone()
            return row["role"] if row else None

    def get_all_admin_chat_ids(self) -> List[int]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT chat_id FROM users WHERE role = 'admin'")
            return [row["chat_id"] for row in cur.fetchall()]

    def get_all_chat_ids(self) -> List[int]:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT chat_id FROM users")
            return [row["chat_id"] for row in cur.fetchall()]

    def get_user_count(self) -> Dict:
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("SELECT role, COUNT(*) AS count FROM users GROUP BY role")
            return {row["role"]: row["count"] for row in cur.fetchall()}

    # ------------------------------------------------------------------ #
    # Potholes                                                            #
    # ------------------------------------------------------------------ #

    def is_duplicate(self, latitude: float, longitude: float) -> bool:
        """
        Check whether a pothole already exists within configured radius.

        Uses a fast bounding box filter first, then precise Haversine distance.
        """
        radius_m = config.DUPLICATE_RADIUS_METERS

        lat_margin = radius_m / 111_000.0
        lon_margin = radius_m / (
            111_000.0 * max(math.cos(math.radians(latitude)), 0.0001)
        )

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                SELECT latitude, longitude
                FROM potholes
                WHERE latitude BETWEEN ? AND ?
                  AND longitude BETWEEN ? AND ?
            """, (
                latitude - lat_margin,
                latitude + lat_margin,
                longitude - lon_margin,
                longitude + lon_margin,
            ))

            for row in cur.fetchall():
                distance = calculate_distance(
                    latitude,
                    longitude,
                    row["latitude"],
                    row["longitude"]
                )

                if distance <= radius_m:
                    return True

        return False

    def add_pothole(self, pothole: Pothole) -> Optional[int]:
        """
        Insert a pothole into the database.

        Returns:
            - new pothole ID if inserted
            - None if duplicate
        """
        if self.is_duplicate(pothole.latitude, pothole.longitude):
            logger.info(
                "Duplicate pothole ignored at (%s, %s)",
                pothole.latitude,
                pothole.longitude
            )
            return None

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO potholes
                (
                    latitude,
                    longitude,
                    city,
                    region,
                    severity,
                    area,
                    depth,
                    confidence,
                    timestamp,
                    image_path
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                pothole.latitude,
                pothole.longitude,
                pothole.city,
                pothole.region,
                pothole.severity.value,
                pothole.area,
                pothole.depth,
                pothole.confidence,
                pothole.timestamp.isoformat(),
                pothole.image_path
            ))

            return cur.lastrowid

    def update_pothole_image_path(self, pothole_id: int, image_path: str) -> None:
        """
        Persist detection image path after the image has been saved.

        This fixes the previous issue where image_path existed only in memory,
        but not in SQLite.
        """
        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(
                "UPDATE potholes SET image_path = ? WHERE id = ?",
                (image_path, pothole_id)
            )

    def get_potholes(
        self,
        filters: Dict = None,
        sort_by: str = "timestamp",
        sort_order: str = "DESC",
        limit: int = None
    ) -> List[Pothole]:
        query = "SELECT * FROM potholes WHERE 1=1"
        params = []

        if filters:
            if "region" in filters:
                query += " AND region = ?"
                params.append(filters["region"])

            if "severity" in filters:
                query += " AND severity = ?"
                params.append(filters["severity"])

            if "start_date" in filters:
                query += " AND timestamp >= ?"
                params.append(filters["start_date"])

            if "end_date" in filters:
                query += " AND timestamp <= ?"
                params.append(filters["end_date"])

        valid_sort_columns = ["timestamp", "severity", "depth", "area", "confidence"]
        if sort_by not in valid_sort_columns:
            sort_by = "timestamp"

        valid_sort_orders = ["ASC", "DESC"]
        sort_order = sort_order.upper()
        if sort_order not in valid_sort_orders:
            sort_order = "DESC"

        # Severity is textual in SQLite, so plain ORDER BY severity is not logical.
        if sort_by == "severity":
            severity_order = """
                CASE severity
                    WHEN 'low' THEN 1
                    WHEN 'medium' THEN 2
                    WHEN 'high' THEN 3
                    WHEN 'critical' THEN 4
                    ELSE 0
                END
            """
            query += f" ORDER BY {severity_order} {sort_order}, timestamp DESC"
        else:
            query += f" ORDER BY {sort_by} {sort_order}"

        if limit is not None:
            query += " LIMIT ?"
            params.append(int(limit))

        with self.get_connection() as conn:
            cur = conn.cursor()
            cur.execute(query, params)
            rows = cur.fetchall()

            potholes = []
            for row in rows:
                try:
                    severity = Severity(row["severity"])
                except ValueError:
                    severity = Severity.LOW

                potholes.append(
                    Pothole(
                        id=row["id"],
                        latitude=row["latitude"],
                        longitude=row["longitude"],
                        city=row["city"] or "Unknown",
                        region=row["region"] or "Unknown",
                        severity=severity,
                        area=row["area"] or 0.0,
                        depth=row["depth"] or 0.0,
                        confidence=row["confidence"] or 0.0,
                        timestamp=datetime.fromisoformat(row["timestamp"]),
                        image_path=row["image_path"]
                    )
                )

            return potholes

    def get_latest_potholes(self, limit: int = 5) -> List[Pothole]:
        return self.get_potholes(
            sort_by="timestamp",
            sort_order="DESC",
            limit=limit
        )

    def get_statistics(self) -> Dict:
        with self.get_connection() as conn:
            cur = conn.cursor()

            cur.execute("SELECT COUNT(*) AS total FROM potholes")
            total = cur.fetchone()["total"]

            cur.execute("""
                SELECT severity, COUNT(*) AS count
                FROM potholes
                GROUP BY severity
            """)
            severity_stats = {
                row["severity"]: row["count"]
                for row in cur.fetchall()
                if row["severity"]
            }

            cur.execute("""
                SELECT region, COUNT(*) AS count
                FROM potholes
                WHERE region IS NOT NULL AND region != ''
                GROUP BY region
                ORDER BY count DESC
                LIMIT 10
            """)
            region_stats = [
                (row["region"], row["count"])
                for row in cur.fetchall()
            ]

            today = datetime.now().strftime("%Y-%m-%d")
            cur.execute(
                "SELECT COUNT(*) AS count FROM potholes WHERE timestamp LIKE ?",
                (f"{today}%",)
            )
            today_count = cur.fetchone()["count"]

            return {
                "total": total,
                "by_severity": severity_stats,
                "top_regions": region_stats,
                "today": today_count
            }

    # ------------------------------------------------------------------ #
    # Offline logs                                                        #
    # ------------------------------------------------------------------ #

    def save_offline_log(self, potholes: List[Pothole]):
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = os.path.join(
            config.OFFLINE_LOG_DIR,
            f"potholes_{timestamp}.json"
        )

        data = []
        for p in potholes:
            data.append({
                "latitude": float(p.latitude),
                "longitude": float(p.longitude),
                "city": str(p.city),
                "region": str(p.region),
                "severity": p.severity.value,
                "area": float(p.area),
                "depth": float(p.depth),
                "confidence": float(p.confidence),
                "timestamp": (
                    p.timestamp.isoformat()
                    if isinstance(p.timestamp, datetime)
                    else str(p.timestamp)
                ),
                "image_path": p.image_path
            })

        try:
            os.makedirs(config.OFFLINE_LOG_DIR, exist_ok=True)

            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(
                "Saved %s potholes to offline log: %s",
                len(potholes),
                filename
            )
        except Exception as e:
            logger.error("Error saving offline log: %s", e)

    def sync_offline_logs(self):
        if not os.path.exists(config.OFFLINE_LOG_DIR):
            return

        for filename in os.listdir(config.OFFLINE_LOG_DIR):
            if not filename.endswith(".json"):
                continue

            filepath = os.path.join(config.OFFLINE_LOG_DIR, filename)

            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)

                for item in data:
                    try:
                        severity = Severity(item["severity"])
                    except ValueError:
                        severity = Severity.LOW

                    pothole = Pothole(
                        latitude=float(item["latitude"]),
                        longitude=float(item["longitude"]),
                        city=item.get("city", "Unknown"),
                        region=item.get("region", "Unknown"),
                        severity=severity,
                        area=float(item["area"]),
                        depth=float(item["depth"]),
                        confidence=float(item["confidence"]),
                        timestamp=datetime.fromisoformat(item["timestamp"]),
                        image_path=item.get("image_path")
                    )

                    self.add_pothole(pothole)

                os.remove(filepath)
                logger.info("Synced and removed offline log: %s", filename)

            except json.JSONDecodeError as e:
                logger.error("Corrupted JSON file %s: %s", filename, e)

                backup_dir = os.path.join(config.OFFLINE_LOG_DIR, "corrupted")
                os.makedirs(backup_dir, exist_ok=True)

                backup_path = os.path.join(backup_dir, filename)

                # Avoid overwriting an older corrupted backup with same name.
                if os.path.exists(backup_path):
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    backup_path = os.path.join(
                        backup_dir,
                        f"{timestamp}_{filename}"
                    )

                os.rename(filepath, backup_path)

            except Exception as e:
                logger.error("Error syncing offline log %s: %s", filename, e)