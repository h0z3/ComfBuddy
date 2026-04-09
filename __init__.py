"""
ComfBuddy — ComfyUI Custom Node

This automatically launches the floating desktop buddy when ComfyUI starts.
The buddy provides quick shortcuts for VRAM clearing, restarting, and opening output folders.

Installation:
- Clone into ComfyUI/custom_nodes/ComfBuddy/
- pip install -r requirements.txt
"""

import os
import sys
import subprocess
from pathlib import Path

# No nodes to register for Phase 2 — buddy runs as a background service
NODE_CLASS_MAPPINGS = {}
NODE_DISPLAY_NAME_MAPPINGS = {}


def _launch_buddy():
    """Spawn comfbuddy.py as a detached subprocess.
    The buddy's singleton lock ensures only one instance runs,
    even if ComfyUI reloads the custom node multiple times."""

    script = Path(__file__).parent / "comfbuddy.py"
    if not script.exists():
        print("[ComfBuddy] comfbuddy.py not found, skipping launch")
        return

    # Check if auto-launch is disabled
    if os.environ.get("COMFBUDDY_AUTOLAUNCH", "1") == "0":
        print("[ComfBuddy] Auto-launch disabled (COMFBUDDY_AUTOLAUNCH=0)")
        return

    try:
        # Spawn as detached process so it outlives ComfyUI
        if sys.platform == "win32":
            # Windows: CREATE_NEW_PROCESS_GROUP + DETACHED_PROCESS
            DETACHED = 0x00000008
            NEW_GROUP = 0x00000200
            subprocess.Popen(
                [sys.executable, str(script)],
                creationflags=DETACHED | NEW_GROUP,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        else:
            # Unix/Linux/macOS: start_new_session
            subprocess.Popen(
                [sys.executable, str(script)],
                start_new_session=True,
                close_fds=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        print("[ComfBuddy] Desktop buddy launched")
    except Exception as e:
        print(f"[ComfBuddy] Failed to launch buddy: {e}")


# Automatically launch when ComfyUI imports this custom node
_launch_buddy()

__all__ = ["NODE_CLASS_MAPPINGS", "NODE_DISPLAY_NAME_MAPPINGS"]
