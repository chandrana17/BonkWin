"""
detect.py — TantuSpank v1.0.0
Windows tray app — knock detection via FFT + sound effects.
Privacy-first. Local-only. 0% idle CPU.
"""
import os
import sys
import time
import logging
import logging.handlers
import tempfile
from datetime import date
import pygame
import random
import glob
import threading
import json
import webbrowser
from collections import deque

import pystray
from PIL import Image, ImageDraw, ImageFont
import psutil
import numpy as np
import sounddevice as sd

from crack_overlay import CrackOverlay
from constants import (
    APP_VERSION, APP_NAME, APP_URL, UPI_ID, DONATE_POPUP_SIZE,
    SAMPLE_RATE, BLOCK_DURATION, BLOCK_SIZE, RMS_FLOOR, FREQ_CUTOFF,
    AMBIENT_HISTORY_SECONDS, AMBIENT_MULTIPLIER,
    MIN_SOUNDS_PER_PACK, DEFAULT_SENSITIVITY, DEFAULT_COOLDOWN_MS,
    HARD_HIT_MULTIPLIER, MIN_VOLUME,
    STREAK_WINDOW_MS, STREAK_MIN_KNOCKS, STREAK_COOLDOWN_S,
    MAX_STREAK_NOTIFICATIONS, STREAK_DEQUE_MAXLEN,
    CRACK_DURATION_MS, CRACK_ALPHA,
    CALIBRATION_SECONDS, CALIBRATION_BLOCK_MS,
    CALIBRATION_DEFAULT_RMS, CALIBRATION_BASELINE_MIN, CALIBRATION_BASELINE_MAX,
    CALIBRATION_RMS_DIVISOR,
    STATS_SAVE_INTERVAL, SETTINGS_FILENAME, OUTPUT_FILENAME,
    LOG_FILENAME, LOG_MAX_BYTES, LOG_BACKUP_COUNT, MIN_FILE_SIZE,
    ICON_SIZE, ICON_FONT_SIZE, ICON_BG_COLOR, ICON_TEXT_COLOR, ICON_TEXT,
    MIXER_CHANNELS, COMBO_VOLUME, RECENT_AUDIO_LIMIT,
    DEFAULT_CONFIG, ADULT_MARKERS, AUDIO_EXTENSIONS, AUDIO_GLOBS,
    COOLDOWN_MIN_MS, COOLDOWN_MAX_MS,
    PRANK_COOLDOWN_DEFAULT, PRANK_COOLDOWN_MIN, PRANK_COOLDOWN_MAX,
)
from prank_effects import PrankManager

# ═══════════════════════════════════════════════════════════════
# GLOBAL STATE
# ═══════════════════════════════════════════════════════════════
is_enabled = True
sound_pack_id = "ouch"
sounds = []
sounds_lock = threading.Lock()
cached_sound_objects = []
cached_sounds_lock = threading.Lock()
combo_sounds = []
combo_sounds_lock = threading.Lock()
icon = None
pygame_initialized = False
sound_enabled = False
last_trigger_time = 0

# Full rotation shuffle state
play_history = []
play_history_lock = threading.Lock()

# Streak state
streak_timestamps = deque(maxlen=STREAK_DEQUE_MAXLEN)
last_streak_time = 0

# Crack overlay
crack_overlay = None

# Sensitivity slider window ref
_sensitivity_window = None
_sensitivity_window_lock = threading.Lock()

# Cooldown slider window ref
_cooldown_window = None
_cooldown_window_lock = threading.Lock()

# Prank cooldown slider window ref
_prank_cd_window = None
_prank_cd_window_lock = threading.Lock()

# Donate popup ref
_donate_window = None
_donate_window_lock = threading.Lock()

# Prank manager ref
prank_manager = None

# File picker window ref
_file_picker_window = None
_file_picker_lock = threading.Lock()

# Calibration state
_calibrating = False
_calibration_lock = threading.Lock()

performance_tracking = False
performance_start_time = 0
performance_peak_ram = 0
successful_knock_count = 0

# Pack manifest cache
pack_registry = {}

# Persistent config
config = dict(DEFAULT_CONFIG)
spanks_since_save = 0
config_lock = threading.Lock()
SETTINGS_FILE = None


# ═══════════════════════════════════════════════════════════════
# UTILITY / PATHS
# ═══════════════════════════════════════════════════════════════

def get_project_dir():
    if getattr(sys, "frozen", False):
        # Allow reading custom sound-packs next to the executable if present and populated
        ext_dir = os.path.dirname(sys.executable)
        ext_packs = os.path.join(ext_dir, "sound-packs")
        if os.path.exists(ext_packs):
            # Check if there are actually any mp3/wav files inside the custom sound-packs
            has_files = False
            for root, dirs, files in os.walk(ext_packs):
                if any(f.lower().endswith(AUDIO_EXTENSIONS) for f in files):
                    has_files = True
                    break
            if has_files:
                return ext_dir
        # Otherwise fallback to PyInstaller extraction temp dir
        return sys._MEIPASS
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    if getattr(sys, "frozen", False):
        data_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "TantuSpank")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    return os.path.dirname(os.path.abspath(__file__))


def get_sound_packs_dir():
    return os.path.join(get_project_dir(), "sound-packs")


# ── Logging setup ──
_logger = logging.getLogger(APP_NAME)
_logger.setLevel(logging.INFO)
_log_formatter = logging.Formatter("%(asctime)s %(message)s", datefmt="%H:%M:%S")

# Console handler
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(_log_formatter)
_logger.addHandler(_console_handler)


def _setup_file_logging():
    """Add rotating file handler after data dir is known."""
    log_path = os.path.join(get_data_dir(), LOG_FILENAME)
    fh = logging.handlers.RotatingFileHandler(
        log_path, maxBytes=LOG_MAX_BYTES, backupCount=LOG_BACKUP_COUNT, encoding="utf-8"
    )
    fh.setFormatter(_log_formatter)
    _logger.addHandler(fh)


def log_output(message):
    _logger.info(message)


def init_files():
    _setup_file_logging()


def is_adult_file(filename):
    """Check if filename contains 18+ marker."""
    lower = filename.lower()
    return any(marker in lower for marker in ADULT_MARKERS)


# ═══════════════════════════════════════════════════════════════
# STARTUP MANAGEMENT
# ═══════════════════════════════════════════════════════════════

def get_startup_folder():
    return os.path.join(os.environ["APPDATA"], "Microsoft", "Windows", "Start Menu", "Programs", "Startup")


def get_startup_file_path():
    return os.path.join(get_startup_folder(), "TantuSpank.bat")


def is_startup_enabled(item=None):
    return os.path.exists(get_startup_file_path())


def toggle_startup(icon, item):
    startup_path = get_startup_file_path()
    if is_startup_enabled():
        try:
            os.remove(startup_path)
        except Exception as e:
            log_output(f"[STARTUP] Remove error: {e}")
    else:
        try:
            project_dir = get_project_dir()
            python_exe = sys.executable
            script_path = os.path.abspath(__file__)
            cmd = f'@echo off\ncd /d "{project_dir}"\nstart "" "{python_exe}" "{script_path}"\n'
            with open(startup_path, "w", encoding="utf-8") as f:
                f.write(cmd)
        except Exception as e:
            log_output(f"[STARTUP] Create error: {e}")
    build_and_set_menu()


# ═══════════════════════════════════════════════════════════════
# TRAY ICON
# ═══════════════════════════════════════════════════════════════

