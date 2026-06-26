"""System health monitoring service."""

import logging
import os
import shutil
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import psutil

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class HealthService:
    def get_system_metrics(self) -> Dict[str, Any]:
        cpu = psutil.cpu_percent(interval=0.5)
        mem = psutil.virtual_memory()
        disk = shutil.disk_usage(settings.storage_path if os.path.exists(settings.storage_path) else "/")

        gpu_percent = None
        vram_percent = None
        try:
            import subprocess

            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=utilization.gpu,memory.used,memory.total", "--format=csv,noheader,nounits"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            if result.returncode == 0:
                parts = result.stdout.strip().split(",")
                gpu_percent = float(parts[0].strip())
                mem_used = float(parts[1].strip())
                mem_total = float(parts[2].strip())
                vram_percent = (mem_used / mem_total * 100) if mem_total > 0 else 0
        except Exception:
            pass

        net = psutil.net_io_counters()
        network_mbps = (net.bytes_sent + net.bytes_recv) / (1024 * 1024)

        degraded = cpu > settings.degraded_mode_cpu_threshold
        if gpu_percent and gpu_percent > settings.degraded_mode_gpu_threshold:
            degraded = True

        return {
            "cpu_percent": cpu,
            "ram_percent": mem.percent,
            "gpu_percent": gpu_percent,
            "vram_percent": vram_percent,
            "disk_percent": disk.used / disk.total * 100,
            "network_mbps": round(network_mbps, 2),
            "degraded_mode": degraded,
        }

    async def get_camera_health(self, db) -> List[Dict[str, Any]]:
        from sqlalchemy import select

        from app.models import Camera

        result = await db.execute(select(Camera).where(Camera.is_active == True))
        cameras = result.scalars().all()

        return [
            {
                "id": str(c.id),
                "name": c.name,
                "status": c.status.value if hasattr(c.status, "value") else c.status,
                "ip_address": c.ip_address,
                "ai_enabled": c.ai_enabled,
                "last_seen_at": c.last_seen_at.isoformat() if c.last_seen_at else None,
            }
            for c in cameras
        ]


health_service = HealthService()
