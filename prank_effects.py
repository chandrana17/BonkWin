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

# ═══════════════════════════════════════════════════════════════
# HACKER TERMINAL SCRIPTS (PowerShell)
# ═══════════════════════════════════════════════════════════════

MATRIX_SCRIPT = r'''
$Host.UI.RawUI.WindowTitle = '[ BREACH DETECTED ]'
try { mode con cols=100 lines=35 } catch {}
$Host.UI.RawUI.BackgroundColor = 'Black'
$Host.UI.RawUI.ForegroundColor = 'Green'
Clear-Host
$w = 100; $end = (Get-Date).AddSeconds(45)
while ((Get-Date) -lt $end) {
    $line = -join (1..$w | ForEach-Object { [char](Get-Random -Minimum 33 -Maximum 126) })
    Write-Host $line -ForegroundColor (@('Green','DarkGreen') | Get-Random) -NoNewline
    Start-Sleep -Milliseconds 25
}
'''

INFILTRATION_SCRIPT = r'''
$Host.UI.RawUI.WindowTitle = '[ MAINFRAME ACCESS ]'
try { mode con cols=90 lines=30 } catch {}
$Host.UI.RawUI.BackgroundColor = 'Black'
Clear-Host
$msgs = @(
    @('[SYS] Initializing breach protocol v4.2.1...', 'Green'),
    @('[NET] Bypassing firewall layer 1 (stateful)...', 'Green'),
    @('[NET] Bypassing firewall layer 2 (IDS/IPS)...', 'Green'),
    @('[NET] Bypassing firewall layer 3 (WAF)...', 'Green'),
    @('[!!!] ACCESS GRANTED - subnet 10.0.0.0/8', 'Red'),
    @('[SCN] Scanning ports 1-65535...', 'Green'),
    @('[SCN] Found 847 open services on 23 hosts', 'Green'),
    @('[EXP] Extracting credentials from LSASS...', 'Green'),
    @('[CRY] Decrypting RSA-4096 keys (GPU accel)...', 'Green'),
    @('[!!!] ROOT ACCESS OBTAINED', 'Red'),
    @('[DWN] Downloading classified files (2.4 TB)...', 'Green'),
    @('[PER] Injecting persistence module...', 'Green'),
    @('[CLN] Covering tracks - clearing event logs...', 'Green'),
    @('[OK ] Mission complete. Exfiltration done.', 'Yellow')
)
foreach ($item in $msgs) {
    Write-Host "[$(Get-Date -Format 'HH:mm:ss.fff')] $($item[0])" -ForegroundColor $item[1]
    Start-Sleep -Milliseconds (Get-Random -Minimum 300 -Maximum 1500)
}
Write-Host "`n>>> DUMPING ACTIVE CONNECTIONS..." -ForegroundColor Yellow
netstat -an
Start-Sleep 20
'''

EXTRACTION_SCRIPT = r'''
$Host.UI.RawUI.WindowTitle = '[ DATA EXTRACTION ]'
try { mode con cols=100 lines=35 } catch {}
$Host.UI.RawUI.BackgroundColor = 'Black'
$Host.UI.RawUI.ForegroundColor = 'Green'
Clear-Host
Write-Host '>>> EXTRACTING FILE SYSTEM DATA...' -ForegroundColor Red
Write-Host '>>> TARGET: C:\Windows\System32' -ForegroundColor Red
Write-Host ''
tree C:\Windows\System32 /F 2>$null
'''


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
        scripts = [MATRIX_SCRIPT, INFILTRATION_SCRIPT, EXTRACTION_SCRIPT]
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