def create_image():
    icon_path = os.path.join(get_project_dir(), "assets", "logo.png")
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except Exception:
            pass
            
    icon_path2 = os.path.join(get_project_dir(), "icon.png")
    if os.path.exists(icon_path2):
        try:
            return Image.open(icon_path2)
        except Exception:
            pass

    width, height = 64, 64
    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse([0, 0, width, height], fill=(255, 69, 0))
    try:
        font = ImageFont.truetype("arialbd.ttf", 40)
    except IOError:
        font = ImageFont.load_default()
    text = "T"
    try:
        left, top, right, bottom = dc.textbbox((0, 0), text, font=font)
        tw, th = right - left, bottom - top
        dc.text(((width - tw) / 2, (height - th) / 2 - 4), text, font=font, fill=(255, 255, 255))
    except AttributeError:
        tw, th = dc.textsize(text, font=font)
        dc.text(((width - tw) / 2, (height - th) / 2), text, font=font, fill=(255, 255, 255))
    return image


# ═══════════════════════════════════════════════════════════════
# CONFIG / STATS
# ═══════════════════════════════════════════════════════════════

def load_config():
    global config, SETTINGS_FILE, sound_pack_id
    SETTINGS_FILE = os.path.join(get_data_dir(), SETTINGS_FILENAME)

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                for key in config:
                    if key in saved:
                        config[key] = saved[key]
        except Exception as e:
            log_output(f"[CONFIG] Load error: {e}")

    with config_lock:
        sound_pack_id = config.get("last_used_pack", "ouch")

    # Clamp stale baseline_multiplier from previous buggy calibration
    if config.get("baseline_multiplier", 1.0) > CALIBRATION_BASELINE_MAX:
        config["baseline_multiplier"] = 1.0
        config["calibration_done"] = False
        log_output("[CONFIG] Reset stale baseline_multiplier")

    _rollover_daily_stats()
    log_output(f"[CONFIG] Total: {config['total_spanks']}, Today: {config['today_count']}, Best: {config['best_day']}")
    return config


def _rollover_daily_stats():
    today_str = date.today().isoformat()
    with config_lock:
        if config.get("today_date", "") != today_str:
            if config.get("today_count", 0) > config.get("best_day", 0):
                config["best_day"] = config["today_count"]
            config["today_count"] = 0
            config["today_date"] = today_str


def save_config():
    if SETTINGS_FILE is None:
        return
    with config_lock:
        try:
            config["last_used_pack"] = sound_pack_id
            # Atomic write: temp file → rename
            dir_name = os.path.dirname(SETTINGS_FILE)
            fd, tmp_path = tempfile.mkstemp(suffix=".tmp", dir=dir_name)
            try:
                with os.fdopen(fd, "w", encoding="utf-8") as f:
                    json.dump(config, f, indent=2)
                os.replace(tmp_path, SETTINGS_FILE)
            except Exception:
                # Clean up temp file on failure
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass
                raise
        except Exception as e:
            log_output(f"[CONFIG] Save error: {e}")


def on_open_settings(icon, item):
    try:
        if not os.path.exists(SETTINGS_FILE):
            save_config()
        os.startfile(SETTINGS_FILE)
    except Exception:
        pass


def on_reset_stats(icon, item):
    global spanks_since_save
    with config_lock:
        config["total_spanks"] = 0
        config["today_count"] = 0
        config["best_day"] = 0
        config["today_date"] = date.today().isoformat()
    spanks_since_save = 0
    save_config()
    update_tray_menu()


def update_tray_menu():
    global icon
    if icon is None:
        return
    count = config["total_spanks"]
    icon.title = f"{APP_NAME} v{APP_VERSION} — {count} Spank{'s' if count != 1 else ''}"
    build_and_set_menu()


# ═══════════════════════════════════════════════════════════════
# PACK REGISTRY — Manifest-based discovery
# ═══════════════════════════════════════════════════════════════

def scan_packs():
    global pack_registry
    packs_dir = get_sound_packs_dir()
    registry = {}
    total_mp3 = 0
    total_adult = 0

    if not os.path.exists(packs_dir):
        os.makedirs(os.path.join(packs_dir, "ouch"), exist_ok=True)
        return registry

    for entry in os.listdir(packs_dir):
        entry_path = os.path.join(packs_dir, entry)
        if not os.path.isdir(entry_path) or entry == "combo":
            continue

        manifest_path = os.path.join(entry_path, "pack-manifest.json")
        if not os.path.exists(manifest_path):
            # Auto-create minimal manifest for folders without one
            manifest = {"id": entry, "name": entry.replace("-", " ").title(), "adult": False}
            try:
                with open(manifest_path, "w", encoding="utf-8") as f:
                    json.dump(manifest, f, indent=2)
            except Exception:
                pass
        else:
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
            except Exception:
                manifest = {"id": entry, "name": entry.replace("-", " ").title(), "adult": False}

        # Count files
        mp3_files = [f for f in os.listdir(entry_path) if f.lower().endswith(AUDIO_EXTENSIONS)]
        adult_files = [f for f in mp3_files if is_adult_file(f)]
        clean_files = [f for f in mp3_files if not is_adult_file(f)]

        manifest["path"] = entry_path
        manifest["total_files"] = len(mp3_files)
        manifest["adult_files"] = len(adult_files)
        manifest["clean_files"] = len(clean_files)
        manifest["has_adult_files"] = len(adult_files) > 0

        pack_id = manifest.get("id", entry)
        registry[pack_id] = manifest
        total_mp3 += len(mp3_files)
        total_adult += len(adult_files)

    pack_registry = registry
    log_output(f"[PACKS] {len(registry)} packs, {total_mp3} files total ({total_adult} marked 18+)")
    return registry


def get_total_file_count():
    """Count total MP3 files across all packs."""
    total = 0
    packs_dir = get_sound_packs_dir()
    for entry in os.listdir(packs_dir):
        entry_path = os.path.join(packs_dir, entry)
        if os.path.isdir(entry_path):
            total += len([f for f in os.listdir(entry_path) if f.lower().endswith(AUDIO_EXTENSIONS)])
    return total


def _cache_sounds():
    """Pre-load sound files as pygame.mixer.Sound objects, respecting 18+ filter and disabled files."""
    global cached_sound_objects, play_history
    if not pygame_initialized:
        return

    with sounds_lock:
        current_files = sounds.copy()

    allow_adult = config.get("allow_adult_audio", False)
    disabled = config.get("disabled_files", {}).get(sound_pack_id, [])

    new_cache = []
    for sf in current_files:
        basename = os.path.basename(sf)
        # Skip 18+ files if adult audio disabled
        if not allow_adult and is_adult_file(basename):
            log_output(f"[CACHE] Skip 18+ file: {basename}")
            continue
        # Skip user-disabled files
        if basename in disabled:
            log_output(f"[CACHE] Skip disabled: {basename}")
            continue
        try:
            if os.path.getsize(sf) < MIN_FILE_SIZE:
                continue
            snd = pygame.mixer.Sound(sf)
            new_cache.append(snd)
        except Exception as e:
            log_output(f"[CACHE] Skip {basename}: {e}")

    with cached_sounds_lock:
        cached_sound_objects = new_cache
    with play_history_lock:
        play_history = []

    log_output(f"[CACHE] {len(new_cache)} sounds loaded (adult={'ON' if allow_adult else 'OFF'})")


