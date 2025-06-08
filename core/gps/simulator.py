"""
GPS simulator for testing and development.
"""
import json
import logging
import random
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List
import math

from config.config import GPSConfig
from config.logging import get_logger


class GPSSimulator:
    """Simulates GPS coordinates for testing purposes."""

    def __init__(self, config: GPSConfig):
        self.config = config
        self.logger = get_logger(__name__)
        self.running = False
        self._lock = threading.Lock()
        self._simulation_thread: Optional[threading.Thread] = None

        # Current position
        self.current_position: Dict[str, Any] = {}

        # Simulation parameters
        self.route_points: List[Dict[str, float]] = []
        self.current_route_index = 0
        self.speed_kmh = 30.0  # Average speed in km/h

        # Cache for geocoding
        self.geocoding_cache: Dict[str, str] = {}
        self._load_geocoding_cache()

        # Initialize with default route (Belgrade area)
        self._initialize_default_route()

    def _initialize_default_route(self):
        """Initialize with a default route in Belgrade, Serbia."""
        # Route through Belgrade with known pothole-prone areas
        self.route_points = [
            {'lat': 44.7866, 'lon': 20.4489},  # Republic Square
            {'lat': 44.7847, 'lon': 20.4567},  # Knez Mihailova
            {'lat': 44.7831, 'lon': 20.4681},  # Kalemegdan
            {'lat': 44.7765, 'lon': 20.4578},  # Studentski trg
            {'lat': 44.7729, 'lon': 20.4567},  # Slavija
            {'lat': 44.7654, 'lon': 20.4789},  # Autokomanda
            {'lat': 44.7598, 'lon': 20.4912},  # Voždovac
            {'lat': 44.7543, 'lon': 20.5034},  # Banjica
        ]

        # Set initial position
        if self.route_points:
            first_point = self.route_points[0]
            self.current_position = {
                'latitude': first_point['lat'],
                'longitude': first_point['lon'],
                'altitude': random.uniform(70, 120),  # Belgrade altitude range
                'accuracy': random.uniform(3, 8),
                'timestamp': datetime.now(),
                'address': self._get_address(first_point['lat'], first_point['lon'])
            }

    def start(self):
        """Start GPS simulation."""
        if self.running:
            self.logger.warning("GPS simulator already running")
            return

        self.running = True
        self._simulation_thread = threading.Thread(target=self._simulation_loop, daemon=True)
        self._simulation_thread.start()
        self.logger.info("GPS simulator started")

    def stop(self):
        """Stop GPS simulation."""
        self.running = False
        if self._simulation_thread and self._simulation_thread.is_alive():
            self._simulation_thread.join(timeout=5.0)
        self.logger.info("GPS simulator stopped")

    def _simulation_loop(self):
        """Main simulation loop."""
        while self.running:
            try:
                # Move to next position
                self._update_position()

                # Sleep for simulation interval (1 second)
                time.sleep(1.0)

            except Exception as e:
                self.logger.error(f"Error in GPS simulation loop: {e}")
                time.sleep(1.0)

    def _update_position(self):
        """Update current position along the route."""
        if not self.route_points:
            return

        # Get current and next waypoints
        current_idx = self.current_route_index % len(self.route_points)
        next_idx = (self.current_route_index + 1) % len(self.route_points)

        current_point = self.route_points[current_idx]
        next_point = self.route_points[next_idx]

        # Calculate distance and bearing
        distance = self._calculate_distance(
            current_point['lat'], current_point['lon'],
            next_point['lat'], next_point['lon']
        )

        # Calculate movement step (speed in m/s)
        speed_ms = self.speed_kmh * 1000 / 3600
        step_distance = speed_ms  # 1 second step

        # If we're close to the next waypoint, move to it
        if distance < step_distance:
            self.current_route_index = next_idx
            new_lat = next_point['lat']
            new_lon = next_point['lon']
        else:
            # Calculate new position along the route
            bearing = self._calculate_bearing(
                current_point['lat'], current_point['lon'],
                next_point['lat'], next_point['lon']
            )
            new_lat, new_lon = self._move_position(
                current_point['lat'], current_point['lon'],
                bearing, step_distance
            )

        # Add some random noise for realism
        new_lat += random.uniform(-0.00001, 0.00001)
        new_lon += random.uniform(-0.00001, 0.00001)

        # Update position with thread safety
        with self._lock:
            self.current_position = {
                'latitude': new_lat,
                'longitude': new_lon,
                'altitude': random.uniform(70, 120),
                'accuracy': random.uniform(3, 8),
                'timestamp': datetime.now(),
                'address': self._get_address(new_lat, new_lon)
            }

    def get_current_position(self) -> Dict[str, Any]:
        """Get current GPS position."""
        with self._lock:
            return self.current_position.copy()

    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in meters using Haversine formula."""
        R = 6371000  # Earth's radius in meters

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lat = math.radians(lat2 - lat1)
        delta_lon = math.radians(lon2 - lon1)

        a = (math.sin(delta_lat / 2) ** 2 +
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(delta_lon / 2) ** 2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

        return R * c

    def _calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate bearing from point 1 to point 2."""
        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        delta_lon = math.radians(lon2 - lon1)

        y = math.sin(delta_lon) * math.cos(lat2_rad)
        x = (math.cos(lat1_rad) * math.sin(lat2_rad) -
             math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(delta_lon))

        bearing = math.atan2(y, x)
        return (math.degrees(bearing) + 360) % 360

    def _move_position(self, lat: float, lon: float, bearing: float, distance: float) -> tuple:
        """Move position by distance and bearing."""
        R = 6371000  # Earth's radius in meters

        lat_rad = math.radians(lat)
        lon_rad = math.radians(lon)
        bearing_rad = math.radians(bearing)

        new_lat_rad = math.asin(
            math.sin(lat_rad) * math.cos(distance / R) +
            math.cos(lat_rad) * math.sin(distance / R) * math.cos(bearing_rad)
        )

        new_lon_rad = lon_rad + math.atan2(
            math.sin(bearing_rad) * math.sin(distance / R) * math.cos(lat_rad),
            math.cos(distance / R) - math.sin(lat_rad) * math.sin(new_lat_rad)
        )

        return math.degrees(new_lat_rad), math.degrees(new_lon_rad)

    def _get_address(self, lat: float, lon: float) -> str:
        """Get address for coordinates (cached)."""
        cache_key = f"{lat:.6f},{lon:.6f}"

        if cache_key in self.geocoding_cache:
            return self.geocoding_cache[cache_key]

        # Simple address generation for Belgrade area
        addresses = [
            "Knez Mihailova, Belgrade, Serbia",
            "Terazije, Belgrade, Serbia",
            "Slavija Square, Belgrade, Serbia",
            "Republic Square, Belgrade, Serbia",
            "Kalemegdan Park, Belgrade, Serbia",
            "Autokomanda, Belgrade, Serbia",
            "Voždovac, Belgrade, Serbia",
            "Banjica, Belgrade, Serbia"
        ]

        address = random.choice(addresses)
        self.geocoding_cache[cache_key] = address
        self._save_geocoding_cache()

        return address

    def _load_geocoding_cache(self):
        """Load geocoding cache from file."""
        try:
            cache_file = Path(self.config.cache_file)
            if cache_file.exists():
                with open(cache_file, 'r', encoding='utf-8') as f:
                    self.geocoding_cache = json.load(f)
                self.logger.debug(f"Loaded {len(self.geocoding_cache)} cached addresses")
        except Exception as e:
            self.logger.warning(f"Failed to load geocoding cache: {e}")
            self.geocoding_cache = {}

    def _save_geocoding_cache(self):
        """Save geocoding cache to file."""
        try:
            cache_file = Path(self.config.cache_file)
            cache_file.parent.mkdir(parents=True, exist_ok=True)

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(self.geocoding_cache, f, indent=2, ensure_ascii=False)
        except Exception as e:
            self.logger.warning(f"Failed to save geocoding cache: {e}")

    def set_route(self, waypoints: List[Dict[str, float]]):
        """Set custom route waypoints."""
        if waypoints:
            self.route_points = waypoints
            self.current_route_index = 0
            self.logger.info(f"Set custom route with {len(waypoints)} waypoints")

    def set_speed(self, speed_kmh: float):
        """Set simulation speed in km/h."""
        if speed_kmh > 0:
            self.speed_kmh = speed_kmh
            self.logger.info(f"Set simulation speed to {speed_kmh} km/h")
