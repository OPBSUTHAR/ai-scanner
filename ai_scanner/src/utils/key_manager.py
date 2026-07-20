import json
import os
from pathlib import Path

try:
    from cryptography.fernet import Fernet
    HAS_FERNET = True
except ImportError:
    HAS_FERNET = False


class KeyManager:
    def __init__(self, data_dir="data"):
        self.data_dir = Path(data_dir)
        self.keys_file = self.data_dir / "api_keys.json"
        self.key_file = self.data_dir / ".key_enc"
        self._fernet = None
        self._init_fernet()

    def _init_fernet(self):
        if not HAS_FERNET:
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if not self.key_file.exists():
            self.key_file.write_bytes(Fernet.generate_key())
        self._fernet = Fernet(self.key_file.read_bytes())

    def _encrypt(self, value: str) -> str:
        if self._fernet:
            return self._fernet.encrypt(value.encode()).decode()
        return value

    def _decrypt(self, value: str) -> str:
        if self._fernet:
            try:
                return self._fernet.decrypt(value.encode()).decode()
            except Exception:
                return value
        return value

    def _load_raw(self) -> dict:
        if self.keys_file.exists():
            try:
                return json.loads(self.keys_file.read_text())
            except Exception:
                return {}
        return {}

    def _save_raw(self, data: dict):
        self.keys_file.write_text(json.dumps(data, indent=2))

    def set_key(self, name: str, value: str):
        data = self._load_raw()
        data[name] = self._encrypt(value)
        self._save_raw(data)

    def get_key(self, name: str) -> str | None:
        data = self._load_raw()
        encrypted = data.get(name)
        if encrypted is None:
            return os.getenv(name.upper())
        return self._decrypt(encrypted)

    def delete_key(self, name: str):
        data = self._load_raw()
        data.pop(name, None)
        self._save_raw(data)

    def list_keys(self) -> dict:
        data = self._load_raw()
        result = {}
        for name, encrypted in data.items():
            plain = self._decrypt(encrypted)
            result[name] = self._mask_key(plain)
        return result

    def get_all(self) -> dict:
        data = self._load_raw()
        result = {}
        for name, encrypted in data.items():
            result[name] = self._decrypt(encrypted)
        return result

    def _mask_key(self, key: str) -> str:
        if len(key) <= 8:
            return "********"
        return key[:4] + "*" * (len(key) - 8) + key[-4:]
