import logging
import json
import os
import time
import datetime
from concurrent.futures import ThreadPoolExecutor
from typing import List, Optional, Tuple, Any
from geopy.geocoders import Nominatim
from geopy.distance import geodesic
from geopy.exc import GeocoderUnavailable
from core.data.models import Pothole, GPSPoint
from core.data.repository import PotholeRepository
from core.gps import GPSProvider

logger = logging.getLogger(__name__)


class PotholeService:
    def __init__(self, detector, gps_provider: 'GPSProvider', repository: PotholeRepository):
        self.detector = detector
        self.gps_provider = gps_provider
        self.repository = repository
        self.geolocator = Nominatim(user_agent="pothole_detector")

        # Spatiotemporal deduplication
        self.recent_potholes = []
        self.duplicate_threshold = 15  # meters
        self.time_window = 300  # 5 minutes

        # Asynchronous geocoding
        self.geocoding_executor = ThreadPoolExecutor(max_workers=2)
        self.geocoding_cache = {}
        self.cache_file = "geocoding_cache.json"
        self._load_cache()

    def _load_cache(self):
        """Load geocoding cache from file"""
        if os.path.exists(self.cache_file):
            try:
                with open(self.cache_file, 'r') as f:
                    self.geocoding_cache = json.load(f)
                logger.info(f"Loaded geocoding cache with {len(self.geocoding_cache)} entries")
            except Exception as e:
                logger.error(f"Failed to load geocoding cache: {str(e)}")
                self.geocoding_cache = {}
        else:
            self.geocoding_cache = {}

    def _save_cache(self):
        """Save geocoding cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.geocoding_cache, f)
        except Exception as e:
            logger.error(f"Failed to save geocoding cache: {str(e)}")

    def _reverse_geocode(self, location: GPSPoint) -> tuple[str, str, str] | tuple[Any, Any, Any] | tuple[Any]:
        """Perform reverse geocoding with caching"""
        cache_key = f"{location.latitude:.6f},{location.longitude:.6f}"

        # Return cached result if available
        if cache_key in self.geocoding_cache:
            return tuple(self.geocoding_cache[cache_key])

        default_result = ('Unknown Street', 'Unknown City', 'Unknown Region')

        try:
            location_data = self.geolocator.reverse(
                (location.latitude, location.longitude),
                language='en',
                timeout=5
            )

            if not location_data or not location_data.raw.get('address'):
                return default_result

            address = location_data.raw['address']
            street = address.get('road', 'Unknown Street')
            city = address.get('city', address.get('town', 'Unknown City'))
            region = address.get('state', address.get('county', 'Unknown Region'))

            result = (street, city, region)
            self.geocoding_cache[cache_key] = result
            self._save_cache()
            return result

        except GeocoderUnavailable:
            logger.warning("Geocoding service unavailable")
            return default_result
        except Exception as e:
            logger.error(f"Geocoding error: {str(e)}")
            return default_result

    def _get_location_info(self, location: GPSPoint) -> tuple[str, str, str] | tuple[Any] | Any:
        """Get location info with async execution"""
        cache_key = f"{location.latitude:.6f},{location.longitude:.6f}"

        if cache_key in self.geocoding_cache:
            return tuple(self.geocoding_cache[cache_key])

        # Submit geocoding task asynchronously
        future = self.geocoding_executor.submit(self._reverse_geocode, location)
        try:
            # Wait for result with timeout
            return future.result(timeout=3)
        except Exception:
            return ('Processing...', 'Processing...', 'Processing...')

    def _create_pothole_object(self, detection: dict, location: GPSPoint) -> Pothole:
        """Create a Pothole object from detection data"""
        street, city, region = self._get_location_info(location)

        return Pothole(
            location=location.dict(),  # Convert to dictionary
            street=street,
            city=city,
            region=region,
            severity_level=detection['severity'].value,  # Convert enum to string if needed
            severity_score=detection['score'],
            confidence=detection['confidence'],
            detected_at=datetime.now()
        )

    def _is_duplicate_location(self, location: GPSPoint) -> bool:
        """Check if location is near recent detections within time window"""
        now = datetime.datetime.now()
        cutoff = now - datetime.timedelta(seconds=self.time_window)

        # Filter recent potholes within time window
        recent = [p for p in self.recent_potholes if p['timestamp'] > cutoff]
        self.recent_potholes = recent

        # Check distance to each recent pothole
        new_point = (location.latitude, location.longitude)
        for pothole in recent:
            existing_point = (pothole['location'].latitude, pothole['location'].longitude)
            if geodesic(new_point, existing_point).meters < self.duplicate_threshold:
                return True
        return False

    def process_frame(self, frame) -> Optional[List[dict]]:
        """Process a frame and save detections"""
        # Get synchronized GPS location
        frame_timestamp = time.time()
        location = self.gps_provider.get_location_at_time(frame_timestamp)

        if not location:
            logger.warning("No GPS data available")
            return None

        if self._is_duplicate_location(location):
            return None

        detections = self.detector.detect(frame)
        if not detections:
            return None

        processed_detections = []

        for detection in detections:
            pothole = self._create_pothole_object(detection, location)

            if self.repository.save_pothole(pothole):
                # Add to recent detections
                self.recent_potholes.append({
                    'location': location,
                    'timestamp': datetime.datetime.now()
                })
                loc_key = (round(location.latitude, 6), round(location.longitude, 6))
                logger.info(f"Detected {detection['severity'].value} pothole at {loc_key}")
                processed_detections.append(detection)

        return processed_detections