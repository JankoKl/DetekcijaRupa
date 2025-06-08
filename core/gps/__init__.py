# core/gps/__init__.py
"""
GPS module for location tracking and simulation.
"""
from .simulator import GPSSimulator
from .serial_receiver import SerialGPSReceiver

__all__ = ['GPSSimulator', 'SerialGPSReceiver']