def load_combo_sounds():
    global combo_sounds
    combo_dir = os.path.join(get_sound_packs_dir(), "combo")
    if not os.path.exists(combo_dir) or not pygame_initialized:
        return
    new_combos = []
    for ext in AUDIO_GLOBS:
        for f in glob.glob(os.path.join(combo_dir, ext)):
            try:
                if os.path.getsize(f) < MIN_FILE_SIZE:
                    continue
                snd = pygame.mixer.Sound(f)
                new_combos.append(snd)
            except Exception:
                pass
    with combo_sounds_lock:
        combo_sounds = new_combos
    log_output(f"[COMBO] {len(new_combos)} combo sounds")


def load_pack(pack_id_or_path):
    """Load all sound files from specified pack."""
    global sounds, sound_pack_id
    new_sounds = []
    
    if pack_id_or_path == "favorites":
        favs = config.get("favorite_files", [])
        valid_sounds = [sf for sf in favs if os.path.exists(sf) and os.path.getsize(sf) >= MIN_FILE_SIZE]
        with sounds_lock:
            sounds = valid_sounds
            sound_pack_id = "favorites"
        _cache_sounds()
        log_output(f"[PACK] 'favorites' → {len(valid_sounds)} files")
        return len(valid_sounds)

    if os.path.isabs(pack_id_or_path):
        target = pack_id_or_path
        if os.path.exists(target):
            if os.path.isfile(target):
                new_sounds.append(target)
            elif os.path.isdir(target):
                for ext in AUDIO_GLOBS:
                    new_sounds.extend(glob.glob(os.path.join(target, ext)))
                new_sounds = sorted(list(set(new_sounds)))
        with sounds_lock:
            sounds = new_sounds
            sound_pack_id = pack_id_or_path
        _cache_sounds()
        return len(new_sounds)

    if pack_id_or_path in pack_registry:
        target = pack_registry[pack_id_or_path]["path"]
    else:
        target = os.path.join(get_sound_packs_dir(), pack_id_or_path)

    if os.path.exists(target) and os.path.isdir(target):
        for ext in AUDIO_GLOBS:
            new_sounds.extend(glob.glob(os.path.join(target, ext)))
        new_sounds = sorted(list(set(new_sounds)))

    valid_sounds = [sf for sf in new_sounds if os.path.getsize(sf) >= MIN_FILE_SIZE]

    with sounds_lock:
        sounds = valid_sounds
        sound_pack_id = pack_id_or_path

    _cache_sounds()
    log_output(f"[PACK] '{pack_id_or_path}' → {len(valid_sounds)} files")
    return len(valid_sounds)


def on_pack_selected(icon_ref, pack_id):
    global sound_enabled

    if pack_id in pack_registry:
        manifest = pack_registry[pack_id]
        if manifest.get("adult", False) and not config.get("adult_confirmed", False):
            warning = manifest.get("warning", "This pack contains adult content. Are you 18+?")
            if not _show_adult_warning(warning):
                return
            with config_lock:
                config["adult_confirmed"] = True
            save_config()

    if pygame_initialized:
        try:
            pygame.mixer.stop()
        except Exception:
            pass

    loaded = load_pack(pack_id)
    with cached_sounds_lock:
        active_count = len(cached_sound_objects)

    if active_count >= MIN_SOUNDS_PER_PACK:
        sound_enabled = True
        with config_lock:
            config["last_used_pack"] = pack_id
    else:
        sound_enabled = False
        log_output(f"[PACK] '{pack_id}' → 0 active sounds after filtering")
        _fallback_to_ouch(pack_id)

    save_config()
    build_and_set_menu()


def _fallback_to_ouch(failed_id):
    global sound_enabled
    if failed_id != "ouch":
        load_pack("ouch")
        with cached_sounds_lock:
            sound_enabled = len(cached_sound_objects) >= MIN_SOUNDS_PER_PACK
        log_output("[PACK] Fallback → ouch")


def _show_adult_warning(message):
    import tkinter as tk
    result = [False]

    def on_confirm():
        result[0] = True
        root.destroy()

    def on_cancel():
        root.destroy()

    root = tk.Tk()
    root.title("Age Verification")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.configure(bg="#1a1a2e")
    root.grab_set()  # modal
    w, h = 420, 200
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    tk.Label(root, text="⚠️", font=("Segoe UI Emoji", 28), bg="#1a1a2e").pack(pady=(10, 0))
    tk.Label(root, text=message, font=("Segoe UI", 10), fg="#e0e0e0", bg="#1a1a2e",
             wraplength=380, justify="center").pack(pady=10, padx=20)

    btn_frame = tk.Frame(root, bg="#1a1a2e")
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="I am 18+ — Enable", command=on_confirm,
              bg="#e74c3c", fg="white", font=("Segoe UI", 10, "bold"),
              relief="flat", padx=15, pady=5, cursor="hand2").pack(side="left", padx=10)
    tk.Button(btn_frame, text="Cancel", command=on_cancel,
              bg="#2c2c54", fg="#aaa", font=("Segoe UI", 10),
              relief="flat", padx=15, pady=5, cursor="hand2").pack(side="left", padx=10)

    root.bind("<Escape>", lambda e: on_cancel())
    root.protocol("WM_DELETE_WINDOW", on_cancel)
    root.mainloop()
    return result[0]


# ═══════════════════════════════════════════════════════════════
# FEATURE: 18+ AUDIO TOGGLE
# ═══════════════════════════════════════════════════════════════

def on_toggle_adult_audio(icon_ref, item):
    with config_lock:
        config["allow_adult_audio"] = not config.get("allow_adult_audio", False)
    save_config()
    # Reload current pack with new filter
    if pygame_initialized:
        _cache_sounds()
    build_and_set_menu()
    state = "ON" if config["allow_adult_audio"] else "OFF"
    log_output(f"[18+] Adult audio: {state}")


def is_adult_audio_allowed(item):
    return config.get("allow_adult_audio", False)


# ═══════════════════════════════════════════════════════════════
# FEATURE: PER-FILE SELECT/DESELECT
# ═══════════════════════════════════════════════════════════════

def on_open_file_picker(icon_ref, item):
    """Open file picker window to enable/disable individual sounds and favorites."""
    global _file_picker_window
    with _file_picker_lock:
        if _file_picker_window is not None:
            try:
                _file_picker_window.lift()
                _file_picker_window.focus_force()
                return
            except Exception:
                _file_picker_window = None

    t = threading.Thread(target=_create_sound_manager, daemon=True)
    t.start()


