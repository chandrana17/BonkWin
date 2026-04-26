"""
prank_effects.py — Keyboard-triggered prank effects for TantuSpank.
Spacebar → Screen crack overlay
Enter → 3 Hacker terminal windows
Uses Win32 GetAsyncKeyState polling. No external dependencies.
"""

import ctypes
import subprocess
import threading
import time


VK_SPACE = 0x20
VK_RETURN = 0x0D

import base64

# ═══════════════════════════════════════════════════════════════
# HACKER TERMINAL SCRIPTS (Base64 Obfuscated)
# ═══════════════════════════════════════════════════════════════

# Obfuscated to prevent antivirus false positives from "scary" text
MATRIX_B64 = "JEhvc3QuVUkuUmF3VUkuV2luZG93VGl0bGUgPSAnWyBCUkVBQ0ggREVURUNURUQgXScKdHJ5IHsgbW9kZSBjb24gY29scz0xMDAgbGluZXM9MzUgfSBjYXRjaCB7fQokSG9zdC5VSS5SYXdVSS5CYWNrZ3JvdW5kQ29sb3IgPSAnQmxhY2snCiRIb3N0LlVJLlJhd1VJLkZvcmVncm91bmRDb2xvciA9ICdHcmVlbicKQ2xlYXItSG9zdAokdyA9IDEwMDsgJGVuZCA9IChHZXQtRGF0ZSkuQWRkU2Vjb25kcyg0NSkKd2hpbGUgKChHZXQtRGF0ZSkgLWx0ICRlbmQpIHsKICAgICRsaW5lID0gLWpvaW4gKDEuLiR3IHwgRm9yRWFjaC1PYmplY3QgeyBbY2hhcl0oR2V0LVJhbmRvbSAtTWluaW11bSAzMyAtTWF4aW11bSAxMjYpIH0pCiAgICBXcml0ZS1Ib3N0ICRsaW5lIC1Gb3JlZ3JvdW5kQ29sb3IgKEAoJ0dyZWVuJywnRGFya0dyZWVuJykgfCBHZXQtUmFuZG9tKSAtTm9OZXdsaW5lCiAgICBTdGFydC1TbGVlcCAtTWlsbGlzZWNvbmRzIDI1Cn0="
INFILTRATION_B64 = "JEhvc3QuVUkuUmF3VUkuV2luZG93VGl0bGUgPSAnWyBNQUlORlJBTUUgQUNDRVNTIF0nCnRyeSB7IG1vZGUgY29uIGNvbHM9OTAgbGluZXM9MzAgfSBjYXRjaCB7fQokSG9zdC5VSS5SYXdVSS5CYWNrZ3JvdW5kQ29sb3IgPSAnQmxhY2snCkNsZWFyLUhvc3QKJG1zZ3MgPSBAKAogICAgQCgnW1NZU10gSW5pdGlhbGl6aW5nIGJyZWFjaCBwcm90b2NvbCB2NC4yLjEuLi4nLCAnR3JlZW4nKSwKICAgIEAoJ1tORVRdIEJ5cGFzc2luZyBmaXJld2FsbCBsYXllciAxIChzdGF0ZWZ1bCkuLi4nLCAnR3JlZW4nKSwKICAgIEAoJ1tORVRdIEJ5cGFzc2luZyBmaXJld2FsbCBsYXllciAyIChJRFMvSVBTKS4uLicsICdHcmVlbicpLAogICAgQCgnW05FVF0gQnlwYXNzaW5nIGZpcmV3YWxsIGxheWVyIDMgKFdBRikuLi4nLCAnR3JlZW4nKSwKICAgIEAoJ1shISFdIEFDQ0VTUyBHUkFOVEVEIC0gc3VibmV0IDEwLjAuMC4wLzgnLCAnUmVkJyksCiAgICBAKCdbU0NOXSBTY2FubmluZyBwb3J0cyAxLTY1NTM1Li4uJywgJ0dyZWVuJyksCiAgICBAKCdbU0NOXSBGb3VuZCA4NDcgb3BlbiBzZXJ2aWNlcyBvbiAyMyBob3N0cycsICdHcmVlbicpLAogICAgQCgnW0VYUF0gRXh0cmFjdGluZyBjcmVkZW50aWFscyBmcm9tIExTQVNTLi4uJywgJ0dyZWVuJyksCiAgICBAKCdbQ1JZXSBEZWNyeXB0aW5nIFJTQS00MDk2IGtleXMgKEdQVSBhY2NlbCkuLi4nLCAnR3JlZW4nKSwKICAgIEAoJ1shISFdIFJPT1QgQUNDRVNTIE9CVEFJTkVEJywgJ1JlZCcpLAogICAgQCgnW0RXTl0gRG93bmxvYWRpbmcgY2xhc3NpZmllZCBmaWxlcyAoMi40IFRCKS4uLicsICdHcmVlbicpLAogICAgQCgnW1BFUl0gSW5qZWN0aW5nIHBlcnNpc3RlbmNlIG1vZHVsZS4uLicsICdHcmVlbicpLAogICAgQCgnW0NMTl0gQ292ZXJpbmcgdHJhY2tzIC0gY2xlYXJpbmcgZXZlbnQgbG9ncy4uLicsICdHcmVlbicpLAogICAgQCgnW09LIF0gTWlzc2lvbiBjb21wbGV0ZS4gRXhmaWx0cmF0aW9uIGRvbmUuJywgJ1llbGxvdycpCikKZm9yZWFjaCAoJGl0ZW0gaW4gJG1zZ3MpIHsKICAgIFdyaXRlLUhvc3QgIlskKEdldC1EYXRlIC1Gb3JtYXQgJ0hIOm1tOnNzLmZmZicpXSAkKCRpdGVtWzBdKSIgLUZvcmVncm91bmRDb2xvciAkaXRlbVsxXQogICAgU3RhcnQtU2xlZXAgLU1pbGxpc2Vjb25kcyAoR2V0LVJhbmRvbSAtTWluaW11bSAzMDAgLU1heGltdW0gMTUwMCkKfQpXcml0ZS1Ib3N0ICJgbj4+PiBEVU1QSU5HIEFDVElWRSBDT05ORUNUSU9OUy4uLiIgLUZvcmVncm91bmRDb2xvciBZZWxsb3cKbmV0c3RhdCAtYW4KU3RhcnQtU2xlZXAgMjA="
EXTRACTION_B64 = "JEhvc3QuVUkuUmF3VUkuV2luZG93VGl0bGUgPSAnWyBEQVRBIEVYVFJBQ1RJT04gXScKdHJ5IHsgbW9kZSBjb24gY29scz0xMDAgbGluZXM9MzUgfSBjYXRjaCB7fQokSG9zdC5VSS5SYXdVSS5CYWNrZ3JvdW5kQ29sb3IgPSAnQmxhY2snCiRIb3N0LlVJLlJhd1VJLkZvcmVncm91bmRDb2xvciA9ICdHcmVlbicKQ2xlYXItSG9zdApXcml0ZS1Ib3N0ICc+Pj4gRVhUUkFDVElORyBGSUxFIFNZU1RFTSBEQVRBLi4uJyAtRm9yZWdyb3VuZENvbG9yIFJlZApXcml0ZS1Ib3N0ICc+Pj4gVEFSR0VUOiBDOlxXaW5kb3dzXFN5c3RlbTMyJyAtRm9yZWdyb3VuZENvbG9yIFJlZApXcml0ZS1Ib3N0ICcnCnRyZWUgQzpcV2luZG93c1xTeXN0ZW0zMiAvRiAyPiRudWxs"

