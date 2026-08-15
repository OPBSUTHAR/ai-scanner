import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.camera.bluetooth_camera import (
    BluetoothCameraManager,
    BluetoothDevice,
    BluetoothCameraConfig,
    ConnectionState,
    generate_pairing_qr_code_base64,
    BLEAK_AVAILABLE
)
from src.utils.bluetooth_qr import (
    BluetoothQRGenerator,
    BluetoothPairingData,
    create_bluetooth_qr_for_device,
    create_bluetooth_qr_file,
    create_url_qr_base64
)


class TestBluetoothQRGenerator:
    def test_generate_pairing_qr_base64(self):
        qr_base64 = create_bluetooth_qr_for_device(
            device_id="AA:BB:CC:DD:EE:FF".replace(":", ""),
            device_name="Test Camera",
            device_address="AA:BB:CC:DD:EE:FF"
        )
        
        assert qr_base64.startswith("data:image/png;base64,")
        assert len(qr_base64) > 100
    
    def test_parse_pairing_qr(self):
        generator = BluetoothQRGenerator()
        
        # Create a QR code
        qr_data = generator.generate_pairing_qr(
            device_id="AA:BB:CC:DD:EE:FF".replace(":", ""),
            device_name="Test Camera",
            device_address="AA:BB:CC:DD:EE:FF"
        )
        
        # Parse it back
        parsed = generator.parse_pairing_qr(qr_data)
        
        assert parsed is not None
        assert parsed.device_name == "Test Camera"
        assert parsed.device_address == "AA:BB:CC:DD:EE:FF"
        assert parsed.type == "bluetooth_camera_pairing"
    
    def test_generate_connection_qr(self):
        generator = BluetoothQRGenerator()
        qr_data = generator.generate_connection_qr("192.168.1.100", 5000, "device123")
        
        parsed = generator.parse_connection_qr(qr_data)
        
        assert parsed is not None
        assert parsed["host"] == "192.168.1.100"
        assert parsed["port"] == 5000
        assert parsed["device_id"] == "device123"


class TestBluetoothDevice:
    def test_device_creation(self):
        device = BluetoothDevice(
            address="AA:BB:CC:DD:EE:FF",
            name="Test Camera",
            rssi=-45,
            is_camera=True,
            battery_level=85
        )
        
        assert device.address == "AA:BB:CC:DD:EE:FF"
        assert device.name == "Test Camera"
        assert device.rssi == -45
        assert device.is_camera is True
        assert device.battery_level == 85


class TestBluetoothCameraConfig:
    def test_config_creation(self):
        config = BluetoothCameraConfig(
            device_address="AA:BB:CC:DD:EE:FF",
            device_name="Test Camera",
            image_width=1280,
            image_height=720,
            jpeg_quality=90,
            auto_capture=True,
            capture_interval=1.0
        )
        
        assert config.device_address == "AA:BB:CC:DD:EE:FF"
        assert config.image_width == 1280
        assert config.image_height == 720
        assert config.jpeg_quality == 90
        assert config.auto_capture is True
        assert config.capture_interval == 1.0


class TestBluetoothCameraManager:
    @pytest.mark.skipif(not BLEAK_AVAILABLE, reason="bleak not installed")
    def test_manager_creation(self):
        manager = BluetoothCameraManager()
        assert manager.is_available() is True
        assert manager.state == ConnectionState.DISCONNECTED
    
    @pytest.mark.skipif(not BLEAK_AVAILABLE, reason="bleak not installed")
    def test_manager_not_available(self):
        with patch('src.camera.bluetooth_camera.BLEAK_AVAILABLE', False):
            manager = BluetoothCameraManager()
            assert manager.is_available() is False


class TestBluetoothIntegration:
    def test_qr_generation_for_web(self):
        """Test QR code generation for web app integration"""
        qr_base64 = create_bluetooth_qr_for_device(
            device_id="11:22:33:44:55:66".replace(":", ""),
            device_name="GoPro Hero 10",
            device_address="11:22:33:44:55:66",
            config={"width": 1920, "height": 1080, "quality": 90}
        )
        
        assert qr_base64.startswith("data:image/png;base64,")
        
        # Verify it can be parsed
        generator = BluetoothQRGenerator()
        # The QR data is embedded in the base64, but we can't easily extract it
        # without decoding the image. This is a smoke test.
    
    def test_pairing_data_structure(self):
        """Test the pairing data structure used in QR codes"""
        pairing = BluetoothPairingData(
            device_id="AA:BB:CC:DD:EE:FF".replace(":", ""),
            device_name="Test Camera",
            device_address="AA:BB:CC:DD:EE:FF",
            config={"width": 640, "height": 480, "quality": 85}
        )
        
        assert pairing.type == "bluetooth_camera_pairing"
        assert pairing.version == "1.0"
        assert pairing.device_name == "Test Camera"
        assert pairing.config["width"] == 640

    def test_url_qr_base64(self):
        """QR-first pairing encodes a connect URL."""
        qr = create_url_qr_base64("http://192.168.1.50:5000/bt/cam/abc123")
        assert qr.startswith("data:image/png;base64,")
        assert len(qr) > 100


if __name__ == "__main__":
    pytest.main([__file__, "-v"])