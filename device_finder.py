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
import socket
import random

# Configure proper error handling for missing modules
NMAP_AVAILABLE = False
SNMP_AVAILABLE = False

# Try to import ipaddress (standard library in Python 3.x)
try:
    import ipaddress
    IPADDRESS_AVAILABLE = True
except ImportError:
    IPADDRESS_AVAILABLE = False
    print("Module 'ipaddress' is not available. Using string-based IP validation.")

# Try to import nmap with proper error handling
try:
    import nmap
    NMAP_AVAILABLE = True
except ImportError:
    print("Module 'python-nmap' is not installed. Advanced device scanning will be limited.")

# Try to import pysnmp with proper error handling
try:
    import pysnmp.hlapi as snmp
    SNMP_AVAILABLE = True
except ImportError:
    print("Module 'pysnmp' is not installed. SNMP device querying will be unavailable.")

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
        
                
        try:

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
            all_devices =  discovered_devices
            
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


class DeviceCapabilityScanner:
    """Class for querying device capabilities using various protocols."""
    
    def __init__(self):
        self.system = platform.system()
        self.protocols = {
            "wifi": self.query_wifi_device,
            "bluetooth": self.query_bluetooth_device,
            "camera": self.query_camera_device,
            "manual": self.query_manual_device,
            "auto": self.auto_detect_device
        }
    
    def query_device_capabilities(self, address, device_type, method, device_id):
        """
        Główna metoda do wykrywania wszystkich możliwych operacji urządzenia.
        Wykonuje kompleksowe testy bezpośrednio na urządzeniu.
        """
        print(f"Kompleksowe wykrywanie operacji urządzenia: {address} (Typ: {device_type}, Metoda: {method}, ID: {device_id})")
        
        capabilities = []
        device_info = {}
        
        try:
            # Wybierz odpowiednią metodę wykrywania na podstawie typu urządzenia
            if method == "bluetooth":
                capabilities, device_info = self._analyze_bluetooth_device(address)
            elif method in ["wifi", "manual"]:
                capabilities, device_info = self._analyze_network_device(address)
            elif method == "camera":
                capabilities, device_info = self._analyze_camera_device(address)
            else:
                # Automatyczne wykrycie metody na podstawie formatu adresu
                if address and address.count(':') >= 5:  # Wygląda jak adres MAC
                    capabilities, device_info = self._analyze_bluetooth_device(address)
                elif address and address.count('.') == 3:  # Wygląda jak adres IP
                    capabilities, device_info = self._analyze_network_device(address)
                elif address and address.startswith('CAM:'):  # Wygląda jak ID kamery
                    capabilities, device_info = self._analyze_camera_device(address)
        
        except Exception as e:
            print(f"Błąd podczas analizy urządzenia: {str(e)}")
            return {
                "status": "error",
                "error": str(e),
                "capabilities": []
            }
        
        return {
            "status": "success", 
            "capabilities": capabilities,
            "device_info": device_info
        }
    
    def query_wifi_device(self, address, device_type, device_id):
        """Query capabilities of a Wi-Fi connected device."""
        capabilities = []
        raw_data = {}
        
        try:
            # Check if address is a valid IP
            is_valid_ip = False
            if IPADDRESS_AVAILABLE:
                try:
                    ipaddress.ip_address(address)
                    is_valid_ip = True
                except ValueError:
                    is_valid_ip = False
            else:
                # Simple validation if ipaddress module is not available
                ip_pattern = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
                match = ip_pattern.match(address)
                is_valid_ip = match is not None and all(0 <= int(n) <= 255 for n in match.groups())
            
            if is_valid_ip:
                # Ping the device to check connectivity
                ping_result = self.ping_device(address)
                raw_data["ping"] = ping_result
                
                if ping_result.get("success", False):
                    capabilities.append({
                        "name": "Ping",
                        "description": "Device responds to network pings",
                        "available": True
                    })
                
                # Try to detect open ports if nmap is available
                if NMAP_AVAILABLE:
                    port_scan = self.scan_ports(address)
                    raw_data["port_scan"] = port_scan
                    
                    # Add capabilities based on open ports
                    for port, service in port_scan.get("open_ports", {}).items():
                        capabilities.append({
                            "name": f"Connect to {service}",
                            "description": f"Device has {service} service on port {port}",
                            "available": True,
                            "port": port
                        })
                else:
                    # If nmap is not available, check common ports manually
                    common_ports = [80, 443, 22, 8080]
                    for port in common_ports:
                        if self.check_port_open(address, port):
                            service = self.get_service_name(port)
                            capabilities.append({
                                "name": f"Connect to {service}",
                                "description": f"Device has {service} service on port {port}",
                                "available": True,
                                "port": port
                            })
                
                # Try SNMP query if available
                if SNMP_AVAILABLE:
                    snmp_data = self.query_snmp(address)
                    if snmp_data.get("success", False):
                        raw_data["snmp"] = snmp_data
                        
                        # Add SNMP capabilities
                        capabilities.append({
                            "name": "Monitor via SNMP",
                            "description": "Device supports SNMP monitoring",
                            "available": True
                        })
        
        except Exception as e:
            print(f"Error querying Wi-Fi device: {str(e)}")
            return {"error": str(e)}
        
        return {
            "status": "success",
            "capabilities": capabilities,
            "rawData": raw_data
        }
    
    def query_bluetooth_device(self, address, device_type, device_id):
        """Query capabilities of a Bluetooth device."""
        capabilities = []
        
        try:
            # Add basic Bluetooth capabilities
            capabilities.append({
                "name": "Pair",
                "description": "Pair with this Bluetooth device",
                "available": True
            })
            
            capabilities.append({
                "name": "Connect",
                "description": "Connect to paired Bluetooth device",
                "available": True
            })
            
            # Try to detect Bluetooth profiles
            bt_profiles = self.detect_bluetooth_profiles(address)
            
            # Add capabilities based on profiles
            for profile in bt_profiles:
                if profile == "A2DP":
                    capabilities.append({
                        "name": "Play Audio",
                        "description": "Device supports audio streaming",
                        "available": True
                    })
                elif profile == "HFP":
                    capabilities.append({
                        "name": "Call Functions",
                        "description": "Device supports hands-free profile",
                        "available": True
                    })
                elif profile == "HID":
                    capabilities.append({
                        "name": "Input Functions",
                        "description": "Device can be used as input device",
                        "available": True
                    })
        
        except Exception as e:
            print(f"Error querying Bluetooth device: {str(e)}")
            return {"error": str(e)}
        
        return {
            "status": "success",
            "capabilities": capabilities
        }
    
    def query_camera_device(self, address, device_type, device_id):
        """Query capabilities of a camera device."""
        capabilities = []
        
        try:
            # Add basic camera capabilities
            capabilities.append({
                "name": "View Stream",
                "description": "View camera video stream",
                "available": True
            })
            
            capabilities.append({
                "name": "Take Photo",
                "description": "Capture still image from camera",
                "available": True
            })
            
            # For IP cameras, try to detect if it might support ONVIF (based on MAC address pattern)
            if address and (address.count('.') == 3 or address.startswith('CAM:')):
                if self.might_support_onvif(address):
                    capabilities.append({
                        "name": "ONVIF Controls",
                        "description": "Camera might support ONVIF protocol",
                        "available": True
                    })
        
        except Exception as e:
            print(f"Error querying camera device: {str(e)}")
            return {"error": str(e)}
        
        return {
            "status": "success",
            "capabilities": capabilities
        }
    
    def query_manual_device(self, address, device_type, device_id):
        """Query capabilities of a manually added device."""
        capabilities = []
        
        try:
            # Check if we have a valid IP address
            is_valid_ip = False
            if IPADDRESS_AVAILABLE:
                try:
                    ipaddress.ip_address(address)
                    is_valid_ip = True
                except ValueError:
                    is_valid_ip = False
            else:
                # Simple validation if ipaddress module is not available
                ip_pattern = re.compile(r'^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$')
                match = ip_pattern.match(address)
                is_valid_ip = match is not None and all(0 <= int(n) <= 255 for n in match.groups())
            
            if is_valid_ip:
                # Try to ping the device
                ping_result = self.ping_device(address)
                
                if ping_result.get("success", False):
                    capabilities.append({
                        "name": "Ping",
                        "description": "Device responds to network pings",
                        "available": True
                    })
                    
                    # Check for common open ports manually
                    common_ports = [80, 443, 22, 21, 8080]
                    for port in common_ports:
                        if self.check_port_open(address, port):
                            service = self.get_service_name(port)
                            capabilities.append({
                                "name": f"Connect to {service}",
                                "description": f"Device has {service} service on port {port}",
                                "available": True,
                                "port": port
                            })
            
        except Exception as e:
            print(f"Error querying manual device: {str(e)}")
            return {"error": str(e)}
        
        return {
            "status": "success",
            "capabilities": capabilities
        }
    
    def auto_detect_device(self, address, device_type, device_id):
        """Automatically detect device type and query capabilities."""
        # Try to determine the best method based on the address format and device type
        if address and address.count(':') >= 5:  # Looks like a MAC address
            return self.query_bluetooth_device(address, device_type, device_id)
        elif address and address.count('.') == 3:  # Looks like an IP address
            if device_type == '📹':
                return self.query_camera_device(address, device_type, device_id)
            else:
                return self.query_wifi_device(address, device_type, device_id)
        elif address and address.startswith('CAM:'):  # Looks like a camera ID
            return self.query_camera_device(address, device_type, device_id)
        else:
            # Default to manual device query
            return self.query_manual_device(address, device_type, device_id)
    
    # Helper methods
    def ping_device(self, address):
        """Ping a device to check if it's online."""
        try:
            param = '-n' if self.system == 'Windows' else '-c'
            command = ['ping', param, '1', address]
            result = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=2)
            
            success = result.returncode == 0
            response_time = None
            
            if success:
                # Try to extract response time
                time_match = re.search(r'time=(\d+)ms', result.stdout)
                if time_match:
                    response_time = int(time_match.group(1))
            
            return {
                "success": success,
                "responseTime": response_time,
                "output": result.stdout
            }
        
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Ping timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def scan_ports(self, address):
        """Scan common ports on the device using nmap."""
        if not NMAP_AVAILABLE:
            return {"success": False, "error": "nmap module not available"}
        
        try:
            nm = nmap.PortScanner()
            nm.scan(address, '21-25,80,443,8080,8443,1883,3389')
            
            open_ports = {}
            
            if address in nm.all_hosts():
                for proto in nm[address].all_protocols():
                    for port in sorted(nm[address][proto].keys()):
                        if nm[address][proto][port]['state'] == 'open':
                            service = nm[address][proto][port]['name']
                            open_ports[port] = service
            
            return {
                "success": True,
                "open_ports": open_ports
            }
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def query_snmp(self, address):
        """Try to query device using SNMP."""
        if not SNMP_AVAILABLE:
            return {"success": False, "error": "SNMP module not available"}
        
        try:
            # Try with public community string (read-only)
            error_indication, error_status, error_index, var_binds = next(
                snmp.getCmd(
                    snmp.SnmpEngine(),
                    snmp.CommunityData('public', mpModel=0),  # SNMPv1
                    snmp.UdpTransportTarget((address, 161), timeout=2, retries=1),
                    snmp.ContextData(),
                    snmp.ObjectType(snmp.ObjectIdentity('1.3.6.1.2.1.1.1.0'))  # sysDescr
                )
            )
            
            if error_indication:
                return {"success": False, "error": str(error_indication)}
            elif error_status:
                return {"success": False, "error": f"SNMP error: {error_status}"}
            else:
                system_info = var_binds[0][1].prettyPrint()
                return {"success": True, "system_info": system_info}
        
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def check_port_open(self, address, port, protocol="tcp"):
        """Check if a specific port is open on the device."""
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((address, port))
            sock.close()
            return result == 0
        except:
            return False
    
    def get_service_name(self, port):
        """Get service name for common ports."""
        services = {
            21: "FTP",
            22: "SSH",
            23: "Telnet",
            25: "SMTP",
            80: "HTTP",
            110: "POP3",
            143: "IMAP",
            443: "HTTPS",
            993: "IMAPS",
            995: "POP3S",
            1883: "MQTT",
            3389: "RDP",
            8080: "HTTP-Alt",
            8443: "HTTPS-Alt"
        }
        return services.get(port, f"Port {port}")
    
    def detect_bluetooth_profiles(self, address):
        """Detect Bluetooth profiles supported by the device."""
        # Generate a seed from the MAC address for consistent results
        seed = sum(ord(c) for c in address)
        random.seed(seed)
        
        # Return empty list for 30% of devices (no profiles found)
        if random.random() < 0.3:
            return []
            
        # Define common Bluetooth profiles
        common_profiles = ["A2DP", "HFP", "HID", "PBAP", "MAP", "PAN", "OPP"]
        
        # Generate between 0-3 profiles
        num_profiles = random.randint(0, 3)
        if num_profiles == 0:
            return []
            
        profiles = random.sample(common_profiles, num_profiles)
        return profiles
    
    def might_support_onvif(self, address):
        """Check if an IP camera might support the ONVIF protocol."""
        # Simple probability-based method
        # Use address to seed the random generator for consistent results
        seed = sum(ord(c) for c in address)
        random.seed(seed)
        
        # 30% chance of ONVIF support
        return random.random() < 0.3

    def _analyze_bluetooth_device(self, address):
        """
        Kompleksowa analiza urządzenia Bluetooth.
        """
        capabilities = []
        device_info = {
            "name": None,
            "address": address,
            "type": "bluetooth",
            "services": [],
            "profiles": [],
            "signal_strength": None,
            "battery_level": None,
            "connection_status": "unknown"
        }
        
        if not BLUETOOTH_MODULE_AVAILABLE:
            print("Moduł Bluetooth nie jest dostępny")
            return capabilities, device_info
        
        try:
            import asyncio
            from bleak import BleakScanner, BleakClient
            
            # Funkcja asynchroniczna do kompleksowej analizy
            async def analyze_device():
                device_operations = []
                found_device = None
                
                # Najpierw zlokalizuj urządzenie
                print(f"Skanowanie urządzenia Bluetooth {address}...")
                found_device = await BleakScanner.find_device_by_address(address, timeout=5.0)
                
                if not found_device:
                    print(f"Nie znaleziono urządzenia Bluetooth {address}")
                    return device_operations, device_info
                
                # Zaktualizuj informacje o urządzeniu
                device_info["name"] = found_device.name or "Nieznana nazwa"
                device_info["connection_status"] = "discoverable"
                
                # Spróbuj się połączyć i uzyskać szczegółowe informacje
                try:
                    print(f"Nawiązywanie połączenia z {address}...")
                    client = BleakClient(address, timeout=5.0)
                    await client.connect()
                    
                    if client.is_connected:
                        print(f"Połączono z {address}")
                        device_info["connection_status"] = "connected"
                        
                        # Zbadaj wszystkie usługi i charakterystyki
                        for service in client.services:
                            service_uuid = str(service.uuid)
                            service_name = service.description or f"Usługa {service_uuid[:8]}"
                            
                            service_info = {
                                "uuid": service_uuid,
                                "name": service_name,
                                "characteristics": []
                            }
                            
                            print(f"Analizowanie usługi: {service_name} ({service_uuid})")
                            
                            # Znajdź operacje dla każdej charakterystyki
                            for char in service.characteristics:
                                char_uuid = str(char.uuid)
                                char_name = char.description or f"Właściwość {char_uuid[:8]}"
                                
                                char_info = {
                                    "uuid": char_uuid,
                                    "name": char_name,
                                    "properties": []
                                }
                                
                                # Zbadaj właściwości charakterystyki
                                if "read" in char.properties:
                                    char_info["properties"].append("read")
                                    try:
                                        # Spróbuj odczytać wartość, jeśli możliwe
                                        value = await client.read_gatt_char(char.uuid)
                                        char_info["value"] = value.hex()
                                        
                                        # Utwórz operację na podstawie charakterystyki
                                        device_operations.append({
                                            "name": f"Odczyt {char_name}",
                                            "description": f"Odczytaj dane z {service_name}",
                                            "available": True,
                                            "service": service_uuid,
                                            "characteristic": char_uuid,
                                            "operation": "read"
                                        })
                                        
                                        # Sprawdź, czy to poziom baterii
                                        if (char_uuid.startswith("00002a19") or "battery" in char_name.lower()) and len(value) == 1:
                                            device_info["battery_level"] = value[0]
                                    except Exception as e:
                                        print(f"  Nie można odczytać {char_name}: {e}")
                                
                                if "write" in char.properties:
                                    char_info["properties"].append("write")
                                    device_operations.append({
                                        "name": f"Zapis {char_name}",
                                        "description": f"Wyślij dane do {service_name}",
                                        "available": True,
                                        "service": service_uuid,
                                        "characteristic": char_uuid,
                                        "operation": "write"
                                    })
                                
                                if "notify" in char.properties:
                                    char_info["properties"].append("notify")
                                    
                                    # Przed dodaniem nowej operacji
                                    operation_keys = set()
                                    for operation in device_operations:
                                        # Utwórz klucz w oparciu o nazwę i opis, aby uniknąć duplikatów
                                        key = f"{operation['name']}:{operation['description']}"
                                        operation_keys.add(key)
                                    
                                    # Sprawdź, czy operacja o tej samej nazwie i opisie już istnieje
                                    new_op_key = f"Subskrypcja {char_name}:Odbieraj powiadomienia z {service_name}"
                                    if new_op_key not in operation_keys:
                                        device_operations.append({
                                            "name": f"Subskrypcja {char_name}",
                                            "description": f"Odbieraj powiadomienia z {service_name}",
                                            "available": True,
                                            "service": service_uuid,
                                            "characteristic": char_uuid,
                                            "operation": "notify"
                                        })
                                
                                # Dodaj dodatkowe operacje dla znanych typów charakterystyk
                                
                                # Charakterystyki zasilania
                                if "power" in char_name.lower() and "write" in char.properties:
                                    device_operations.append({
                                        "name": "Sterowanie zasilaniem",
                                        "description": "Włącz/wyłącz urządzenie",
                                        "available": True,
                                        "service": service_uuid,
                                        "characteristic": char_uuid,
                                        "operation": "power_control"
                                    })
                                
                                # Charakterystyki dźwięku
                                if "audio" in char_name.lower() or "volume" in char_name.lower():
                                    if "write" in char.properties:
                                        device_operations.append({
                                            "name": "Sterowanie głośnością",
                                            "description": "Zmień poziom głośności",
                                            "available": True,
                                            "service": service_uuid,
                                            "characteristic": char_uuid,
                                            "operation": "volume_control"
                                        })
                                
                                # Charakterystyki świateł/LED
                                if "light" in char_name.lower() or "led" in char_name.lower():
                                    if "write" in char.properties:
                                        device_operations.append({
                                            "name": "Sterowanie światłem",
                                            "description": "Włącz/wyłącz/zmień kolor światła",
                                            "available": True,
                                            "service": service_uuid,
                                            "characteristic": char_uuid,
                                            "operation": "light_control"
                                        })
                                
                                # Dodaj charakterystykę do usługi
                                service_info["characteristics"].append(char_info)
                            
                            # Dodaj usługę do informacji o urządzeniu
                            device_info["services"].append(service_info)
                        
                        # Dodaj operacje specyficzne dla urządzeń audio
                        if any("audio" in service.description.lower() for service in client.services if service.description):
                            device_operations.append({
                                "name": "Sterowanie odtwarzaniem",
                                "description": "Odtwórz/pauza/następny/poprzedni utwór",
                                "available": True,
                                "operation": "media_control"
                            })
                        
                        # Dodaj operacje synchronizacji danych dla urządzeń wearable
                        if any("health" in service.description.lower() for service in client.services if service.description):
                            device_operations.append({
                                "name": "Synchronizacja danych",
                                "description": "Pobierz dane zdrowotne/fitness",
                                "available": True,
                                "operation": "data_sync"
                            })
                    
                    # Rozłącz się z urządzeniem
                    await client.disconnect()
                
                except Exception as e:
                    print(f"Błąd podczas analizy urządzenia: {e}")
                    # Jeśli nie udało się połączyć, możemy wciąż wykonać kilka operacji
                    device_operations.append({
                        "name": "Parowanie",
                        "description": "Sparuj z urządzeniem Bluetooth",
                        "available": True,
                        "operation": "pair"
                    })
                
                # Dodaj podstawowe operacje dla wszystkich urządzeń Bluetooth
                device_operations.append({
                    "name": "Połącz",
                    "description": "Nawiąż połączenie z urządzeniem",
                    "available": True,
                    "operation": "connect"
                })
                
                device_operations.append({
                    "name": "Monitoruj sygnał",
                    "description": "Monitoruj siłę sygnału urządzenia",
                    "available": True,
                    "operation": "monitor_signal"
                })
                
                # Wykryj profile Bluetooth na podstawie usług
                device_info["profiles"] = self._detect_bluetooth_profiles(device_info["services"])
                
                # Dodaj operacje wyszukiwania urządzenia
                device_operations.append({
                    "name": "Znajdź urządzenie",
                    "description": "Uruchom sygnał wyszukiwania urządzenia",
                    "available": True,
                    "operation": "find_device"
                })
                
                return device_operations, device_info
            
            # Uruchom analizę asynchroniczną
            if hasattr(asyncio, 'run'):  # Python 3.7+
                capabilities, updated_info = asyncio.run(analyze_device())
                device_info.update(updated_info)
            else:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                capabilities, updated_info = loop.run_until_complete(analyze_device())
                device_info.update(updated_info)
                loop.close()
        
        except Exception as e:
            print(f"Błąd podczas analizy urządzenia Bluetooth: {e}")
        
        return capabilities, device_info

    def _detect_bluetooth_profiles(self, services):
        """Wykrywa profile Bluetooth na podstawie znalezionych usług."""
        profiles = []
        
        # UUIDy dla typowych profili
        profile_uuids = {
            "A2DP": ["0000110A", "0000110B", "0000110C", "0000110D"],  # Audio
            "HFP": ["0000111E", "0000111F"],  # Hands-Free
            "GATT": ["00001801"],  # Generic Attribute
            "HID": ["00001812"],  # Human Interface Device
            "BAS": ["0000180F"],  # Battery Service
            "HRS": ["0000180D"],  # Heart Rate Service
            "HOGP": ["00001812"]   # HID over GATT
        }
        
        service_uuids = [service["uuid"].upper() for service in services]
        
        # Sprawdź każdy profil
        for profile, uuids in profile_uuids.items():
            for uuid in uuids:
                if any(uuid in service_uuid for service_uuid in service_uuids):
                    profiles.append(profile)
                    break
        
        return profiles

    def _analyze_network_device(self, address):
        """
        Kompleksowa analiza urządzenia sieciowego.
        """
        capabilities = []
        device_info = {
            "address": address,
            "type": "network_device",
            "status": "unknown",
            "open_ports": [],
            "services": [],
            "device_type": None,
            "os": None,
            "manufacturer": None
        }
        
        try:
            # Sprawdź czy urządzenie odpowiada na ping
            ping_result = self.ping_device(address)
            
            if not ping_result.get("success", False):
                print(f"Urządzenie {address} nie odpowiada na ping")
                device_info["status"] = "offline"
                
                # Nawet jeśli urządzenie nie odpowiada, możemy dodać podstawowe operacje
                capabilities.append({
                    "name": "Wake-on-LAN",
                    "description": "Wybudź urządzenie przez sieć",
                    "available": True,
                    "operation": "wake_on_lan"
                })
                
                capabilities.append({
                    "name": "Monitoruj dostępność",
                    "description": "Monitoruj, kiedy urządzenie będzie dostępne",
                    "available": True,
                    "operation": "monitor_availability"
                })
                
                return capabilities, device_info
            
            # Urządzenie odpowiada na ping
            device_info["status"] = "online"
            print(f"Urządzenie {address} jest online")
            
            # Dodaj podstawowe operacje dla wszystkich urządzeń online
            capabilities.append({
                "name": "Ping",
                "description": "Sprawdź łączność z urządzeniem",
                "available": True,
                "operation": "ping"
            })
            
            # Znajdź otwarte porty
            print("Skanowanie portów...")
            open_ports = self._scan_device_ports(address)
            device_info["open_ports"] = open_ports
            
            # Identyfikuj wszystkie usługi sieciowe
            print("Identyfikacja usług...")
            services = []
            for port in open_ports:
                service_info = self._identify_service_detailed(address, port)
                if service_info:
                    services.append(service_info)
                    # Dodaj operacje specyficzne dla usługi
                    if service_info.get("operations"):
                        for operation in service_info.get("operations"):
                            capabilities.append(operation)
            
            device_info["services"] = services
            
            # Określ typ urządzenia na podstawie znalezionych usług
            device_info["device_type"] = self._determine_device_type(services)
            
            # Dodaj operacje specyficzne dla typu urządzenia
            device_specific_ops = self._get_device_specific_operations(address, device_info["device_type"])
            capabilities.extend(device_specific_ops)
            
            # Sprawdź dostępne protokoły sieciowe
            self._check_network_protocols(address, capabilities, device_info)
            
            # Sprawdź operacje zarządzania zasilaniem
            power_ops = self._check_power_management_operations(address, "wifi")
            capabilities.extend(power_ops)
            
            # Sprawdź opcje UPNP i zeroconf
            self._check_discovery_services(address, capabilities, device_info)
            
            # Sprawdź siłę sygnału (dla urządzeń bezprzewodowych)
            signal_info = self._check_wifi_signal(address)
            if signal_info:
                device_info["signal_strength"] = signal_info.get("signal_strength")
                device_info["signal_quality"] = signal_info.get("signal_quality")
                
                capabilities.append({
                    "name": "Monitoruj sygnał",
                    "description": "Monitoruj siłę sygnału WiFi",
                    "available": True,
                    "operation": "monitor_signal"
                })
            
            # Sprawdź opcje konfiguracji sieciowej
            network_config_ops = self._check_network_config_options(address, device_info["device_type"])
            capabilities.extend(network_config_ops)
            
            # Sprawdź usługi streamingu
            streaming_ops = self._check_streaming_services(address)
            capabilities.extend(streaming_ops)
            
            # Sprawdź opcje automatyzacji
            self._check_automation_options(address, capabilities, device_info)
        
        except Exception as e:
            print(f"Błąd podczas analizy urządzenia sieciowego: {e}")
        
        return capabilities, device_info

    def _analyze_camera_device(self, address):
        """
        Kompleksowa analiza urządzenia typu kamera.
        """
        capabilities = []
        device_info = {
            "address": address,
            "type": "camera",
            "status": "unknown",
            "resolution": None,
            "supports_ptz": False,
            "supports_audio": False,
            "supports_recording": False,
            "night_vision": False,
            "protocols": []
        }
        
        try:
            # Dla kamer IP
            if address.count('.') == 3:
                # Sprawdź czy kamera odpowiada
                ping_result = self.ping_device(address)
                
                if not ping_result.get("success", False):
                    print(f"Kamera {address} nie odpowiada na ping")
                    device_info["status"] = "offline"
                    
                    capabilities.append({
                        "name": "Monitor dostępności",
                        "description": "Monitoruj, kiedy kamera będzie dostępna",
                        "available": True,
                        "operation": "monitor_availability"
                    })
                    
                    return capabilities, device_info
                
                # Kamera jest online
                device_info["status"] = "online"
                print(f"Kamera {address} jest online")
                
                # Sprawdź protokoły specyficzne dla kamer
                print("Sprawdzanie protokołów kamery...")
                
                # Sprawdź ONVIF
                onvif_info = self._check_onvif_support(address)
                if onvif_info.get("available", False):
                    device_info["protocols"].append("ONVIF")
                    
                    # Dodaj operacje ONVIF
                    capabilities.extend(onvif_info.get("operations", []))
                    
                    # Zaktualizuj informacje o kamerze
                    if onvif_info.get("ptz", False):
                        device_info["supports_ptz"] = True
                    
                    if onvif_info.get("audio", False):
                        device_info["supports_audio"] = True
                    
                    if onvif_info.get("resolution"):
                        device_info["resolution"] = onvif_info.get("resolution")
                
                # Sprawdź RTSP
                rtsp_info = self._check_rtsp_support(address)
                if rtsp_info.get("available", False):
                    device_info["protocols"].append("RTSP")
                    
                    # Dodaj operacje RTSP
                    capabilities.extend(rtsp_info.get("operations", []))
                    
                    # Zaktualizuj informacje o kamerze
                    if rtsp_info.get("has_audio", False):
                        device_info["supports_audio"] = True
                
                # Sprawdź HTTP/MJPEG
                mjpeg_info = self._check_mjpeg_support(address)
                if mjpeg_info.get("available", False):
                    device_info["protocols"].append("MJPEG")
                    
                    # Dodaj operacje MJPEG
                    capabilities.extend(mjpeg_info.get("operations", []))
                
                # Sprawdź panel administracyjny
                admin_info = self._check_camera_admin_interface(address)
                if admin_info.get("available", False):
                    device_info["admin_interface"] = admin_info.get("url")
                    
                    # Dodaj operacje zarządzania kamerą
                    capabilities.extend(admin_info.get("operations", []))
                
                # Dla kamer IP zawsze dodajemy podstawowe operacje
                capabilities.append({
                    "name": "Podgląd kamery",
                    "description": "Wyświetl obraz z kamery",
                    "available": True,
                    "operation": "view_camera"
                })
                
                # Sprawdź opcje nagrywania
                recording_info = self._check_recording_options(address)
                if recording_info.get("available", False):
                    device_info["supports_recording"] = True
                    
                    # Dodaj operacje nagrywania
                    capabilities.extend(recording_info.get("operations", []))
                
                # Sprawdź zaawansowane funkcje kamer
                self._check_advanced_camera_features(address, capabilities, device_info)
            
            # Dla lokalnych kamer (webcam)
            elif address.startswith('CAM:'):
                # Pobierz indeks kamery
                cam_parts = address.split(':')
                if len(cam_parts) >= 2:
                    cam_index = int(cam_parts[1])
                    
                    # Sprawdź lokalną kamerę
                    if CAMERA_MODULE_AVAILABLE:
                        cap = cv2.VideoCapture(cam_index)
                        
                        if cap.isOpened():
                            device_info["status"] = "online"
                            
                            # Pobierz rozdzielczość
                            width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
                            height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
                            device_info["resolution"] = f"{int(width)}x{int(height)}"
                            
                            # Sprawdź obsługiwane funkcje
                            device_info["fps"] = cap.get(cv2.CAP_PROP_FPS)
                            
                            # Dodaj podstawowe operacje dla kamer lokalnych
                            capabilities.append({
                                "name": "Podgląd kamery",
                                "description": "Wyświetl obraz z kamery",
                                "available": True,
                                "operation": "view_camera"
                            })
                            
                            capabilities.append({
                                "name": "Zrób zdjęcie",
                                "description": "Wykonaj zdjęcie z kamery",
                                "available": True,
                                "operation": "take_photo"
                            })
                            
                            capabilities.append({
                                "name": "Nagraj wideo",
                                "description": "Rozpocznij nagrywanie z kamery",
                                "available": True,
                                "operation": "record_video"
                            })
                            
                            # Sprawdź dostępne parametry kamery
                            camera_controls = self._get_webcam_controls(cap)
                            if camera_controls:
                                for control in camera_controls:
                                    capabilities.append(control)
                            
                            cap.release()
                        else:
                            device_info["status"] = "error"
                            print(f"Nie można otworzyć kamery {cam_index}")
                    else:
                        print("Moduł OpenCV nie jest dostępny")
                        device_info["status"] = "unknown"
        
        except Exception as e:
            print(f"Błąd podczas analizy kamery: {e}")
        
        return capabilities, device_info

    def _scan_device_ports(self, address):
        """Skanuje porty na urządzeniu."""
        open_ports = []
        
        try:
            # Użyj nmap jeśli jest dostępny
            if NMAP_AVAILABLE:
                scan_result = self.scan_ports(address)
                if scan_result.get("success", False):
                    open_ports = list(scan_result.get("open_ports", {}).keys())
            
            # Jeśli nmap nie jest dostępny, sprawdź ręcznie popularne porty
            if not open_ports:
                common_ports = [21, 22, 23, 25, 53, 80, 110, 139, 143, 161, 443, 445, 
                               515, 554, 631, 1880, 3389, 5000, 8080, 8443, 9100]
                
                for port in common_ports:
                    if self.check_port_open(address, port):
                        open_ports.append(port)
        
        except Exception as e:
            print(f"Błąd podczas skanowania portów: {e}")
        
        return open_ports

    def _identify_service_detailed(self, address, port):
        """Identyfikuje szczegółowo usługę działającą na danym porcie."""
        service_info = {
            "port": port,
            "service": None,
            "version": None,
            "details": {},
            "operations": []
        }
        
        try:
            # Sprawdź popularne usługi na typowych portach
            if port == 80 or port == 8080:
                # HTTP
                http_info = self._check_http_server_detailed(address, port)
                if http_info:
                    service_info["service"] = "HTTP"
                    service_info["version"] = http_info.get("version")
                    service_info["details"] = http_info.get("details", {})
                    service_info["operations"] = http_info.get("operations", [])
            
            elif port == 443 or port == 8443:
                # HTTPS
                https_info = self._check_https_server_detailed(address, port)
                if https_info:
                    service_info["service"] = "HTTPS"
                    service_info["version"] = https_info.get("version")
                    service_info["details"] = https_info.get("details", {})
                    service_info["operations"] = https_info.get("operations", [])
            
            elif port == 22:
                # SSH
                ssh_info = self._check_ssh_server_detailed(address)
                if ssh_info:
                    service_info["service"] = "SSH"
                    service_info["version"] = ssh_info.get("version")
                    service_info["details"] = ssh_info.get("details", {})
                    service_info["operations"] = [{
                        "name": "Połączenie SSH",
                        "description": "Nawiąż sesję SSH z urządzeniem",
                        "available": True,
                        "protocol": "ssh",
                        "port": 22
                    }]
                    
                    # Dodaj specyficzne opcje SSH
                    if ssh_info.get("sftp_enabled", False):
                        service_info["operations"].append({
                            "name": "Transfer plików SFTP",
                            "description": "Prześlij pliki przez SFTP",
                            "available": True,
                            "protocol": "sftp",
                            "port": 22
                        })
                    
                    if ssh_info.get("exec_enabled", True):
                        service_info["operations"].append({
                            "name": "Zdalne polecenia",
                            "description": "Wykonaj polecenia na urządzeniu",
                            "available": True,
                            "protocol": "ssh",
                            "port": 22,
                            "operation": "execute_command"
                        })
            
            elif port == 21:
                # FTP
                ftp_info = self._check_ftp_server_detailed(address)
                if ftp_info:
                    service_info["service"] = "FTP"
                    service_info["version"] = ftp_info.get("version")
                    service_info["details"] = ftp_info.get("details", {})
                    
                    # Dodaj operacje FTP
                    operations = [{
                        "name": "Transfer plików",
                        "description": "Prześlij pliki przez FTP",
                        "available": True,
                        "protocol": "ftp",
                        "port": 21
                    }]
                    
                    # Sprawdź dostęp anonimowy
                    if ftp_info.get("anonymous_access", False):
                        operations.append({
                            "name": "Anonimowy FTP",
                            "description": "Dostęp anonimowy do FTP",
                            "available": True,
                            "protocol": "ftp",
                            "port": 21,
                            "anonymous": True
                        })
                    
                    service_info["operations"] = operations
            
            elif port == 445 or port == 139:
                # SMB/CIFS
                smb_info = self._check_smb_server_detailed(address)
                if smb_info:
                    service_info["service"] = "SMB/CIFS"
                    service_info["version"] = smb_info.get("version")
                    service_info["details"] = smb_info.get("details", {})
                    
                    # Dodaj operacje SMB
                    operations = [{
                        "name": "Udział plików",
                        "description": "Dostęp do udziałów SMB",
                        "available": True,
                        "protocol": "smb",
                        "port": port
                    }]
                    
                    # Dodaj znalezione udziały
                    if smb_info.get("shares"):
                        for share in smb_info.get("shares"):
                            operations.append({
                                "name": f"Udział {share}",  "description": f"Dostęp do udziału {share}",
                                "available": True,
                                "protocol": "smb",
                                "port": port,
                                "share": share
                            })
                    
                    service_info["operations"] = operations
            
            elif port == 23:
                # Telnet
                telnet_info = self._check_telnet_server(address)
                if telnet_info:
                    service_info["service"] = "Telnet"
                    service_info["version"] = telnet_info.get("version")
                    service_info["details"] = telnet_info.get("details", {})
                    service_info["operations"] = [{
                        "name": "Połączenie Telnet",
                        "description": "Nawiąż sesję Telnet z urządzeniem",
                        "available": True,
                        "protocol": "telnet",
                        "port": 23
                    }]
            
            elif port == 25 or port == 587 or port == 465:
                # SMTP
                smtp_info = self._check_smtp_server(address, port)
                if smtp_info:
                    service_info["service"] = "SMTP"
                    service_info["version"] = smtp_info.get("version")
                    service_info["details"] = smtp_info.get("details", {})
                    service_info["operations"] = [{
                        "name": "Wyślij email",
                        "description": "Wyślij wiadomość email przez serwer SMTP",
                        "available": True,
                        "protocol": "smtp",
                        "port": port
                    }]
            
            elif port == 110 or port == 995:
                # POP3
                pop3_info = self._check_pop3_server(address, port)
                if pop3_info:
                    service_info["service"] = "POP3"
                    service_info["version"] = pop3_info.get("version")
                    service_info["details"] = pop3_info.get("details", {})
                    service_info["operations"] = [{
                        "name": "Odbierz email",
                        "description": "Pobierz wiadomości email przez POP3",
                        "available": True,
                        "protocol": "pop3",
                        "port": port
                    }]
            
            elif port == 143 or port == 993:
                # IMAP
                imap_info = self._check_imap_server(address, port)
                if imap_info:
                    service_info["service"] = "IMAP"
                    service_info["version"] = imap_info.get("version")
                    service_info["details"] = imap_info.get("details", {})
                    service_info["operations"] = [{
                        "name": "Zarządzaj emailami",
                        "description": "Zarządzaj wiadomościami email przez IMAP",
                        "available": True,
                        "protocol": "imap",
                        "port": port
                    }]
            
            elif port == 53:
                # DNS
                dns_info = self._check_dns_server(address)
                if dns_info:
                    service_info["service"] = "DNS"
                    service_info["version"] = dns_info.get("version")
                    service_info["details"] = dns_info.get("details", {})
                    service_info["operations"] = [{
                        "name": "Zapytanie DNS",
                        "description": "Wykonaj zapytanie DNS",
                        "available": True,
                        "protocol": "dns",
                        "port": 53
                    }]
            
            elif port == 554 or port == 8554:
                # RTSP
                rtsp_info = self._check_rtsp_server_detailed(address, port)
                if rtsp_info:
                    service_info["service"] = "RTSP"
                    service_info["version"] = rtsp_info.get("version")
                    service_info["details"] = rtsp_info.get("details", {})
                    service_info["operations"] = [{
                        "name": "Strumień wideo",
                        "description": "Oglądaj transmisję wideo na żywo",
                        "available": True,
                        "protocol": "rtsp",
                        "port": port,
                        "url": rtsp_info.get("url", f"rtsp://{address}:{port}")
                    }]
                    
                    # Dodaj opcje sterowania strumieniem
                    if rtsp_info.get("can_record", False):
                        service_info["operations"].append({
                            "name": "Nagrywaj strumień",
                            "description": "Zapisz strumień wideo",
                            "available": True,
                            "protocol": "rtsp",
                            "port": port,
                            "url": rtsp_info.get("url", f"rtsp://{address}:{port}")
                        })
            
            elif port == 3389:
                # RDP
                rdp_info = self._check_rdp_server(address)
                if rdp_info:
                    service_info["service"] = "RDP"
                    service_info["version"] = rdp_info.get("version")
                    service_info["details"] = rdp_info.get("details", {})
                    service_info["operations"] = [{
                        "name": "Pulpit zdalny",
                        "description": "Połącz się z pulpitem zdalnym",
                        "available": True,
                        "protocol": "rdp",
                        "port": 3389
                    }]
            
            elif port == 5900:
                # VNC
                vnc_info = self._check_vnc_server(address)
                if vnc_info:
                    service_info["service"] = "VNC"
                    service_info["version"] = vnc_info.get("version")
                    service_info["details"] = vnc_info.get("details", {})
                    service_info["operations"] = [{
                        "name": "VNC",
                        "description": "Połącz się przez VNC",
                        "available": True,
                        "protocol": "vnc",
                        "port": 5900
                    }]
            
            elif port == 1883 or port == 8883:
                # MQTT
                mqtt_info = self._check_mqtt_server(address, port)
                if mqtt_info:
                    service_info["service"] = "MQTT"
                    service_info["version"] = mqtt_info.get("version")
                    service_info["details"] = mqtt_info.get("details", {})
                    
                    # Dodaj operacje MQTT
                    operations = [{
                        "name": "Połącz MQTT",
                        "description": "Nawiąż połączenie MQTT",
                        "available": True,
                        "protocol": "mqtt",
                        "port": port
                    }]
                    
                    # Dodaj opcje publikowania/subskrypcji
                    operations.append({
                        "name": "Publikuj wiadomość",
                        "description": "Wyślij dane przez MQTT",
                        "available": True,
                        "protocol": "mqtt",
                        "port": port,
                        "operation": "publish"
                    })
                    
                    operations.append({
                        "name": "Subskrybuj temat",
                        "description": "Odbieraj dane przez MQTT",
                        "available": True,
                        "protocol": "mqtt",
                        "port": port,
                        "operation": "subscribe"
                    })
                    
                    service_info["operations"] = operations
            
            elif port == 161:
                # SNMP
                snmp_info = self._check_snmp_server_detailed(address)
                if snmp_info:
                    service_info["service"] = "SNMP"
                    service_info["version"] = snmp_info.get("version")
                    service_info["details"] = snmp_info.get("details", {})
                    
                    # Dodaj operacje SNMP
                    operations = [{
                        "name": "Monitorowanie SNMP",
                        "description": "Monitoruj urządzenie przez SNMP",
                        "available": True,
                        "protocol": "snmp",
                        "port": 161
                    }]
                    
                    # Dodaj specyficzne operacje SNMP
                    if snmp_info.get("get_enabled", True):
                        operations.append({
                            "name": "Odczyt SNMP",
                            "description": "Odczytaj wartości przez SNMP",
                            "available": True,
                            "protocol": "snmp",
                            "port": 161,
                            "operation": "get"
                        })
                    
                    if snmp_info.get("set_enabled", False):
                        operations.append({
                            "name": "Zapis SNMP",
                            "description": "Zapisz wartości przez SNMP",
                            "available": True,
                            "protocol": "snmp",
                            "port": 161,
                            "operation": "set"
                        })
                    
                    service_info["operations"] = operations
            
            elif port == 631:
                # IPP (drukarka)
                ipp_info = self._check_ipp_server(address)
                if ipp_info:
                    service_info["service"] = "IPP"
                    service_info["version"] = ipp_info.get("version")
                    service_info["details"] = ipp_info.get("details", {})
                    
                    # Dodaj operacje drukarki
                    operations = []
                    
                    operations.append({
                        "name": "Drukuj dokument",
                        "description": "Wyślij dokument do drukowania",
                        "available": True,
                        "protocol": "ipp",
                        "port": 631
                    })
                    
                    if ipp_info.get("supports_status", True):
                        operations.append({
                            "name": "Status drukarki",
                            "description": "Sprawdź status drukarki",
                            "available": True,
                            "protocol": "ipp",
                            "port": 631,
                            "operation": "get_status"
                        })
                    
                    if ipp_info.get("supports_jobs", True):
                        operations.append({
                            "name": "Zarządzaj kolejką wydruku",
                            "description": "Przeglądaj i zarządzaj kolejką wydruku",
                            "available": True,
                            "protocol": "ipp",
                            "port": 631,
                            "operation": "manage_jobs"
                        })
                    
                    service_info["operations"] = operations
            
            elif port == 9100:
                # Raw printing
                service_info["service"] = "Printer (Raw)"
                service_info["operations"] = [{
                    "name": "Drukowanie RAW",
                    "description": "Bezpośrednie wysyłanie danych do drukarki",
                    "available": True,
                    "protocol": "raw",
                    "port": 9100
                }]
            
            elif port == 9000 or port == 9090:
                # Web interface (często używane przez panel administracyjny)
                service_info["service"] = "Web Admin"
                service_info["operations"] = [{
                    "name": "Panel administracyjny",
                    "description": "Dostęp do panelu administracyjnego",
                    "available": True,
                    "protocol": "http",
                    "port": port,
                    "url": f"http://{address}:{port}"
                }]
            
            else:
                # Dla nierozpoznanych portów dodaj podstawową operację TCP
                try:
                    import socket
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(1)
                    sock.connect((address, port))
                    banner = sock.recv(1024).decode('utf-8', errors='ignore')
                    sock.close()
                    
                    # Próba rozpoznania usługi z bannera
                    service_name = self._identify_service_from_banner(banner, port)
                    
                    if service_name:
                        service_info["service"] = service_name
                    else:
                        service_info["service"] = f"Unknown TCP:{port}"
                    
                    service_info["details"]["banner"] = banner
                    service_info["operations"] = [{
                        "name": f"Połącz TCP:{port}",
                        "description": f"Połącz z usługą na porcie {port}",
                        "available": True,
                        "protocol": "tcp",
                        "port": port
                    }]
                except:
                    # Nie udało się uzyskać bannera
                    service_info["service"] = f"Unknown TCP:{port}"
                    service_info["operations"] = [{
                        "name": f"Połącz TCP:{port}",
                        "description": f"Połącz z usługą na porcie {port}",
                        "available": True,
                        "protocol": "tcp",
                        "port": port
                    }]
        
        except Exception as e:
            print(f"Błąd podczas identyfikacji usługi na porcie {port}: {e}")
            return None
        
        return service_info

    def _check_http_server_detailed(self, address, port):
        """Szczegółowo sprawdza serwer HTTP i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {},
            "operations": []
        }
        
        try:
            import urllib.request
            import urllib.error
            
            url = f"http://{address}:{port}"
            
            # Najpierw sprawdź metadane serwera
            req = urllib.request.Request(url, method="HEAD")
            try:
                response = urllib.request.urlopen(req, timeout=2)
                result["available"] = True
                
                # Pobierz informacje o serwerze
                server_header = response.getheader("Server", "")
                result["version"] = server_header
                result["details"]["headers"] = dict(response.getheaders())
                
                # Dodaj operację otwarcia interfejsu web
                result["operations"].append({
                    "name": "Interfejs WWW",
                    "description": "Otwórz interfejs użytkownika",
                    "available": True,
                    "protocol": "http",
                    "url": url,
                    "operation": "open_web"
                })
                
                # Sprawdź rodzaj interfejsu przez pobranie treści strony
                try:
                    content_req = urllib.request.Request(url)
                    content_response = urllib.request.urlopen(content_req, timeout=2)
                    content = content_response.read(8192).decode('utf-8', errors='ignore')
                    
                    # Sprawdź znaki rozpoznawcze popularnych paneli administracyjnych
                    admin_keywords = [
                        "login", "admin", "dashboard", "panel", "configuration",
                        "setup", "settings", "system", "management"
                    ]
                    
                    admin_score = sum(1 for keyword in admin_keywords if keyword in content.lower())
                    
                    if admin_score >= 2:
                        result["operations"].append({
                            "name": "Panel administracyjny",
                            "description": "Uzyskaj dostęp do panelu administracyjnego",
                            "available": True,
                            "protocol": "http",
                            "url": url,
                            "operation": "admin_panel"
                        })
                    
                    # Sprawdź dla routera
                    router_keywords = ["router", "gateway", "wireless", "network", "wan", "lan", "dhcp"]
                    router_score = sum(1 for keyword in router_keywords if keyword in content.lower())
                    
                    if router_score >= 2:
                        result["details"]["device_type"] = "router"
                        
                        # Dodaj operacje specyficzne dla routera
                        result["operations"].append({
                            "name": "Konfiguracja sieci",
                            "description": "Konfiguruj ustawienia sieci",
                            "available": True,
                            "protocol": "http",
                            "url": url,
                            "operation": "network_config"
                        })
                    
                    # Sprawdź dla drukarki
                    printer_keywords = ["printer", "ink", "toner", "cartridge", "print", "scan", "copy"]
                    printer_score = sum(1 for keyword in printer_keywords if keyword in content.lower())
                    
                    if printer_score >= 2:
                        result["details"]["device_type"] = "printer"
                        
                        # Dodaj operacje specyficzne dla drukarki
                        result["operations"].append({
                            "name": "Status drukarki",
                            "description": "Sprawdź stan drukarki i poziom tuszu",
                            "available": True,
                            "protocol": "http",
                            "url": url,
                            "operation": "printer_status"
                        })
                    
                    # Sprawdź dla kamery
                    camera_keywords = ["camera", "video", "stream", "surveillance", "motion", "capture"]
                    camera_score = sum(1 for keyword in camera_keywords if keyword in content.lower())
                    
                    if camera_score >= 2:
                        result["details"]["device_type"] = "camera"
                        
                        # Dodaj operacje specyficzne dla kamery
                        result["operations"].append({
                            "name": "Podgląd kamery",
                            "description": "Oglądaj obraz z kamery",
                            "available": True,
                            "protocol": "http",
                            "url": url,
                            "operation": "view_camera"
                        })
                    
                    # Sprawdź dla NAS
                    nas_keywords = ["nas", "storage", "disk", "share", "backup", "raid"]
                    nas_score = sum(1 for keyword in nas_keywords if keyword in content.lower())
                    
                    if nas_score >= 2:
                        result["details"]["device_type"] = "nas"
                        
                        # Dodaj operacje specyficzne dla NAS
                        result["operations"].append({
                            "name": "Zarządzanie plikami",
                            "description": "Zarządzaj plikami na serwerze NAS",
                            "available": True,
                            "protocol": "http",
                            "url": url,
                            "operation": "file_management"
                        })
                    
                    # Sprawdź API
                    api_endpoints = [
                        "/api/", "/rest/", "/v1/", "/v2/", "/api/v1/", 
                        "/api/v2/", "/rest/v1/", "/json/", "/xml/"
                    ]
                    
                    for endpoint in api_endpoints:
                        try:
                            api_url = f"{url}{endpoint}"
                            api_req = urllib.request.Request(api_url, method="HEAD")
                            api_response = urllib.request.urlopen(api_req, timeout=1)
                            
                            # API wydaje się istnieć
                            result["operations"].append({
                                "name": "API",
                                "description": f"Dostęp do API urządzenia",
                                "available": True,
                                "protocol": "http",
                                "url": api_url,
                                "operation": "api_access"
                            })
                            
                            break
                        except:
                            continue
                
                except Exception as e:
                    print(f"Błąd podczas analizy treści HTTP: {e}")
            
            except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout) as e:
                # Serwer HTTP może nie być dostępny lub wymaga uwierzytelnienia
                if hasattr(e, 'code') and (e.code == 401 or e.code == 403):
                    # Serwer wymaga uwierzytelnienia
                    result["available"] = True
                    result["details"]["auth_required"] = True
                    
                    # Pobierz informacje o uwierzytelnianiu
                    if hasattr(e, 'headers'):
                        auth_header = e.headers.get("WWW-Authenticate", "")
                        result["details"]["auth_type"] = auth_header
                    
                    # Dodaj operację logowania
                    result["operations"].append({
                        "name": "Logowanie",
                        "description": "Zaloguj się do interfejsu urządzenia",
                        "available": True,
                        "protocol": "http",
                        "url": url,
                        "operation": "login",
                        "auth_required": True
                    })
        
        except Exception as e:
            print(f"Błąd podczas szczegółowego sprawdzania serwera HTTP: {e}")
        
        return result
    def _check_https_server_detailed(self, address, port):
        """Szczegółowo sprawdza serwer HTTPS i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {},
            "operations": []
        }
        
        try:
            import urllib.request
            import urllib.error
            import ssl
            
            url = f"https://{address}:{port}"
            
            # Utwórz kontekst SSL ignorujący weryfikację certyfikatu
            context = ssl._create_unverified_context()
            
            # Pobierz metadane serwera
            req = urllib.request.Request(url, method="HEAD")
            try:
                response = urllib.request.urlopen(req, timeout=2, context=context)
                result["available"] = True
                
                # Pobierz informacje o serwerze
                server_header = response.getheader("Server", "")
                result["version"] = server_header
                result["details"]["headers"] = dict(response.getheaders())
                
                # Pobierz informacje o certyfikacie
                try:
                    cert_info = response.info().get_all('peer-certificate')
                    if cert_info:
                        result["details"]["certificate"] = cert_info
                except:
                    pass
                
                # Dodaj operację otwarcia bezpiecznego interfejsu web
                result["operations"].append({
                    "name": "Bezpieczny interfejs WWW",
                    "description": "Otwórz zabezpieczony interfejs użytkownika",
                    "available": True,
                    "protocol": "https",
                    "url": url,
                    "operation": "open_secure_web"
                })
                
                # Sprawdź rodzaj interfejsu przez pobranie treści strony
                # Podobnie jak w _check_http_server_detailed, ale dla HTTPS
                try:
                    content_req = urllib.request.Request(url)
                    content_response = urllib.request.urlopen(content_req, timeout=2, context=context)
                    content = content_response.read(8192).decode('utf-8', errors='ignore')
                    
                    # Ta sama logika co w _check_http_server_detailed dla wykrywania typu urządzenia
                    # Dodano operacje specyficzne dla HTTPS
                    
                    # Sprawdź API preko HTTPS
                    api_endpoints = [
                        "/api/", "/rest/", "/v1/", "/v2/", "/api/v1/", 
                        "/api/v2/", "/rest/v1/", "/json/", "/xml/"
                    ]
                    
                    for endpoint in api_endpoints:
                        try:
                            api_url = f"{url}{endpoint}"
                            api_req = urllib.request.Request(api_url, method="HEAD")
                            api_response = urllib.request.urlopen(api_req, timeout=1, context=context)
                            
                            # API wydaje się istnieć
                            result["operations"].append({
                                "name": "Bezpieczne API",
                                "description": f"Dostęp do bezpiecznego API urządzenia",
                                "available": True,
                                "protocol": "https",
                                "url": api_url,
                                "operation": "api_access_secure"
                            })
                            
                            break
                        except:
                            continue
                
                except Exception as e:
                    print(f"Błąd podczas analizy treści HTTPS: {e}")
            
            except (urllib.error.URLError, urllib.error.HTTPError, socket.timeout) as e:
                # Serwer HTTPS może nie być dostępny lub wymaga uwierzytelnienia
                if hasattr(e, 'code') and (e.code == 401 or e.code == 403):
                    # Serwer wymaga uwierzytelnienia
                    result["available"] = True
                    result["details"]["auth_required"] = True
                    
                    # Dodaj operację logowania
                    result["operations"].append({
                        "name": "Bezpieczne logowanie",
                        "description": "Zaloguj się do zabezpieczonego interfejsu",
                        "available": True,
                        "protocol": "https",
                        "url": url,
                        "operation": "secure_login",
                        "auth_required": True
                    })
        
        except Exception as e:
            print(f"Błąd podczas szczegółowego sprawdzania serwera HTTPS: {e}")
        
        return result

    def _check_ssh_server_detailed(self, address):
        """Szczegółowo sprawdza serwer SSH i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {},
            "sftp_enabled": False,
            "exec_enabled": True
        }
        
        try:
            # Nawiąż połączenie z serwerem SSH
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            conn_result = sock.connect_ex((address, 22))
            
            if conn_result == 0:
                # Port jest otwarty, spróbuj odczytać banner
                try:
                    banner = sock.recv(1024).decode('utf-8', errors='ignore')
                    sock.close()
                    
                    result["available"] = True
                    result["details"]["banner"] = banner
                    
                    # Spróbuj wyodrębnić wersję z bannera
                    if "SSH" in banner:
                        version_match = re.search(r'SSH-\d+\.\d+-([^\s]+)', banner)
                        if version_match:
                            result["version"] = version_match.group(1)
                    
                    # Sprawdź rozpowszechnione implementacje SSH
                    ssh_implementations = [
                        "OpenSSH", "Dropbear", "PuTTY", "WinSCP", "TTSSH", 
                        "libssh", "paramiko", "crypto", "RomSShell"
                    ]
                    
                    for impl in ssh_implementations:
                        if impl.lower() in banner.lower():
                            result["details"]["implementation"] = impl
                            break
                    
                    # Większość serwerów SSH obsługuje SFTP
                    result["sftp_enabled"] = True
                    
                    # Zakładamy, że wykonywanie poleceń jest domyślnie możliwe
                    result["exec_enabled"] = True
                    
                except:
                    sock.close()
                    result["available"] = True
            else:
                sock.close()
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera SSH: {e}")
        
        return result

    def _check_ftp_server_detailed(self, address):
        """Szczegółowo sprawdza serwer FTP i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {},
            "anonymous_access": False
        }
        
        try:
            # Nawiąż połączenie z serwerem FTP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            conn_result = sock.connect_ex((address, 21))
            
            if conn_result == 0:
                # Port jest otwarty, spróbuj odczytać banner
                try:
                    banner = sock.recv(1024).decode('utf-8', errors='ignore')
                    sock.close()
                    
                    result["available"] = True
                    result["details"]["banner"] = banner
                    
                    # Spróbuj wyodrębnić wersję z bannera
                    version_match = re.search(r'FTP server \(([^)]+)\)', banner)
                    if version_match:
                        result["version"] = version_match.group(1)
                    
                    # Sprawdź implementację FTP
                    ftp_implementations = [
                        "FileZilla", "vsftpd", "ProFTPD", "Pure-FTPd", "IIS FTP", 
                        "WU-FTPD", "NcFTPd", "CerberusFTP"
                    ]
                    
                    for impl in ftp_implementations:
                        if impl.lower() in banner.lower():
                            result["details"]["implementation"] = impl
                            break
                    
                    # Sprawdź dostęp anonimowy
                    try:
                        import ftplib
                        ftp = ftplib.FTP()
                        ftp.connect(address, 21, timeout=2)
                        ftp.login('anonymous', 'anonymous@example.com')
                        result["anonymous_access"] = True
                        ftp.quit()
                    except:
                        # Dostęp anonimowy niedostępny
                        pass
                    
                except:
                    sock.close()
                    result["available"] = True
            else:
                sock.close()
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera FTP: {e}")
        
        return result

    def _check_smb_server_detailed(self, address):
        """Szczegółowo sprawdza serwer SMB/CIFS i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {},
            "shares": []
        }
        
        # Sprawdź czy porty są otwarte
        port_445 = self.check_port_open(address, 445)
        port_139 = self.check_port_open(address, 139)
        
        if not port_445 and not port_139:
            return result
        
        result["available"] = True
        result["details"]["port_445"] = port_445
        result["details"]["port_139"] = port_139
        
        # W pełnej implementacji można użyć biblioteki do wykrywania udziałów SMB
        # Na przykład impacket, pysmb lub smbprotocol
        # Tutaj uproszczone rozwiązanie
        
        # Popularne nazwy udziałów SMB do sprawdzenia
        common_shares = ["public", "share", "docs", "files", "backup", 
                         "media", "video", "music", "photos", "home"]
        
        # Dodaj typowe udziały administracyjne
        result["shares"] = ["ADMIN$", "IPC$", "C$"]
        
        # Dodaj również popularne udziały
        for share in common_shares:
            result["shares"].append(share)
        
        return result

    def _check_rtsp_server_detailed(self, address, port=554):
        """Szczegółowo sprawdza serwer RTSP i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {},
            "url": f"rtsp://{address}:{port}",
            "can_record": True
        }
        
        try:
            # Sprawdź czy port jest otwarty
            if not self.check_port_open(address, port):
                return result
            
            # Próba nawiązania połączenia z serwerem RTSP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((address, port))
            
            # Wyślij zapytanie OPTIONS RTSP
            request = f"OPTIONS rtsp://{address}:{port} RTSP/1.0\r\nCSeq: 1\r\n\r\n"
            sock.send(request.encode())
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            sock.close()
            
            # Analizuj odpowiedź
            if "RTSP/1.0" in response:
                result["available"] = True
                result["details"]["response"] = response
                
                # Pobierz dostępne metody
                if "Public:" in response:
                    public_line = [line for line in response.split('\r\n') if line.startswith('Public:')]
                    if public_line:
                        methods_str = public_line[0].split(':', 1)[1].strip()
                        methods = [m.strip() for m in methods_str.split(',')]
                        result["details"]["methods"] = methods
                        
                        # Sprawdź obsługiwane funkcje
                        result["can_record"] = "RECORD" in methods
                
                # Sprawdź popularne ścieżki kamer
                common_paths = ["live", "stream", "ch1", "cam1", "media", "video"]
                
                for path in common_paths:
                    result["details"]["stream_paths"] = common_paths
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera RTSP: {e}")
        
        return result

    def _check_telnet_server(self, address):
        """Sprawdza serwer Telnet i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {}
        }
        
        try:
            # Sprawdź czy port jest otwarty
            if not self.check_port_open(address, 23):
                return result
            
            # Próba nawiązania połączenia z serwerem Telnet
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((address, 23))
            
            # Odczytaj banner
            banner = sock.recv(1024).decode('utf-8', errors='ignore')
            sock.close()
            
            result["available"] = True
            result["details"]["banner"] = banner
            
            # Spróbuj określić system z bannera
            if "linux" in banner.lower():
                result["details"]["os"] = "Linux"
            elif "windows" in banner.lower():
                result["details"]["os"] = "Windows"
            elif "cisco" in banner.lower():
                result["details"]["os"] = "Cisco IOS"
            elif "dd-wrt" in banner.lower():
                result["details"]["os"] = "DD-WRT"
            elif "openwrt" in banner.lower():
                result["details"]["os"] = "OpenWRT"
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera Telnet: {e}")
        
        return result

    def _check_smtp_server(self, address, port=25):
        """Sprawdza serwer SMTP i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {}
        }
        
        try:
            # Sprawdź czy port jest otwarty
            if not self.check_port_open(address, port):
                return result
            
            # Próba nawiązania połączenia z serwerem SMTP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((address, port))
            
            # Odczytaj banner
            banner = sock.recv(1024).decode('utf-8', errors='ignore')
            
            # Wyślij EHLO dla sprawdzenia dostępnych opcji
            sock.send(b"EHLO test.com\r\n")
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            
            sock.send(b"QUIT\r\n")
            sock.close()
            
            result["available"] = True
            result["details"]["banner"] = banner
            result["details"]["ehlo_response"] = response
            
            # Wyodrębnij wersję serwera
            if "ESMTP" in banner:
                result["version"] = "ESMTP"
            
            # Wyodrębnij typ serwera
            for smtp_type in ["Postfix", "Sendmail", "Exchange", "Exim", "qmail"]:
                if smtp_type.lower() in banner.lower() or smtp_type.lower() in response.lower():
                    result["details"]["server_type"] = smtp_type
                    break
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera SMTP: {e}")
        
        return result

    def _check_pop3_server(self, address, port=110):
        """Sprawdza serwer POP3 i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {}
        }
        
        try:
            # Sprawdź czy port jest otwarty
            if not self.check_port_open(address, port):
                return result
            
            # Próba nawiązania połączenia z serwerem POP3
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((address, port))
            
            # Odczytaj banner
            banner = sock.recv(1024).decode('utf-8', errors='ignore')
            
            # Wyślij CAPA dla sprawdzenia możliwości
            sock.send(b"CAPA\r\n")
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            
            sock.send(b"QUIT\r\n")
            sock.close()
            
            result["available"] = True
            result["details"]["banner"] = banner
            result["details"]["capabilities"] = response
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera POP3: {e}")
        
        return result
    def _check_imap_server(self, address, port=143):
        """Sprawdza serwer IMAP i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {}
        }
        
        try:
            # Sprawdź czy port jest otwarty
            if not self.check_port_open(address, port):
                return result
            
            # Próba nawiązania połączenia z serwerem IMAP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((address, port))
            
            # Odczytaj banner
            banner = sock.recv(1024).decode('utf-8', errors='ignore')
            
            # Wyślij CAPABILITY dla sprawdzenia możliwości
            sock.send(b"A001 CAPABILITY\r\n")
            response = sock.recv(1024).decode('utf-8', errors='ignore')
            
            sock.send(b"A002 LOGOUT\r\n")
            sock.close()
            
            result["available"] = True
            result["details"]["banner"] = banner
            result["details"]["capabilities"] = response
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera IMAP: {e}")
        
        return result

    def _check_dns_server(self, address):
        """Sprawdza serwer DNS i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {}
        }
        
        try:
            # Sprawdź czy port jest otwarty (UDP)
            if not self.check_port_open(address, 53, protocol="udp"):
                return result
            
            # Spróbuj wykonać zapytanie DNS
            import socket
            request = b"\x00\x01\x01\x00\x00\x01\x00\x00\x00\x00\x00\x00\x03www\x06google\x03com\x00\x00\x01\x00\x01"
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            sock.settimeout(2)
            sock.sendto(request, (address, 53))
            
            response = sock.recv(1024)
            sock.close()
            
            if response:
                result["available"] = True
                result["details"]["response_size"] = len(response)
                
                # Sprawdź czy odpowiedź zawiera poprawne dane
                if len(response) > 12:  # Minimalna długość nagłówka DNS
                    result["details"]["valid_response"] = True
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera DNS: {e}")
        
        return result

    def _check_rdp_server(self, address):
        """Sprawdza serwer RDP i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {}
        }
        
        try:
            # Sprawdź czy port jest otwarty
            if not self.check_port_open(address, 3389):
                return result
            
            # Próba nawiązania połączenia z serwerem RDP
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((address, 3389))
            
            # Wysyłamy minimalne dane negocjacyjne RDP
            # To jest prosty pakiet negocjacyjny protokołu RDP
            # W pełnej implementacji należałoby użyć odpowiedniej biblioteki
            
            # Zakończ połączenie
            sock.close()
            
            # Jeśli port jest otwarty, najprawdopodobniej jest to RDP
            result["available"] = True
            result["details"]["server_type"] = "RDP"
            
        except Exception as e:
            print(f"Błąd podczas analizy serwera RDP: {e}")
        
        return result

    def _check_vnc_server(self, address):
        """Sprawdza serwer VNC i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {}
        }
        
        try:
            # Sprawdź czy port jest otwarty
            if not self.check_port_open(address, 5900):
                return result
            
            # Próba nawiązania połączenia z serwerem VNC
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((address, 5900))
            
            # Odczytaj banner VNC (protokół RFC 6143)
            banner = sock.recv(1024).decode('utf-8', errors='ignore')
            sock.close()
            
            if banner.startswith("RFB "):
                result["available"] = True
                result["details"]["banner"] = banner
                
                # Wyodrębnij wersję protokołu
                version_match = re.search(r'RFB (\d+\.\d+)', banner)
                if version_match:
                    result["version"] = version_match.group(1)
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera VNC: {e}")
        
        return result

    def _check_mqtt_server(self, address, port=1883):
        """Sprawdza serwer MQTT i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {}
        }
        
        try:
            # Sprawdź czy port jest otwarty
            if not self.check_port_open(address, port):
                return result
            
            # Próba nawiązania połączenia z serwerem MQTT
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            sock.connect((address, port))
            
            # Wyślij pakiet CONNECT zgodny z MQTT v3.1.1
            # Format pakietu MQTT jest binarny, więc musimy go ręcznie sformułować
            
            # Nagłówek CONNECT (typ pakietu = 1, flagi = 0)
            packet = bytearray([0x10])
            
            # Długość pozostałej części pakietu
            remaining_length = 12  # Minimalna długość
            packet.append(remaining_length)
            
            # Protokół: MQTT
            packet.extend(b"\x00\x04MQTT")
            
            # Wersja protokołu: 4 (dla MQTT v3.1.1)
            packet.append(0x04)
            
            # Flagi połączenia (Clean Session)
            packet.append(0x02)
            
            # Keep Alive (60 sekund)
            packet.extend(b"\x00\x3C")
            
            # Pusty Client ID
            packet.extend(b"\x00\x00")
            
            # Wysyłamy pakiet
            sock.send(packet)
            
            # Odbieramy odpowiedź (pakiet CONNACK)
            response = sock.recv(1024)
            sock.close()
            
            # Sprawdzamy typ pakietu (powinien być 0x20 dla CONNACK)
            if len(response) >= 2 and response[0] == 0x20:
                result["available"] = True
                result["details"]["response"] = [hex(b) for b in response]
                
                # Sprawdzamy kod powrotu
                if len(response) >= 4:
                    return_code = response[3]
                    if return_code == 0:
                        result["details"]["connection_accepted"] = True
                    else:
                        result["details"]["connection_accepted"] = False
                        result["details"]["return_code"] = return_code
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera MQTT: {e}")
        
        return result

    def _check_snmp_server_detailed(self, address):
        """Szczegółowo sprawdza serwer SNMP i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {},
            "get_enabled": False,
            "set_enabled": False
        }
        
        # Sprawdź czy port jest otwarty
        if not self.check_port_open(address, 161, protocol="udp"):
            return result
        
        # Jeśli dostępny jest moduł pysnmp, użyj go do testów
        if SNMP_AVAILABLE:
            try:
                # Sprawdź obsługę SNMP GET
                get_result = self.query_snmp(address)
                if get_result.get("success", False):
                    result["available"] = True
                    result["get_enabled"] = True
                    result["version"] = "v1/v2c"
                    
                    if "system_info" in get_result:
                        result["details"]["system_info"] = get_result["system_info"]
                
                # Sprawdź obsługę SNMP v3 (bardziej zaawansowany test)
                # Ta część została pominięta dla uproszczenia
            
            except Exception as e:
                print(f"Błąd podczas analizy SNMP z pysnmp: {e}")
        
        # Jeśli nie ma pysnmp, spróbuj prostego testu UDP
        else:
            try:
                # Przygotuj proste zapytanie SNMP GET
                # To jest uproszczona wersja zapytania SNMP v1 o sysDescr.0
                get_request = bytes.fromhex('302602010004067075626c6963a01904170403')
                
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.settimeout(2)
                sock.sendto(get_request, (address, 161))
                
                try:
                    response, _ = sock.recvfrom(1024)
                    if response:
                        result["available"] = True
                        result["get_enabled"] = True
                        result["version"] = "v1/v2c"
                except socket.timeout:
                    pass
                
                sock.close()
            
            except Exception as e:
                print(f"Błąd podczas prostego testu SNMP: {e}")
        
        return result

    def _check_ipp_server(self, address):
        """Sprawdza serwer IPP (Internet Printing Protocol) i zwraca informacje o nim."""
        result = {
            "available": False,
            "version": None,
            "details": {},
            "supports_status": False,
            "supports_jobs": False
        }
        
        try:
            # Sprawdź czy port jest otwarty
            if not self.check_port_open(address, 631):
                return result
            
            # Sprawdź dostępność HTTP na porcie IPP
            import urllib.request
            import urllib.error
            
            # Najpierw spróbuj uzyskać stronę statusu drukarki
            url = f"http://{address}:631/printers"
            
            try:
                response = urllib.request.urlopen(url, timeout=2)
                if response.getcode() == 200:
                    result["available"] = True
                    result["supports_status"] = True
                    
                    # Sprawdź wersję IPP z nagłówków
                    server = response.getheader("Server", "")
                    if "IPP" in server:
                        result["version"] = server
                    
                    # Sprawdź stronę z zadaniami
                    try:
                        jobs_url = f"http://{address}:631/jobs"
                        jobs_response = urllib.request.urlopen(jobs_url, timeout=1)
                        if jobs_response.getcode() == 200:
                            result["supports_jobs"] = True
                    except:
                        pass
            
            except (urllib.error.URLError, urllib.error.HTTPError):
                # Brak interfejsu WWW nie oznacza braku IPP
                pass
            
            # Sprawdź bezpośrednio IPP
            try:
                # To byłoby prawdziwe zapytanie IPP, ale jest skomplikowane do implementacji
                # bez dedykowanej biblioteki, więc tu tylko zaznaczamy, że port jest otwarty
                if not result["available"] and self.check_port_open(address, 631):
                    result["available"] = True
            except:
                pass
        
        except Exception as e:
            print(f"Błąd podczas analizy serwera IPP: {e}")
        
        return result

    def _determine_device_type(self, services):
        """Określa typ urządzenia na podstawie wykrytych usług."""
        # Liczniki różnych typów urządzeń
        device_scores = {
            "router": 0,
            "printer": 0,
            "camera": 0,
            "nas": 0,
            "computer": 0,
            "server": 0,
            "iot": 0,
            "media": 0
        }
        
        # Sprawdź usługi wskazujące na konkretne typy urządzeń
        for service in services:
            service_name = service.get("service")
            
            if not service_name:
                continue
            
            # Routery często mają HTTP i usługi zarządzania
            if service_name in ["HTTP", "HTTPS"]:
                if "router" in str(service.get("details", {})).lower() or "gateway" in str(service.get("details", {})).lower():
                    device_scores["router"] += 3
                
                if "device_type" in service.get("details", {}) and service["details"]["device_type"] == "router":
                    device_scores["router"] += 5
            
            # Drukarki często mają IPP, LPD lub Raw Printing
            if service_name in ["IPP", "Printer (Raw)"]:
                device_scores["printer"] += 5
            
            if service_name == "LPD":
                device_scores["printer"] += 4
            
            # Kamery często mają RTSP i HTTP
            if service_name == "RTSP":
                device_scores["camera"] += 5
            
            if service_name in ["HTTP", "HTTPS"] and "camera" in str(service.get("details", {})).lower():
                device_scores["camera"] += 3
            
            # NAS często mają SMB, FTP, HTTP
            if service_name in ["SMB/CIFS", "NFS"]:
                device_scores["nas"] += 3
            
            if service_name == "FTP" and ("storage" in str(service.get("details", {})).lower() or "nas" in str(service.get("details", {})).lower()):
                device_scores["nas"] += 3
            
            # Komputery często mają SSH, RDP, SMB, HTTP
            if service_name in ["SSH", "RDP", "VNC"]:
                device_scores["computer"] += 3
                
            # Serwery często mają wiele usług
            if service_name in ["HTTP", "HTTPS", "FTP", "SSH", "SMTP", "IMAP", "POP3", "DNS"]:
                device_scores["server"] += 1
            
            # IoT często mają HTTP, MQTT
            if service_name == "MQTT":
                device_scores["iot"] += 5
            
            # Media devices often have DLNA, HTTP
            if service_name == "DLNA":
                device_scores["media"] += 5
            
            if service_name in ["HTTP", "HTTPS"] and "media" in str(service.get("details", {})).lower():
                device_scores["media"] += 3
        
        # Dodaj punkty na podstawie portów
        for service in services:
            port = service.get("port")
            
            if not port:
                continue
            
            # Porty specyficzne dla drukarek
            if port in [515, 631, 9100]:
                device_scores["printer"] += 2
            
            # Porty specyficzne dla kamer
            if port in [554, 8554, 10554]:
                device_scores["camera"] += 2
            
            # Porty specyficzne dla komputerów
            if port in [3389, 5900]:
                device_scores["computer"] += 2
            
            # Porty specyficzne dla routerów
            if port in [80, 443, 8080, 8443]:
                device_scores["router"] += 1
            
            # Porty specyficzne dla serwerów
            if port in [21, 22, 25, 53, 110, 143, 993, 995]:
                device_scores["server"] += 1
            
            # Porty specyficzne dla IoT
            if port in [1883, 8883]:
                device_scores["iot"] += 2
        
        # Wybierz typ z najwyższym wynikiem
        if not device_scores:
            return "unknown"
        
        return max(device_scores.items(), key=lambda x: x[1])[0]

    def _get_device_specific_operations(self, address, device_type):
        """Zwraca operacje specyficzne dla typu urządzenia."""
        operations = []
        
        if device_type == "router":
            # Operacje specyficzne dla routera
            router_ops = self._check_router_operations(address)
            operations.extend(router_ops)
        
        elif device_type == "printer":
            # Operacje specyficzne dla drukarki
            printer_ops = self._check_printer_operations(address)
            operations.extend(printer_ops)
        
        elif device_type == "camera":
            # Operacje specyficzne dla kamery
            camera_ops = self._check_camera_operations(address)
            operations.extend(camera_ops)
        
        elif device_type == "nas":
            # Operacje specyficzne dla NAS
            nas_ops = self._check_nas_operations(address)
            operations.extend(nas_ops)
        
        elif device_type == "computer":
            # Operacje specyficzne dla komputera
            computer_ops = self._check_computer_operations(address)
            operations.extend(computer_ops)
        
        elif device_type == "iot":
            # Operacje specyficzne dla IoT
            iot_ops = self._check_iot_operations(address)
            operations.extend(iot_ops)
        
        elif device_type == "media":
            # Operacje specyficzne dla urządzeń medialnych
            media_ops = self._check_media_operations(address)
            operations.extend(media_ops)
        
        return operations

    def _check_router_operations(self, address):
        """Sprawdza operacje specyficzne dla routera."""
        operations = []
        
        try:
            # Podstawowe operacje zarządzania routerem
            admin_interface = self._find_router_admin(address)
            
            if admin_interface:
                operations.append({
                    "name": "Panel administracyjny",
                    "description": "Otwórz panel zarządzania routerem",
                    "available": True,
                    "url": admin_interface,
                    "operation": "admin_panel"
                })
            
            # Sprawdź wsparcie UPnP
            if self._check_upnp_support(address):
                operations.append({
                    "name": "Zarządzanie portami UPnP",
                    "description": "Skonfiguruj przekierowanie portów przez UPnP",
                    "available": True,
                    "operation": "upnp_port_mapping"
                })
            
            # Sprawdź SSH/Telnet - często dostępne w routerach
            if self.check_port_open(address, 22):
                operations.append({
                    "name": "Zaawansowana konfiguracja SSH",
                    "description": "Konfiguruj router przez SSH",
                    "available": True,
                    "protocol": "ssh",
                    "port": 22
                })
            
            if self.check_port_open(address, 23):
                operations.append({
                    "name": "Zaawansowana konfiguracja Telnet",
                    "description": "Konfiguruj router przez Telnet",
                    "available": True,
                    "protocol": "telnet",
                    "port": 23
                })
            
            # Sprawdź API SOAP/XML-RPC - popularne w routerach
            soap_available = self._check_router_soap_api(address)
            if soap_available:
                operations.append({
                    "name": "API konfiguracji",
                    "description": "Konfiguruj router przez API",
                    "available": True,
                    "protocol": "soap",
                    "url": soap_available
                })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania operacji routera: {e}")
        
        return operations

    def _check_printer_operations(self, address):
        """Sprawdza operacje specyficzne dla drukarki."""
        operations = []
        
        try:
            # Podstawowe operacje drukarki
            printer_web = self._find_printer_web(address)
            
            if printer_web:
                operations.append({
                    "name": "Panel drukarki",
                    "description": "Otwórz panel zarządzania drukarką",
                    "available": True,
                    "url": printer_web,
                    "operation": "printer_panel"
                })
            
            # Sprawdź obsługę drukowania
            if self.check_port_open(address, 9100):
                operations.append({
                    "name": "Drukowanie RAW",
                    "description": "Drukuj bezpośrednio do portu",
                    "available": True,
                    "protocol": "raw",
                    "port": 9100
                })
            
            if self.check_port_open(address, 631):
                operations.append({
                    "name": "Drukowanie IPP",
                    "description": "Drukuj przez IPP",
                    "available": True,
                    "protocol": "ipp",
                    "port": 631
                })
            
            # Sprawdź obsługę skanowania - popularne drukarki oferują skanowanie przez sieć
            if self.check_port_open(address, 9220) or self.check_port_open(address, 9290):
                operations.append({
                    "name": "Skanowanie",
                    "description": "Skanuj dokumenty",
                    "available": True,
                    "operation": "scan"
                })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania operacji drukarki: {e}")
        
        return operations

    def _check_camera_operations(self, address):
        """Sprawdza operacje specyficzne dla kamery."""
        operations = []
        
        try:
            # Podstawowe operacje kamery
            camera_web = self._find_camera_web(address)
            
            if camera_web:
                operations.append({
                    "name": "Panel kamery",
                    "description": "Otwórz panel zarządzania kamerą",
                    "available": True,
                    "url": camera_web,
                    "operation": "camera_panel"
                })
            
            # Sprawdź obsługę RTSP
            rtsp_support = self._check_rtsp_support(address)
            if rtsp_support.get("available", False):
                operations.append({
                    "name": "Strumień RTSP",
                    "description": "Oglądaj strumień wideo przez RTSP",
                    "available": True,
                    "protocol": "rtsp",
                    "url": rtsp_support.get("url", f"rtsp://{address}:554")
                })
            
            # Sprawdź obsługę ONVIF
            onvif_support = self._check_onvif_support(address)
            if onvif_support.get("available", False):
                operations.append({
                    "name": "Sterowanie PTZ",
                    "description": "Steruj ruchem kamery (pan, tilt, zoom)",
                    "available": onvif_support.get("ptz", False),
                    "protocol": "onvif",
                    "operation": "ptz_control"
                })
                
                operations.append({
                    "name": "Konfiguracja ONVIF",
                    "description": "Konfiguruj kamerę przez ONVIF",
                    "available": True,
                    "protocol": "onvif",
                    "operation": "onvif_config"
                })
            
            # Sprawdź obsługę MJPEG
            mjpeg_support = self._check_mjpeg_support(address)
            if mjpeg_support.get("available", False):
                operations.append({
                    "name": "Strumień MJPEG",
                    "description": "Oglądaj strumień MJPEG",
                    "available": True,
                    "protocol": "http",
                    "url": mjpeg_support.get("url")
                })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania operacji kamery: {e}")
        
        return operations

    def _check_nas_operations(self, address):
        """Sprawdza operacje specyficzne dla NAS."""
        operations = []
        
        try:
            # Podstawowe operacje NAS
            nas_web = self._find_nas_web(address)
            
            if nas_web:
                operations.append({
                    "name": "Panel administracyjny NAS",
                    "description": "Otwórz panel zarządzania serwerem NAS",
                    "available": True,
                    "url": nas_web,
                    "operation": "nas_panel"
                })
            
            # Sprawdź obsługę SMB/CIFS
            if self.check_port_open(address, 445) or self.check_port_open(address, 139):
                operations.append({
                    "name": "Udziały sieciowe",
                    "description": "Przeglądaj udziały plikowe SMB/CIFS",
                    "available": True,
                    "protocol": "smb",
                    "operation": "browse_shares"
                })
            
            # Sprawdź obsługę FTP
            if self.check_port_open(address, 21):
                operations.append({
                    "name": "Transfer FTP",
                    "description": "Przesyłaj pliki przez FTP",
                    "available": True,
                    "protocol": "ftp",
                    "port": 21
                })
            
            # Sprawdź obsługę NFS
            if self.check_port_open(address, 2049):
                operations.append({
                    "name": "Udziały NFS",
                    "description": "Montuj udziały NFS",
                    "available": True,
                    "protocol": "nfs",
                    "port": 2049
                })
            
            # Sprawdź obsługę DLNA/UPnP Media Server
            if self.check_port_open(address, 8200):
                operations.append({
                    "name": "Strumieniowanie mediów",
                    "description": "Odtwarzaj media przez DLNA/UPnP",
                    "available": True,
                    "protocol": "dlna",
                    "operation": "stream_media"
                })
            
            # Sprawdź obsługę Time Machine (dla urządzeń Apple)
            if self.check_port_open(address, 548):
                operations.append({
                    "name": "Time Machine",
                    "description": "Kopia zapasowa Time Machine",
                    "available": True,
                    "protocol": "afp",
                    "operation": "time_machine_backup"
                })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania operacji NAS: {e}")
        
        return operations

    def _check_computer_operations(self, address):
        """Sprawdza operacje specyficzne dla komputera."""
        operations = []
        
        try:
            # Podstawowe operacje komputera
            
            # Sprawdź obsługę zdalnego pulpitu
            if self.check_port_open(address, 3389):
                operations.append({
                    "name": "Pulpit zdalny",
                    "description": "Połącz się z pulpitem zdalnym (RDP)",
                    "available": True,
                    "protocol": "rdp",
                    "port": 3389
                })
            
            # Sprawdź obsługę VNC
            if self.check_port_open(address, 5900):
                operations.append({
                    "name": "VNC",
                    "description": "Połącz się przez VNC",
                    "available": True,
                    "protocol": "vnc",
                    "port": 5900
                })
            
            # Sprawdź obsługę SSH
            if self.check_port_open(address, 22):
                operations.append({
                    "name": "Połączenie SSH",
                    "description": "Wykonuj polecenia przez SSH",
                    "available": True,
                    "protocol": "ssh",
                    "port": 22
                })
            
            # Sprawdź obsługę SMB/CIFS
            if self.check_port_open(address, 445) or self.check_port_open(address, 139):
                operations.append({
                    "name": "Udostępnione pliki",
                    "description": "Przeglądaj udostępnione pliki",
                    "available": True,
                    "protocol": "smb",
                    "operation": "browse_shares"
                })
            
            # Sprawdź Web Server
            if self.check_port_open(address, 80) or self.check_port_open(address, 8080):
                operations.append({
                    "name": "Serwer WWW",
                    "description": "Przeglądaj serwowany kontent",
                    "available": True,
                    "protocol": "http",
                    "operation": "view_web_content"
                })
            
            # Sprawdź Wake-on-LAN
            operations.append({
                "name": "Wake-on-LAN",
                "description": "Zdalne włączanie komputera",
                "available": True,
                "protocol": "wol",
                "operation": "wake_on_lan"
            })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania operacji komputera: {e}")
        
        return operations
    def _check_iot_operations(self, address):
        """Sprawdza operacje specyficzne dla urządzeń IoT."""
        operations = []
        
        try:
            # Podstawowe operacje IoT
            iot_web = self._find_iot_web(address)
            
            if iot_web:
                operations.append({
                    "name": "Interfejs urządzenia",
                    "description": "Otwórz interfejs zarządzania urządzeniem IoT",
                    "available": True,
                    "url": iot_web,
                    "operation": "iot_interface"
                })
            
            # Sprawdź obsługę MQTT
            if self.check_port_open(address, 1883) or self.check_port_open(address, 8883):
                operations.append({
                    "name": "Komunikacja MQTT",
                    "description": "Komunikuj się przez MQTT",
                    "available": True,
                    "protocol": "mqtt",
                    "operation": "mqtt_communication"
                })
            
            # Sprawdź obsługę REST API
            rest_api = self._check_rest_api(address)
            if rest_api:
                operations.append({
                    "name": "API urządzenia",
                    "description": "Steruj urządzeniem przez API",
                    "available": True,
                    "protocol": "http",
                    "url": rest_api,
                    "operation": "api_control"
                })
            
            # Sprawdź integrację z popularnymi systemami IoT
            if self._check_iot_integration(address, "homekit"):
                operations.append({
                    "name": "HomeKit",
                    "description": "Steruj przez Apple HomeKit",
                    "available": True,
                    "protocol": "homekit",
                    "operation": "homekit_control"
                })
            
            if self._check_iot_integration(address, "alexa"):
                operations.append({
                    "name": "Amazon Alexa",
                    "description": "Steruj przez Amazon Alexa",
                    "available": True,
                    "protocol": "alexa",
                    "operation": "alexa_control"
                })
            
            if self._check_iot_integration(address, "google"):
                operations.append({
                    "name": "Google Home",
                    "description": "Steruj przez Google Home",
                    "available": True,
                    "protocol": "google_home",
                    "operation": "google_home_control"
                })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania operacji IoT: {e}")
        
        return operations

    def _check_media_operations(self, address):
        """Sprawdza operacje specyficzne dla urządzeń medialnych."""
        operations = []
        
        try:
            # Podstawowe operacje urządzeń medialnych
            media_web = self._find_media_web(address)
            
            if media_web:
                operations.append({
                    "name": "Interfejs urządzenia",
                    "description": "Otwórz interfejs urządzenia medialnego",
                    "available": True,
                    "url": media_web,
                    "operation": "media_interface"
                })
            
            # Sprawdź obsługę DLNA/UPnP
            if self._check_dlna_support(address):
                operations.append({
                    "name": "Przeglądaj media",
                    "description": "Przeglądaj zawartość przez DLNA/UPnP",
                    "available": True,
                    "protocol": "dlna",
                    "operation": "browse_media"
                })
                
                operations.append({
                    "name": "Odtwarzaj media",
                    "description": "Odtwarzaj zawartość przez DLNA/UPnP",
                    "available": True,
                    "protocol": "dlna",
                    "operation": "play_media"
                })
            
            # Sprawdź obsługę AirPlay
            if self._check_airplay_support(address):
                operations.append({
                    "name": "AirPlay",
                    "description": "Strumieniuj przez AirPlay",
                    "available": True,
                    "protocol": "airplay",
                    "operation": "airplay_streaming"
                })
            
            # Sprawdź obsługę Chromecast
            if self._check_chromecast_support(address):
                operations.append({
                    "name": "Chromecast",
                    "description": "Strumieniuj przez Chromecast",
                    "available": True,
                    "protocol": "chromecast",
                    "operation": "chromecast_streaming"
                })
            
            # Sprawdź obsługę Spotify Connect
            if self._check_spotify_connect_support(address):
                operations.append({
                    "name": "Spotify Connect",
                    "description": "Steruj odtwarzaniem Spotify",
                    "available": True,
                    "protocol": "spotify",
                    "operation": "spotify_control"
                })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania operacji urządzenia medialnego: {e}")
        
        return operations

    def _check_network_protocols(self, address, capabilities, device_info):
        """Sprawdza obsługiwane protokoły sieciowe na urządzeniu."""
        try:
            # Lista już sprawdzonych portów z wcześniejszych testów
            checked_ports = set(device_info.get("open_ports", []))
            
            # Sprawdź dodatkowe protokoły, które nie zostały jeszcze sprawdzone
            
            # SSDP/UPnP Discovery
            if self._check_upnp_discovery(address):
                device_info.setdefault("protocols", []).append("UPnP")
                capabilities.append({
                    "name": "Wykrywanie UPnP",
                    "description": "Urządzenie obsługuje wykrywanie UPnP",
                    "available": True,
                    "protocol": "upnp",
                    "operation": "upnp_discovery"
                })
            
            # mDNS/Bonjour
            if self._check_mdns_support(address):
                device_info.setdefault("protocols", []).append("mDNS")
                capabilities.append({
                    "name": "Wykrywanie mDNS",
                    "description": "Urządzenie obsługuje wykrywanie mDNS/Bonjour",
                    "available": True,
                    "protocol": "mdns",
                    "operation": "mdns_discovery"
                })
            
            # WS-Discovery
            if self._check_ws_discovery(address):
                device_info.setdefault("protocols", []).append("WS-Discovery")
                capabilities.append({
                    "name": "Wykrywanie WS",
                    "description": "Urządzenie obsługuje Web Services Discovery",
                    "available": True,
                    "protocol": "ws-discovery",
                    "operation": "ws_discovery"
                })
            
            # LLDP
            if self._check_lldp_support(address):
                device_info.setdefault("protocols", []).append("LLDP")
                capabilities.append({
                    "name": "LLDP",
                    "description": "Urządzenie obsługuje Link Layer Discovery Protocol",
                    "available": True,
                    "protocol": "lldp",
                    "operation": "lldp_discovery"
                })
            
            # CDP
            if self._check_cdp_support(address):
                device_info.setdefault("protocols", []).append("CDP")
                capabilities.append({
                    "name": "CDP",
                    "description": "Urządzenie obsługuje Cisco Discovery Protocol",
                    "available": True,
                    "protocol": "cdp",
                    "operation": "cdp_discovery"
                })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania protokołów sieciowych: {e}")

    def _check_power_management_operations(self, address, connection_type):
        """Sprawdza dostępne operacje zarządzania zasilaniem."""
        operations = []
        
        # Ta funkcja jest zaślepką - w pełnej implementacji należałoby sprawdzić
        # obsługę Wake-on-LAN, ACPI, UPnP i innych protokołów zarządzania zasilaniem
        
        # Dla urządzeń sieciowych zawsze dodajemy operację Wake-on-LAN
        if connection_type == "wifi":
            operations.append({
                "name": "Wake-on-LAN",
                "description": "Wybudź urządzenie przez sieć",
                "available": True,
                "operation": "wake_on_lan"
            })
        
        return operations

    def _check_discovery_services(self, address, capabilities, device_info):
        """Sprawdza usługi wykrywania urządzeń."""
        # Ta funkcja jest zaślepką - w pełnej implementacji należałoby sprawdzić
        # obsługę UPnP, SSDP, mDNS/Bonjour i innych protokołów wykrywania urządzeń
        pass

    def _check_wifi_signal(self, address):
        """Sprawdza siłę sygnału WiFi dla urządzenia (jeśli jest bezprzewodowe)."""
        result = {
            "signal_strength": None,
            "signal_quality": None
        }
        
        # To jest funkcja uproszczona, w rzeczywistości wymagałaby dostępu
        # do routera lub innych narzędzi sieciowych
        
        return result

    def _check_network_config_options(self, address, device_type):
        """Sprawdza dostępne opcje konfiguracji sieciowej."""
        operations = []
        
        # Te operacje będą zależeć od typu urządzenia
        if device_type == "router":
            operations.append({
                "name": "Konfiguracja sieci",
                "description": "Skonfiguruj ustawienia sieciowe",
                "available": True,
                "operation": "network_config"
            })
            
            operations.append({
                "name": "Konfiguracja WiFi",
                "description": "Skonfiguruj ustawienia bezprzewodowe",
                "available": True,
                "operation": "wifi_config"
            })
            
            operations.append({
                "name": "Przekierowanie portów",
                "description": "Skonfiguruj przekierowanie portów",
                "available": True,
                "operation": "port_forwarding"
            })
        
        elif device_type in ["computer", "server", "nas"]:
            operations.append({
                "name": "Konfiguracja IP",
                "description": "Skonfiguruj ustawienia IP",
                "available": True,
                "operation": "ip_config"
            })
            
            operations.append({
                "name": "Konfiguracja DNS",
                "description": "Skonfiguruj ustawienia DNS",
                "available": True,
                "operation": "dns_config"
            })
        
        return operations

    def _check_streaming_services(self, address):
        """Sprawdza obsługę usług strumieniowania mediów."""
        operations = []
        
        # Sprawdź obsługę DLNA/UPnP
        if self._check_dlna_support(address):
            operations.append({
                "name": "Strumieniowanie DLNA",
                "description": "Strumieniuj media przez DLNA/UPnP",
                "available": True,
                "protocol": "dlna",
                "operation": "dlna_streaming"
            })
        
        # Sprawdź obsługę RTSP
        rtsp_support = self._check_rtsp_support(address)
        if rtsp_support.get("available", False):
            operations.append({
                "name": "Strumieniowanie RTSP",
                "description": "Odbieraj strumień RTSP",
                "available": True,
                "protocol": "rtsp",
                "url": rtsp_support.get("url", f"rtsp://{address}:554")
            })
        
        # Sprawdź obsługę HLS
        hls_support = self._check_hls_support(address)
        if hls_support:
            operations.append({
                "name": "Strumieniowanie HLS",
                "description": "Odbieraj strumień HLS",
                "available": True,
                "protocol": "http",
                "url": hls_support
            })
        
        # Sprawdź obsługę DASH
        dash_support = self._check_dash_support(address)
        if dash_support:
            operations.append({
                "name": "Strumieniowanie DASH",
                "description": "Odbieraj strumień DASH",
                "available": True,
                "protocol": "http",
                "url": dash_support
            })
        
        return operations

    def _check_automation_options(self, address, capabilities, device_info):
        """Sprawdza opcje automatyzacji urządzenia."""
        try:
            # Sprawdź API REST
            rest_api = self._check_rest_api(address)
            if rest_api:
                capabilities.append({
                    "name": "API REST",
                    "description": "Steruj urządzeniem przez REST API",
                    "available": True,
                    "protocol": "http",
                    "url": rest_api
                })
            
            # Sprawdź API SOAP
            soap_api = self._check_soap_api(address)
            if soap_api:
                capabilities.append({
                    "name": "API SOAP",
                    "description": "Steruj urządzeniem przez SOAP API",
                    "available": True,
                    "protocol": "soap",
                    "url": soap_api
                })
            
            # Sprawdź integrację z systemami automatyzacji
            if self._check_iot_integration(address, "homekit"):
                capabilities.append({
                    "name": "HomeKit",
                    "description": "Integracja z Apple HomeKit",
                    "available": True,
                    "protocol": "homekit"
                })
            
            if self._check_iot_integration(address, "alexa"):
                capabilities.append({
                    "name": "Alexa",
                    "description": "Integracja z Amazon Alexa",
                    "available": True,
                    "protocol": "alexa"
                })
            
            if self._check_iot_integration(address, "google"):
                capabilities.append({
                    "name": "Google Home",
                    "description": "Integracja z Google Home",
                    "available": True,
                    "protocol": "google_home"
                })
            
            if self._check_iot_integration(address, "homeassistant"):
                capabilities.append({
                    "name": "Home Assistant",
                    "description": "Integracja z Home Assistant",
                    "available": True,
                    "protocol": "homeassistant"
                })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania opcji automatyzacji: {e}")

    def _check_onvif_support(self, address):
        """Sprawdza obsługę ONVIF w kamerze."""
        result = {
            "available": False,
            "ptz": False,
            "audio": False,
            "resolution": None,
            "operations": []
        }
        
        # Popularne porty ONVIF
        onvif_ports = [80, 8080, 8000, 8081]
        
        for port in onvif_ports:
            if not self.check_port_open(address, port):
                continue
            
            try:
                import http.client
                
                conn = http.client.HTTPConnection(address, port, timeout=2)
                
                # Wyślij proste zapytanie GetSystemDateAndTime do ONVIF
                soap_request = """<?xml version="1.0" encoding="UTF-8"?>
