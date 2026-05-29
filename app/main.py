import sys
import os

# Ensure Python can find modules inside app/ regardless of working directory.
sys.path.insert(0, os.path.dirname(__file__))

import cv2
import logging
import threading
import time
from datetime import datetime
from queue import Queue, Empty
from http.server import HTTPServer, BaseHTTPRequestHandler
from geopy.geocoders import Nominatim

from config import config
from database import PotholeDatabase
from bot import PotholeBot
from gps_provider import SimulatedGPS, RealGPS
from utils import save_detection_image
from prometheus_client import start_http_server, Counter, Summary


logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

logger = logging.getLogger(__name__)


class HealthHandler(BaseHTTPRequestHandler):
    """
    Minimal HTTP health endpoint used mainly in BOT_ONLY/cloud mode.

    Endpoints:
        GET /        -> 200 OK
        GET /health  -> 200 OK
    """

    def do_GET(self):
        if self.path in ("/", "/health"):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"OK")
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):
        # Silence default HTTP server logs to keep application logs clean.
        return


def start_health_server(port: int = 8000):
    """
    Start a lightweight HTTP health server in a daemon thread.

    This is useful for deployments that expect the app to listen on port 8000
    even when the app is running only as a Telegram bot.
    """
    server = HTTPServer(("0.0.0.0", port), HealthHandler)

    thread = threading.Thread(
        target=server.serve_forever,
        name="health-server",
        daemon=True
    )
    thread.start()

    logger.info("Health server started on port %s", port)
    return server


