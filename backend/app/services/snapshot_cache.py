"""In-memory snapshot cache to reduce camera API load."""

import threading
import time
from typing import Dict, Optional, Tuple
from uuid import UUID

_lock = threading.Lock()
_cache: Dict[str, Tuple[bytes, int, int, str, float]] = {}
DEFAULT_TTL = 4.0


def get_cached(camera_id: UUID, ttl: float = DEFAULT_TTL) -> Optional[Tuple[bytes, int, int, str]]:
    key = str(camera_id)
    with _lock:
        entry = _cache.get(key)
        if not entry:
            return None
        jpeg, w, h, source, ts = entry
        if time.time() - ts > ttl:
            del _cache[key]
            return None
        return jpeg, w, h, source


def set_cached(camera_id: UUID, jpeg: bytes, width: int, height: int, source: str) -> None:
    key = str(camera_id)
    with _lock:
        _cache[key] = (jpeg, width, height, source, time.time())
