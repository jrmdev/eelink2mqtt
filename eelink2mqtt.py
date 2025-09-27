#!/usr/bin/env -S python3
import socket
import struct
import threading
import time
import json
import argparse
from datetime import datetime
from typing import Dict, Optional, Tuple
import paho.mqtt.client as mqtt


class EelinkV2Server:
    """Server for handling Eelink V2.0 protocol GPS tracker connections."""
    
    # Protocol constants
    HEADER_MARK1 = 0x67
    HEADER_MARK2 = 0x67
    CMD_LOGIN = 0x01
    CMD_HEARTBEAT = 0x03
    CMD_LOCATION = 0x12
    
    # MQTT configuration
    MQTT_BROKER = "127.0.0.1"
    MQTT_PORT = 1883
    MQTT_USER = "mosquitto"
    MQTT_PASS = "mosquitto"
    MQTT_TOPIC_PREFIX = "eelink"

    def __init__(self, host: str = '0.0.0.0', port: int = 5064, verbose: bool=False):
        self.host = host
        self.port = port
        self.verbose = verbose
        self.server_socket = None
        self.running = False
        self.mqtt_client = None
        self._setup_mqtt()
    
    def _setup_mqtt(self):
        """Initialize MQTT client connection."""
        self.mqtt_client = mqtt.Client()
        self.mqtt_client.username_pw_set(self.MQTT_USER, self.MQTT_PASS)
        
        try:
            self.mqtt_client.connect(self.MQTT_BROKER, self.MQTT_PORT, 60)
            self.mqtt_client.loop_start()
            self._log("MQTT client connected successfully")
        except Exception as e:
            self._log(f"MQTT connection failed: {e}")
    
    def _publish_mqtt(self, device_id: str, data: Dict):
        """Publish data to MQTT broker for Home Assistant."""
        if not self.mqtt_client:
            return
        
        try:
            # Publish full state data
            topic = f"{self.MQTT_TOPIC_PREFIX}/{device_id}/state"
            payload = json.dumps(data)
            self.mqtt_client.publish(topic, payload, retain=True)
            self._log(f"Published to MQTT: {topic}")
        except Exception as e:
            self._log(f"MQTT publish error: {e}")
    
    def _log(self, message: str):
        """Print timestamped log message."""
        if self.verbose:
            print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {message}")
    
    def start_server(self):
        """Start the server to listen for connections."""
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind((self.host, self.port))
        self.server_socket.listen(5)
        self.running = True
        
        print(f"Server listening on {self.host}:{self.port}")
        
        try:
            while self.running:
                client_socket, client_address = self.server_socket.accept()
                self._log(f"New connection from: {client_address}")
                
                thread = threading.Thread(
                    target=self._handle_client,
                    args=(client_socket, client_address),
                    daemon=True
                )
                thread.start()
        except Exception as e:
            self._log(f"Server error: {e}")
        finally:
            self.stop_server()
    
    def _handle_client(self, client_socket: socket.socket, client_address: Tuple):
        """Handle all communication with a connected client."""
        device_imei = None
        
        try:
            while self.running:
                data = client_socket.recv(1024)
                if not data:
                    self._log(f"Connection closed by {client_address}")
                    break
                
                self._log(f"Received from {client_address}: {data.hex()}")
                device_imei = self._process_packet(client_socket, data, device_imei)
                
        except Exception as e:
            self._log(f"Error handling client {client_address}: {e}")
        finally:
            client_socket.close()
            self._log(f"Disconnected from {client_address}")
    
    def _process_packet(self, client_socket: socket.socket, packet: bytes, device_imei: Optional[str]) -> Optional[str]:
        """Process packet and return device IMEI if available."""
        if len(packet) < 9 or packet[0] != self.HEADER_MARK1 or packet[1] != self.HEADER_MARK2:
            self._log("Invalid packet header or too short. Discarding.")
            return device_imei
        
        cmd = packet[2]
        
        try:
            if cmd == self.CMD_LOGIN:
                return self._handle_login(client_socket, packet)
            elif cmd == self.CMD_HEARTBEAT:
                self._handle_heartbeat(client_socket, packet, device_imei)
            elif cmd == self.CMD_LOCATION:
                self._handle_location(client_socket, packet, device_imei)
            else:
                self._log(f"Unsupported command 0x{cmd:02x}. Sending generic ACK.")
                self._send_ack(client_socket, packet)
        except Exception as e:
            self._log(f"Error processing packet: {e}")
        
        return device_imei
    
    def _handle_login(self, client_socket: socket.socket, packet: bytes) -> str:
        """Handle device login packet."""
        self._log("Handling LOGIN packet")
        
        if len(packet) < 20:
            self._log("Login packet too short")
            return None
        
        imei = hex(int.from_bytes(packet[7:15], 'big'))[2:]
        seq = int.from_bytes(packet[5:7], 'big')
        
        self._log(f"Device IMEI: {imei}, Seq: {seq}")
        
        response = struct.pack(
            '>BBBHHIHB',
            self.HEADER_MARK1, self.HEADER_MARK2,
            self.CMD_LOGIN,
            9,  # size
            seq,
            int(time.time()),
            1,  # version
            0   # ps_action
        )
        
        client_socket.send(response)
        self._log(f"LOGIN ACK sent: {response.hex()}")
        
        return str(imei)
    
    def _handle_heartbeat(self, client_socket: socket.socket, packet: bytes, device_imei: Optional[str]):
        """Handle heartbeat packet."""
        self._log("Handling HEARTBEAT packet")
        
        seq = int.from_bytes(packet[5:7], 'big')
        status = int.from_bytes(packet[7:9], 'big')
        
        self._log(f"Seq: {seq}, Status: 0x{status:04X}")
        self._parse_status(status)
        
        if device_imei:
            self._publish_mqtt(device_imei, {
                "status": status,
                "timestamp": datetime.now().isoformat()
            })
        
        response = struct.pack('>BBBHH', self.HEADER_MARK1, self.HEADER_MARK2, self.CMD_HEARTBEAT, 2, seq)
        client_socket.send(response)
        self._log(f"HEARTBEAT ACK sent: {response.hex()}")
    
    def _handle_location(self, client_socket: socket.socket, packet: bytes, device_imei: Optional[str]):
        """Handle GPS location data packet."""
        self._log("Handling LOCATION DATA packet")
        
        chunks = [packet[i:i+74] for i in range(0, len(packet), 74)]
        
        for chunk in chunks:
            seq = int.from_bytes(chunk[5:7], 'big')
            data_section = chunk[7:]
            
            position, offset = self._parse_position(data_section)
            
            # Parse additional data
            status = int.from_bytes(data_section[offset:offset+2], 'big')
            battery = int.from_bytes(data_section[offset+2:offset+4], 'big') / 1000.0
            ain0 = int.from_bytes(data_section[offset+4:offset+6], 'big')
            ain1 = int.from_bytes(data_section[offset+6:offset+8], 'big')
            mileage = int.from_bytes(data_section[offset+8:offset+12], 'big') / 1000.0
            gsm_cntr = int.from_bytes(data_section[offset+12:offset+14], 'big')
            gps_cntr = int.from_bytes(data_section[offset+14:offset+16], 'big')
            pdm_step = int.from_bytes(data_section[offset+16:offset+18], 'big')
            pdm_time = int.from_bytes(data_section[offset+18:offset+20], 'big')
            temperature = int.from_bytes(data_section[offset+20:offset+22], 'big') / 256.0
            humidity = int.from_bytes(data_section[offset+22:offset+24], 'big')
            illuminance = int.from_bytes(data_section[offset+24:offset+28], 'big')
            co2 = int.from_bytes(data_section[offset+28:offset+32], 'big')
            
            # Log data
            self._log(f"Seq: {seq}")
            self._log(f"Date: {position.get('date')}")
            self._log(f"Location: {position.get('latitude')}, {position.get('longitude')}")
            self._log(f"Altitude: {position.get('altitude_m')} m, Speed: {position.get('speed_kmh')} km/h")
            self._log(f"Battery: {battery} V, Temperature: {temperature} °C")
            self._parse_status(status)
            
            # Publish to MQTT
            if device_imei:
                mqtt_data = {
                    "timestamp": position.get('date'),
                    "latitude": position.get('latitude'),
                    "longitude": position.get('longitude'),
                    "altitude": position.get('altitude_m'),
                    "speed": position.get('speed_kmh'),
                    "course": position.get('course_deg'),
                    "satellites": position.get('satellites'),
                    "battery": battery,
                    "temperature": temperature,
                    "humidity": humidity,
                    "illuminance": illuminance,
                    "co2": co2,
                    "mileage": mileage,
                    "steps": pdm_step,
                    "status": status,
                    "ain0": ain0,
                    "ain1": ain1,
                    "cell_info": position.get('bsid0')
                }
                self._publish_mqtt(device_imei, mqtt_data)
            
            # Send ACK
            response = struct.pack('>BBBHH', self.HEADER_MARK1, self.HEADER_MARK2, self.CMD_LOCATION, 2, seq)
            client_socket.send(response)
            self._log(f"LOCATION ACK sent: {response.hex()}")
            self._log("-" * 50)
    
    def _parse_position(self, data: bytes) -> Tuple[Dict, int]:
        """Parse POSITION structure from bytes."""
        offset = 0
        position = {}
        
        # Time (4 bytes)
        timestamp = struct.unpack_from(">I", data, offset)[0]
        offset += 4
        position["time"] = timestamp
        position["date"] = datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S")
        
        # Mask (1 byte)
        mask = struct.unpack_from(">B", data, offset)[0]
        offset += 1
        
        # GPS data (bit 0)
        if mask & 0x01:
            lat, lon, alt, speed, course, sats = struct.unpack_from(">iiHHHB", data, offset)
            offset += 15
            position["latitude"] = lat / (162000000 / 90.0)
            position["longitude"] = lon / (324000000 / 180.0)
            position["altitude_m"] = struct.unpack(">h", struct.pack(">H", alt))[0]
            position["speed_kmh"] = speed
            position["course_deg"] = course
            position["satellites"] = sats
        
        # BSID0 (bit 1)
        if mask & 0x02:
            mcc, mnc, lac, cid, rxlev = struct.unpack_from(">HHHIB", data, offset)
            offset += 11
            position["bsid0"] = {"mcc": mcc, "mnc": mnc, "lac": lac, "cid": cid, "rxlev": rxlev}
        
        # BSID1 (bit 2)
        if mask & 0x04:
            lac, ci, rxlev = struct.unpack_from(">HIB", data, offset)
            offset += 7
            position["bsid1"] = {"lac": lac, "ci": ci, "rxlev": rxlev}
        
        # BSID2 (bit 3)
        if mask & 0x08:
            lac, ci, rxlev = struct.unpack_from(">HIB", data, offset)
            offset += 7
            position["bsid2"] = {"lac": lac, "ci": ci, "rxlev": rxlev}
        
        # BSS0 (bit 4)
        if mask & 0x10:
            bssid = data[offset:offset+6]
            rssi = struct.unpack_from(">b", data, offset+6)[0]
            offset += 7
            position["bss0"] = {"bssid": ":".join(f"{b:02x}" for b in bssid), "rssi": rssi}
        
        # BSS1 (bit 5)
        if mask & 0x20:
            bssid = data[offset:offset+6]
            rssi = struct.unpack_from(">b", data, offset+6)[0]
            offset += 7
            position["bss1"] = {"bssid": ":".join(f"{b:02x}" for b in bssid), "rssi": rssi}
        
        # BSS2 (bit 6)
        if mask & 0x40:
            bssid = data[offset:offset+6]
            rssi = struct.unpack_from(">b", data, offset+6)[0]
            offset += 7
            position["bss2"] = {"bssid": ":".join(f"{b:02x}" for b in bssid), "rssi": rssi}
        
        return position, offset
    
    def _parse_status(self, status: int):
        """Parse and log device status bits."""
        status &= 0xFFFF
        
        status_bits = {
            0: ("GPS fixed", "GPS NOT fixed"),
            1: ("Car device", "NOT car device"),
            2: ("Engine fired", "Engine NOT fired"),
            3: ("Accelerometer supported", "No accelerometer"),
            4: ("Motion-warning active", "Motion-warning inactive"),
            5: ("Relay control supported", "No relay control"),
            6: ("Relay triggered", "Relay NOT triggered"),
            7: ("External charging supported", "No external charging"),
            8: ("Charging", "NOT charging"),
            9: ("Device active", "Device stationary"),
            10: ("GPS module running", "GPS module NOT running"),
            11: ("OBD module running", "OBD module NOT running"),
            12: ("DIN0 HIGH", "DIN0 LOW"),
            13: ("DIN1 HIGH", "DIN1 LOW"),
            14: ("DIN2 HIGH", "DIN2 LOW"),
            15: ("DIN3 HIGH", "DIN3 LOW"),
        }
        
        self._log(f"Device status: 0x{status:04X}")
        for bit, (high_msg, low_msg) in status_bits.items():
            msg = high_msg if status & (1 << bit) else low_msg
            self._log(f"  Bit {bit}: {msg}")
    
    def _send_ack(self, client_socket: socket.socket, packet: bytes):
        """Send generic acknowledgment."""
        seq = int.from_bytes(packet[5:7], 'big')
        response = struct.pack('>BBBHH', self.HEADER_MARK1, self.HEADER_MARK2, packet[2], 2, seq)
        client_socket.send(response)
        self._log(f"Generic ACK sent: {response.hex()}")
    
    def stop_server(self):
        """Stop the server gracefully."""
        self.running = False
        
        if self.mqtt_client:
            self.mqtt_client.loop_stop()
            self.mqtt_client.disconnect()
        
        if self.server_socket:
            self.server_socket.close()
        
        self._log("Server stopped")


def main():
    parser = argparse.ArgumentParser(description="EelinkV2Server runner")
    parser.add_argument('-v', '--verbose', action='store_true', help='Print all debug information to the console')
    parser.add_argument('-H', '--host', action='store', help='Server host address', default='0.0.0.0')
    parser.add_argument('-p', '--port', action='store', help='Server port number', default=5064)
    args = parser.parse_args()

    server = EelinkV2Server(port=args.ports, verbose=args.verbose)
    try:
        server.start_server()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.stop_server()


if __name__ == "__main__":
    main()
