import asyncio
import json
import time
import uuid
import base64
import logging
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Callable, Any
from pathlib import Path
from enum import Enum

try:
    from bleak import BleakClient, BleakScanner, BleakGATTCharacteristic
    from bleak.backends.device import BLEDevice
    from bleak.backends.scanner import AdvertisementData
    BLEAK_AVAILABLE = True
except ImportError:
    BLEAK_AVAILABLE = False
    BleakClient = None
    BleakScanner = None
    BLEDevice = None
    AdvertisementData = None
    BleakGATTCharacteristic = None

import cv2
import numpy as np
import qrcode
from PIL import Image

from src.camera.capture import CameraCapture, CaptureResult


logger = logging.getLogger(__name__)


class BluetoothCameraServiceUUIDs:
    """Standard UUIDs for Bluetooth camera services"""
    DEVICE_INFO = "0000180a-0000-1000-8000-00805f9b34fb"
    CAMERA_SERVICE = "0000181e-0000-1000-8000-00805f9b34fb"
    IMAGE_TRANSFER = "00002a00-0000-1000-8000-00805f9b34fb"
    CAMERA_CONTROL = "00002a01-0000-1000-8000-00805f9b34fb"
    BATTERY_SERVICE = "0000180f-0000-1000-8000-00805f9b34fb"


class ConnectionState(Enum):
    DISCONNECTED = "disconnected"
    SCANNING = "scanning"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    STREAMING = "streaming"
    ERROR = "error"


@dataclass
class BluetoothDevice:
    address: str
    name: str
    rssi: int = 0
    services: List[str] = field(default_factory=list)
    manufacturer_data: Dict[int, bytes] = field(default_factory=dict)
    is_camera: bool = False
    battery_level: Optional[int] = None
    paired: bool = False


@dataclass
class BluetoothCameraConfig:
    device_address: str
    device_name: str
    image_width: int = 640
    image_height: int = 480
    jpeg_quality: int = 85
    auto_capture: bool = False
    capture_interval: float = 2.0


