"""Abstract key management with a local development adapter."""

from pathlib import Path
from typing import Protocol

from cryptography.fernet import Fernet


class KMS(Protocol):
    """Interface implemented by local and cloud key managers."""

    def get_data_key(self) -> bytes: ...


class LocalFileKMS:
    """Read a Fernet-encoded development key from a file."""

    def __init__(self, path: str) -> None:
        self.path = Path(path)

    def get_data_key(self) -> bytes:
        """Load an existing key; create a local development key on first use."""
        if not self.path.exists():
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_bytes(Fernet.generate_key())
        return self.path.read_bytes().strip()


class AWSKMSAdapter:
    """Boundary for cloud envelope encryption."""

    def __init__(self, key_id: str) -> None:
        self.key_id = key_id

    def get_data_key(self) -> bytes:
        """Require cloud GenerateDataKey integration before use."""
        raise NotImplementedError("Configure an AWS KMS GenerateDataKey adapter")
