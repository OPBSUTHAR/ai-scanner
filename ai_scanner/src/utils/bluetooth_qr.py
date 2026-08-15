import json
import base64
import qrcode
from io import BytesIO
from typing import Optional, Dict, Any
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class BluetoothPairingData:
    type: str = "bluetooth_camera_pairing"
    version: str = "1.0"
    device_id: str = ""
    device_name: str = ""
    device_address: str = ""
    service_uuid: str = ""
    config: Optional[Dict[str, Any]] = None
    timestamp: int = 0
    pairing_code: Optional[str] = None


class BluetoothQRGenerator:
    DEFAULT_CONFIG = {
        "width": 640,
        "height": 480,
        "quality": 85,
        "auto_capture": True,
        "interval": 2.0
    }
    
    def __init__(self, box_size: int = 10, border: int = 4):
        self.box_size = box_size
        self.border = border
        
    def generate_pairing_qr(
        self,
        device_id: str,
        device_name: str,
        device_address: str,
        service_uuid: str = "",
        config: Optional[Dict[str, Any]] = None,
        pairing_code: Optional[str] = None,
        output_path: Optional[str] = None
    ) -> str:
        import time
        
        pairing_data = BluetoothPairingData(
            device_id=device_id,
            device_name=device_name,
            device_address=device_address,
            service_uuid=service_uuid,
            config=config or self.DEFAULT_CONFIG,
            timestamp=int(time.time()),
            pairing_code=pairing_code
        )
        
        qr_data = json.dumps(asdict(pairing_data), separators=(',', ':'))
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=self.box_size,
            border=self.border,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        if output_path:
            img.save(output_path)
            
        return qr_data
    
    def generate_pairing_qr_base64(
        self,
        device_id: str,
        device_name: str,
        device_address: str,
        service_uuid: str = "",
        config: Optional[Dict[str, Any]] = None,
        pairing_code: Optional[str] = None
    ) -> str:
        self.generate_pairing_qr(
            device_id=device_id,
            device_name=device_name,
            device_address=device_address,
            service_uuid=service_uuid,
            config=config,
            pairing_code=pairing_code,
            output_path=None
        )
        
        pairing_data = BluetoothPairingData(
            device_id=device_id,
            device_name=device_name,
            device_address=device_address,
            service_uuid=service_uuid,
            config=config or self.DEFAULT_CONFIG,
            pairing_code=pairing_code
        )
        
        qr_data = json.dumps(asdict(pairing_data), separators=(',', ':'))
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=self.box_size,
            border=self.border,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        buffered = BytesIO()
        img.save(buffered, format="PNG")
        img_base64 = base64.b64encode(buffered.getvalue()).decode()
        
        return f"data:image/png;base64,{img_base64}"
    
    def generate_connection_qr(
        self,
        host: str,
        port: int,
        device_id: str = "",
        output_path: Optional[str] = None
    ) -> str:
        connection_data = {
            "type": "bluetooth_camera_connection",
            "version": "1.0",
            "host": host,
            "port": port,
            "device_id": device_id,
            "protocol": "ws"
        }
        
        qr_data = json.dumps(connection_data, separators=(',', ':'))
        
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_M,
            box_size=self.box_size,
            border=self.border,
        )
        qr.add_data(qr_data)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        if output_path:
            img.save(output_path)
            
        return qr_data
    
    def parse_pairing_qr(self, qr_data: str) -> Optional[BluetoothPairingData]:
        try:
            data = json.loads(qr_data)
            if data.get("type") == "bluetooth_camera_pairing":
                return BluetoothPairingData(**data)
        except Exception:
            pass
        return None
    
    def parse_connection_qr(self, qr_data: str) -> Optional[Dict[str, Any]]:
        try:
            data = json.loads(qr_data)
            if data.get("type") == "bluetooth_camera_connection":
                return data
        except Exception:
            pass
        return None


def create_bluetooth_qr_for_device(
    device_id: str,
    device_name: str,
    device_address: str,
    config: Optional[Dict[str, Any]] = None
) -> str:
    generator = BluetoothQRGenerator()
    return generator.generate_pairing_qr_base64(
        device_id=device_id,
        device_name=device_name,
        device_address=device_address,
        config=config
    )


def create_bluetooth_qr_file(
    device_id: str,
    device_name: str,
    device_address: str,
    output_path: str,
    config: Optional[Dict[str, Any]] = None
) -> str:
    generator = BluetoothQRGenerator()
    return generator.generate_pairing_qr(
        device_id=device_id,
        device_name=device_name,
        device_address=device_address,
        config=config,
        output_path=output_path
    )


def create_url_qr_base64(url: str, box_size: int = 10, border: int = 4) -> str:
    """Generate a QR code (base64 data URL) that simply encodes a URL.

    Used for the QR-first pairing flow: the scanner page shows a code that the
    user scans with their Bluetooth device, which opens the connection URL.
    """
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=box_size,
        border=border,
    )
    qr.add_data(url)
    qr.make(fit=True)

    img = qr.make_image(fill_color="black", back_color="white")

    buffered = BytesIO()
    img.save(buffered, format="PNG")
    img_base64 = base64.b64encode(buffered.getvalue()).decode()

    return f"data:image/png;base64,{img_base64}"