class PotholeDetectionSystem:
    def __init__(self):
        self.db = PotholeDatabase()
        self.bot = PotholeBot(self.db)
        self.running = True

        self.detector = None
        self.geolocator = None
        self.gps = None

        self.detection_queue = Queue()
        self.notification_queue = Queue()

        self.pothole_counter = None
        self.severity_counter = {}
        self.frame_time = None

        self.health_server = None

        if config.BOT_ONLY:
            logger.info("BOT_ONLY mode enabled — skipping detector, GPS and CV pipeline")
            self.health_server = start_health_server(8000)
            return

        # Heavy imports and model loading are done only in full CV mode.
        from detector import PotholeDetector

        self.detector = PotholeDetector()
        self.geolocator = Nominatim(user_agent="pothole_detector")

        # Start Prometheus metrics server.
        start_http_server(8000)
        logger.info("Prometheus metrics server started on port 8000")

        # Prometheus metrics.
        self.pothole_counter = Counter(
            "pothole_detections_total",
            "Total potholes detected"
        )

        self.severity_counter = {
            "LOW": Counter(
                "pothole_severity_low_total",
                "Low severity potholes"
            ),
            "MEDIUM": Counter(
                "pothole_severity_medium_total",
                "Medium severity potholes"
            ),
            "HIGH": Counter(
                "pothole_severity_high_total",
                "High severity potholes"
            ),
            "CRITICAL": Counter(
                "pothole_severity_critical_total",
                "Critical severity potholes"
            ),
        }

        self.frame_time = Summary(
            "frame_processing_duration_seconds",
            "Time spent processing each frame"
        )

        if config.USE_SIMULATION:
            self.gps = SimulatedGPS()
            logger.info("Using simulated GPS")
        else:
            self.gps = RealGPS(config.GPS_PORT, config.GPS_BAUDRATE)
            logger.info("Using real GPS on %s:%s", config.GPS_PORT, config.GPS_BAUDRATE)

        if config.HEADLESS:
            logger.info("Running in HEADLESS mode — no GUI window")
        else:
            logger.info("Running in GUI mode — press Q to quit")

    def process_video(self):
        """
        Main video processing loop.

        Responsibilities:
            - open live camera or video file
            - read frames
            - optionally skip frames
            - attach latest GPS data
            - run YOLO + MiDaS detector
            - save new potholes to SQLite
            - save annotated detection image
            - push high/critical potholes to notification queue
            - optionally display GUI window
            - optionally save processed output video
        """
        cap = None
        video_writer = None

        try:
            if config.USE_LIVE_CAMERA:
                cap = cv2.VideoCapture(config.CAMERA_INDEX)
                logger.info("Using live camera feed, camera index=%s", config.CAMERA_INDEX)

                cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.VIDEO_WIDTH)
                cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.VIDEO_HEIGHT)
            else:
                cap = cv2.VideoCapture(config.VIDEO_FILE)
                logger.info("Using video file: %s", config.VIDEO_FILE)

            if not cap.isOpened():
                if config.HEADLESS:
                    logger.warning(
                        "No video source available — bot will continue with existing database data"
                    )
                    return

                raise ValueError("Could not open video source")

            if config.SAVE_VIDEO and not config.HEADLESS:
                output_dir = os.path.dirname(config.VIDEO_OUTPUT_PATH)
                if output_dir:
                    os.makedirs(output_dir, exist_ok=True)

                fourcc = cv2.VideoWriter_fourcc(*"XVID")
                video_writer = cv2.VideoWriter(
                    config.VIDEO_OUTPUT_PATH,
                    fourcc,
                    config.VIDEO_FPS,
                    (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
                )

                logger.info("Video recording enabled: %s", config.VIDEO_OUTPUT_PATH)

            frame_count = 0
            last_gps_data = None

            while self.running and cap.isOpened():
                with self.frame_time.time():
                    ret, frame = cap.read()

                    if not ret:
                        logger.info("Video stream ended or frame could not be read")
                        break

                    frame_count += 1

                    if frame_count % config.FRAME_SKIP != 0:
                        continue

                    frame = cv2.resize(
                        frame,
                        (config.VIDEO_WIDTH, config.VIDEO_HEIGHT)
                    )

                    gps_data = self.gps.get_gps_data() if self.gps else None

                    if gps_data:
                        last_gps_data = gps_data
                    else:
                        gps_data = last_gps_data

                    if gps_data and not config.HEADLESS:
                        gps_text = (
                            f"{gps_data['city']}, {gps_data['region']} "
                            f"({gps_data['latitude']:.5f}, {gps_data['longitude']:.5f})"
                        )

                        cv2.putText(
                            frame,
                            gps_text,
                            (10, 25),
                            cv2.FONT_HERSHEY_SIMPLEX,
                            0.6,
                            (0, 255, 255),
                            2
                        )

                    potholes, annotated_frame = self.detector.detect_potholes(
                        frame,
                        gps_data
                    )

                    for pothole in potholes:
                        # Current behavior: only store detections if GPS data exists.
                        # add_pothole() itself performs duplicate detection.
                        if not gps_data:
                            logger.debug("Skipping pothole because GPS data is unavailable")
                            continue

                        try:
                            pothole_id = self.db.add_pothole(pothole)

                            # None means duplicate.
                            if not pothole_id:
                                continue

                            self.pothole_counter.inc()

                            severity_key = pothole.severity.value.upper()
                            if severity_key in self.severity_counter:
                                self.severity_counter[severity_key].inc()

                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            image_path = save_detection_image(
                                annotated_frame,
                                pothole_id,
                                timestamp
                            )

                            # Important: persist image_path in database.
                            self.db.update_pothole_image_path(
                                pothole_id,
                                image_path
                            )

                            pothole.id = pothole_id
                            pothole.image_path = image_path

                            logger.info(
                                "New pothole detected: ID=%s, Severity=%s, "
                                "Depth=%.3fm, Location=(%.6f, %.6f)",
                                pothole_id,
                                pothole.severity.value,
                                pothole.depth,
                                pothole.latitude,
                                pothole.longitude
                            )

                            self.notification_queue.put(pothole)

                        except Exception as e:
                            logger.error("Database/write error: %s", e)
                            self.db.save_offline_log([pothole])

                    if config.SAVE_VIDEO and video_writer:
                        video_writer.write(annotated_frame)

                    if not config.HEADLESS:
                        cv2.imshow("Pothole Detection", annotated_frame)

                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            logger.info("Quit requested from GUI")
                            break

        except Exception as e:
            logger.error("Processing error: %s", e)

        finally:
            if cap:
                cap.release()

            if video_writer:
                video_writer.release()

            if not config.HEADLESS:
                cv2.destroyAllWindows()

            if isinstance(self.gps, RealGPS):
                self.gps.close()

            logger.info("Video processing stopped")

    def notification_worker(self):
        """
        Read potholes from notification_queue and send Telegram notifications.

        Runs in a background thread so Telegram sending does not block video
        processing.
        """
        import asyncio

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            while self.running:
                try:
                    pothole = self.notification_queue.get(timeout=1)
                    loop.run_until_complete(
                        self.bot.notify_new_pothole(pothole)
                    )
                    self.notification_queue.task_done()

                except Empty:
                    continue

                except Exception as e:
                    logger.error("Notification worker error: %s", e)

        finally:
            loop.close()
            logger.info("Notification worker stopped")

    def sync_offline_data(self):
        """
        Periodically sync offline JSON logs into SQLite.

        This is not a remote database sync. It only retries local JSON logs
        created when direct DB writing failed.
        """
        while self.running:
            try:
                self.db.sync_offline_logs()
            except Exception as e:
                logger.error("Offline sync error: %s", e)

            # Sleep in smaller chunks so shutdown is more responsive.
            for _ in range(60):
                if not self.running:
                    break
                time.sleep(1)

        logger.info("Offline sync worker stopped")

    def run(self):
        """
        Start the system.

        BOT_ONLY mode:
            - only Telegram bot + health server run
            - no detector
            - no GPS
            - no video processing
            - no Prometheus metrics

        Full mode:
            - video thread
            - offline sync thread
            - notification thread
            - Telegram bot in main thread
            - Prometheus metrics server
        """
        if config.BOT_ONLY:
            try:
                logger.info("Starting Telegram bot in BOT_ONLY mode")
                self.bot.run()
            except KeyboardInterrupt:
                logger.info("Shutdown requested")
            finally:
                self.running = False
            return

        video_thread = threading.Thread(
            target=self.process_video,
            name="video-thread"
        )

        sync_thread = threading.Thread(
            target=self.sync_offline_data,
            name="offline-sync-thread",
            daemon=True
        )

        notification_thread = threading.Thread(
            target=self.notification_worker,
            name="notification-thread",
            daemon=True
        )

        video_thread.start()
        sync_thread.start()
        notification_thread.start()

        try:
            logger.info("Starting Telegram bot")
            self.bot.run()

        except KeyboardInterrupt:
            logger.info("Shutdown requested")

        finally:
            self.running = False

            logger.info("Waiting for video thread to stop")
            video_thread.join(timeout=10)

            logger.info("System stopped")


def main():
    system = PotholeDetectionSystem()
    system.run()


if __name__ == "__main__":
    main()