class BluetoothCameraManager:
    def __init__(self):
        self.client: Optional[BleakClient] = None
        self.device: Optional[BluetoothDevice] = None
        self.state = ConnectionState.DISCONNECTED
        self.config: Optional[BluetoothCameraConfig] = None
        self._frame_callback: Optional[Callable[[np.ndarray], None]] = None
        self._notification_callback: Optional[Callable[[str], None]] = None
        self._streaming_task: Optional[asyncio.Task] = None
        self._image_buffer: bytearray = bytearray()
        self._expecting_image = False
        self._image_size = 0
        self._image_received = 0
        
    def is_available(self) -> bool:
        return BLEAK_AVAILABLE

    async def scan_for_devices(
        self,
        duration: float = 10.0,
        filter_camera_only: bool = True,
        callback: Optional[Callable[[BluetoothDevice], None]] = None
    ) -> List[BluetoothDevice]:
        if not BLEAK_AVAILABLE:
            logger.warning("bleak not available, cannot scan for Bluetooth devices")
            return []
            
        self.state = ConnectionState.SCANNING
        devices: List[BluetoothDevice] = []
        
        def detection_callback(device: BLEDevice, adv: AdvertisementData):
            name = adv.local_name or device.name or "Unknown"
            addr = device.address
            rssi = adv.rssi or 0
            
            manufacturer_data = adv.manufacturer_data
            service_uuids = adv.service_uuids or []
            
            is_camera = self._is_camera_device(name, service_uuids, manufacturer_data)
            
            if filter_camera_only and not is_camera:
                return
                
            bt_device = BluetoothDevice(
                address=addr,
                name=name,
                rssi=rssi,
                services=service_uuids,
                manufacturer_data=manufacturer_data,
                is_camera=is_camera
            )
            
            if not any(d.address == addr for d in devices):
                devices.append(bt_device)
                if callback:
                    callback(bt_device)
                    
        scanner = BleakScanner(detection_callback)
        await scanner.start()
        await asyncio.sleep(duration)
        await scanner.stop()
        
        self.state = ConnectionState.DISCONNECTED
        return devices
    
    def _is_camera_device(
        self,
        name: str,
        service_uuids: List[str],
        manufacturer_data: Dict[int, bytes]
    ) -> bool:
        camera_keywords = ["camera", "cam", "webcam", "ipcam", "gopro", "dji", "insta360"]
        name_lower = name.lower()
        
        if any(kw in name_lower for kw in camera_keywords):
            return True
            
        camera_service_uuids = [
            "0000181e-0000-1000-8000-00805f9b34fb",
            "00001820-0000-1000-8000-00805f9b34fb",
        ]
        
        for uuid_str in service_uuids:
            if uuid_str.lower() in [u.lower() for u in camera_service_uuids]:
                return True
                
        return False

    async def connect(self, device: BluetoothDevice) -> bool:
        if not BLEAK_AVAILABLE:
            logger.error("bleak not available")
            return False
            
        self.state = ConnectionState.CONNECTING
        self.device = device
        
        try:
            self.client = BleakClient(device.address)
            await self.client.connect()
            
            if not self.client.is_connected:
                self.state = ConnectionState.ERROR
                return False
                
            services = await self.client.get_services()
            camera_service = None
            
            for service in services:
                if "181e" in service.uuid.lower() or "1820" in service.uuid.lower():
                    camera_service = service
                    break
                    
            if camera_service is None:
                for service in services:
                    chars = service.characteristics
                    for char in chars:
                        if "write" in char.properties or "write-without-response" in char.properties:
                            camera_service = service
                            break
                    if camera_service:
                        break
            
            self.state = ConnectionState.CONNECTED
            logger.info(f"Connected to {device.name} ({device.address})")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to {device.name}: {e}")
            self.state = ConnectionState.ERROR
            return False
    
    async def disconnect(self):
        if self._streaming_task:
            self._streaming_task.cancel()
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                pass
            self._streaming_task = None
            
        if self.client and self.client.is_connected:
            await self.client.disconnect()
            
        self.client = None
        self.device = None
        self.state = ConnectionState.DISCONNECTED
        
    async def configure_camera(self, config: BluetoothCameraConfig) -> bool:
        if not self.client or not self.client.is_connected:
            return False
            
        self.config = config
        
        try:
            config_data = {
                "width": config.image_width,
                "height": config.image_height,
                "quality": config.jpeg_quality,
                "auto_capture": config.auto_capture,
                "interval": config.capture_interval
            }
            data = json.dumps(config_data).encode()
            
            for service in self.client.services:
                for char in service.characteristics:
                    if "write" in char.properties:
                        await self.client.write_gatt_char(char.uuid, data)
                        return True
                        
            return False
        except Exception as e:
            logger.error(f"Failed to configure camera: {e}")
            return False
    
    async def capture_single(self) -> Optional[np.ndarray]:
        if not self.client or not self.client.is_connected:
            return None
            
        try:
            for service in self.client.services:
                for char in service.characteristics:
                    if "write" in char.properties:
                        await self.client.write_gatt_char(char.uuid, b"CAPTURE")
                        break
                        
            self._expecting_image = True
            self._image_buffer = bytearray()
            
            for _ in range(50):
                await asyncio.sleep(0.1)
                if not self._expecting_image and len(self._image_buffer) > 0:
                    break
                    
            if len(self._image_buffer) > 0:
                nparr = np.frombuffer(self._image_buffer, np.uint8)
                img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                return img
                
            return None
        except Exception as e:
            logger.error(f"Failed to capture image: {e}")
            return None
    
    def _notification_handler(self, sender: BleakGATTCharacteristic, data: bytearray):
        if self._expecting_image:
            self._image_buffer.extend(data)
            if len(data) < 512:
                self._expecting_image = False
        elif data.startswith(b"IMG_START"):
            self._expecting_image = True
            self._image_size = int.from_bytes(data[9:13], 'big')
            self._image_buffer = bytearray()
            self._image_received = 0
        elif data.startswith(b"IMG_END"):
            self._expecting_image = False
        elif self._expecting_image:
            self._image_buffer.extend(data)
            self._image_received += len(data)
        elif data.startswith(b"NOTIFY:"):
            msg = data[7:].decode('utf-8', errors='ignore')
            if self._notification_callback:
                self._notification_callback(msg)
                
    async def start_streaming(self, callback: Callable[[np.ndarray], None]) -> bool:
        if not self.client or not self.client.is_connected:
            return False
            
        self._frame_callback = callback
        self.state = ConnectionState.STREAMING
        
        try:
            for service in self.client.services:
                for char in service.characteristics:
                    if "notify" in char.properties or "indicate" in char.properties:
                        await self.client.start_notify(char.uuid, self._notification_handler)
                        
            async def stream_loop():
                while self.state == ConnectionState.STREAMING:
                    img = await self.capture_single()
                    if img is not None and self._frame_callback:
                        self._frame_callback(img)
                    await asyncio.sleep(self.config.capture_interval if self.config else 2.0)
                    
            self._streaming_task = asyncio.create_task(stream_loop())
            return True
        except Exception as e:
            logger.error(f"Failed to start streaming: {e}")
            self.state = ConnectionState.ERROR
            return False
            
    async def stop_streaming(self):
        self.state = ConnectionState.CONNECTED
        if self._streaming_task:
            self._streaming_task.cancel()
            try:
                await self._streaming_task
            except asyncio.CancelledError:
                pass
            self._streaming_task = None
            
        if self.client and self.client.is_connected:
            for service in self.client.services:
                for char in service.characteristics:
                    if "notify" in char.properties:
                        try:
                            await self.client.stop_notify(char.uuid)
                        except Exception:
                            pass
                            
    def get_battery_level(self) -> Optional[int]:
        return self.device.battery_level if self.device else None


