import serial
import time
import random

def generate_nmea_sentence():
    # Random lat/lon values
    lat_deg = random.randint(0, 89)
    lat_min = random.uniform(0, 59.9999)
    lat = f"{lat_deg:02d}{lat_min:07.4f}"
    lat_dir = random.choice(["N", "S"])

    lon_deg = random.randint(0, 179)
    lon_min = random.uniform(0, 59.9999)
    lon = f"{lon_deg:03d}{lon_min:07.4f}"
    lon_dir = random.choice(["E", "W"])

    # UTC time
    timestamp = time.strftime("%H%M%S")

    # GPGGA NMEA sentence format
    sentence = f"GPGGA,{timestamp}.00,{lat},{lat_dir},{lon},{lon_dir},1,08,0.9,545.4,M,46.9,M,,"
    checksum = 0
    for c in sentence:
        checksum ^= ord(c)
    full_sentence = f"${sentence}*{checksum:02X}\r\n"
    return full_sentence

def send_gps_data(port="COM10", baudrate=4800):
    with serial.Serial(port, baudrate, timeout=1) as ser:
        print(f"Sending GPS data to {port} at {baudrate} baud...")
        while True:
            nmea = generate_nmea_sentence()
            print("Sending:", nmea.strip())
            ser.write(nmea.encode('ascii'))
            time.sleep(1)  # Send every second

if __name__ == "__main__":
    send_gps_data("COM10")
