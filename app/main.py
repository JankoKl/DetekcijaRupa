import sys
import os

# Fix: osigurava da Python pronalazi module unutar app/ foldera
# bez obzira odakle se skripta pokrece
sys.path.insert(0, os.path.dirname(__file__))

import cv2
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
from gps_provider import SimulatedGPS, RealGPS
from utils import save_detection_image
from prometheus_client import start_http_server, Counter, Summary


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
        self.notification_queue = Queue()
        # Fix: running=True ovde, ne na pocetku process_video,
        # jer sync_thread krece odmah i mora da vidi True
        self.running = True

        # Start Prometheus metrics server
        start_http_server(8000)

        # Define Prometheus metrics
        self.pothole_counter = Counter('pothole_detections_total', 'Total potholes detected')
        self.severity_counter = {
            'LOW': Counter('pothole_severity_low_total', 'Low severity potholes'),
            'MEDIUM': Counter('pothole_severity_medium_total', 'Medium severity potholes'),
            'HIGH': Counter('pothole_severity_high_total', 'High severity potholes'),
            'CRITICAL': Counter('pothole_severity_critical_total', 'Critical severity potholes'),
        }
        self.frame_time = Summary('frame_processing_duration_seconds', 'Time spent processing each frame')

        if config.USE_SIMULATION:
            self.gps = SimulatedGPS()
        else:
            self.gps = RealGPS(config.GPS_PORT, config.GPS_BAUDRATE)

    def process_video(self):
        """Main video processing loop"""
        # Fix: uklonjen dupli serial.Serial() otvor koji je bio ovde
        # GPS se vec inicijalizuje kroz self.gps u __init__
        cap = None
        video_writer = None

        try:
            # Open video or webcam
            if config.USE_LIVE_CAMERA:
                cap = cv2.VideoCapture(config.CAMERA_INDEX)
                logger.info("Using live webcam feed.")
                cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.VIDEO_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.VIDEO_HEIGHT)
            else:
                cap = cv2.VideoCapture(config.VIDEO_FILE)
                logger.info(f"Using video file: {config.VIDEO_FILE}")

            if not cap.isOpened():
                raise ValueError("Could not open video source")

            # Prepare video writer if enabled
            if config.SAVE_VIDEO:
                fourcc = cv2.VideoWriter_fourcc(*'XVID')
                video_writer = cv2.VideoWriter(
                    config.VIDEO_OUTPUT_PATH,
                    fourcc,
                    config.VIDEO_FPS,
                    (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
                )
                logger.info(f"Video recording enabled: {config.VIDEO_OUTPUT_PATH}")

            frame_count = 0
            last_gps_data = None

            while self.running and cap.isOpened():
                with self.frame_time.time():
                    ret, frame = cap.read()
                    if not ret:
                        break

                    frame_count += 1

                    if frame_count % config.FRAME_SKIP != 0:
                        continue

                    frame = cv2.resize(frame, (config.VIDEO_WIDTH, config.VIDEO_HEIGHT))

                    gps_data = self.gps.get_gps_data()
                    if gps_data:
                        last_gps_data = gps_data
                    else:
                        gps_data = last_gps_data

                    if gps_data:
                        gps_text = f"{gps_data['city']}, {gps_data['region']} ({gps_data['latitude']:.5f}, {gps_data['longitude']:.5f})"
                        cv2.putText(frame, gps_text, (10, 25), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)

                    potholes, annotated_frame = self.detector.detect_potholes(frame, gps_data)

                    for pothole in potholes:
                        if gps_data and not self.db.is_duplicate(pothole.latitude, pothole.longitude):
                            try:
                                pothole_id = self.db.add_pothole(pothole)
                                if pothole_id:
                                    self.pothole_counter.inc()
                                    severity = pothole.severity.value.upper()
                                    if severity in self.severity_counter:
                                        self.severity_counter[severity].inc()
                                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                                    image_path = save_detection_image(annotated_frame, pothole_id, timestamp)
                                    pothole.id = pothole_id
                                    pothole.image_path = image_path
                                    logger.info(f"New pothole detected: ID={pothole_id}, "
                                                f"Severity={pothole.severity.value}, "
                                                f"Depth={pothole.depth:.3f}m, "
                                                f"Location=({pothole.latitude:.6f}, {pothole.longitude:.6f})")
                                    # Posalji notifikaciju adminima za HIGH i CRITICAL rupe
                                    self.notification_queue.put(pothole)
                            except Exception as e:
                                logger.error(f"Database error: {e}")
                                self.db.save_offline_log([pothole])

                    if config.SAVE_VIDEO and video_writer:
                        video_writer.write(annotated_frame)

                    cv2.imshow('Pothole Detection', annotated_frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break

        except Exception as e:
            logger.error(f"Processing error: {e}")

        finally:
            if cap:
                cap.release()
            if video_writer:
                video_writer.release()
            cv2.destroyAllWindows()
            self.running = False
            logger.info("Video processing stopped")
            if isinstance(self.gps, RealGPS):
                self.gps.close()

    def notification_worker(self):
        """
        Čita rupe iz notification_queue i šalje Telegram notifikacije.
        Vrti se u posebnom threadu da ne blokira video processing.
        """
        import asyncio
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        while self.running:
            try:
                pothole = self.notification_queue.get(timeout=1)
                loop.run_until_complete(self.bot.notify_new_pothole(pothole))
            except Exception:
                pass
        loop.close()

    def sync_offline_data(self):
        """Periodically sync offline data"""
        while self.running:
            try:
                self.db.sync_offline_logs()
            except Exception as e:
                logger.error(f"Sync error: {e}")
            time.sleep(60)

    def run(self):
        """Run the complete system"""
        video_thread = threading.Thread(target=self.process_video)
        video_thread.start()

        sync_thread = threading.Thread(target=self.sync_offline_data)
        sync_thread.start()

        notif_thread = threading.Thread(target=self.notification_worker, daemon=True)
        notif_thread.start()

        try:
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