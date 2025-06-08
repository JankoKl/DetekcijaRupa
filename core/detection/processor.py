import cv2
import logging
import time

from core.capture.frame_capture import FrameCapture
from core.services.pothole_service import PotholeService
from core.detection.severity import SeverityLevel

logger = logging.getLogger(__name__)

class VideoProcessor:
    def __init__(self, source: str, service: PotholeService):
        try:
            self.capture = FrameCapture(source)
            # Test frame read
            ret, _ = self.capture.get_frame()
            if not ret:
                raise IOError(f"Could not read from video source {source}")
        except Exception as e:
            logger.error(f"Video source initialization failed: {str(e)}")
            raise

        self.service = service
        self.frame_count = 0
        self.process_every = 3
        logger.info(f"Initialized video processor for source: {source}")

    def process_stream(self):
        try:
            while True:
                ret, frame = self.capture.get_frame()
                if not ret:
                    logger.info("End of video stream")
                    break

                self.frame_count += 1
                if self.frame_count % self.process_every != 0:
                    continue

                frame = cv2.resize(frame, (1020, 500))
                detections = self.service.process_frame(frame)

                if detections:
                    self.draw_detections(frame, detections)

                cv2.imshow('Pothole Detection', frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break

        except KeyboardInterrupt:
            logger.info("Processing interrupted by user")
        except Exception as e:
            logger.error(f"Processing error: {str(e)}", exc_info=True)
        finally:
            self.capture.release()
            cv2.destroyAllWindows()
            logger.info("Video processing stopped")

    @staticmethod
    def draw_detections(frame, detections):
        color_map = {
            SeverityLevel.LOW: (0, 255, 0),
            SeverityLevel.MEDIUM: (0, 165, 255),
            SeverityLevel.HIGH: (0, 0, 255)
        }
        for det in detections:
            color = color_map[det['severity']]
            cv2.rectangle(frame,
                          (int(det['bbox'][0]), int(det['bbox'][1])),
                          (int(det['bbox'][2]), int(det['bbox'][3])),
                          color, 2)
            cv2.putText(frame,
                        f"{det['severity'].value} ({det['score']:.2f})",
                        (int(det['bbox'][0]), int(det['bbox'][1]) - 10),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, color, 2)