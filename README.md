# 🚗 Pothole Detection System

A real-time computer vision system that automatically detects and maps road potholes from a moving vehicle. A mounted camera feeds into a YOLOv8 + MiDaS pipeline that classifies severity, records GPS location, and pushes live alerts to a Telegram bot.

![Demonstration gif](https://github.com/user-attachments/assets/2c675218-1e69-4023-a27a-ad3767bbf9e1)

---

## 📱 Try the Live Bot

**No installation needed** — the bot runs 24/7 on [Fly.io](https://fly.io) with a pre-seeded demo database.

👉 **[Open Bot on Telegram](https://t.me/potholedetectionBOT)**

---

## Features

- Real-time pothole detection (YOLOv8)
- MiDaS depth estimation per pothole
- Severity classification: Low / Medium / High / Critical
- GPS location tagging (real hardware or simulated)
- Duplicate detection prevention via Haversine radius check
- Detection images saved per pothole
- Offline mode with automatic database resync
- Telegram bot with interactive inline menus and role-based access
- Admin real-time alerts for HIGH and CRITICAL detections
- Prometheus metrics + Grafana dashboard
- Dockerized with CI/CD via GitHub Actions → Docker Hub
- `BOT_ONLY` mode for lightweight cloud deployment 
---

## 📱 Telegram Bot Commands

| Command | Description |
|---|---|
| `/start` | Main menu with all options |
| `/locations` | Browse potholes by region |
| `/severity` | Filter by severity level |
| `/map` | View all locations on Google Maps |
| `/latest` | Last 5 detected potholes |
| `/stats` | Statistics by severity and region |
| `/status` | System status and user count |
| `/export` | Download all data as CSV |
| `/help` | Help center |

![Telegram bot screenshot](imgs/photo_2025-06-12_00-26-59.jpg)

---

## System Architecture

![Diagram](imgs/Dijagram.png)

Three parallel threads run simultaneously:

- **Video thread** — reads frames, runs YOLO + MiDaS, writes to database
- **Sync thread** — periodically syncs offline logs to the database
- **Notification thread** — sends Telegram alerts to admin on HIGH/CRITICAL detections

In `BOT_ONLY` mode, only the bot thread runs — no CV models are loaded, making it suitable for low-resource cloud deployments.

---

## APM & Monitoring

![Grafana dashboard](imgs/grafana.png)

Prometheus metrics exposed on port `8000`:

| Metric | Description |
|---|---|
| `pothole_detections_total` | Total potholes detected |
| `pothole_severity_low_total` | Low severity count |
| `pothole_severity_medium_total` | Medium severity count |
| `pothole_severity_high_total` | High severity count |
| `pothole_severity_critical_total` | Critical severity count |
| `frame_processing_duration_seconds` | Frame processing time |

- Prometheus UI: `http://localhost:9090`
- Grafana Dashboard: `http://localhost:3000`

---

## Built With

- Python 3.13
- OpenCV
- PyTorch + YOLOv8 (Ultralytics)
- MiDaS
- SQLite
- Docker
- Prometheus + Grafana
- python-telegram-bot
- Fly.io (cloud deployment)

---

## CI/CD

GitHub Actions builds and pushes the Docker image to Docker Hub on every commit to `main` (except documentation-only changes).

Docker Hub: [jankokl/detekcija-rupa](https://hub.docker.com/repository/docker/jankokl/detekcija-rupa)

---

## For Developers

<details>
<summary>Click to expand setup instructions</summary>

### Run Locally

```bash
git clone https://github.com/jankokl/DetekcijaRupa.git
cd DetekcijaRupa
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your values:

```bash
cp .env.example .env
```

Minimum required variables:

```env
BOT_TOKEN=           # from @BotFather on Telegram
ADMIN_CHAT_ID=       # your chat ID from @userinfobot

USE_LIVE_CAMERA=False
VIDEO_FILE=p.mp4
USE_SIMULATION=True
YOLO_MODEL_PATH=best.pt
BOT_ONLY=False
HEADLESS=False
```

Run:

```bash
cd app
python main.py
```

### Run with Docker

```bash
docker run -p 8000:8000 --env-file=.env jankokl/detekcija-rupa
```

### Run Full Stack (with Prometheus + Grafana)

```bash
docker compose up -d
```

### Deploy to Fly.io (BOT_ONLY mode)

```bash
fly launch --region fra
fly secrets set BOT_TOKEN=... ADMIN_CHAT_ID=... BOT_ONLY=True HEADLESS=True DB_PATH=app/data/pothole.db
fly deploy
```

</details>

---

## Author

**Janko Klikovac**
GitHub: [@JankoKl](https://github.com/JankoKl)