def _create_sound_manager():
    global _file_picker_window
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("TantuSpank — Sound Manager")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.configure(bg="#16213e")

    w = 700
    h = 500
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    with _file_picker_lock:
        _file_picker_window = root

    allow_adult = config.get("allow_adult_audio", False)

    # Left pane: Pack list
    left_frame = tk.Frame(root, bg="#1a1a2e", width=200)
    left_frame.pack(side="left", fill="y")
    left_frame.pack_propagate(False)

    tk.Label(left_frame, text="Sound Packs", font=("Segoe UI", 12, "bold"), bg="#1a1a2e", fg="#e94560").pack(pady=10)

    pack_listbox = tk.Listbox(left_frame, bg="#0f3460", fg="#e0e0e0", selectbackground="#e94560", borderwidth=0, highlightthickness=0, font=("Segoe UI", 10))
    pack_listbox.pack(fill="both", expand=True, padx=10, pady=10)

    packs = sorted(pack_registry.keys(), key=lambda k: pack_registry[k].get("name", k))
    
    # We will populate custom files implicitly using `recent_audios`
    recent_list = config.get("recent_audios", [])
    has_recent = len(recent_list) > 0
    if has_recent:
        packs.append("recent_custom_files")

    for pid in packs:
        if pid == "recent_custom_files":
            pack_listbox.insert(tk.END, "Custom Files")
        else:
            pack_name = pack_registry[pid].get("name", pid)
            pack_listbox.insert(tk.END, pack_name)

    # Right pane: File list
    right_frame = tk.Frame(root, bg="#16213e")
    right_frame.pack(side="right", fill="both", expand=True)

    header_label = tk.Label(right_frame, text="Select a pack", font=("Segoe UI", 14, "bold"), bg="#16213e", fg="#e94560")
    header_label.pack(pady=10)

    canvas = tk.Canvas(right_frame, bg="#16213e", highlightthickness=0)
    scrollbar = ttk.Scrollbar(right_frame, orient="vertical", command=canvas.yview)
    scroll_frame = tk.Frame(canvas, bg="#16213e")

    scroll_frame.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
    canvas.create_window((0, 0), window=scroll_frame, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="top", fill="both", expand=True, padx=10, pady=5)
    scrollbar.pack(side="right", fill="y")

    current_vars = {}

    def save_current_pack():
        if hasattr(save_current_pack, 'current_pid') and save_current_pack.current_pid:
            pid = save_current_pack.current_pid
            if pid == "recent_custom_files":
                return
            disabled = []
            for af, var in current_vars.items():
                if not var.get() and not (is_adult_file(af) and not allow_adult):
                    disabled.append(af)
            with config_lock:
                if "disabled_files" not in config:
                    config["disabled_files"] = {}
                config["disabled_files"][pid] = disabled

    def toggle_fav(af, btn):
        with config_lock:
            favs = config.get("favorite_files", [])
            if af in favs:
                favs.remove(af)
                btn.config(text="♡", fg="#888")
            else:
                if af not in favs:
                    favs.append(af)
                btn.config(text="❤️", fg="#e94560")
            config["favorite_files"] = favs

    def on_pack_select(evt):
        sel = pack_listbox.curselection()
        if not sel: return
        idx = sel[0]
        pid = packs[idx]

        save_current_pack()
        save_current_pack.current_pid = pid

        for widget in scroll_frame.winfo_children():
            widget.destroy()
        current_vars.clear()

        pack_path = ""
        if pid == "recent_custom_files":
            header_label.config(text="Custom Files")
            audio_files = [] 
            abs_files = recent_list
        else:
            pack_name = pack_registry[pid].get("name", pid)
            header_label.config(text=f"Files in {pack_name}")
            pack_path = pack_registry[pid]["path"]
            if os.path.isdir(pack_path):
                audio_files = sorted([f for f in os.listdir(pack_path) if f.lower().endswith(AUDIO_EXTENSIONS)])
            else:
                audio_files = []
            abs_files = [os.path.join(pack_path, f) for f in audio_files]

        disabled = config.get("disabled_files", {}).get(pid, [])
        favs = config.get("favorite_files", [])
        
        # Iterate over paths
        for idx, abs_path in enumerate(abs_files):
            if pid == "recent_custom_files":
                af = abs_path
                display_name = os.path.basename(af)
            else:
                af = audio_files[idx]
                display_name = af

            if not os.path.exists(abs_path):
                continue

            is_18 = is_adult_file(display_name)
            is_disabled = (af in disabled) if pid != "recent_custom_files" else False
            is_blocked_by_filter = is_18 and not allow_adult

            var = tk.BooleanVar(value=not is_disabled and not is_blocked_by_filter)
            current_vars[af] = var

            if is_18:
                display_name = f"🔞 {display_name}"

            fg_color = "#666" if is_blocked_by_filter else ("#e0e0e0" if not is_disabled else "#888")

            row_frame = tk.Frame(scroll_frame, bg="#16213e")
            row_frame.pack(fill="x", pady=2)

            cb = tk.Checkbutton(row_frame, text=display_name, variable=var,
                                bg="#16213e", fg=fg_color, selectcolor="#0f3460",
                                activebackground="#16213e", activeforeground="#e0e0e0",
                                font=("Segoe UI", 10), anchor="w",
                                state="disabled" if is_blocked_by_filter else "normal")
            
            if pid != "recent_custom_files":
                cb.pack(side="left", fill="x", expand=True)
            else:
                # Can't disable custom files via checkbox in this view, just unlist them from UI
                tk.Label(row_frame, text=display_name, bg="#16213e", fg="#e0e0e0", font=("Segoe UI", 10), anchor="w").pack(side="left", fill="x", expand=True, padx=5)

            is_fav = abs_path in favs
            fav_btn = tk.Button(row_frame, text="❤️" if is_fav else "♡", font=("Segoe UI Emoji", 10),
                                bg="#16213e", fg="#e94560" if is_fav else "#888", activebackground="#16213e",
                                activeforeground="#ff4466", relief="flat", cursor="hand2")
            fav_btn.config(command=lambda f=abs_path, b=fav_btn: toggle_fav(f, b))
            fav_btn.pack(side="right", padx=10)

    pack_listbox.bind("<<ListboxSelect>>", on_pack_select)

    def on_apply():
        save_current_pack()
        save_config()
        if pygame_initialized:
            _cache_sounds()
        build_and_set_menu()
        with _file_picker_lock:
            _file_picker_window = None
        root.destroy()

    def on_close():
        with _file_picker_lock:
            _file_picker_window = None
        root.destroy()

    btn_frame = tk.Frame(right_frame, bg="#16213e")
    btn_frame.pack(pady=10)
    tk.Button(btn_frame, text="Apply Settings", command=on_apply, bg="#e94560", fg="white",
              font=("Segoe UI", 10, "bold"), relief="flat", padx=20, pady=5, cursor="hand2").pack(side="left", padx=10)
    tk.Button(btn_frame, text="Close", command=on_close, bg="#2c2c54", fg="#aaa",
              font=("Segoe UI", 10), relief="flat", padx=20, pady=5, cursor="hand2").pack(side="left", padx=10)

    save_current_pack.current_pid = None
    if sound_pack_id in packs:
        idx = packs.index(sound_pack_id)
        pack_listbox.selection_set(idx)
        pack_listbox.event_generate("<<ListboxSelect>>")
    elif packs:
        pack_listbox.selection_set(0)
        pack_listbox.event_generate("<<ListboxSelect>>")

    root.bind("<Escape>", lambda e: on_close())
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


# ═══════════════════════════════════════════════════════════════
# FEATURE A — LIVE SENSITIVITY SLIDER
# ═══════════════════════════════════════════════════════════════

def on_open_sensitivity_slider(icon_ref, item):
    global _sensitivity_window
    with _sensitivity_window_lock:
        if _sensitivity_window is not None:
            try:
                _sensitivity_window.lift()
                _sensitivity_window.focus_force()
                return
            except Exception:
                _sensitivity_window = None
    t = threading.Thread(target=_create_sensitivity_slider, daemon=True)
    t.start()