class BluetoothCameraCapture(CameraCapture):
    def __init__(
        self,
        camera_id: int = 0,
        width: int = 1920,
        height: int = 1080,
        bluetooth_manager: Optional[BluetoothCameraManager] = None
    ):
        super().__init__(camera_id, width, height)
        self.bluetooth_manager = bluetooth_manager or BluetoothCameraManager()
        self.use_bluetooth = False
        self._bluetooth_frame: Optional[np.ndarray] = None
        self._bluetooth_frame_ready = asyncio.Event()
        
    def open_bluetooth(self, device: BluetoothDevice, config: Optional[BluetoothCameraConfig] = None) -> bool:
        if not self.bluetooth_manager.is_available():
            logger.error("Bluetooth not available (bleak not installed)")
            return False
            
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            connected = loop.run_until_complete(self.bluetooth_manager.connect(device))
            if not connected:
                return False
                
            if config is None:
                config = BluetoothCameraConfig(
                    device_address=device.address,
                    device_name=device.name,
                    image_width=self.width,
                    image_height=self.height
                )
                
            configured = loop.run_until_complete(
                self.bluetooth_manager.configure_camera(config)
            )
            if not configured:
                loop.run_until_complete(self.bluetooth_manager.disconnect())
                return False
                
            self.use_bluetooth = True
            self._bluetooth_frame_ready.clear()
            
            def frame_callback(frame: np.ndarray):
                self._bluetooth_frame = frame
                self._bluetooth_frame_ready.set()
                
            loop.run_until_complete(
                self.bluetooth_manager.start_streaming(frame_callback)
            )
            
            return True
        except Exception as e:
            logger.error(f"Failed to open Bluetooth camera: {e}")
            return False
        finally:
            loop.close()
            
    def capture_frame(self) -> Optional[np.ndarray]:
        if self.use_bluetooth and self.bluetooth_manager.state == ConnectionState.STREAMING:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                if self._bluetooth_frame_ready.is_set():
                    frame = self._bluetooth_frame
                    self._bluetooth_frame_ready.clear()
                    return frame
                return None
            finally:
                loop.close()
        else:
            return super().capture_frame()
            
    def release(self):
        if self.use_bluetooth:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                loop.run_until_complete(self.bluetooth_manager.stop_streaming())
                loop.run_until_complete(self.bluetooth_manager.disconnect())
            finally:
                loop.close()
            self.use_bluetooth = False
        else:
            super().release()


def generate_pairing_qr_code(device: BluetoothDevice, output_path: str, include_config: bool = True) -> str:
    pairing_data = {
        "type": "bluetooth_camera_pairing",
        "version": "1.0",
        "device": {
            "address": device.address,
            "name": device.name,
            "is_camera": device.is_camera
        },
            "timestamp": int(time.time())
    }
    
    if include_config:
        pairing_data["config"] = {
            "width": 640,
            "height": 480,
            "quality": 85,
            "auto_capture": True,
            "interval": 2.0
        }
        
    qr_data = json.dumps(pairing_data, separators=(',', ':'))
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    img.save(output_path)
    
    return qr_data


def generate_pairing_qr_code_base64(device: BluetoothDevice, include_config: bool = True) -> str:
    pairing_data = {
        "type": "bluetooth_camera_pairing",
        "version": "1.0",
        "device": {
            "address": device.address,
            "name": device.name,
            "is_camera": device.is_camera
        }
    }
    
    if include_config:
        pairing_data["config"] = {
            "width": 640,
            "height": 480,
            "quality": 85,
            "auto_capture": True,
            "interval": 2.0
        }
        
    qr_data = json.dumps(pairing_data, separators=(',', ':'))
    
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    qr.add_data(qr_data)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    
    from io import BytesIO
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()
    
    return f"data:image/png;base64,{img_base64}"


async def scan_bluetooth_cameras(
    duration: float = 10.0,
    callback: Optional[Callable[[BluetoothDevice], None]] = None
) -> List[BluetoothDevice]:
    manager = BluetoothCameraManager()
    return await manager.scan_for_devices(duration, filter_camera_only=True, callback=callback)


def create_bluetooth_camera_capture(
    device: BluetoothDevice,
    width: int = 1920,
    height: int = 1080
) -> Optional[BluetoothCameraCapture]:
    if not BLEAK_AVAILABLE:
        logger.error("bleak not installed. Run: pip install bleak")
        return None
        
    manager = BluetoothCameraManager()
    capture = BluetoothCameraCapture(
        camera_id=0,
        width=width,
        height=height,
        bluetooth_manager=manager
    )
    
    config = BluetoothCameraConfig(
        device_address=device.address,
        device_name=device.name,
        image_width=width,
        image_height=height
    )
    
    if capture.open_bluetooth(device, config):
        return capture
    return None