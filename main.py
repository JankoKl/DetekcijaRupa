import logging
import os
import cv2
import numpy as np
from core.services.pothole_service import PotholeService
from config.config import Config

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    # Load configuration
    config = Config()

    # Initialize pothole service
    pothole_service = PotholeService(config)

    # Load video
    video_path = config.video_path
    if not os.path.exists(video_path):
        logger.error(f"Video file not found: {video_path}")
        return

    # Open video capture
    cap = cv2.VideoCapture(video_path)

    # Check if video capture is opened
    if not cap.isOpened():
        logger.error("Unable to open video capture")
        return

    # Set up video writer
    video_writer = cv2.VideoWriter("output.mp4", cv2.VideoWriter_fourcc(*"mp4v"), 30, (int(cap.get(3)), int(cap.get(4))))

    # Loop through frames
    while True:
        # Read frame
        ret, frame = cap.read()

        # Check if frame is read
        if not ret:
            break

        # Detect potholes
        potholes = pothole_service.detect_potholes(frame)

        # Log detection results
        logger.info(f"Detected {len(potholes)} potholes")

        # Draw potholes on frame
        for pothole in potholes:
            cv2.rectangle(frame, (pothole.x, pothole.y), (pothole.x + pothole.w, pothole.y + pothole.h), (0, 255, 0), 2)

        # Write frame to video writer
        video_writer.write(frame)

    # Release video capture and writer
    cap.release()
    video_writer.release()

if __name__ == "__main__":
    main()
