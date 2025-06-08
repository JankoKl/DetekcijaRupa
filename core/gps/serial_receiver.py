from typing import Optional

import serial
import time
import threading
import logging
from core.gps.gps_point import GPSPoint

logger = logging.getLogger(__name__)


class SerialGPSReceiver:
    def __init__(self, port: str, baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.serial = serial.Serial(port, baudrate, timeout=1)
        self.location_buffer = []
        self.max_buffer_size = 10
        self._running = False
        self._thread = threading.Thread(target=self._update_loop, daemon=True)
        self.start()
        logger.info(f"GPS receiver initialized on {port}")

    def start(self):
        """Start the background update thread"""
        self._running = True
        self._thread.start()
        logger.info("GPS receiver update thread started")

    def stop(self):
        """Stop the background update thread"""
        self._running = False
        if self._thread.is_alive():
            self._thread.join(timeout=1.0)
        self.serial.close()

    def _update_loop(self):
        """Background thread to continuously read from serial"""
        while self._running:
            self.update()
            time.sleep(0.01)  # Short sleep to read frequently

    def read_location(self) -> Optional[GPSPoint]:
        """Read and parse GPS data from serial"""
        try:
            line = self.serial.readline().decode('utf-8').strip()
            if line.startswith('$GPGGA'):
                parts = line.split(',')
                if len(parts) > 6 and parts[6] != '0':  # Check fix quality
                    lat = self._parse_coordinate(parts[2], parts[3])
                    lon = self._parse_coordinate(parts[4], parts[5])
                    return GPSPoint(lat, lon, time.time())
        except Exception as e:
            logger.error(f"GPS read error: {str(e)}")
        return None

    def _parse_coordinate(self, value: str, direction: str) -> float:
        """Convert NMEA coordinate to decimal degrees"""
        degrees = float(value[:2]) if len(value) > 4 else float(value[:3])
        minutes = float(value[2:]) if len(value) > 4 else float(value[3:])
        decimal = degrees + minutes / 60
        if direction in ['S', 'W']:
            decimal *= -1
        return decimal

    def update(self):
        """Update location buffer with new readings"""
        location = self.read_location()
        if location:
            self.location_buffer.append(location)
            if len(self.location_buffer) > self.max_buffer_size:
                self.location_buffer.pop(0)

    def get_current_location(self) -> Optional[GPSPoint]:
        """Get latest GPS reading"""
        if self.location_buffer:
            return self.location_buffer[-1]
        return None

    def get_location_at_time(self, timestamp: float) -> Optional[GPSPoint]:
        """Get closest GPS reading to given timestamp"""
        if not self.location_buffer:
            return None

        # Find closest by timestamp
        closest = min(self.location_buffer, key=lambda loc: abs(loc.timestamp - timestamp))
        return closest