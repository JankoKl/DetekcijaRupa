#!/bin/sh
set -e

mkdir -p /app/data

python app/seed_database.py

exec python app/main.py