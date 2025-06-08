import serial
import random
import time
from datetime import datetime


def generate_random_gps_data(base_lat, base_lon, radius_km):
    """
    Generates random GPS coordinates within a radius of a base location
    """
    # Convert radius from km to degrees (approximate)
    radius_deg = radius_km / 111.32

    # Generate random offset
    u = random.random()
    v = random.random()
    w = radius_deg * u
    t = 2 * 3.141592653589793 * v
    x = w * (1 if random.random() > 0.5 else -1)
    y = w * (1 if random.random() > 0.5 else -1)

    new_lat = base_lat + x
    new_lon = base_lon + y

    # Format to 6 decimal places
    return round(new_lat, 6), round(new_lon, 6)


def simulate_gps_receiver(port='COM10', baudrate=9600):
    # Base coordinates (center of your test area)
    base_latitude = 44.7866  # Example: Belgrade coordinates
    base_longitude = 20.4489
    radius_km = 5  # 5km radius around base location

    try:
        with serial.Serial(port, baudrate, timeout=1) as ser:
            print(f"Simulating GPS data on {port}... Press Ctrl+C to stop.")

            while True:
                # Generate random GPS data
                lat, lon = generate_random_gps_data(base_latitude, base_longitude, radius_km)

                # Simulate some additional GPS data fields
                speed = round(random.uniform(0, 60), 2)  # 0-60 km/h
                altitude = round(random.uniform(100, 200), 1)
                satellites = random.randint(5, 12)
                timestamp = datetime.utcnow().strftime('%H%M%S')

                # Format the NMEA-like message (simplified)
                gps_message = f"{lat},{lon},{speed},{altitude},{satellites},{timestamp}\n"

                # Send to serial port
                ser.write(gps_message.encode('utf-8'))
                print(f"Sent: {gps_message.strip()}")

                # Wait before sending next reading
                time.sleep(1)

    except serial.SerialException as e:
        print(f"Error opening serial port: {e}")
    except KeyboardInterrupt:
        print("\nGPS simulation stopped.")


if __name__ == "__main__":
    simulate_gps_receiver()