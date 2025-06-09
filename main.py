import cv2
import serial
import logging
import threading
import time
from datetime import datetime
from queue import Queue
from geopy.geocoders import Nominatim

from config import config
from database import PotholeDatabase
from detector import PotholeDetector
from bot import PotholeBot
from utils import save_detection_image

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


class PotholeDetectionSystem:
    def __init__(self):
        self.db = PotholeDatabase()
        self.detector = PotholeDetector()
        self.bot = PotholeBot(self.db)
        self.geolocator = Nominatim(user_agent="pothole_detector")
        self.detection_queue = Queue()
        self.running = False

    def parse_nmea_gps(self, nmea_sentence):
        """Parse NMEA GPS sentence to extract coordinates"""
        try:
            parts = nmea_sentence.strip().split(',')

            # Check if it's a GPGGA sentence (most common for location)
            if parts[0] == '$GPGGA' and len(parts) >= 6:
                # Extract latitude
                lat_raw = parts[2]
                lat_dir = parts[3]

                # Extract longitude
                lon_raw = parts[4]
                lon_dir = parts[5]

                # Check if we have valid data
                if lat_raw and lon_raw:
                    # Convert NMEA format to decimal degrees
                    lat = self.nmea_to_decimal(lat_raw, lat_dir)
                    lon = self.nmea_to_decimal(lon_raw, lon_dir)

                    return lat, lon

            # Alternative: GPRMC sentence
            elif parts[0] == '$GPRMC' and len(parts) >= 7:
                if parts[2] == 'A':  # A = Active, V = Void
                    lat_raw = parts[3]
                    lat_dir = parts[4]
                    lon_raw = parts[5]
                    lon_dir = parts[6]

                    if lat_raw and lon_raw:
                        lat = self.nmea_to_decimal(lat_raw, lat_dir)
                        lon = self.nmea_to_decimal(lon_raw, lon_dir)
                        return lat, lon

        except (ValueError, IndexError) as e:
            logger.debug(f"GPS parsing error: {e}")

        return None, None

    def nmea_to_decimal(self, coord_str, direction):
        """Convert NMEA coordinate format to decimal degrees"""
        try:
            # NMEA format: DDMM.MMMM for latitude, DDDMM.MMMM for longitude
            if '.' in coord_str:
                parts = coord_str.split('.')
                degrees_and_minutes = parts[0]
                decimal_minutes = parts[1]

                # Extract degrees (first 2 or 3 digits)
                if len(degrees_and_minutes) == 4:  # Latitude
                    degrees = int(degrees_and_minutes[:2])
                    minutes = int(degrees_and_minutes[2:])
                else:  # Longitude (5 digits)
                    degrees = int(degrees_and_minutes[:3])
                    minutes = int(degrees_and_minutes[3:])

                # Convert to decimal
                decimal = degrees + (minutes + float('0.' + decimal_minutes)) / 60

                # Apply direction
                if direction in ['S', 'W']:
                    decimal = -decimal

                return decimal
        except:
            return 0.0

    def get_gps_data(self, ser):
        """Read and parse GPS data from serial port"""
        try:
            # Read line from serial port
            line = ser.readline().decode('utf-8', errors='ignore').strip()

            if line:
                # Parse NMEA sentence
                lat, lon = self.parse_nmea_gps(line)

                if lat is not None and lon is not None:
                    # Get location info using geocoding
                    try:
                        location = self.geolocator.reverse((lat, lon), timeout=5)
                        if location and location.raw.get('address'):
                            address = location.raw['address']
                            city = address.get('city', address.get('town', 'Unknown'))
                            region = address.get('state', 'Unknown')
                        else:
                            city, region = 'Unknown', 'Unknown'
                    except Exception as e:
                        logger.debug(f"Geocoding error: {e}")
                        city, region = 'Unknown', 'Unknown'

                    return {
                        'latitude': lat,
                        'longitude': lon,
                        'city': city,
                        'region': region
                    }

        except Exception as e:
            logger.error(f"GPS reading error: {e}")

        return None

    def process_video(self):
        """Main video processing loop"""
        self.running = True
        ser = None
        cap = None

        try:
            # Initialize serial port
            try:
                ser = serial.Serial(config.GPS_PORT, config.GPS_BAUDRATE, timeout=1)
                logger.info("GPS serial port opened")
            except Exception as e:
                logger.warning(f"Could not open GPS port: {e}. Continuing without GPS.")

            # Open video
            cap = cv2.VideoCapture(config.VIDEO_FILE)
            if not cap.isOpened():
                raise ValueError("Could not open video file")

            frame_count = 0
            last_gps_data = None

            while self.running and cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_count += 1

                # Skip frames according to config
                if frame_count % config.FRAME_SKIP != 0:
                    continue

                # Get GPS data - CALL THE PARSING METHOD HERE
                if ser and ser.is_open:
                    gps_data = self.get_gps_data(ser)  # This calls parse_nmea_gps internally
                    if gps_data:
                        last_gps_data = gps_data
                        logger.debug(f"GPS: {gps_data['latitude']:.6f}, {gps_data['longitude']:.6f}")
                else:
                    # Use last known GPS data or default
                    gps_data = last_gps_data

                # Resize frame
                frame = cv2.resize(frame, (config.VIDEO_WIDTH, config.VIDEO_HEIGHT))

                # Detect potholes
                potholes, annotated_frame = self.detector.detect_potholes(frame, gps_data)

                # Process detected potholes
                for pothole in potholes:
                    # Check if it's a duplicate
                    if gps_data and not self.db.is_duplicate(pothole.latitude, pothole.longitude):
                        # Save to database
                        try:
                            pothole_id = self.db.add_pothole(pothole)
                            if pothole_id:
                                # Save detection image
                                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                image_path = save_detection_image(annotated_frame, pothole_id, timestamp)

                                logger.info(f"New pothole detected: ID={pothole_id}, "
                                            f"Severity={pothole.severity.value}, "
                                            f"Depth={pothole.depth:.3f}m, "
                                            f"Location=({pothole.latitude:.6f}, {pothole.longitude:.6f})")
                        except Exception as e:
                            logger.error(f"Database error: {e}")
                            # Save to offline log
                            self.db.save_offline_log([pothole])

                # Display annotated frame
                cv2.imshow('Pothole Detection', annotated_frame)

                # Check for quit
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        except Exception as e:
            logger.error(f"Processing error: {e}")

        finally:
            # Cleanup
            if cap:
                cap.release()
            if ser and ser.is_open:
                ser.close()
            cv2.destroyAllWindows()
            self.running = False
            logger.info("Video processing stopped")



    def sync_offline_data(self):
        """Periodically sync offline data"""
        while self.running:
            try:
                self.db.sync_offline_logs()
            except Exception as e:
                logger.error(f"Sync error: {e}")
            time.sleep(60)  # Sync every minute

    def run(self):
        """Run the complete system"""
        # Start video processing in a separate thread
        video_thread = threading.Thread(target=self.process_video)
        video_thread.start()

        # Start offline sync in a separate thread
        sync_thread = threading.Thread(target=self.sync_offline_data)
        sync_thread.start()

        try:
            # Run bot in main thread
            self.bot.run()
        except KeyboardInterrupt:
            logger.info("Shutting down...")
        finally:
            self.running = False
            video_thread.join()
            sync_thread.join()


def main():
    system = PotholeDetectionSystem()
    system.run()


if __name__ == '__main__':
    main()