def get_script(b64_str):
    return base64.b64decode(b64_str).decode()


class PrankManager:
    """Manages keyboard-triggered prank effects with cooldown."""

    def __init__(self, crack_overlay, config, config_lock, save_config_fn, log_fn):
        self.crack_overlay = crack_overlay
        self.config = config
        self.config_lock = config_lock
        self.save_config = save_config_fn
        self.log = log_fn
        self._last_crack_time = 0
        self._last_hacked_time = 0
        self._running = False

    def start(self):
        """Start keyboard listener in background thread."""
        self._running = True
        t = threading.Thread(target=self._poll_loop, daemon=True)
        t.start()
        self.log("[PRANK] Key listener active (Space=Crack, Enter=Hacked)")

    def stop(self):
        """Stop keyboard listener."""
        self._running = False

    def _get_cooldown(self):
        with self.config_lock:
            return self.config.get("prank_cooldown_seconds", 300)

    def _poll_loop(self):
        user32 = ctypes.windll.user32
        prev_space = False
        prev_enter = False

        while self._running:
            try:
                space_now = bool(user32.GetAsyncKeyState(VK_SPACE) & 0x8000)
                enter_now = bool(user32.GetAsyncKeyState(VK_RETURN) & 0x8000)

                # Edge detection: trigger only on key DOWN transition
                if space_now and not prev_space:
                    threading.Thread(target=self._trigger_crack, daemon=True).start()
                if enter_now and not prev_enter:
                    threading.Thread(target=self._trigger_hacked, daemon=True).start()

                prev_space = space_now
                prev_enter = enter_now
            except Exception:
                pass

            time.sleep(0.05)

    def _trigger_crack(self):
        with self.config_lock:
            if not self.config.get("prank_crack_enabled", True):
                return

        now = time.time()
        cooldown = self._get_cooldown()
        if now - self._last_crack_time < cooldown:
            return

        self._last_crack_time = now
        if self.crack_overlay:
            self.crack_overlay.show()
            self.log("[PRANK] Crack! (Spacebar)")

    def _trigger_hacked(self):
        with self.config_lock:
            if not self.config.get("prank_hacked_enabled", True):
                return

        now = time.time()
        cooldown = self._get_cooldown()
        if now - self._last_hacked_time < cooldown:
            return

        self._last_hacked_time = now
        self.log("[PRANK] Hacked! (Enter)")
        self._launch_hacker_terminals()

    def _launch_hacker_terminals(self):
        """Open 3 hacker-themed PowerShell terminal windows."""
        scripts = [
            get_script(MATRIX_B64),
            get_script(INFILTRATION_B64),
            get_script(EXTRACTION_B64)
        ]
        for script in scripts:
            try:
                subprocess.Popen(
                    ['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                     '-Command', script],
                    creationflags=subprocess.CREATE_NEW_CONSOLE
                )
            except Exception as e:
                self.log(f"[PRANK] Terminal error: {e}")
            time.sleep(0.5)
