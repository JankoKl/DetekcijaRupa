import random
import time
import threading
import logging
import datetime
from typing import Optional

from core.data.models import GPSPoint
from core.gps import GPSProvider

logger = logging.getLogger(__name__)


class GPSSimulator(GPSProvider):
    def __init__(self, center_lat=44.0165, center_lon=21.0059, radius=0.01):  # Kragujevac coordinates
        self.center_lat = center_lat
        self.center_lon = center_lon
        self.radius = radius
        self.location_buffer = []
        self.max_buffer_size = 10
        self._running = False
        self._thread = None
        self.start()
        logger.info("GPS simulator initialized")

    def start(self):
        """Start the background update thread"""
        if not self._running:
            self._running = True
            self._thread = threading.Thread(target=self._update_loop, daemon=True)
            self._thread.start()
            logger.info("GPS simulator update thread started")

    def stop(self):
        """Stop the background update thread"""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=1.0)

    def _update_loop(self):
        """Background thread to continuously update location"""
        while self._running:
            try:
                self.update()
                time.sleep(0.1)  # Update 10 times per second
            except Exception as e:
                logger.error(f"GPS simulator error: {e}")
                time.sleep(1.0)

    def generate_location(self) -> GPSPoint:
        """Generate random location near center point"""
        lat = self.center_lat + random.uniform(-self.radius, self.radius)
        lon = self.center_lon + random.uniform(-self.radius, self.radius)
        return GPSPoint(
            latitude=lat,
            longitude=lon,
            timestamp=datetime.datetime.now()
        )

    def update(self):
        """Update location buffer with new simulated location"""
        location = self.generate_location()
        self.location_buffer.append(location)
        if len(self.location_buffer) > self.max_buffer_size:
            self.location_buffer.pop(0)

    def get_current_location(self) -> Optional[GPSPoint]:
        """Get latest simulated location"""
        if self.location_buffer:
            return self.location_buffer[-1]
        return None

    def get_location_at_time(self, timestamp: float) -> Optional[GPSPoint]:
        """Get closest simulated location to given timestamp"""
        if not self.location_buffer:
            return None

        # Convert timestamp to datetime for comparison
        target_time = datetime.datetime.fromtimestamp(timestamp)

        # Find closest by timestamp
        closest = min(
            self.location_buffer,
            key=lambda loc: abs((loc.timestamp - target_time).total_seconds())
        )
        return closest