def _create_sensitivity_slider():
    global _sensitivity_window
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("TantuSpank — Sensitivity")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.configure(bg="#16213e")
    w, h = 340, 140
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    with _sensitivity_window_lock:
        _sensitivity_window = root

    current_val = config.get("sensitivity", 0.75)
    var = tk.DoubleVar(value=current_val)

    label = tk.Label(root, text=f"{int(current_val * 100)}%",
                     font=("Segoe UI", 16, "bold"), fg="#e94560", bg="#16213e")
    label.pack(pady=(12, 0))

    def on_slide(val):
        fval = float(val)
        label.config(text=f"{int(fval * 100)}%")
        with config_lock:
            config["sensitivity"] = round(fval, 2)

    slider = ttk.Scale(root, from_=0.0, to=1.0, orient="horizontal",
                       variable=var, command=on_slide, length=280)
    slider.pack(pady=8)

    # Labels below slider
    label_frame = tk.Frame(root, bg="#16213e")
    label_frame.pack(fill="x", padx=30)
    tk.Label(label_frame, text="Quiet Room", font=("Segoe UI", 8), fg="#888",
             bg="#16213e").pack(side="left")
    tk.Label(label_frame, text="Noisy Room", font=("Segoe UI", 8), fg="#888",
             bg="#16213e").pack(side="right")

    def on_close():
        global _sensitivity_window
        save_config()
        build_and_set_menu()
        with _sensitivity_window_lock:
            _sensitivity_window = None
        root.destroy()

    root.bind("<Escape>", lambda e: on_close())
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


# ═══════════════════════════════════════════════════════════════
# FEATURE A2 — BONK COOLDOWN SLIDER
# ═══════════════════════════════════════════════════════════════

def on_open_cooldown_slider(icon_ref, item):
    global _cooldown_window
    with _cooldown_window_lock:
        if _cooldown_window is not None:
            try:
                _cooldown_window.lift()
                _cooldown_window.focus_force()
                return
            except Exception:
                _cooldown_window = None
    t = threading.Thread(target=_create_cooldown_slider, daemon=True)
    t.start()


def _create_cooldown_slider():
    global _cooldown_window
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("TantuSpank — Bonk Cooldown")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.configure(bg="#16213e")
    w, h = 380, 160
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    with _cooldown_window_lock:
        _cooldown_window = root

    current_ms = config.get("cooldown_ms", DEFAULT_COOLDOWN_MS)
    var = tk.IntVar(value=current_ms)

    label = tk.Label(root, text=f"{current_ms} ms",
                     font=("Segoe UI", 16, "bold"), fg="#e94560", bg="#16213e")
    label.pack(pady=(12, 0))

    desc = tk.Label(root, text="Wait time between bonk detections",
                    font=("Segoe UI", 8), fg="#888", bg="#16213e")
    desc.pack()

    def on_slide(val):
        ms = int(float(val))
        label.config(text=f"{ms} ms")
        with config_lock:
            config["cooldown_ms"] = ms

    slider = ttk.Scale(root, from_=COOLDOWN_MIN_MS, to=COOLDOWN_MAX_MS,
                       orient="horizontal", variable=var, command=on_slide, length=320)
    slider.pack(pady=8)

    label_frame = tk.Frame(root, bg="#16213e")
    label_frame.pack(fill="x", padx=30)
    tk.Label(label_frame, text="Rapid (100ms)", font=("Segoe UI", 8), fg="#888",
             bg="#16213e").pack(side="left")
    tk.Label(label_frame, text="Slow (3s)", font=("Segoe UI", 8), fg="#888",
             bg="#16213e").pack(side="right")

    def on_close():
        global _cooldown_window
        save_config()
        build_and_set_menu()
        with _cooldown_window_lock:
            _cooldown_window = None
        root.destroy()

    root.bind("<Escape>", lambda e: on_close())
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


# ═══════════════════════════════════════════════════════════════
# FEATURE P — PRANK EFFECTS (Toggle + Cooldown Slider)
# ═══════════════════════════════════════════════════════════════

def _fmt_prank_cd(seconds):
    """Format prank cooldown for menu display."""
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    return f"{m}m" if s == 0 else f"{m}m {s}s"


def on_toggle_prank_crack(icon_ref, item):
    with config_lock:
        config["prank_crack_enabled"] = not config.get("prank_crack_enabled", True)
    save_config()
    build_and_set_menu()


def is_prank_crack_on(item):
    return config.get("prank_crack_enabled", True)


def on_toggle_prank_hacked(icon_ref, item):
    with config_lock:
        config["prank_hacked_enabled"] = not config.get("prank_hacked_enabled", True)
    save_config()
    build_and_set_menu()


def is_prank_hacked_on(item):
    return config.get("prank_hacked_enabled", True)


def on_open_prank_cd_slider(icon_ref, item):
    global _prank_cd_window
    with _prank_cd_window_lock:
        if _prank_cd_window is not None:
            try:
                _prank_cd_window.lift()
                _prank_cd_window.focus_force()
                return
            except Exception:
                _prank_cd_window = None
    t = threading.Thread(target=_create_prank_cd_slider, daemon=True)
    t.start()


def _create_prank_cd_slider():
    global _prank_cd_window
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    root.title("TantuSpank — Prank Cooldown")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.configure(bg="#16213e")
    w, h = 400, 160
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    with _prank_cd_window_lock:
        _prank_cd_window = root

    current = config.get("prank_cooldown_seconds", PRANK_COOLDOWN_DEFAULT)
    var = tk.IntVar(value=current)

    label = tk.Label(root, text=_fmt_prank_cd(current),
                     font=("Segoe UI", 16, "bold"), fg="#e94560", bg="#16213e")
    label.pack(pady=(12, 0))

    desc = tk.Label(root, text="Wait time between prank triggers",
                    font=("Segoe UI", 8), fg="#888", bg="#16213e")
    desc.pack()

    def on_slide(val):
        s = int(float(val))
        label.config(text=_fmt_prank_cd(s))
        with config_lock:
            config["prank_cooldown_seconds"] = s

    slider = ttk.Scale(root, from_=PRANK_COOLDOWN_MIN, to=PRANK_COOLDOWN_MAX,
                       orient="horizontal", variable=var, command=on_slide, length=340)
    slider.pack(pady=8)

    label_frame = tk.Frame(root, bg="#16213e")
    label_frame.pack(fill="x", padx=30)
    tk.Label(label_frame, text="10s", font=("Segoe UI", 8), fg="#888",
             bg="#16213e").pack(side="left")
    tk.Label(label_frame, text="60m", font=("Segoe UI", 8), fg="#888",
             bg="#16213e").pack(side="right")

    def on_close():
        global _prank_cd_window
        save_config()
        build_and_set_menu()
        with _prank_cd_window_lock:
            _prank_cd_window = None
        root.destroy()

    root.bind("<Escape>", lambda e: on_close())
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


# ═══════════════════════════════════════════════════════════════
# FEATURE D — STREAK MODE
# ═══════════════════════════════════════════════════════════════

def check_streak(current_time):
    global last_streak_time
    if not config.get("streak_enabled", True):
        return False
    if current_time - last_streak_time < STREAK_COOLDOWN_S:
        return False
    streak_timestamps.append(current_time)
    window_start = current_time - (STREAK_WINDOW_MS / 1000.0)
    recent = [t for t in streak_timestamps if t >= window_start]
    if len(recent) >= STREAK_MIN_KNOCKS:
        last_streak_time = current_time
        streak_timestamps.clear()
        return True
    return False


def play_combo_sound():
    with combo_sounds_lock:
        if not combo_sounds:
            return
        snd = random.choice(combo_sounds)
    try:
        channel = snd.play()
        if channel:
            channel.set_volume(COMBO_VOLUME)
    except Exception:
        pass

    # Streak notification (max 3 times ever)
    with config_lock:
        count = config.get("streak_notif_count", 0)
        if count < MAX_STREAK_NOTIFICATIONS:
            config["streak_notif_count"] = count + 1
            should_notify = True
        else:
            should_notify = False

    if should_notify and icon:
        try:
            icon.notify("Streak! Keep going.", APP_NAME)
        except Exception:
            pass
    save_config()


