"""
crack_overlay.py — Fake screen crack overlay for TantuSpank.
Shows a translucent crack PNG on hard hits. Click-through, no focus steal.
"""
import os
import sys
import threading
import ctypes
import ctypes.wintypes

# Windows constants for click-through transparent window
GWL_EXSTYLE = -20
WS_EX_LAYERED = 0x00080000
WS_EX_TRANSPARENT = 0x00000020
WS_EX_TOPMOST = 0x00000008
WS_EX_TOOLWINDOW = 0x00000080  # Hide from taskbar


class CrackOverlay:
    """Borderless, transparent, always-on-top, click-through fullscreen crack overlay."""

    def __init__(self, crack_png_path, duration_ms=500):
        self.crack_png_path = crack_png_path
        self.duration_ms = duration_ms
        self._root = None
        self._active = False
        self._lock = threading.Lock()

    def show(self):
        """Show the crack overlay. Safe to call from any thread."""
        if not os.path.exists(self.crack_png_path):
            return
        with self._lock:
            if self._active:
                return
            self._active = True
        t = threading.Thread(target=self._show_window, daemon=True)
        t.start()

    def _show_window(self):
        """Create and display the overlay window."""
        try:
            import tkinter as tk
            from PIL import Image, ImageTk

            root = tk.Tk()
            root.withdraw()
            self._root = root

            # Get cursor position to determine which monitor
            cursor_x = root.winfo_pointerx()
            cursor_y = root.winfo_pointery()

            # Get monitor info at cursor position
            try:
                user32 = ctypes.windll.user32

                class MONITORINFO(ctypes.Structure):
                    _fields_ = [
                        ("cbSize", ctypes.wintypes.DWORD),
                        ("rcMonitor", ctypes.wintypes.RECT),
                        ("rcWork", ctypes.wintypes.RECT),
                        ("dwFlags", ctypes.wintypes.DWORD),
                    ]

                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

                pt = POINT(cursor_x, cursor_y)
                MONITOR_DEFAULTTONEAREST = 2
                hMonitor = user32.MonitorFromPoint(pt, MONITOR_DEFAULTTONEAREST)
                mi = MONITORINFO()
                mi.cbSize = ctypes.sizeof(MONITORINFO)
                user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi))

                mon_x = mi.rcMonitor.left
                mon_y = mi.rcMonitor.top
                mon_w = mi.rcMonitor.right - mi.rcMonitor.left
                mon_h = mi.rcMonitor.bottom - mi.rcMonitor.top
            except Exception:
                mon_x, mon_y = 0, 0
                mon_w = root.winfo_screenwidth()
                mon_h = root.winfo_screenheight()

            # Load and resize crack image
            img = Image.open(self.crack_png_path).convert("RGBA")
            img = img.resize((mon_w, mon_h), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)

            # Configure window
            root.overrideredirect(True)
            root.geometry(f"{mon_w}x{mon_h}+{mon_x}+{mon_y}")
            root.attributes("-topmost", True)
            root.attributes("-transparentcolor", "black")
            root.configure(bg="black")
            root.attributes("-alpha", 0.85)

            label = tk.Label(root, image=photo, bg="black", bd=0)
            label.pack(fill="both", expand=True)

            root.deiconify()
            root.update_idletasks()

            # Make click-through using Windows API
            try:
                hwnd = ctypes.windll.user32.GetForegroundWindow()
                # Find our window by iterating — use the root's winfo_id
                hwnd = root.winfo_id()
                # Get parent window handle
                hwnd = ctypes.windll.user32.GetParent(hwnd)
                if hwnd:
                    style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    style |= WS_EX_LAYERED | WS_EX_TRANSPARENT | WS_EX_TOPMOST | WS_EX_TOOLWINDOW
                    ctypes.windll.user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)
            except Exception:
                pass  # Best effort — still works visually even without click-through

            # Auto-hide after duration
            root.after(self.duration_ms, self._hide)
            root.mainloop()

        except Exception as e:
            pass  # Silent fail — overlay is cosmetic
        finally:
            with self._lock:
                self._active = False

    def _hide(self):
        """Hide and destroy the overlay window."""
        try:
            if self._root:
                self._root.destroy()
                self._root = None
        except Exception:
            pass

    def cleanup(self):
        """Force cleanup on app exit."""
        try:
            if self._root:
                self._root.destroy()
                self._root = None
        except Exception:
            pass
