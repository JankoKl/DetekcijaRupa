#  Pothole Detection System with Telegram & APM Integration

## Overview

The Pothole Detection System is a real-time Python-based application that uses computer vision and GPS data to automatically detect potholes in road surfaces. It uses YOLOv8 for object detection, MiDaS for depth estimation, and integrates with a Telegram bot for real-time notifications. It includes full Application Performance Monitoring (APM) using Prometheus and Grafana, as well as Dockerized deployment via Docker Hub.

![Demonstration gif](https://github.com/user-attachments/assets/2c675218-1e69-4023-a27a-ad3767bbf9e1)

---

## Features

- Real-time pothole detection (YOLOv8)
- MiDaS-based depth estimation
- Live input from video camera or from video file
- SQLite database for local storage
- Stores images of detected potholes
- Telegram bot for real-time updates and interaction
- Duplicate detection prevention
- Offline mode with automatic resync
- GPS integration (real or simulated)
- Dockerized app with Docker Hub support
- Exposes Prometheus metrics for monitoring
- Grafana dashboard to visualize performance metrics

---

##  System Architecture

![Diagram.](imgs/Dijagram.png "Diagram.")

---

##  Configuration

Configuration is handled via a `.env` file in the project root. Example:

```env
USE_SIMULATION=True
GPS_PORT=COM10
GPS_BAUDRATE=9600
USE_LIVE_CAMERA=False  
CAMERA_INDEX=0
VIDEO_FILE=p.mp4
VIDEO_WIDTH=1020
VIDEO_HEIGHT=500
FRAME_SKIP=3
SAVE_VIDEO=False
VIDEO_OUTPUT_PATH=output/demo_output.avi
VIDEO_FPS=20
DUPLICATE_RADIUS_METERS=5.0
TELEGRAM_TOKEN=your_bot_token
TELEGRAM_CHAT_ID=your_chat_id
```

Make sure to create your own `.env` file or duplicate `.env.example` and update values as needed.

---

##  How to Run

###  Run Locally 

Install dependencies:

```bash
pip install -r requirements.txt
```

Start the app:

```bash
python app/main.py
```

Metrics will be available at: `http://localhost:8000/metrics`

> **Note:** You must have a `.env` file configured correctly before running.

---

### Run from Docker Hub (No Setup Required)

> Requires [Docker](https://www.docker.com/products/docker-desktop)

```bash
docker run -p 8000:8000 --env-file=.env jankokl/detekcija-rupa
```

This will pull and run the latest container image from Docker Hub.

Docker Hub link: [jankokl/detekcija-rupa](https://hub.docker.com/repository/docker/jankokl/detekcija-rupa)

---

## APM & Monitoring

The application exposes Prometheus-compatible metrics on `/metrics` (default port: `8000`).

To monitor metrics using Prometheus + Grafana:

### Step 1: Start Monitoring Stack

```bash
docker-compose up
```

This starts:
- Prometheus (on port 9090)
- Grafana (on port 3000)

### Step 2: View Metrics

- Prometheus UI: [http://localhost:9090](http://localhost:9090)
- Grafana Dashboard: [http://localhost:3000](http://localhost:3000)

Metrics include:
- `pothole_detections_total`
- `pothole_severity_<level>_total`
- `frame_processing_duration_seconds`

Grafana is preconfigured to scrape these via Prometheus.

> ![Grafana dashboard](imgs/grafana.png)

---

##  Telegram Bot

Interact with the system via Telegram. Available commands:

- `/start` – Help
- `/locations` – Browse pothole locations
- `/map` – View all on Google Maps
- `/stats` – System statistics
- `/help` – List of commands

![Telegram bot screenshot.](imgs/photo_2025-06-12_00-26-59.jpg)

---

##  CI/CD Pipeline

GitHub Actions build the Docker image and push it to Docker Hub on each commit to `main`.

---

##  Built With

- Python 3.11
- OpenCV
- PyTorch + YOLOv8
- MiDaS
- SQLite
- Docker
- Prometheus
- Grafana
- Telegram Bot API

---

##  Author

**Janko Klikovac**  
GitHub: [@JankoKl](https://github.com/JankoKl)

---

## 

This project uses open-source components and is intended for educational and research purposes.