def on_toggle_streak(icon_ref, item):
    with config_lock:
        config["streak_enabled"] = not config.get("streak_enabled", True)
    save_config()
    build_and_set_menu()


def is_streak_enabled(item):
    return config.get("streak_enabled", True)


# ═══════════════════════════════════════════════════════════════
# FEATURE E — SCREEN CRACK OVERLAY
# ═══════════════════════════════════════════════════════════════

def on_toggle_crack(icon_ref, item):
    with config_lock:
        config["crack_enabled"] = not config.get("crack_enabled", True)
    save_config()
    build_and_set_menu()


def is_crack_enabled(item):
    return config.get("crack_enabled", True)


# ═══════════════════════════════════════════════════════════════
# FEATURE F — AUTO CALIBRATE
# ═══════════════════════════════════════════════════════════════

def run_calibration(device_index, sample_rate):
    global _calibrating
    with _calibration_lock:
        if _calibrating:
            return
        _calibrating = True

    log_output("[CALIBRATE] Starting...")
    if icon:
        try:
            icon.notify(f"Calibrating... Stay quiet for {CALIBRATION_SECONDS}s.", APP_NAME)
        except Exception:
            pass
    try:
        recording = sd.rec(int(sample_rate * CALIBRATION_SECONDS),
                           samplerate=sample_rate, channels=1,
                           device=device_index, dtype='float32')
        sd.wait()
        rms_values = []
        block_size = int(sample_rate * CALIBRATION_BLOCK_MS)
        audio = recording[:, 0]
        for i in range(0, len(audio) - block_size, block_size):
            block = audio[i:i + block_size]
            rms = np.sqrt(np.mean(block ** 2))
            rms_values.append(rms)
        avg_rms = sum(rms_values) / len(rms_values) if rms_values else CALIBRATION_DEFAULT_RMS
        baseline = max(CALIBRATION_BASELINE_MIN, min(1.0 + (avg_rms * 50), CALIBRATION_BASELINE_MAX))
        with config_lock:
            config["baseline_multiplier"] = round(baseline, 3)
            config["calibration_done"] = True
        save_config()
        log_output(f"[CALIBRATE] Done. Baseline: {baseline:.3f}")
        if icon:
            try:
                icon.notify("Calibration complete!", APP_NAME)
            except Exception:
                pass
    except Exception as e:
        log_output(f"[CALIBRATE] Error: {e}")
        with config_lock:
            config["calibration_done"] = True
            config["baseline_multiplier"] = 1.0
        save_config()
    finally:
        with _calibration_lock:
            _calibrating = False


def on_recalibrate(icon_ref, item):
    with config_lock:
        config["calibration_done"] = False
    save_config()
    log_output("[CALIBRATE] Recalibration requested")


# ═══════════════════════════════════════════════════════════════
# TRAY MENU ACTIONS
# ═══════════════════════════════════════════════════════════════

def on_toggle_enable(icon_ref, item):
    global is_enabled
    is_enabled = not is_enabled
    update_tray_menu()

def get_enable_state(item):
    return is_enabled

def on_quit(icon_ref, item):
    save_config()
    if crack_overlay:
        crack_overlay.cleanup()
    icon_ref.stop()

def on_select_custom_file(icon_ref, item):
    import tkinter as tk
    from tkinter import filedialog
    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    file_path = filedialog.askopenfilename(
        title="Select Sound File",
        filetypes=[("Audio Files", "*.wav *.mp3 *.ogg")]
    )
    if file_path:
        file_path = os.path.normpath(file_path)
        with config_lock:
            recent = config.get("recent_audios", [])
            if file_path in recent:
                recent.remove(file_path)
            recent.insert(0, file_path)
            config["recent_audios"] = recent[:RECENT_AUDIO_LIMIT]
        on_pack_selected(icon_ref, file_path)
    root.destroy()

def on_toggle_favorite(icon_ref, item):
    with config_lock:
        favs = config.setdefault("favorites", [])
        if sound_pack_id in favs:
            while sound_pack_id in favs:
                favs.remove(sound_pack_id)
        else:
            favs.append(sound_pack_id)
    save_config()
    build_and_set_menu()

def on_about(icon_ref, item):
    """Show about info and open website."""
    if icon_ref:
        try:
            icon_ref.notify(f"{APP_NAME} v{APP_VERSION}\nFree forever. Made by TantuCore.", APP_NAME)
        except Exception:
            pass
    webbrowser.open(APP_URL)


def on_donate(icon_ref, item):
    """Open donation popup."""
    global _donate_window
    with _donate_window_lock:
        if _donate_window is not None:
            try:
                _donate_window.lift()
                _donate_window.focus_force()
                return
            except Exception:
                _donate_window = None
    t = threading.Thread(target=_create_donate_popup, daemon=True)
    t.start()


