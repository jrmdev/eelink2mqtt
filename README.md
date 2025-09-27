# eelink2mqtt - Eelink V2.0 GPS Tracker Server

A Python server implementation for the Eelink V2.0 protocol that receives GPS tracker data and publishes it to MQTT for Home Assistant integration.

## Features

- 🛰️ **GPS Location Tracking** - Real-time latitude, longitude, altitude, speed, and course
- 🔋 **Device Monitoring** - Battery voltage, charging status, and device activity
- 🌡️ **Environmental Sensors** - Temperature, humidity, illuminance, and CO2 levels
- 📱 **Device Status** - GPS fix status, motion detection, and I/O pin states
- 🏠 **Home Assistant Integration** - MQTT autodiscovery and dashboard cards
- 📊 **Comprehensive Telemetry** - Mileage tracking, step counting, and cellular info

## Supported Devices

This server works with GPS trackers that implement the Eelink V2.0 protocol, including:
- Various personal GPS trackers
- Vehicle tracking devices
- Asset tracking devices

## Installation

### Requirements

```bash
pip install paho-mqtt
```

### Configuration

1. Clone this repository:
```bash
git clone https://github.com/jrmdev/eelink2mqtt
cd eelink2mqtt
```

2. Edit the MQTT configuration in `eelink2mqtt.py`:
```python
MQTT_BROKER = "127.0.0.1"  # Your MQTT broker IP
MQTT_USER = "mosquitto"       # Your MQTT username
MQTT_PASS = "mosquitto"       # Your MQTT password
```

3. Run the server:
```bash
python eelink2mqtt.py
```

The server will listen on `0.0.0.0:5064` by default.

## Home Assistant Integration

Add the following configuration to your `configuration.yaml` file. Replace `<DEVICE_IMEI>` with your tracker's IMEI number:

### MQTT Sensors

```yaml
mqtt:
  sensor:
    # Last Fix
    - name: "Tracker Last GPS Fix"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.timestamp }}"
      icon: mdi:clock
    # Battery
    - name: "Tracker Battery"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.battery }}"
      unit_of_measurement: "V"
      device_class: voltage
      icon: mdi:battery

    # Temperature
    - name: "Tracker Temperature"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.temperature }}"
      unit_of_measurement: "°C"
      device_class: temperature

    # Humidity
    - name: "Tracker Humidity"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.humidity }}"
      unit_of_measurement: "%"
      device_class: humidity

    # Speed
    - name: "Tracker Speed"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.speed }}"
      unit_of_measurement: "km/h"
      icon: mdi:speedometer

    # Altitude
    - name: "Tracker Altitude"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.altitude }}"
      unit_of_measurement: "m"
      icon: mdi:elevation-rise

    # Mileage
    - name: "Tracker Mileage"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.mileage }}"
      unit_of_measurement: "km"
      icon: mdi:counter
    # Course
    - name: "Tracker Course"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.course }}"
      unit_of_measurement: "deg"
      icon: mdi:sign-direction
    # Steps
    - name: "Tracker Steps"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.steps }}"
      icon: mdi:walk

    # Satellites
    - name: "Tracker Satellites"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.satellites }}"
      icon: mdi:satellite-variant

    # CO2
    - name: "Tracker CO2"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.co2 }}"
      unit_of_measurement: "ppm"
      device_class: carbon_dioxide

    # Illuminance
    - name: "Tracker Illuminance"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ value_json.illuminance }}"
      unit_of_measurement: "lx"
      device_class: illuminance
  device_tracker:
    - name: "GPS Tracker"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      json_attributes_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "home"
      payload_home: "home"
      payload_not_home: "not_home"
      source_type: gps
  binary_sensor:
    # GPS Fix Status
    - name: "Tracker GPS Fixed"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ 'ON' if value_json.status | int | bitwise_and(1) else 'OFF' }}"
      device_class: connectivity

    # Charging Status
    - name: "Tracker Charging"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ 'ON' if value_json.status | int | bitwise_and(256) else 'OFF' }}"
      device_class: battery_charging

    # Motion Status
    - name: "Tracker Active"
      state_topic: "eelink/<DEVICE_IMEI>/state"
      value_template: "{{ 'ON' if value_json.status | int | bitwise_and(512) else 'OFF' }}"
      device_class: motion
```

