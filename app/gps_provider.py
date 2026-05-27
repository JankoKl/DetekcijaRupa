import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

import serial
import logging
import random
import time
from abc import ABC, abstractmethod
from geopy.geocoders import Nominatim

logger = logging.getLogger(__name__)

# Koliko sekundi da se kešira geocoding rezultat pre nego što se traži novi
GEOCODE_CACHE_TTL = 30  # sekundi


class BaseGPS(ABC):
    @abstractmethod
    def get_gps_data(self):
        pass


class RealGPS(BaseGPS):
    def __init__(self, port, baudrate):
        self.ser = None
        self.port = port
        self.baudrate = baudrate
        self.geolocator = Nominatim(user_agent="pothole_detector")

        # Keš za geocoding — ne zovemo API za svaki NMEA paket
        self._last_city = 'Unknown'
        self._last_region = 'Unknown'
        self._last_geocode_lat = None
        self._last_geocode_lon = None
        self._last_geocode_time = 0

        try:
            self.ser = serial.Serial(port, baudrate, timeout=1)
            logger.info("GPS serial port opened")
        except Exception as e:
            logger.warning(f"Could not open GPS port: {e}")

    def get_gps_data(self):
        try:
            if not self.ser or not self.ser.is_open:
                return None

            line = self.ser.readline().decode('utf-8', errors='ignore').strip()
            if not line:
                return None

            lat, lon = self._parse_nmea_sentence(line)
            if lat is not None and lon is not None:
                city, region = self._get_location_info(lat, lon)
                return {
                    'latitude': lat,
                    'longitude': lon,
                    'city': city,
                    'region': region
                }
        except Exception as e:
            logger.error(f"GPS reading error: {e}")
        return None

    def _parse_nmea_sentence(self, sentence):
        try:
            parts = sentence.split(',')
            if parts[0] == '$GPGGA' and len(parts) >= 6:
                lat = self._nmea_to_decimal(parts[2], parts[3])
                lon = self._nmea_to_decimal(parts[4], parts[5])
                return lat, lon
            elif parts[0] == '$GPRMC' and len(parts) >= 7 and parts[2] == 'A':
                lat = self._nmea_to_decimal(parts[3], parts[4])
                lon = self._nmea_to_decimal(parts[5], parts[6])
                return lat, lon
        except Exception as e:
            logger.debug(f"NMEA parse error: {e}")
        return None, None

    def _nmea_to_decimal(self, coord_str, direction):
        try:
            if not coord_str or '.' not in coord_str:
                return 0.0

            if direction in ['N', 'S']:
                degrees = int(coord_str[:2])
                minutes = float(coord_str[2:])
            else:
                degrees = int(coord_str[:3])
                minutes = float(coord_str[3:])

            decimal = degrees + minutes / 60.0
            if direction in ['S', 'W']:
                decimal *= -1
            return decimal
        except Exception:
            return 0.0

    def _get_location_info(self, lat, lon):
        """
        Fix: keširamo geocoding rezultat GEOCODE_CACHE_TTL sekundi.
        GPS se čita svaki frejm, ali Nominatim API se zove samo jednom
        u definisanom intervalu — izbegavamo rate limiting.
        """
        now = time.time()
        if (
            self._last_geocode_lat is not None
            and abs(lat - self._last_geocode_lat) < 0.001
            and abs(lon - self._last_geocode_lon) < 0.001
            and now - self._last_geocode_time < GEOCODE_CACHE_TTL
        ):
            return self._last_city, self._last_region

        try:
            location = self.geolocator.reverse((lat, lon), timeout=5)
            if location and location.raw.get('address'):
                address = location.raw['address']
                city = address.get('city', address.get('town', 'Unknown'))
                region = address.get('state', 'Unknown')
                self._last_city = city
                self._last_region = region
                self._last_geocode_lat = lat
                self._last_geocode_lon = lon
                self._last_geocode_time = now
                return city, region
        except Exception as e:
            logger.debug(f"Geocoding error: {e}")

        return self._last_city, self._last_region

    def close(self):
        if self.ser and self.ser.is_open:
            self.ser.close()


class SimulatedGPS(BaseGPS):
    def __init__(self):
        self.geolocator = Nominatim(user_agent="pothole_detector_sim")

        # Granice Srbije
        self.lat_min, self.lat_max = 42.2, 46.2
        self.lon_min, self.lon_max = 18.8, 23.0

        # Fix: keš za geocoding — SimulatedGPS menjao koordinate svaki frejm
        # i pravilo HTTP zahtev ka OSM za svaki, što dovodi do rate limitinga
        # za par minuta rada. Sada se koordinate menjaju jednom u TTL intervalu,
        # a geocoding se zove samo kad se koordinate stvarno promene.
        self._cached_data = None
        self._cache_time = 0

    def get_gps_data(self):
        now = time.time()

        # Vrati keširane podatke ako TTL nije istekao
        if self._cached_data and now - self._cache_time < GEOCODE_CACHE_TTL:
            return self._cached_data

        # Generiši nove koordinate i geocoduj ih
        try:
            lat = round(random.uniform(self.lat_min, self.lat_max), 6)
            lon = round(random.uniform(self.lon_min, self.lon_max), 6)
            city, region = self._get_location_info(lat, lon)

            self._cached_data = {
                'latitude': lat,
                'longitude': lon,
                'city': city,
                'region': region
            }
            self._cache_time = now
            return self._cached_data

        except Exception as e:
            logger.debug(f"Simulated GPS error: {e}")
            # Ako nova lokacija ne uspe, vrati stare podatke ako postoje
            return self._cached_data

    def _get_location_info(self, lat, lon):
        try:
            location = self.geolocator.reverse((lat, lon), timeout=5)
            if location and location.raw.get('address'):
                address = location.raw['address']
                return (
                    address.get('city', address.get('town', 'Unknown')),
                    address.get('state', 'Unknown')
                )
        except Exception as e:
            logger.debug(f"Simulated geocoding error: {e}")
        return 'Unknown', 'Unknown'