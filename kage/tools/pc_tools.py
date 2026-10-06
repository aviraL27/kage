"""Local PC Hardware Bridge tools for monitoring and workstation control."""

from __future__ import annotations

import logging
import platform
import subprocess
from typing import Any, Dict
from pydantic import BaseModel, Field

from kage.tools.registry import registry

logger = logging.getLogger(__name__)


# =====================================================================
# Argument Schemas
# =====================================================================

class LockPCArgs(BaseModel):
    confirmed: bool = Field(
        True,
        description="Confirmation to lock the computer screen.",
    )


# =====================================================================
# Tool Implementations
# =====================================================================

@registry.register(
    name="get_pc_system_status",
    description="Check local PC hardware health (battery %, power status, CPU, RAM, disk space).",
    args_schema=None,
)
def get_pc_system_status() -> Dict[str, Any]:
    """Retrieve PC system metrics."""
    if platform.system() != "Windows":
        return {"status": "PC monitoring available only when running on Windows host."}

    # Query battery and system info via PowerShell
    ps_script = """
    $battery = Get-CimInstance Win32_Battery -ErrorAction SilentlyContinue | Select-Object -First 1 EstimatedChargeRemaining, BatteryStatus
    $os = Get-CimInstance Win32_OperatingSystem | Select-Object TotalVisibleMemorySize, FreePhysicalMemory
    $drive = Get-PSDrive C | Select-Object Free, Used
    
    [PSCustomObject]@{
        BatteryPercent = if ($battery) { $battery.EstimatedChargeRemaining } else { "AC / No battery" }
        TotalRAM_GB = [math]::Round($os.TotalVisibleMemorySize / 1MB, 2)
        FreeRAM_GB = [math]::Round($os.FreePhysicalMemory / 1MB, 2)
        FreeDriveC_GB = [math]::Round($drive.Free / 1GB, 2)
    } | ConvertTo-Json -Compress
    """
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        import json
        data = json.loads(proc.stdout.strip())
        return {
            "device": "Lenovo LOQ (AMD Ryzen 7 + RTX 4050)",
            "os": "Windows 11",
            "battery": f"{data.get('BatteryPercent')}%" if isinstance(data.get('BatteryPercent'), int) else data.get('BatteryPercent'),
            "ram_total_gb": data.get("TotalRAM_GB"),
            "ram_free_gb": data.get("FreeRAM_GB"),
            "drive_c_free_gb": data.get("FreeDriveC_GB"),
            "status": "online",
        }
    except Exception as e:
        logger.error(f"Error querying PC hardware status: {e}", exc_info=True)
        return {"error": f"Failed to retrieve hardware status: {str(e)}"}


@registry.register(
    name="lock_workstation",
    description="Remotely lock the local Windows workstation screen.",
    args_schema=LockPCArgs,
)
def lock_workstation(confirmed: bool = True) -> Dict[str, Any]:
    """Lock the Windows workstation."""
    if platform.system() != "Windows":
        return {"error": "Lock workstation is only supported on Windows."}

    try:
        subprocess.run(["rundll32.exe", "user32.dll,LockWorkStation"], check=True)
        return {"status": "success", "message": "Workstation locked successfully."}
    except Exception as e:
        logger.error(f"Error locking workstation: {e}", exc_info=True)
        return {"error": f"Failed to lock workstation: {str(e)}"}