### Dashboard Card

Add this Lovelace card to your Home Assistant dashboard:

```yaml
type: vertical-stack
cards:
  - type: horizontal-stack
    cards:
      - type: gauge
        entity: sensor.tracker_battery
        name: Battery
        needle: true
        min: 3
        max: 4.2
        severity:
          green: 3.7
          yellow: 3.5
          red: 3.3
      - type: sensor
        entity: sensor.tracker_speed
        name: Speed
        icon: mdi:speedometer
        graph: line
      - type: sensor
        entity: sensor.tracker_satellites
        name: Satellites
        icon: mdi:satellite-variant
  - type: entities
    title: Tracker Status
    show_header_toggle: false
    entities:
      - entity: binary_sensor.tracker_gps_fixed
        name: GPS Lock
      - entity: sensor.tracker_last_gps_fix
        name: Last Fix
      - entity: binary_sensor.tracker_charging
        name: Charging
      - entity: binary_sensor.tracker_active
        name: Motion
      - entity: sensor.tracker_mileage
        name: Mileage
      - entity: sensor.tracker_course
        name: Bearing
        icon: mdi:compass
  - type: glance
    title: Environment
    columns: 4
    entities:
      - entity: sensor.tracker_temperature
        name: Temp
      - entity: sensor.tracker_humidity
        name: Humidity
      - entity: sensor.tracker_illuminance
        name: Light
      - entity: sensor.tracker_co2
        name: CO2
```

It may look like the following:
<img width="1586" height="729" alt="image" src="https://github.com/user-attachments/assets/4ec9476e-869d-4ccf-95dd-813bcf8d8ec4" />


## Protocol Details

The server handles the following Eelink V2.0 protocol commands:

- **0x01** - Login packet (device authentication)
- **0x03** - Heartbeat packet (keepalive and status)
- **0x12** - GPS location data packet (position and telemetry)

Each packet includes:
- GPS coordinates (latitude/longitude)
- Device status bits (16-bit status word)
- Environmental sensors
- Battery and power information
- Cellular network information

## MQTT Data Format

The server publishes JSON data to `eelink/{IMEI}/state` with the following structure:

```json
{
  "timestamp": "2024-01-01 12:00:00",
  "latitude": 40.7128,
  "longitude": -74.0060,
  "altitude": 10,
  "speed": 25,
  "course": 180,
  "satellites": 8,
  "battery": 3.8,
  "temperature": 22.5,
  "humidity": 65,
  "illuminance": 500,
  "co2": 400,
  "mileage": 1234.5,
  "steps": 5000,
  "status": 1025,
  "cell_info": {
    "mcc": 310,
    "mnc": 260,
    "lac": 1234,
    "cid": 5678,
    "rxlev": 25
  }
}
```

## Device Configuration

Configure your Eelink GPS tracker with:
- **Server IP**: Your server's IP address
- **Server Port**: 5064 (default)
- **Protocol**: TCP
- **Reporting Interval**: As desired (recommended: 30-300 seconds)

To configure the tracker to use your server, send the following SMS to it:

`Server,"tcp://<your_server>:5064"#`

## Troubleshooting

### No Data Received
- Check that the tracker is configured with the correct server IP and port
- Verify network connectivity between tracker and server
- Check firewall settings on port 5064

### MQTT Not Working
- Verify MQTT broker credentials and connectivity
- Check MQTT broker logs for authentication errors
- Ensure topics are correctly configured in Home Assistant

### Invalid GPS Coordinates
- Ensure GPS has a fix (check satellites count > 4)
- Verify GPS antenna is not obstructed
- Check GPS fix status in the device status bits

## License

This project is open source and available under the [MIT License](LICENSE).

## Contributing

Contributions are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.