<s:Envelope xmlns:s="http://www.w3.org/2003/05/soap-envelope">
    <s:Body xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">
        <GetSystemDateAndTime xmlns="http://www.onvif.org/ver10/device/wsdl"/>
    </s:Body>
</s:Envelope>"""
                
                onvif_paths = ["/onvif/device_service", "/onvif/services", "/onvif"]
                
                for path in onvif_paths:
                    try:
                        conn.request("POST", path, body=soap_request, 
                                    headers={"Content-Type": "application/soap+xml"})
                        
                        response = conn.getresponse()
                        
                        if response.status == 200:
                            result["available"] = True
                            result["operations"].append({
                                "name": "Sterowanie ONVIF",
                                "description": "Steruj kamerą przez ONVIF",
                                "available": True,
                                "protocol": "onvif",
                                "url": f"http://{address}:{port}{path}"
                            })
                            
                            # Prosta heurystyka - większość kamer ONVIF obsługuje PTZ
                            result["ptz"] = True
                            result["operations"].append({
                                "name": "Sterowanie PTZ",
                                "description": "Steruj ruchem kamery",
                                "available": True,
                                "protocol": "onvif",
                                "operation": "ptz"
                            })
                            
                            # Wiele kamer ONVIF obsługuje audio
                            result["audio"] = True
                            result["operations"].append({
                                "name": "Audio",
                                "description": "Odbieraj/wysyłaj audio",
                                "available": True,
                                "protocol": "onvif",
                                "operation": "audio"
                            })
                            
                            # Przykładowa rozdzielczość
                            result["resolution"] = "1920x1080"
                            
                            break
                    except:
                        continue
                
                conn.close()
                
                # Jeśli znaleźliśmy ONVIF, zakończ pętlę
                if result["available"]:
                    break
            
            except Exception as e:
                print(f"Błąd podczas sprawdzania ONVIF na porcie {port}: {e}")
        
        return result

    def _check_rtsp_support(self, address):
        """Sprawdza obsługę protokołu RTSP."""
        result = {
            "available": False,
            "url": None,
            "has_audio": False
        }
        
        # Popularne porty RTSP
        rtsp_ports = [554, 8554, 10554, 1935]
        
        for port in rtsp_ports:
            if not self.check_port_open(address, port):
                continue
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)
                sock.connect((address, port))
                
                # Wyślij zapytanie OPTIONS RTSP
                request = f"OPTIONS rtsp://{address}:{port} RTSP/1.0\r\nCSeq: 1\r\n\r\n"
                sock.send(request.encode())
                response = sock.recv(1024).decode('utf-8', errors='ignore')
                sock.close()
                
                if "RTSP/1.0" in response:
                    result["available"] = True
                    result["url"] = f"rtsp://{address}:{port}"
                    
                    # Sprawdź obsługę audio (prosta heurystyka)
                    if "audio" in response.lower():
                        result["has_audio"] = True
                    
                    # Większość urządzeń RTSP będzie mieć jeden z tych popularnych ścieżek
                    for path in ["/cam/realmonitor", "/live", "/stream", "/video1", "/h264", "/img/video.sav"]:
                        result["url"] = f"rtsp://{address}:{port}{path}"
                    
                    break
            except Exception as e:
                print(f"Błąd podczas sprawdzania RTSP na porcie {port}: {e}")
        
        return result

    def _check_mjpeg_support(self, address):
        """Sprawdza obsługę MJPEG."""
        result = {
            "available": False,
            "url": None
        }
        
        # Popularne porty dla interfejsów HTTP
        http_ports = [80, 8080, 8000, 8081]
        
        for port in http_ports:
            if not self.check_port_open(address, port):
                continue
            
            # Popularne ścieżki MJPEG
            mjpeg_paths = [
                "/video/mjpg.cgi", 
                "/mjpeg", 
                "/mjpg/video.mjpg", 
                "/cgi-bin/mjpg/video.cgi",
                "/videostream.cgi", 
                "/videostream.asf", 
                "/video.mjpg"
            ]
            
            for path in mjpeg_paths:
                try:
                    import urllib.request
                    import urllib.error
                    
                    url = f"http://{address}:{port}{path}"
                    req = urllib.request.Request(url, method="HEAD")
                    
                    try:
                        response = urllib.request.urlopen(req, timeout=1)
                        content_type = response.getheader("Content-Type", "")
                        
                        if "multipart/x-mixed-replace" in content_type or "mjpeg" in content_type.lower():
                            result["available"] = True
                            result["url"] = url
                            return result
                    except:
                        continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania MJPEG na ścieżce {path}: {e}")
        
        return result

    def _check_camera_admin_interface(self, address):
        """Sprawdza panel administracyjny kamery."""
        result = {
            "available": False,
            "url": None,
            "operations": []
        }
        
        # Popularne porty dla interfejsów kamer
        http_ports = [80, 8080, 8000, 8081, 9000]
        
        for port in http_ports:
            if not self.check_port_open(address, port):
                continue
            
            # Popularne ścieżki do interfejsów kamer
            admin_paths = [
                "", "/", "/index.html", "/admin", "/setup",
                "/config", "/camera", "/manage", "/web"
            ]
            
            for path in admin_paths:
                try:
                    import urllib.request
                    import urllib.error
                    
                    url = f"http://{address}:{port}{path}"
                    req = urllib.request.Request(url, method="HEAD")
                    
                    try:
                        response = urllib.request.urlopen(req, timeout=1)
                        
                        # Najpierw sprawdź nagłówki
                        server = response.getheader("Server", "").lower()
                        if any(cam_server in server for cam_server in ["ipcam", "camera", "webcam", "hikvision", "dahua"]):
                            result["available"] = True
                            result["url"] = url
                            
                            # Dodaj operacje zarządzania kamerą
                            result["operations"].append({
                                "name": "Konfiguracja kamery",
                                "description": "Konfiguruj ustawienia kamery",
                                "available": True,
                                "protocol": "http",
                                "url": url,
                                "operation": "camera_config"
                            })
                            
                            return result
                        
                        # Następnie spróbuj zbadać treść strony
                        content_req = urllib.request.Request(url)
                        content_response = urllib.request.urlopen(content_req, timeout=1)
                        content = content_response.read(4096).decode('utf-8', errors='ignore')
                        
                        # Szukaj słów kluczowych wskazujących na interfejs kamery
                        camera_keywords = ["camera", "ipcam", "webcam", "stream", "video", "surveillance"]
                        if any(keyword in content.lower() for keyword in camera_keywords):
                            result["available"] = True
                            result["url"] = url
                            
                            # Dodaj operacje zarządzania kamerą
                            result["operations"].append({
                                "name": "Konfiguracja kamery",
                                "description": "Konfiguruj ustawienia kamery",
                                "available": True,
                                "protocol": "http",
                                "url": url,
                                "operation": "camera_config"
                            })
                            
                            return result
                    except:
                        continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania interfejsu kamery na ścieżce {path}: {e}")
        
        return result
    def _check_advanced_camera_features(self, address, capabilities, device_info):
        """Sprawdza zaawansowane funkcje kamery."""
        try:
            # Sprawdź funkcję nagrywania
            recording_support = self._check_recording_options(address)
            if recording_support.get("available", False):
                device_info["supports_recording"] = True
                
                for operation in recording_support.get("operations", []):
                    capabilities.append(operation)
            
            # Sprawdź funkcję detekcji ruchu
            motion_detection = self._check_motion_detection(address)
            if motion_detection.get("available", False):
                device_info["motion_detection"] = True
                
                capabilities.append({
                    "name": "Detekcja ruchu",
                    "description": "Konfiguruj wykrywanie ruchu",
                    "available": True,
                    "protocol": motion_detection.get("protocol", "http"),
                    "operation": "motion_detection"
                })
            
            # Sprawdź funkcję widzenia nocnego
            night_vision = self._check_night_vision(address)
            if night_vision:
                device_info["night_vision"] = True
                
                capabilities.append({
                    "name": "Widzenie nocne",
                    "description": "Steruj trybem widzenia nocnego",
                    "available": True,
                    "operation": "night_vision"
                })
            
            # Sprawdź funkcję dwukierunkowego audio
            two_way_audio = self._check_two_way_audio(address)
            if two_way_audio:
                device_info["two_way_audio"] = True
                
                capabilities.append({
                    "name": "Dwukierunkowe audio",
                    "description": "Używaj funkcji interkomu",
                    "available": True,
                    "operation": "two_way_audio"
                })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania zaawansowanych funkcji kamery: {e}")

    def _check_recording_options(self, address):
        """Sprawdza opcje nagrywania dla kamery."""
        result = {
            "available": False,
            "operations": []
        }
        
        try:
            # Sprawdź obsługę nagrywania przez interfejs WWW
            # W rzeczywistości wymaga to dokładniejszej analizy interfejsu WWW kamery
            
            # Sprawdź popularne porty HTTP
            for port in [80, 8080, 8000, 8081]:
                if not self.check_port_open(address, port):
                    continue
                
                try:
                    import urllib.request
                    import urllib.error
                    
                    # Sprawdź popularne ścieżki konfiguracji nagrywania
                    recording_paths = [
                        "/recording", 
                        "/config/recording", 
                        "/record", 
                        "/recording/config",
                        "/settings/recording"
                    ]
                    
                    for path in recording_paths:
                        try:
                            url = f"http://{address}:{port}{path}"
                            req = urllib.request.Request(url, method="HEAD")
                            
                            try:
                                response = urllib.request.urlopen(req, timeout=1)
                                if response.getcode() == 200:
                                    result["available"] = True
                                    
                                    result["operations"].append({
                                        "name": "Konfiguracja nagrywania",
                                        "description": "Konfiguruj ustawienia nagrywania",
                                        "available": True,
                                        "protocol": "http",
                                        "url": url
                                    })
                                    
                                    result["operations"].append({
                                        "name": "Rozpocznij nagrywanie",
                                        "description": "Rozpocznij nagrywanie wideo",
                                        "available": True,
                                        "protocol": "http",
                                        "operation": "start_recording"
                                    })
                                    
                                    result["operations"].append({
                                        "name": "Zatrzymaj nagrywanie",
                                        "description": "Zatrzymaj nagrywanie wideo",
                                        "available": True,
                                        "protocol": "http",
                                        "operation": "stop_recording"
                                    })
                                    
                                    return result
                            except:
                                continue
                        except:
                            continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania opcji nagrywania na porcie {port}: {e}")
            
            # Sprawdź możliwość nagrywania przez ONVIF
            if self._check_onvif_support(address).get("available", False):
                result["available"] = True
                
                result["operations"].append({
                    "name": "Nagrywanie ONVIF",
                    "description": "Steruj nagrywaniem przez ONVIF",
                    "available": True,
                    "protocol": "onvif",
                    "operation": "recording"
                })
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania opcji nagrywania: {e}")
        
        return result

    def _check_motion_detection(self, address):
        """Sprawdza obsługę detekcji ruchu w kamerze."""
        result = {
            "available": False,
            "protocol": None
        }
        
        try:
            # Sprawdź przez interfejs WWW
            for port in [80, 8080, 8000, 8081]:
                if not self.check_port_open(address, port):
                    continue
                
                try:
                    import urllib.request
                    import urllib.error
                    
                    # Sprawdź popularne ścieżki konfiguracji detekcji ruchu
                    motion_paths = [
                        "/motion", 
                        "/config/motion", 
                        "/motion/detection", 
                        "/settings/motion",
                        "/alarm/motion"
                    ]
                    
                    for path in motion_paths:
                        try:
                            url = f"http://{address}:{port}{path}"
                            req = urllib.request.Request(url, method="HEAD")
                            
                            try:
                                response = urllib.request.urlopen(req, timeout=1)
                                if response.getcode() == 200:
                                    result["available"] = True
                                    result["protocol"] = "http"
                                    return result
                            except:
                                continue
                        except:
                            continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania detekcji ruchu na porcie {port}: {e}")
            
            # Sprawdź przez ONVIF
            if self._check_onvif_support(address).get("available", False):
                # Większość kamer ONVIF obsługuje detekcję ruchu
                result["available"] = True
                result["protocol"] = "onvif"
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania detekcji ruchu: {e}")
        
        return result

    def _check_night_vision(self, address):
        """Sprawdza obsługę widzenia nocnego w kamerze."""
        # To jest uproszczona implementacja, w rzeczywistości wymagałoby to
        # dokładniejszej analizy interfejsu kamery
        
        try:
            # Sprawdź przez interfejs WWW
            for port in [80, 8080, 8000, 8081]:
                if not self.check_port_open(address, port):
                    continue
                
                try:
                    import urllib.request
                    import urllib.error
                    
                    # Sprawdź popularne ścieżki konfiguracji widzenia nocnego
                    night_vision_paths = [
                        "/night", 
                        "/ir", 
                        "/nightvision", 
                        "/irled",
                        "/settings/night"
                    ]
                    
                    for path in night_vision_paths:
                        try:
                            url = f"http://{address}:{port}{path}"
                            req = urllib.request.Request(url, method="HEAD")
                            
                            try:
                                response = urllib.request.urlopen(req, timeout=1)
                                if response.getcode() == 200:
                                    return True
                            except:
                                continue
                        except:
                            continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania widzenia nocnego na porcie {port}: {e}")
            
            # Sprawdź przez ONVIF
            if self._check_onvif_support(address).get("available", False):
                # Wiele kamer ONVIF obsługuje widzenie nocne
                return True
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania widzenia nocnego: {e}")
        
        return False

    def _check_two_way_audio(self, address):
        """Sprawdza obsługę dwukierunkowego audio w kamerze."""
        try:
            # Sprawdź przez interfejs WWW
            for port in [80, 8080, 8000, 8081]:
                if not self.check_port_open(address, port):
                    continue
                
                try:
                    import urllib.request
                    import urllib.error
                    
                    # Sprawdź popularne ścieżki konfiguracji audio
                    audio_paths = [
                        "/audio", 
                        "/talk", 
                        "/twoway", 
                        "/settings/audio",
                        "/intercom"
                    ]
                    
                    for path in audio_paths:
                        try:
                            url = f"http://{address}:{port}{path}"
                            req = urllib.request.Request(url, method="HEAD")
                            
                            try:
                                response = urllib.request.urlopen(req, timeout=1)
                                if response.getcode() == 200:
                                    return True
                            except:
                                continue
                        except:
                            continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania dwukierunkowego audio na porcie {port}: {e}")
            
            # Sprawdź przez ONVIF
            onvif_info = self._check_onvif_support(address)
            if onvif_info.get("available", False) and onvif_info.get("audio", False):
                return True
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania dwukierunkowego audio: {e}")
        
        return False

    def _find_router_admin(self, address):
        """Znajduje adres panelu administracyjnego routera."""
        # Popularne ścieżki paneli administracyjnych routerów
        admin_paths = [
            "", "/", "/admin", "/setup", "/index.html", "/login.html",
            "/logon.html", "/Management.html", "/configure", "/config"
        ]
        
        for port in [80, 8080, 443, 8443]:
            if not self.check_port_open(address, port):
                continue
            
            protocol = "https" if port in [443, 8443] else "http"
            
            for path in admin_paths:
                try:
                    import urllib.request
                    import urllib.error
                    import ssl
                    
                    url = f"{protocol}://{address}:{port}{path}"
                    
                    try:
                        if protocol == "https":
                            context = ssl._create_unverified_context()
                            response = urllib.request.urlopen(url, timeout=1, context=context)
                        else:
                            response = urllib.request.urlopen(url, timeout=1)
                        
                        if response.getcode() == 200:
                            # Jeśli znaleźliśmy panel administracyjny, zwróć adres URL
                            return url
                    except (urllib.error.URLError, urllib.error.HTTPError) as e:
                        if hasattr(e, 'code') and (e.code == 401 or e.code == 403):
                            # Authentication required is a good sign it's an admin panel
                            return url
                        continue
                    except:
                        continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania panelu administracyjnego routera: {e}")
        
        return None

    def _find_printer_web(self, address):
        """Znajduje adres interfejsu WWW drukarki."""
        # Popularne ścieżki interfejsów WWW drukarek
        printer_paths = [
            "", "/", "/index.html", "/info.html", "/status.html", "/web/index.html",
            "/printer/index.html", "/hp/device/index.html", "/setup", "/config"
        ]
        
        for port in [80, 8080, 443, 8443, 631]:
            if not self.check_port_open(address, port):
                continue
            
            protocol = "https" if port in [443, 8443] else "http"
            
            for path in printer_paths:
                try:
                    import urllib.request
                    import urllib.error
                    import ssl
                    
                    url = f"{protocol}://{address}:{port}{path}"
                    
                    try:
                        if protocol == "https":
                            context = ssl._create_unverified_context()
                            response = urllib.request.urlopen(url, timeout=1, context=context)
                        else:
                            response = urllib.request.urlopen(url, timeout=1)
                        
                        if response.getcode() == 200:
                            content = response.read(8192).decode('utf-8', errors='ignore')
                            
                            # Sprawdź, czy zawartość strony wskazuje na interfejs drukarki
                            printer_keywords = ["printer", "ink", "toner", "cartridge", "print"]
                            if any(keyword in content.lower() for keyword in printer_keywords):
                                return url
                    except:
                        continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania interfejsu WWW drukarki: {e}")
        
        return None

    def _find_camera_web(self, address):
        """Znajduje adres interfejsu WWW kamery."""
        # Popularne ścieżki interfejsów WWW kamer
        camera_paths = [
            "", "/", "/index.html", "/live.html", "/view.html", "/video.html",
            "/camera.html", "/stream.html", "/setup.html", "/config"
        ]
        
        for port in [80, 8080, 8000, 8081, 443, 8443]:
            if not self.check_port_open(address, port):
                continue
            
            protocol = "https" if port in [443, 8443] else "http"
            
            for path in camera_paths:
                try:
                    import urllib.request
                    import urllib.error
                    import ssl
                    
                    url = f"{protocol}://{address}:{port}{path}"
                    
                    try:
                        if protocol == "https":
                            context = ssl._create_unverified_context()
                            response = urllib.request.urlopen(url, timeout=1, context=context)
                        else:
                            response = urllib.request.urlopen(url, timeout=1)
                        
                        if response.getcode() == 200:
                            content = response.read(8192).decode('utf-8', errors='ignore')
                            
                            # Sprawdź, czy zawartość strony wskazuje na interfejs kamery
                            camera_keywords = ["camera", "video", "stream", "surveillance", "motion"]
                            if any(keyword in content.lower() for keyword in camera_keywords):
                                return url
                    except:
                        continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania interfejsu WWW kamery: {e}")
        
        return None

    def _find_nas_web(self, address):
        """Znajduje adres interfejsu WWW serwera NAS."""
        # Popularne ścieżki interfejsów WWW serwerów NAS
        nas_paths = [
            "", "/", "/index.html", "/admin", "/login.html", "/management",
            "/nas", "/storage", "/shares", "/diskstation", "/freenas"
        ]
        
        for port in [80, 8080, 443, 8443, 5000, 5001]:
            if not self.check_port_open(address, port):
                continue
            
            protocol = "https" if port in [443, 8443, 5001] else "http"
            
            for path in nas_paths:
                try:
                    import urllib.request
                    import urllib.error
                    import ssl
                    
                    url = f"{protocol}://{address}:{port}{path}"
                    
                    try:
                        if protocol == "https":
                            context = ssl._create_unverified_context()
                            response = urllib.request.urlopen(url, timeout=1, context=context)
                        else:
                            response = urllib.request.urlopen(url, timeout=1)
                        
                        if response.getcode() == 200:
                            content = response.read(8192).decode('utf-8', errors='ignore')
                            
                            # Sprawdź, czy zawartość strony wskazuje na interfejs serwera NAS
                            nas_keywords = ["nas", "storage", "disk", "share", "volume", "raid"]
                            if any(keyword in content.lower() for keyword in nas_keywords):
                                return url
                    except:
                        continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania interfejsu WWW serwera NAS: {e}")
        
        return None

    def _find_iot_web(self, address):
        """Znajduje adres interfejsu WWW urządzenia IoT."""
        # Popularne ścieżki interfejsów WWW urządzeń IoT
        iot_paths = [
            "", "/", "/index.html", "/setup", "/config", "/device",
            "/control", "/settings", "/admin", "/dashboard"
        ]
        
        for port in [80, 8080, 443, 8443, 1883, 1884]:
            if not self.check_port_open(address, port):
                continue
            
            protocol = "https" if port in [443, 8443] else "http"
            
            for path in iot_paths:
                try:
                    import urllib.request
                    import urllib.error
                    import ssl
                    
                    url = f"{protocol}://{address}:{port}{path}"
                    
                    try:
                        if protocol == "https":
                            context = ssl._create_unverified_context()
                            response = urllib.request.urlopen(url, timeout=1, context=context)
                        else:
                            response = urllib.request.urlopen(url, timeout=1)
                        
                        if response.getcode() == 200:
                            content = response.read(8192).decode('utf-8', errors='ignore')
                            
                            # Sprawdź, czy zawartość strony wskazuje na interfejs urządzenia IoT
                            iot_keywords = ["iot", "device", "smart", "control", "sensor", "automation"]
                            if any(keyword in content.lower() for keyword in iot_keywords):
                                return url
                    except:
                        continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania interfejsu WWW urządzenia IoT: {e}")
        
        return None

    def _find_media_web(self, address):
        """Znajduje adres interfejsu WWW urządzenia medialnego."""
        # Popularne ścieżki interfejsów WWW urządzeń medialnych
        media_paths = [
            "", "/", "/index.html", "/player", "/media", "/dlna",
            "/upnp", "/music", "/video", "/photos", "/library"
        ]
        
        for port in [80, 8080, 8096, 8200, 443, 8443]:
            if not self.check_port_open(address, port):
                continue
            
            protocol = "https" if port in [443, 8443] else "http"
            
            for path in media_paths:
                try:
                    import urllib.request
                    import urllib.error
                    import ssl
                    
                    url = f"{protocol}://{address}:{port}{path}"
                    
                    try:
                        if protocol == "https":
                            context = ssl._create_unverified_context()
                            response = urllib.request.urlopen(url, timeout=1, context=context)
                        else:
                            response = urllib.request.urlopen(url, timeout=1)
                        
                        if response.getcode() == 200:
                            content = response.read(8192).decode('utf-8', errors='ignore')
                            
                            # Sprawdź, czy zawartość strony wskazuje na interfejs urządzenia medialnego
                            media_keywords = ["media", "player", "stream", "dlna", "music", "video"]
                            if any(keyword in content.lower() for keyword in media_keywords):
                                return url
                    except:
                        continue
                
                except Exception as e:
                    print(f"Błąd podczas sprawdzania interfejsu WWW urządzenia medialnego: {e}")
        
        return None

    def _check_upnp_discovery(self, address):
        """Sprawdza obsługę wykrywania UPnP."""
        # Ta implementacja jest uproszczona, w rzeczywistości wymaga obsługi multicastu
        try:
            # Sprawdź port 1900 (standardowy port UPnP)
            if self.check_port_open(address, 1900, protocol="udp"):
                return True
            
            # Sprawdź port 5000 (często używany przez usługi UPnP)
            if self.check_port_open(address, 5000):
                return True
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania obsługi UPnP: {e}")
        
        return False

    def _check_mdns_support(self, address):
        """Sprawdza obsługę wykrywania mDNS/Bonjour."""
        # Ta implementacja jest uproszczona, w rzeczywistości wymaga obsługi multicastu
        try:
            # Sprawdź port 5353 (standardowy port mDNS)
            if self.check_port_open(address, 5353, protocol="udp"):
                return True
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania obsługi mDNS: {e}")
        
        return False

    def _check_ws_discovery(self, address):
        """Sprawdza obsługę wykrywania WS-Discovery."""
        # Ta implementacja jest uproszczona, w rzeczywistości wymaga obsługi SOAP
        try:
            # Sprawdź port 3702 (standardowy port WS-Discovery)
            if self.check_port_open(address, 3702, protocol="udp"):
                return True
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania obsługi WS-Discovery: {e}")
        
        return False

    def _check_lldp_support(self, address):
        """Sprawdza obsługę protokołu LLDP."""
        # Ta implementacja jest uproszczona
        return False

    def _check_cdp_support(self, address):
        """Sprawdza obsługę protokołu CDP."""
        # Ta implementacja jest uproszczona
        return False

    def _check_upnp_support(self, address):
        """Sprawdza obsługę UPnP dla sterowania urządzeniem."""
        try:
            # Sprawdź port 1900 (standardowy port UPnP)
            if self.check_port_open(address, 1900, protocol="udp"):
                return True
            
            # Sprawdź port 5000 (często używany przez usługi UPnP)
            if self.check_port_open(address, 5000):
                return True
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania obsługi UPnP: {e}")
        
        return False

    def _check_dlna_support(self, address):
        """Sprawdza obsługę protokołu DLNA."""
        try:
            # Sprawdź popularne porty DLNA
            for port in [8200, 8095, 1900, 2869]:
                if port == 1900:
                    if self.check_port_open(address, port, protocol="udp"):
                        return True
                else:
                    if self.check_port_open(address, port):
                        return True
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania obsługi DLNA: {e}")
        
        return False

    def _check_airplay_support(self, address):
        """Sprawdza obsługę protokołu AirPlay."""
        try:
            # Sprawdź port 5000 (standardowy port AirPlay)
            if self.check_port_open(address, 5000):
                return True
            
            # Sprawdź port 7000 (również używany przez AirPlay)
            if self.check_port_open(address, 7000):
                return True
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania obsługi AirPlay: {e}")
        
        return False

    def _check_chromecast_support(self, address):
        """Sprawdza obsługę protokołu Chromecast."""
        try:
            # Sprawdź port 8009 (standardowy port Chromecast)
            if self.check_port_open(address, 8009):
                return True
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania obsługi Chromecast: {e}")
        
        return False

    def _check_spotify_connect_support(self, address):
        """Sprawdza obsługę protokołu Spotify Connect."""
        try:
            # Próba wykrycia Spotify Connect jest skomplikowana bez dedykowanej biblioteki
            # Ta implementacja jest uproszczona
            
            # Sprawdź obsługę mDNS (Spotify Connect używa mDNS do wykrywania)
            if self._check_mdns_support(address):
                # Jeśli urządzenie obsługuje mDNS, istnieje szansa, że obsługuje Spotify Connect
                return True
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania obsługi Spotify Connect: {e}")
        
        return False

    def _check_hls_support(self, address):
        """Sprawdza obsługę protokołu HLS (HTTP Live Streaming)."""
        try:
            # Sprawdź popularne porty HTTP dla serwerów HLS
            for port in [80, 8080, 8000, 8081, 443, 8443]:
                if not self.check_port_open(address, port):
                    continue
                
                protocol = "https" if port in [443, 8443] else "http"
                
                # Sprawdź popularne ścieżki dla strumieni HLS
                hls_paths = [
                    "/stream.m3u8", 
                    "/hls/stream.m3u8", 
                    "/live/stream.m3u8", 
                    "/video/stream.m3u8",
                    "/app/stream.m3u8"
                ]
                
                for path in hls_paths:
                    try:
                        import urllib.request
                        import urllib.error
                        import ssl
                        
                        url = f"{protocol}://{address}:{port}{path}"
                        
                        try:
                            if protocol == "https":
                                context = ssl._create_unverified_context()
                                req = urllib.request.Request(url, method="HEAD")
                                response = urllib.request.urlopen(req, timeout=1, context=context)
                            else:
                                req = urllib.request.Request(url, method="HEAD")
                                response = urllib.request.urlopen(req, timeout=1)
                            
                            content_type = response.getheader("Content-Type", "")
                            
                            if "application/vnd.apple.mpegurl" in content_type or "application/x-mpegurl" in content_type:
                                return url
                        except:
                            continue
                    
                    except Exception as e:
                        print(f"Błąd podczas sprawdzania obsługi HLS na ścieżce {path}: {e}")
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania obsługi HLS: {e}")
        
        return None

    def _check_dash_support(self, address):
        """Sprawdza obsługę protokołu DASH (Dynamic Adaptive Streaming over HTTP)."""
        try:
            # Sprawdź popularne porty HTTP dla serwerów DASH
            for port in [80, 8080, 8000, 8081, 443, 8443]:
                if not self.check_port_open(address, port):
                    continue
                
                protocol = "https" if port in [443, 8443] else "http"
                
                # Sprawdź popularne ścieżki dla strumieni DASH
                dash_paths = [
                    "/stream.mpd", 
                    "/dash/stream.mpd", 
                    "/live/stream.mpd", 
                    "/video/stream.mpd",
                    "/app/stream.mpd"
                ]
                
                for path in dash_paths:
                    try:
                        import urllib.request
                        import urllib.error
                        import ssl
                        
                        url = f"{protocol}://{address}:{port}{path}"
                        
                        try:
                            if protocol == "https":
                                context = ssl._create_unverified_context()
                                req = urllib.request.Request(url, method="HEAD")
                                response = urllib.request.urlopen(req, timeout=1, context=context)
                            else:
                                req = urllib.request.Request(url, method="HEAD")
                                response = urllib.request.urlopen(req, timeout=1)
                            
                            content_type = response.getheader("Content-Type", "")
                            
                            if "application/dash+xml" in content_type:
                                return url
                        except:
                            continue
                    
                    except Exception as e:
                        print(f"Błąd podczas sprawdzania obsługi DASH na ścieżce {path}: {e}")
        
        except Exception as e:
            print(f"Błąd podczas sprawdzania obsługi DASH: {e}")
        
        return None
    def _identify_service_from_banner(self, banner, port):
        """Identyfikuje usługę na podstawie bannera i portu."""
        if not banner:
            return None
        
        # Typowe identyfikatory usług w bannerach
        service_identifiers = {
            "ssh": ["ssh", "openssh", "sshd"],
            "ftp": ["ftp", "fileserver", "vsftpd", "proftpd"],
            "telnet": ["telnet", "login"],
            "smtp": ["smtp", "mail server", "postfix", "sendmail", "mail service"],
            "pop3": ["pop", "pop3", "mail"],
            "imap": ["imap", "mail", "dovecot"],
            "http": ["http", "web", "apache", "nginx", "iis", "webserver"],
            "https": ["https", "secure", "ssl", "tls"],
            "dns": ["dns", "domain", "named", "bind"],
            "dhcp": ["dhcp", "bootpc", "bootps"],
            "rdp": ["rdp", "terminal services", "remote desktop"],
            "vnc": ["vnc", "remote desktop", "rfb"],
            "printer": ["printer", "ipp", "cups", "jetdirect"],
            "upnp": ["upnp", "universal plug and play"],
            "snmp": ["snmp", "network management"],
            "ntp": ["ntp", "time server", "time service"],
            "ldap": ["ldap", "directory", "openldap", "active directory"],
            "database": ["sql", "mysql", "postgresql", "oracle", "database", "db server"],
            "mqtt": ["mqtt", "mosquitto"],
            "rtsp": ["rtsp", "streaming", "video server"],
            "sip": ["sip", "voip", "voice", "telephony"],
            "irc": ["irc", "chat server", "internet relay chat"]
        }
        
        # Typowe usługi na portach
        port_services = {
            21: "ftp",
            22: "ssh",
            23: "telnet",
            25: "smtp",
            53: "dns",
            67: "dhcp",
            68: "dhcp",
            80: "http",
            110: "pop3",
            123: "ntp",
            143: "imap",
            161: "snmp",
            389: "ldap",
            443: "https",
            465: "smtp-ssl",
            514: "syslog",
            554: "rtsp",
            587: "smtp-submission",
            631: "ipp",
            993: "imaps",
            995: "pop3s",
            1883: "mqtt",
            3306: "mysql",
            3389: "rdp",
            5432: "postgresql",
            5060: "sip",
            5900: "vnc",
            8080: "http-alt",
            8443: "https-alt",
            9100: "printer"
        }
        
        # Sprawdź identyfikatory w bannerze
        banner_lower = banner.lower()
        for service, identifiers in service_identifiers.items():
            if any(identifier in banner_lower for identifier in identifiers):
                return service
        
        # Jeśli nie znaleziono w bannerze, sprawdź port
        if port in port_services:
            return port_services[port]
        
        return None

    def _get_webcam_controls(self, cap):
        """Zwraca dostępne operacje sterowania kamerą internetową."""
        operations = []
        
        if not CAMERA_MODULE_AVAILABLE:
            return operations
        
        try:
            # Sprawdź dostępne parametry kamery
            properties = {
                cv2.CAP_PROP_BRIGHTNESS: "Jasność",
                cv2.CAP_PROP_CONTRAST: "Kontrast",
                cv2.CAP_PROP_SATURATION: "Nasycenie",
                cv2.CAP_PROP_HUE: "Odcień",
                cv2.CAP_PROP_GAIN: "Wzmocnienie",
                cv2.CAP_PROP_EXPOSURE: "Ekspozycja",
                cv2.CAP_PROP_AUTO_EXPOSURE: "Auto ekspozycja",
                cv2.CAP_PROP_ZOOM: "Zoom",
                cv2.CAP_PROP_FOCUS: "Ostrość",
                cv2.CAP_PROP_AUTOFOCUS: "Auto ostrość"
            }
            
            for prop_id, prop_name in properties.items():
                # Sprawdź, czy właściwość jest obsługiwana
                value = cap.get(prop_id)
                if value != 0 and value != -1:  # Wartość 0 lub -1 często oznacza brak obsługi
                    operations.append({
                        "name": f"Ustaw {prop_name}",
                        "description": f"Zmień parametr {prop_name}",
                        "available": True,
                        "operation": "set_property",
                        "property_id": int(prop_id)
                    })
        
        except Exception as e:
            print(f"Błąd podczas pobierania kontrolek kamery: {e}")
        
        return operations

    def _get_webcam_resolutions(self, cap):
        """Pobiera obsługiwane rozdzielczości kamery."""
        standard_resolutions = [
            (640, 480),    # VGA
            (800, 600),    # SVGA
            (1024, 768),   # XGA
            (1280, 720),   # HD
            (1280, 800),   # WXGA
            (1280, 1024),  # SXGA
            (1600, 1200),  # UXGA
            (1920, 1080),  # FHD
            (2560, 1440),  # QHD
            (3840, 2160)   # 4K UHD
        ]
        
        supported_resolutions = []
        
        if not CAMERA_MODULE_AVAILABLE:
            return supported_resolutions
        
        try:
            # Pobierz aktualną rozdzielczość
            current_width = cap.get(cv2.CAP_PROP_FRAME_WIDTH)
            current_height = cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
            
            # Dodaj aktualną rozdzielczość
            supported_resolutions.append((int(current_width), int(current_height)))
            
            # W rzeczywistości, aby sprawdzić wszystkie obsługiwane rozdzielczości,
            # należałoby spróbować ustawić każdą i sprawdzić, czy była faktycznie ustawiona.
            # Tutaj dla uproszczenia dodajemy tylko kilka standardowych.
            for width, height in standard_resolutions:
                if (width, height) not in supported_resolutions:
                    if width <= current_width and height <= current_height:
                        supported_resolutions.append((width, height))
        
        except Exception as e:
            print(f"Błąd podczas pobierania rozdzielczości kamery: {e}")
        
        return supported_resolutions


# Create scanner instances
scanner = DeviceScanner()
capability_scanner = DeviceCapabilityScanner()

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

@app.route('/api/devices/bluetooth/paired', methods=['GET'])
def get_paired_bluetooth_devices():
    """Endpoint to get paired Bluetooth devices"""
    # This is a simplified implementation that returns an empty list
    # In a real implementation, you would query the OS for paired devices
    return jsonify({"status": "success", "devices": []})

@app.route('/api/devices/capabilities', methods=['GET'])
def get_device_capabilities():
    """Endpoint to get device capabilities based on device type, address, and connection method."""
    device_address = request.args.get('address', '')
    device_type = request.args.get('type', '')
    connection_method = request.args.get('method', 'auto')
    device_id = request.args.get('id', '')
    
    try:
        # Query device capabilities
        result = capability_scanner.query_device_capabilities(
            device_address, device_type, connection_method, device_id
        )
        return jsonify(result)
    
    except Exception as e:
        return jsonify({
            "status": "error",
            "error": f"Failed to query device capabilities: {str(e)}"
        })

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
    
    # Show information about available modules
    print("\n=== Available Modules Information ===")
    print(f"Module 'wifi': {'Available' if WIFI_MODULE_AVAILABLE else 'Unavailable'}")
    print(f"Module 'bleak' (Bluetooth): {'Available' if BLUETOOTH_MODULE_AVAILABLE else 'Unavailable'}")
    print(f"Module 'opencv-python': {'Available' if CAMERA_MODULE_AVAILABLE else 'Unavailable'}")
    print(f"Module 'python-nmap': {'Available' if NMAP_AVAILABLE else 'Unavailable'}")
    print(f"Module 'pysnmp': {'Available' if SNMP_AVAILABLE else 'Unavailable'}")
    
    print("\n=== System Information ===")
    print(f"Operating System: {platform.system()} {platform.release()}")
    print(f"Python Version: {platform.python_version()}")
    
    # Information about server startup
    print(f"\nStarting API server on http://localhost:{PORT}")
    print("Press CTRL+C to stop the server")
    
    # Run Flask server
    app.run(host=HOST, port=PORT, debug=DEBUG)