def _create_donate_popup():
    global _donate_window
    import tkinter as tk
    
    root = tk.Tk()
    root.title(f"Support {APP_NAME}")
    root.attributes("-topmost", True)
    root.resizable(False, False)
    root.configure(bg="#16213e")
    w, h = DONATE_POPUP_SIZE
    x = (root.winfo_screenwidth() // 2) - (w // 2)
    y = (root.winfo_screenheight() // 2) - (h // 2)
    root.geometry(f"{w}x{h}+{x}+{y}")

    with _donate_window_lock:
        _donate_window = root

    tk.Label(root, text="Buy Me A Coffee", font=("Segoe UI", 16, "bold"), fg="#e94560", bg="#16213e").pack(pady=(12, 0))
    tk.Label(root, text="Support the developer via UPI", font=("Segoe UI", 10), fg="#888", bg="#16213e").pack(pady=(0, 10))

    try:
        from PIL import ImageTk
        qr_path = os.path.join(get_project_dir(), "assets", "donate_qr.png")
        if os.path.exists(qr_path):
            img = Image.open(qr_path)
            img = img.resize((200, 200), Image.Resampling.LANCZOS)
            photo = ImageTk.PhotoImage(img)
            lbl = tk.Label(root, image=photo, bg="#16213e")
            lbl.image = photo  # keep ref
            lbl.pack(pady=5)
    except Exception as e:
        tk.Label(root, text="(QR Code hidden or error)", fg="red", bg="#16213e").pack(pady=5)

    tk.Label(root, text=UPI_ID, font=("Segoe UI", 12, "bold"), fg="white", bg="#16213e").pack(pady=5)

    def copy_upi():
        root.clipboard_clear()
        root.clipboard_append(UPI_ID)
        root.update()
        btn.config(text="Copied!")
        root.after(2000, lambda: btn.config(text="Copy UPI ID"))

    btn = tk.Button(root, text="Copy UPI ID", command=copy_upi, bg="#e94560", fg="white", 
                    font=("Segoe UI", 10, "bold"), relief="flat", padx=10, pady=5)
    btn.pack(pady=10)

    def on_close():
        global _donate_window
        with _donate_window_lock:
            _donate_window = None
        root.destroy()

    root.bind("<Escape>", lambda e: on_close())
    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


# ═══════════════════════════════════════════════════════════════
# FULL ROTATION SHUFFLE — No repeat until all played
# ═══════════════════════════════════════════════════════════════

def pick_sound_index(total):
    """Pick next sound index, ensuring full rotation before any repeats."""
    global play_history
    if total <= 0:
        return -1
    if total == 1:
        return 0

    with play_history_lock:
        available = [i for i in range(total) if i not in play_history]
        if not available:
            play_history = []
            available = list(range(total))

        idx = random.choice(available)
        play_history.append(idx)
        # Trim history to pack_size - 1
        max_hist = max(total - 1, 1)
        if len(play_history) > max_hist:
            play_history = play_history[-max_hist:]

    return idx


# ═══════════════════════════════════════════════════════════════
# TRAY MENU BUILDER
# ═══════════════════════════════════════════════════════════════

def build_and_set_menu():
    global icon
    img = create_image()

    fav_files = config.get("favorite_files", [])
    recent_list = config.get("recent_audios", config.get("custom_packs", []))

    def make_checked(pack_id):
        return lambda item: pack_id == sound_pack_id

    # Recent files
    recent_items = []
    if not recent_list:
        recent_items.append(pystray.MenuItem("(No recent files)", lambda: None, enabled=False))
    else:
        for r in recent_list:
            recent_items.append(pystray.MenuItem(os.path.basename(r),
                (lambda p: lambda i, it: on_pack_selected(i, p))(r),
                checked=make_checked(r), radio=True))

    # Pack items sorted alphabetically
    pack_items = []
    
    # Prepend Favorites if it exists
    if fav_files:
        p_name = f"⭐ Favorites ({len(fav_files)})"
        mi = pystray.MenuItem(p_name,
            (lambda p: lambda i, it: on_pack_selected(i, p))("favorites"),
            checked=make_checked("favorites"), radio=True)
        pack_items.append(mi)
        pack_items.append(pystray.Menu.SEPARATOR)
        
    for pid, manifest in sorted(pack_registry.items(), key=lambda x: x[1].get("name", x[0])):
        name = manifest.get("name", pid)
        file_count = manifest.get("total_files", 0)
        adult_count = manifest.get("adult_files", 0)

        # Show file count and 18+ indicator
        suffix = f" ({file_count})"
        if adult_count > 0:
            suffix = f" ({file_count}, {adult_count}🔞)"

        mi = pystray.MenuItem(f"{name}{suffix}",
            (lambda p: lambda i, it: on_pack_selected(i, p))(pid),
            checked=make_checked(pid), radio=True)
        pack_items.append(mi)

    # Stats
    total = config.get("total_spanks", 0)
    today = config.get("today_count", 0)
    best = config.get("best_day", 0)
    total_files = sum(m.get("total_files", 0) for m in pack_registry.values())
    total_files += len(recent_list)
    total_packs = len(pack_registry)

    # Active sounds count
    with cached_sounds_lock:
        active_count = len(cached_sound_objects)

    sens_pct = int(config.get("sensitivity", 0.75) * 100)
    cooldown_ms = config.get("cooldown_ms", DEFAULT_COOLDOWN_MS)
    prank_cd_s = config.get("prank_cooldown_seconds", PRANK_COOLDOWN_DEFAULT)
    tooltip = f"{APP_NAME} v{APP_VERSION} — {total} Spank{'s' if total != 1 else ''}"

    menu = pystray.Menu(
        pystray.MenuItem("Enable Detection", on_toggle_enable, checked=get_enable_state),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"Total: {total} | Today: {today} | Best: {best}", lambda: None, enabled=False),
        pystray.MenuItem(f"Sounds: {active_count} active / {total_files} total", lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sound Packs", pystray.Menu(
            *pack_items,
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"Bonk Cooldown ({cooldown_ms}ms)...", on_open_cooldown_slider),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🕒 Recent Custom Files", pystray.Menu(*recent_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🎵 Select Custom File...", on_select_custom_file),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⚙️ Open Sound Manager...", on_open_file_picker),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Settings", pystray.Menu(
            pystray.MenuItem(f"Adjust Sensitivity ({sens_pct}%)...", on_open_sensitivity_slider),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Allow 18+ Audio", on_toggle_adult_audio, checked=is_adult_audio_allowed),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Streak Mode", on_toggle_streak, checked=is_streak_enabled),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Reset Stats", on_reset_stats),
            pystray.MenuItem("Recalibrate", on_recalibrate),
            pystray.MenuItem("Launch at Startup", toggle_startup, checked=is_startup_enabled),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Open Settings File", on_open_settings),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Prank Effects", pystray.Menu(
            pystray.MenuItem("Crack Effect (Spacebar)", on_toggle_prank_crack, checked=is_prank_crack_on),
            pystray.MenuItem("Hacked Effect (Enter)", on_toggle_prank_hacked, checked=is_prank_hacked_on),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(f"Prank Cooldown ({_fmt_prank_cd(prank_cd_s)})...", on_open_prank_cd_slider),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(f"About {APP_NAME} v{APP_VERSION}", on_about),
        pystray.MenuItem("☕ Buy Me a Coffee", on_donate),
        pystray.MenuItem("Quit", on_quit),
    )

    if icon is None:
        icon = pystray.Icon(APP_NAME, img, title=tooltip, menu=menu)
    else:
        icon.title = tooltip
        icon.menu = menu
        icon.update_menu()


def setup_tray_and_run():
    global icon
    build_and_set_menu()
    icon.run()


# ═══════════════════════════════════════════════════════════════
# MAIN — AUDIO ENGINE
# ═══════════════════════════════════════════════════════════════

def main():
    global sounds, sound_pack_id, last_trigger_time
    global successful_knock_count, performance_tracking, performance_start_time
    global pygame_initialized, sound_enabled, performance_peak_ram
    global crack_overlay, _calibrating

    init_files()
    load_config()

    is_first_launch = not config.get("first_launch_done", False)

    performance_tracking = True
    performance_start_time = time.time()
    successful_knock_count = 0
    pygame_initialized = False
    last_trigger_time = 0
    sound_enabled = False

    log_output(f"[PERF] {APP_NAME} v{APP_VERSION} started")

    try:
        pygame.mixer.pre_init(44100, -16, 2, 512)
        pygame.mixer.init()
        pygame.mixer.set_num_channels(MIXER_CHANNELS)
        pygame.init()
        pygame_initialized = True
        log_output("[AUDIO] Engine initialized")
        load_combo_sounds()
    except Exception as e:
        log_output(f"[AUDIO] Init error at start: {e}")
        pygame_initialized = False

    # Init crack overlay
    crack_png = os.path.join(get_project_dir(), "assets", "crack.png")
    crack_overlay = CrackOverlay(crack_png, duration_ms=CRACK_DURATION_MS)

    # Init prank effects
    global prank_manager
    prank_manager = PrankManager(crack_overlay, config, config_lock, save_config, log_output)
    prank_manager.start()

    # Scan packs
    scan_packs()

    if pack_registry:
        with config_lock:
            current = sound_pack_id
        if current in pack_registry:
            pack_to_load = current
        elif "ouch" in pack_registry:
            pack_to_load = "ouch"
        else:
            pack_to_load = list(pack_registry.keys())[0]

        load_pack(pack_to_load)
        with cached_sounds_lock:
            sound_enabled = len(cached_sound_objects) >= MIN_SOUNDS_PER_PACK
    else:
        log_output("[INIT] No packs found")

    # Device discovery
    target_device_index = None

    if "last_device_index" in config:
        cached = config["last_device_index"]
        try:
            sd.check_input_settings(device=cached, samplerate=44100, channels=1)
            target_device_index = cached
        except Exception:
            target_device_index = None

    if target_device_index is None:
        devices = sd.query_devices()
        realtek = [i for i, d in enumerate(devices) if d["max_input_channels"] > 0 and "realtek" in d["name"].lower()]

        for idx in realtek:
            try:
                sd.check_input_settings(device=idx, samplerate=SAMPLE_RATE, channels=1)
                target_device_index = idx
                break
            except sd.PortAudioError:
                continue

        if target_device_index is None:
            target_device_index = sd.default.device[0]
            try:
                sd.check_input_settings(device=target_device_index, samplerate=SAMPLE_RATE, channels=1)
            except sd.PortAudioError:
                for idx, dev in enumerate(devices):
                    if dev["max_input_channels"] > 0:
                        try:
                            sd.check_input_settings(device=idx, samplerate=SAMPLE_RATE, channels=1)
                            target_device_index = idx
                            break
                        except sd.PortAudioError:
                            continue
                else:
                    log_output("[MIC] FATAL: No input devices!")
                    # Show notification and exit gracefully
                    build_and_set_menu()

                    def _notify_no_mic():
                        time.sleep(2)
                        if icon:
                            try:
                                icon.notify("No microphone found. Connect a mic and restart.", APP_NAME)
                            except Exception:
                                pass

                    threading.Thread(target=_notify_no_mic, daemon=True).start()
                    setup_tray_and_run()
                    return

        config["last_device_index"] = target_device_index
        save_config()

    log_output(f"[MIC] {sd.query_devices(target_device_index)['name']}")

    history_length = int(AMBIENT_HISTORY_SECONDS / BLOCK_DURATION)
    ambient_history = deque(maxlen=history_length)
    needs_calibration = not config.get("calibration_done", False)

    if is_first_launch:
        with config_lock:
            config["first_launch_done"] = True
        save_config()

    def process_audio(indata, frames, time_info, status):
        nonlocal ambient_history, needs_calibration
        global is_enabled, sounds, last_trigger_time, successful_knock_count
        global performance_tracking, performance_peak_ram, sound_enabled
        global pygame_initialized, spanks_since_save
        global _calibrating

        with _calibration_lock:
            if _calibrating:
                return
        if not is_enabled:
            return

        current_time = time.time()
        audio_data = indata[:, 0]

        raw_rms = np.sqrt(np.mean(audio_data ** 2))
        if raw_rms < RMS_FLOOR:
            ambient_history.append(raw_rms)
            return

        fft_data = np.fft.rfft(audio_data)
        freqs = np.fft.rfftfreq(len(audio_data), 1 / SAMPLE_RATE)
        filtered_fft = fft_data * (freqs < FREQ_CUTOFF)
        filtered_audio = np.fft.irfft(filtered_fft)
        rms = np.sqrt(np.mean(filtered_audio ** 2))

        # Compute avg_floor from existing history (exclude current frame to prevent knock contamination)
        if len(ambient_history) > 0:
            avg_floor = sum(ambient_history) / len(ambient_history)
        else:
            avg_floor = rms

        with config_lock:
            sens = config.get("sensitivity", DEFAULT_SENSITIVITY)
            baseline_mult = config.get("baseline_multiplier", 1.0)

        multiplier = 5.0 - (sens * 3.5)
        base_floor = 0.10 - (sens * 0.08)
        trigger_threshold = max(base_floor, avg_floor * multiplier) * baseline_mult
        hard_threshold = trigger_threshold * HARD_HIT_MULTIPLIER
        cooldown_seconds = config.get("cooldown_ms", DEFAULT_COOLDOWN_MS) / 1000.0

        # Trigger check using raw_rms for sensitivity, while avg_floor is based on filtered signal
        if raw_rms > trigger_threshold and current_time - last_trigger_time > cooldown_seconds:
            last_trigger_time = current_time
            is_hard_hit = raw_rms > hard_threshold

            # Volume scaling based on raw signal
            volume_multiplier = max(MIN_VOLUME, min(raw_rms / (hard_threshold * 0.8), 1.0))

            if performance_tracking:
                successful_knock_count += 1

            with config_lock:
                config["total_spanks"] += 1
                config["today_count"] += 1
                spanks_since_save += 1
                if config["today_count"] > config.get("best_day", 0):
                    config["best_day"] = config["today_count"]

            if spanks_since_save >= STATS_SAVE_INTERVAL:
                threading.Thread(target=save_config, daemon=True).start()
                spanks_since_save = 0

            if icon:
                threading.Thread(target=update_tray_menu, daemon=True).start()

            log_output(f"[SPANK] RMS={raw_rms:.4f} Vol={int(volume_multiplier*100)}% {'HARD' if is_hard_hit else 'soft'}")

            # Play sound
            with cached_sounds_lock:
                ready = cached_sound_objects.copy()

            if sound_enabled and ready and pygame_initialized:
                idx = pick_sound_index(len(ready))
                if idx >= 0:
                    snd = ready[idx]
                    try:
                        channel = snd.play()
                        if channel:
                            channel.set_volume(volume_multiplier)
                    except Exception as e:
                        log_output(f"[AUDIO] Play error: {e}")

            # Streak
            if check_streak(current_time):
                if pygame_initialized:
                    threading.Thread(target=play_combo_sound, daemon=True).start()

            # Crack overlay
            if is_hard_hit and config.get("crack_enabled", True) and crack_overlay:
                crack_overlay.show()

        # Only update ambient floor with non-knock signals (prevents threshold inflation)
        if raw_rms <= trigger_threshold:
            ambient_history.append(rms)

        # Periodic debug log (~every 2s)
        if random.random() < 0.01:
            log_output(f"[DEBUG] rms={raw_rms:.4f} floor={avg_floor:.4f} thresh={trigger_threshold:.4f} bl={baseline_mult:.2f}")

        # RAM tracking
        if performance_tracking and random.random() < 0.01:
            mem = psutil.Process().memory_info().rss / (1024 * 1024)
            if mem > performance_peak_ram:
                performance_peak_ram = mem

    # Audio stream loop
    while True:
        try:
            if needs_calibration:
                cal_thread = threading.Thread(
                    target=run_calibration,
                    args=(target_device_index, SAMPLE_RATE),
                    daemon=True)
                cal_thread.start()
                cal_thread.join(timeout=CALIBRATION_SECONDS + 5)
                needs_calibration = False

            def _first_launch_notify():
                time.sleep(3)
                if is_first_launch and icon:
                    try:
                        icon.notify("TantuSpank is ready. Bonk your desk to hear it!", APP_NAME)
                    except Exception:
                        pass

            if is_first_launch:
                threading.Thread(target=_first_launch_notify, daemon=True).start()

            with sd.InputStream(
                device=target_device_index,
                samplerate=int(SAMPLE_RATE),
                blocksize=int(BLOCK_SIZE),
                channels=1,
                callback=process_audio,
            ):
                log_output("[ENGINE] Ready.")
                setup_tray_and_run()
                break
        except Exception as e:
            log_output(f"[ERROR] Mic lost: {e} — retry 3s")
            time.sleep(3)

    if performance_tracking:
        duration = time.time() - performance_start_time
        log_output(f"[PERF] {duration:.1f}s, Peak RAM: {performance_peak_ram:.2f}MB, Knocks: {successful_knock_count}")

    if crack_overlay:
        crack_overlay.cleanup()
    if prank_manager:
        prank_manager.stop()
    if pygame_initialized:
        pygame.mixer.quit()


if __name__ == "__main__":
    main()
