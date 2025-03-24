"""
Device Finder - Backend application for device detection and management.
This application provides API endpoints to scan for WiFi networks, Bluetooth devices, and cameras.
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import subprocess
import platform
import re
import time
import json
import os
import sys

# Configuration
DEBUG = True
PORT = 5000
HOST = '0.0.0.0'

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app)  # Enable CORS for all endpoints

# Try to import optional modules
try:
    import wifi
    WIFI_MODULE_AVAILABLE = True
except ImportError:
    WIFI_MODULE_AVAILABLE = False
    print("Module 'wifi' is not installed. Some features may be unavailable.")

try:
    import asyncio
    from bleak import BleakScanner
    BLUETOOTH_MODULE_AVAILABLE = True
except ImportError:
    BLUETOOTH_MODULE_AVAILABLE = False
    print("Module 'bleak' is not installed. Some features may be unavailable.")

try:
    import cv2
    CAMERA_MODULE_AVAILABLE = True
except ImportError:
    CAMERA_MODULE_AVAILABLE = False
    print("Module 'opencv-python' is not installed. Some features may be unavailable.")


class DeviceScanner:
    """Class for scanning various types of devices."""
    
    def __init__(self):
        self.system = platform.system()
        
    def scan_wifi_networks(self):
        """Skanuje dostępne sieci Wi-Fi."""
        if not WIFI_MODULE_AVAILABLE:
            return {"error": "Moduł 'wifi' nie jest dostępny. Nie można skanować sieci Wi-Fi."}
            
        try:
            print("Skanowanie sieci Wi-Fi...")
            networks = []
            
            if self.system == "Windows":
                # Użyj komendy netsh na Windows
                output = subprocess.check_output(["netsh", "wlan", "show", "networks"], encoding="utf-8", errors="ignore")
                network_names = re.findall(r"SSID \d+ : (.*)", output)
                signal_strength = re.findall(r"Signal\s+: (\d+%)", output)
                security = re.findall(r"Authentication\s+: (.*)", output)
                
                # Pobierz również adresy MAC (BSSID) jeśli są dostępne
                # Spróbuj użyć komendy "netsh wlan show networks mode=bssid"
                try:
                    detailed_output = subprocess.check_output(["netsh", "wlan", "show", "networks", "mode=bssid"], 
                                                            encoding="utf-8", errors="ignore")
                    bssids = re.findall(r"BSSID \d+\s+: (.*)", detailed_output)
                except:
                    bssids = []  # Jeśli nie udało się pobrać adresów MAC
                
                for i in range(len(network_names)):
                    # Przypisz adres MAC jeśli jest dostępny dla tego indeksu
                    mac_address = bssids[i] if i < len(bssids) else f"MAC-{i:02d}:{network_names[i][:6].upper()}"
                    
                    networks.append({
                        "name": network_names[i],
                        "signal": signal_strength[i] if i < len(signal_strength) else "N/A",
                        "security": security[i] if i < len(security) else "N/A",
                        "address": mac_address,  # Dodajemy adres MAC do każdej sieci
                        "type": "📡",  # Ikona sieci Wi-Fi
                        "id": f"wifi_{i}"
                    })
            else:
                # Użyj modułu wifi na Linux/macOS
                for i, cell in enumerate(wifi.Cell.all('wlan0')):
                    networks.append({
                        "name": cell.ssid,
                        "signal": f"{cell.signal}%",
                        "security": cell.encryption_type,
                        "address": cell.address,  # Dla modułu wifi, adres MAC jest już dostępny jako cell.address
                        "type": "📡",  # Ikona sieci Wi-Fi
                        "id": f"wifi_{i}"
                    })
                    
            return {"status": "success", "devices": networks}
            
        except Exception as e:
            return {"error": f"Wystąpił błąd podczas skanowania sieci Wi-Fi: {str(e)}"}
    
    async def _scan_bluetooth_devices_async(self):
        """Asynchronously scan for available Bluetooth devices using bleak."""
        devices = []
        print("Scanning Bluetooth devices...")
        
        try:
            # Check if Bluetooth adapter is enabled
            ble_devices = await BleakScanner.discover()
            
            for i, device in enumerate(ble_devices):
                devices.append({
                    "name": device.name if device.name else "Unknown name",
                    "address": device.address,
                    "type": "🔷",  # Bluetooth icon
                    "id": f"bt_{i}"
                })
        except Exception as e:
            print(f"Error while scanning Bluetooth: {e}")
            
        return devices
    
    def scan_bluetooth_devices(self):
        """Scan for available Bluetooth devices and show paired devices."""
        if not BLUETOOTH_MODULE_AVAILABLE:
            # If bleak module is not available, try to get paired devices at least
            paired_devices = get_paired_bluetooth_devices()
            if paired_devices:
                return {
                    "status": "success", 
                    "devices": paired_devices, 
                    "warning": "Scanning for new devices is unavailable, showing only paired devices."
                }
            else:
                return {"error": "Module 'bleak' is not available. Cannot scan Bluetooth devices."}
                
        try:
            # First get paired devices
            paired_devices = get_paired_bluetooth_devices()
            
            # Call the asynchronous function synchronously
            if hasattr(asyncio, 'run'):  # Python 3.7+
                discovered_devices = asyncio.run(self._scan_bluetooth_devices_async())
            else:
                # For older Python versions
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                discovered_devices = loop.run_until_complete(self._scan_bluetooth_devices_async())
                loop.close()
            
            # Combine results, showing paired devices first
            all_devices = paired_devices + discovered_devices
            
            # Remove duplicates (devices with the same address)
            unique_devices = []
            addresses_seen = set()
            
            for device in all_devices:
                if 'address' in device and device['address'] not in addresses_seen:
                    addresses_seen.add(device['address'])
                    unique_devices.append(device)
                elif 'address' not in device:
                    unique_devices.append(device)
            
            return {"status": "success", "devices": unique_devices}
            
        except Exception as e:
            return {"error": f"An error occurred while scanning Bluetooth devices: {str(e)}"}
    
    def list_available_cameras(self):
        """Wyświetla listę dostępnych kamer."""
        if not CAMERA_MODULE_AVAILABLE:
            return {"error": "Moduł 'opencv-python' nie jest dostępny. Nie można skanować kamer."}
            
        try:
            print("Sprawdzanie dostępnych kamer...")
            
            available_cameras = []
            # Sprawdź pierwsze 5 indeksów (0-4)
            for i in range(5):
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret:
                        # Próba uzyskania informacji o urządzeniu
                        # W przypadku kamer nie ma bezpośrednio adresu MAC, więc generujemy unikalny identyfikator
                        
                        # Pobierz rozdzielczość kamery jako część identyfikatora
                        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
                        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
                        
                        # Stwórz identyfikator podobny do MAC
                        camera_id = f"CAM:{i:02d}:{width:04d}:{height:04d}"
                        
                        available_cameras.append({
                            "name": f"Kamera {i}",
                            "index": i,
                            "address": camera_id,  # Dodajemy identyfikator kamery
                            "type": "📹",  # Ikona kamery
                            "id": f"cam_{i}"
                        })
                    cap.release()
                    
            return {"status": "success", "devices": available_cameras}
            
        except Exception as e:
            return {"error": f"Wystąpił błąd podczas sprawdzania kamer: {str(e)}"}


def get_paired_bluetooth_devices():
    """Get a list of paired Bluetooth devices from the system."""
    system = platform.system()
    paired_devices = []
    
    try:
        if system == "Windows":
            # On Windows, use PowerShell to get paired devices
            powershell_cmd = "Get-PnpDevice -Class Bluetooth | Where-Object { $_.Status -eq 'OK' } | Select-Object FriendlyName, DeviceID"
            result = subprocess.run(["powershell", "-Command", powershell_cmd], 
                                   capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                # Parse the result
                lines = result.stdout.strip().split('\n')
                current_device = {}
                
                for i, line in enumerate(lines):
                    line = line.strip()
                    if not line:
                        continue
                    
                    if line.startswith("FriendlyName") or line.startswith("-"):
                        continue  # Skip headers
                    
                    if "DeviceID" in line:
                        # This is a line with DeviceID
                        match = re.search(r"DeviceID\s*:\s*(.*)", line)
                        if match and current_device:
                            current_device["address"] = match.group(1)
                            paired_devices.append(current_device)
                            current_device = {}
                    else:
                        # This is likely a line with device name
                        current_device = {"name": line, "type": "🔷", "id": f"paired_bt_{len(paired_devices)}"}
            
        elif system == "Darwin":  # macOS
            # On macOS, use system tools
            result = subprocess.run(["system_profiler", "SPBluetoothDataType"], 
                                   capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                current_device = None
                
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    
                    if ":" in line and not line.endswith(":"):
                        parts = line.split(":", 1)
                        key = parts[0].strip()
                        value = parts[1].strip()
                        
                        if key == "Device Name" and current_device is None:
                            current_device = {"name": value, "type": "🔷", "id": f"paired_bt_{len(paired_devices)}"}
                        elif key == "Address" and current_device is not None:
                            current_device["address"] = value
                            paired_devices.append(current_device)
                            current_device = None
                
        elif system == "Linux":
            # On Linux, use bluetoothctl
            result = subprocess.run(["bluetoothctl", "paired-devices"], 
                                   capture_output=True, text=True, encoding='utf-8', errors='ignore')
            
            if result.returncode == 0:
                lines = result.stdout.strip().split('\n')
                
                for line in lines:
                    match = re.search(r"Device\s+([0-9A-F:]+)\s+(.*)", line)
                    if match:
                        address = match.group(1)
                        name = match.group(2)
                        paired_devices.append({
                            "name": name,
                            "address": address,
                            "type": "🔷",
                            "id": f"paired_bt_{len(paired_devices)}"
                        })
        
    except Exception as e:
        print(f"Error while getting paired Bluetooth devices: {e}")
    
    # Add information that these are paired devices
    for device in paired_devices:
        device["paired"] = True
        device["name"] = f"{device['name']} (paired)"
    
    return paired_devices


def setup_static_files():
    """Copy frontend files to the static folder."""
    try:
        # Make sure static folder exists
        os.makedirs('static', exist_ok=True)
        os.makedirs('static/css', exist_ok=True)
        os.makedirs('static/js', exist_ok=True)
        
        # Get path to current script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        
        # Location of frontend files (assuming they are in the same folder)
        html_path = os.path.join(script_dir, 'index.html')
        css_path = os.path.join(script_dir, 'style.css')
        js_path = os.path.join(script_dir, 'script.js')
        
        # Copy files if they exist
        if os.path.exists(html_path):
            import shutil
            shutil.copy2(html_path, os.path.join('static', 'index.html'))
            print(f"Copied {html_path} to static folder")
        
        if os.path.exists(css_path):
            import shutil
            shutil.copy2(css_path, os.path.join('static/css', 'style.css'))
            print(f"Copied {css_path} to static/css folder")
        
        if os.path.exists(js_path):
            import shutil
            shutil.copy2(js_path, os.path.join('static/js', 'script.js'))
            print(f"Copied {js_path} to static/js folder")
    
    except Exception as e:
        print(f"Error during static files configuration: {e}")


# Create a single scanner instance for the entire application
scanner = DeviceScanner()

# API Routes
@app.route('/api/devices/wifi', methods=['GET'])
def get_wifi_devices():
    """Endpoint to get available Wi-Fi networks"""
    result = scanner.scan_wifi_networks()
    return jsonify(result)

@app.route('/api/devices/bluetooth', methods=['GET'])
def get_bluetooth_devices():
    """Endpoint to get available Bluetooth devices"""
    result = scanner.scan_bluetooth_devices()
    return jsonify(result)

@app.route('/api/devices/camera', methods=['GET'])
def get_camera_devices():
    """Endpoint to get available cameras"""
    result = scanner.list_available_cameras()
    return jsonify(result)

@app.route('/api/devices/scan', methods=['GET'])
def scan_all_devices():
    """Endpoint to scan all types of devices"""
    method = request.args.get('method', 'all')
    
    if method == 'wifi':
        return jsonify(scanner.scan_wifi_networks())
    elif method == 'bluetooth':
        return jsonify(scanner.scan_bluetooth_devices())
    elif method == 'camera':
        return jsonify(scanner.list_available_cameras())
    else:
        # Scan all device types
        devices = []
        
        # Wi-Fi
        wifi_result = scanner.scan_wifi_networks()
        if 'devices' in wifi_result:
            devices.extend(wifi_result['devices'])
            
        # Bluetooth
        bt_result = scanner.scan_bluetooth_devices()
        if 'devices' in bt_result:
            devices.extend(bt_result['devices'])
            
        # Cameras
        camera_result = scanner.list_available_cameras()
        if 'devices' in camera_result:
            devices.extend(camera_result['devices'])
            
        return jsonify({"status": "success", "devices": devices})

# Web Routes
@app.route('/', methods=['GET'])
def index():
    """Endpoint to serve the main HTML page"""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/static/css/<path:filename>', methods=['GET'])
def serve_css(filename):
    """Endpoint to serve CSS files"""
    return send_from_directory(os.path.join(app.static_folder, 'css'), filename)

@app.route('/static/js/<path:filename>', methods=['GET'])
def serve_js(filename):
    """Endpoint to serve JavaScript files"""
    return send_from_directory(os.path.join(app.static_folder, 'js'), filename)

# HTTP Error handlers
@app.errorhandler(404)
def page_not_found(e):
    """Handle 404 errors"""
    return jsonify({"error": "Resource not found"}), 404

@app.errorhandler(500)
def server_error(e):
    """Handle 500 errors"""
    return jsonify({"error": "Internal server error"}), 500


if __name__ == '__main__':
    # Configure static files before running the server
    setup_static_files()
    
    # Show information about available modules
    print("\n=== Available Modules Information ===")
    print(f"Module 'wifi': {'Available' if WIFI_MODULE_AVAILABLE else 'Unavailable'}")
    print(f"Module 'bleak' (Bluetooth): {'Available' if BLUETOOTH_MODULE_AVAILABLE else 'Unavailable'}")
    print(f"Module 'opencv-python': {'Available' if CAMERA_MODULE_AVAILABLE else 'Unavailable'}")
    
    print("\n=== System Information ===")
    print(f"Operating System: {platform.system()} {platform.release()}")
    print(f"Python Version: {platform.python_version()}")
    
    # Information about server startup
    print(f"\nStarting API server on http://localhost:{PORT}")
    print("Press CTRL+C to stop the server")
    
    # Run Flask server
    app.run(host=HOST, port=PORT, debug=DEBUG)