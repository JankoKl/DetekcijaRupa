# core/gps/serial_receiver.py
"""
Serial GPS receiver for obtaining GPS data.
"""
import serial
import logging
from config.logging import get_logger


class SerialGPSReceiver:
    """Class to receive GPS data from a serial port."""

    def __init__(self, port: str, baudrate: int = 9600):
        self.port = port
        self.baudrate = baudrate
        self.logger = get_logger(__name__)
        self.serial_connection = None

    def connect(self):
        """Connect to the serial port."""
        try:
            self.serial_connection = serial.Serial(self.port, self.baudrate, timeout=1)
            self.logger.info(f"Connected to GPS on {self.port} at {self.baudrate} baud.")
        except Exception as e:
            self.logger.error(f"Failed to connect to GPS: {e}")
            raise

    def read_data(self):
        """Read data from the GPS serial connection."""
        if self.serial_connection and self.serial_connection.is_open:
            try:
                line = self.serial_connection.readline().decode('ascii', errors='replace')
                return line.strip()
            except Exception as e:
                self.logger.error(f"Error reading from GPS: {e}")
                return None
        return None

    def close(self):
        """Close the serial connection."""
        if self.serial_connection:
            self.serial_connection.close()
            self.logger.info("Closed GPS serial connection.")
