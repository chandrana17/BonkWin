import os
import sys
import time
import math
from datetime import datetime
import pygame
import random
import glob
import threading
import json
from collections import deque

import pystray
from PIL import Image, ImageDraw, ImageFont
import psutil
import numpy as np
import sounddevice as sd

is_enabled = True
sound_pack_name = "pack_default"
sounds = []
sounds_lock = threading.Lock()
cached_sound_objects = []
cached_sounds_lock = threading.Lock()
icon = None
pygame_initialized = False
sound_enabled = False
last_trigger_time = 0

performance_tracking = False
performance_start_time = 0
performance_peak_ram = 0
successful_knock_count = 0

# Persistent config
config = {
    "sensitivity": 0.4,
    "cooldown_ms": 300,
    "global_volume": 1.0,
    "last_used_pack": "pack_default",
    "total_spanks": 0,
    "custom_packs": [],
    "favorites": [],
}
spanks_since_save = 0
config_lock = threading.Lock()
SETTINGS_FILE = None


def get_startup_folder():
    """Get the Windows Startup folder path."""
    return os.path.join(
        os.environ["APPDATA"],
        "Microsoft",
        "Windows",
        "Start Menu",
        "Programs",
        "Startup",
    )


def get_startup_file_path():
    """Get the path to the TantuSpank startup batch file."""
    return os.path.join(get_startup_folder(), "TantuSpank.bat")


def is_startup_enabled(item=None):
    """Check if the startup batch file exists."""
    return os.path.exists(get_startup_file_path())


def toggle_startup(icon, item):
    """Enable or disable auto-start by creating/removing a batch file."""
    startup_path = get_startup_file_path()
    if is_startup_enabled():
        try:
            os.remove(startup_path)
            log_output("[STEP 7] ðŸš€ Startup link Removed successfully")
        except Exception as e:
            log_output(f"[STEP 7] Error removing startup link: {e}")
    else:
        try:
            project_dir = get_project_dir()
            python_exe = sys.executable
            script_path = os.path.abspath(__file__)

            # Create a batch file that runs the script
            cmd = f'@echo off\ncd /d "{project_dir}"\nstart "" "{python_exe}" "{script_path}"\n'

            with open(startup_path, "w", encoding="utf-8") as f:
                f.write(cmd)
            log_output("[STEP 7] ðŸš€ Startup link Created successfully")
        except Exception as e:
            log_output(f"[STEP 7] Error creating startup link: {e}")

    build_and_set_menu()


def create_image():
    """Load the official TantuSpank hammer icon for the system tray."""
    icon_path = os.path.join(get_project_dir(), "icon.png")
    if os.path.exists(icon_path):
        try:
            return Image.open(icon_path)
        except Exception as e:
            log_output(f"[UI] Error loading icon.png: {e}. Falling back to default.")
    
    # Fallback to bold white/orange "T" icon (TantuSpank)
    width = 64
    height = 64
    color1 = (255, 69, 0)  # Red-Orange
    color2 = (255, 255, 255)  # White

    image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    dc = ImageDraw.Draw(image)
    dc.ellipse([0, 0, width, height], fill=color1)

    try:
        font = ImageFont.truetype("arialbd.ttf", 40)
    except IOError:
        font = ImageFont.load_default()

    text = "T"
    try:
        left, top, right, bottom = dc.textbbox((0, 0), text, font=font)
        text_w = right - left
        text_h = bottom - top
        dc.text(
            ((width - text_w) / 2, (height - text_h) / 2 - 4),
            text,
            font=font,
            fill=color2,
        )
    except AttributeError:
        # Compatibility for older Pillow versions
        text_w, text_h = dc.textsize(text, font=font)
        dc.text(
            ((width - text_w) / 2, (height - text_h) / 2), text, font=font, fill=color2
        )

    return image


def load_config():
    """Load config from settings.json with defaults."""
    global config, SETTINGS_FILE, sound_pack_name
    SETTINGS_FILE = os.path.join(get_data_dir(), "settings.json")

    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
                saved_config = json.load(f)
                for key in config:
                    if key in saved_config:
                        config[key] = saved_config[key]
        except json.JSONDecodeError:
            log_output(
                "[STEP 6] Error: settings.json contains invalid JSON. Using defaults."
            )
        except Exception as e:
            log_output(f"[STEP 6] Warning: Could not load settings: {e}")

    # Update global sound_pack_name from config
    with config_lock:
        sound_pack_name = config.get("last_used_pack", "pack_default")

    log_output(f"[STEP 6] Loaded stats: {config['total_spanks']} total spanks")
    return config


def save_config():
    """Save config to settings.json. Thread-safe."""
    if SETTINGS_FILE is None:
        log_output(
            "[STEP 6] Warning: SETTINGS_FILE not initialized, cannot save config"
        )
        return
    with config_lock:
        try:
            config["last_used_pack"] = sound_pack_name
            with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
                json.dump(config, f, indent=2)
        except Exception as e:
            log_output(f"[STEP 6] Warning: Could not save settings: {e}")


def on_open_settings(icon, item):
    """Open the settings.json file in the default text editor."""
    try:
        if os.path.exists(SETTINGS_FILE):
            os.startfile(SETTINGS_FILE)
            log_output("[STEP 5] âš™ï¸ Settings file opened for manual editing.")
        else:
            save_config()
            os.startfile(SETTINGS_FILE)
            log_output(
                "[STEP 5] âš™ï¸ Settings file created and opened for manual editing."
            )
    except Exception as e:
        log_output(f"[STEP 5] Error opening settings file: {e}")


def on_reset_stats(icon, item):
    """Reset Spank counter to 0."""
    global spanks_since_save
    config["total_spanks"] = 0
    spanks_since_save = 0
    save_config()
    update_tray_menu()
    log_output("[STEP 6] Stats reset! Counter set to 0.")


def update_tray_menu():
    """Update tray menu and tooltip with current stats."""
    global icon
    if icon is None:
        return

    count = config["total_spanks"]
    if count == 1:
        icon.title = f"TantuSpank â€” {count} Spank Detected"
    else:
        icon.title = f"TantuSpank â€” {count} Spanks Detected"

    build_and_set_menu()


def on_toggle_enable(icon, item):
    global is_enabled
    is_enabled = not is_enabled
    count = config["total_spanks"]
    if is_enabled:
        if count == 1:
            icon.title = f"TantuSpank â€” Listening ({count} Spank)"
        else:
            icon.title = f"TantuSpank â€” Listening ({count} Spanks)"
    else:
        if count == 1:
            icon.title = f"TantuSpank â€” Paused ({count} Spank)"
        else:
            icon.title = f"TantuSpank â€” Paused ({count} Spanks)"


def get_enable_state(item):
    return is_enabled


def on_quit(icon, item):
    log_output("[STEP 3] Quitting TantuSpank...")
    save_config()
    icon.stop()


def get_available_packs():
    """Scan sounds/ directory and return built-in packs."""
    sounds_dir = os.path.join(get_project_dir(), "sounds")
    packs = []
    if os.path.exists(sounds_dir):
        for entry in os.listdir(sounds_dir):
            entry_path = os.path.join(sounds_dir, entry)
            if os.path.isdir(entry_path):
                packs.append(entry)

    return sorted(packs)


def _cache_sounds():
    """Pre-load sound files as pygame.mixer.Sound objects so the audio
    callback never does file I/O.  Safe to call before pygame is ready."""
    global cached_sound_objects
    if not pygame_initialized:
        return
    with sounds_lock:
        current_files = sounds.copy()
    new_cache = []
    for sf in current_files:
        try:
            snd = pygame.mixer.Sound(sf)
            new_cache.append(snd)
        except Exception as e:
            log_output(f"[CACHE] Skipped {os.path.basename(sf)}: {e}")
    with cached_sounds_lock:
        cached_sound_objects = new_cache
    log_output(f"[CACHE] Pre-loaded {len(new_cache)}/{len(current_files)} sound objects")


def load_pack(pack_name):
    """Load all sound files from the specified pack. Supports built-in and absolute paths (folders or single files)."""
    global sounds, sound_pack_name

    new_sounds = []
    
    # Resolve path: absolute (custom folder/file) or relative (built-in pack)
    if os.path.isabs(pack_name):
        target_path = pack_name
    else:
        target_path = os.path.join(get_project_dir(), "sounds", pack_name)

    if os.path.exists(target_path):
        if os.path.isfile(target_path):
            # It's a single file
            new_sounds.append(target_path)
        elif os.path.isdir(target_path):
            # It's a directory
            for ext in ("*.wav", "*.mp3", "*.ogg", "*.WAV", "*.MP3", "*.OGG"):
                new_sounds.extend(glob.glob(os.path.join(target_path, ext)))
            new_sounds = list(set(new_sounds)) # deduplicate

    with sounds_lock:
        sounds = new_sounds
        sound_pack_name = pack_name

    # Pre-cache sound objects (no-op if pygame not yet initialized)
    _cache_sounds()

    display_name = os.path.basename(pack_name) if os.path.isabs(pack_name) else pack_name
    log_output(
        f"[STEP 4] 📁 Switched to pack: {display_name} (Loaded {len(new_sounds)} sounds)"
    )
    return len(new_sounds)


def get_pack_checked(item):
    """Callback to check if this pack is currently selected."""
    with config_lock:
        current_pack = sound_pack_name
    return item.text == f"âœ“ {current_pack}" or item.text == current_pack


def on_pack_selected(icon, pack_name):
    """Handle sound pack selection from tray menu."""
    global sound_enabled
    # Stop any currently playing sounds for a clean switch
    if pygame_initialized:
        try:
            pygame.mixer.stop()
        except Exception:
            pass
    loaded_count = load_pack(pack_name)
    if loaded_count > 0:
        sound_enabled = True
        with config_lock:
            config["last_used_pack"] = pack_name
        log_output(f"[UI] Successfully switched to pack: {pack_name} ({loaded_count} sounds)")
    else:
        sound_enabled = False
        log_output(f"[UI] Warning: Pack '{pack_name}' contains no playable sounds. Keeping previous pack.")
        # Revert to previously working pack if available
        with config_lock:
            last_good_pack = config.get("last_used_pack", "pack_default")
        if last_good_pack != pack_name:  # Avoid infinite loop
            load_pack(last_good_pack)
            sound_enabled = len(sounds) > 0
    save_config()
    build_and_set_menu()


def setup_tray_and_run():
    global icon
    build_and_set_menu()
    icon.run()


def on_set_sensitivity(icon, item):
    """Set sensitivity via menu presets."""
    global config
    try:
        val = float(item.text)
        with config_lock:
            config["sensitivity"] = val
        save_config()
        build_and_set_menu()
        log_output(f"[UI] Sensitivity set to {val}")
    except Exception as e:
        log_output(f"[UI] Error setting sensitivity: {e}")


def on_custom_sensitivity(icon, item):
    """Open a dialog to set custom sensitivity."""
    import tkinter as tk
    from tkinter import simpledialog

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    
    current = config.get("sensitivity", 0.4)
    res = simpledialog.askfloat("Custom Sensitivity", "Enter sensitivity (0.0 to 1.0):", initialvalue=current, minvalue=0.0, maxvalue=1.0)
    
    if res is not None:
        with config_lock:
            config["sensitivity"] = res
        save_config()
        build_and_set_menu()
        log_output(f"[UI] Custom Sensitivity set to {res}")
    
    root.destroy()


def on_select_custom_file(icon, item):
    """Open a file dialog to select a single custom sound file."""
    import tkinter as tk
    from tkinter import filedialog
    import os

    root = tk.Tk()
    root.withdraw()
    root.attributes("-topmost", True)
    
    file_path = filedialog.askopenfilename(
        title="Select Sound File",
        filetypes=[("Audio Files", "*.wav *.mp3 *.ogg *.WAV *.MP3 *.OGG")]
    )
    
    if file_path:
        file_path = os.path.normpath(file_path)
        with config_lock:
            # Maintain backward compatibility with old custom_packs key
            recent_list = config.get("recent_audios", config.get("custom_packs", []))
            if file_path in recent_list:
                recent_list.remove(file_path)
            
            recent_list.insert(0, file_path)
            config["recent_audios"] = recent_list[:5] # keep max 5
            
        on_pack_selected(icon, file_path)
        log_output(f"[UI] Loaded custom file: {file_path}")
    
    root.destroy()


def on_toggle_favorite(icon, item):
    """Add/Remove current pack from favorites."""
    global config
    with config_lock:
        if "favorites" not in config:
            config["favorites"] = []
        
        if sound_pack_name in config["favorites"]:
            while sound_pack_name in config["favorites"]:
                config["favorites"].remove(sound_pack_name)
            log_output(f"[UI] Removed {sound_pack_name} from favorites")
        else:
            config["favorites"].append(sound_pack_name)
            log_output(f"[UI] Added {sound_pack_name} from favorites")
    
    save_config()
    build_and_set_menu()


def build_and_set_menu():
    """Build and set the tray menu with current stats."""
    global icon
    # Check if pystray is locally shadowed, else import at top
    img = create_image()
    
    # 1. Sound Packs Section
    available_packs = get_available_packs()
    fav_list = config.get("favorites", [])
    recent_list = config.get("recent_audios", config.get("custom_packs", []))
    
    def make_checked_func(pack_name):
        return lambda item: pack_name == sound_pack_name

    fav_items = []
    if not fav_list:
        fav_items.append(pystray.MenuItem("(No favorites yet)", lambda: None, enabled=False))
    else:
        for f in fav_list:
            display_name = os.path.basename(f) if os.path.isabs(f) else f
            fav_items.append(
                pystray.MenuItem(
                    display_name,
                    (lambda p: lambda icon, item: on_pack_selected(icon, p))(f),
                    checked=make_checked_func(f),
                    radio=True
                )
            )

    recent_items = []
    if not recent_list:
        recent_items.append(pystray.MenuItem("(No recent files)", lambda: None, enabled=False))
    else:
        for r in recent_list:
            display_name = os.path.basename(r) if os.path.isabs(r) else r
            recent_items.append(
                pystray.MenuItem(
                    display_name,
                    (lambda p: lambda icon, item: on_pack_selected(icon, p))(r),
                    checked=make_checked_func(r),
                    radio=True
                )
            )

    pack_items = []
    for pack in available_packs:
        display_name = os.path.basename(pack) if os.path.isabs(pack) else pack
        pack_items.append(
            pystray.MenuItem(
                display_name,
                (lambda p: lambda icon, item: on_pack_selected(icon, p))(pack),
                checked=make_checked_func(pack),
                radio=True
            )
        )
    
    # 2. Sensitivity Submenu
    sens_presets = ["0.00", "0.25", "0.50", "0.75", "1.00"]
    sens_items = []
    for p in sens_presets:
        val = float(p)
        sens_items.append(
            pystray.MenuItem(
                p,
                on_set_sensitivity,
                checked=(lambda v: lambda item: abs(config.get("sensitivity", 0.4) - v) < 0.01)(val),
                radio=True
            )
        )
    sens_items.append(pystray.Menu.SEPARATOR)
    sens_items.append(pystray.MenuItem(f"Custom ({config.get('sensitivity', 0.4):.2f})", on_custom_sensitivity))

    # 3. Main Menu
    count = config.get("total_spanks", 0)
    stats_text = f"Total Spanks: {count}"
    tooltip = f"TantuSpank — {count} Spank{'s' if count != 1 else ''}"

    is_current_favorite = sound_pack_name in fav_list
    fav_toggle_text = "⭐ Remove Current from Favorites" if is_current_favorite else "⭐ Add Current to Favorites"

    menu = pystray.Menu(
        pystray.MenuItem("Enable Detection", on_toggle_enable, checked=get_enable_state),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem(stats_text, lambda: None, enabled=False),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Sound Selection", pystray.Menu(
            pystray.MenuItem(fav_toggle_text, on_toggle_favorite),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("⭐ Favorites", pystray.Menu(*fav_items)),
            pystray.MenuItem("🕒 Recent Files", pystray.Menu(*recent_items)),
            pystray.MenuItem("📂 Default Packs", pystray.Menu(*pack_items)),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("🎵 Select Custom File...", on_select_custom_file)
        )),
        pystray.MenuItem("Sensitivity", pystray.Menu(*sens_items)),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Settings", pystray.Menu(
            pystray.MenuItem("Reset Stats", on_reset_stats),
            pystray.MenuItem("Launch at Startup", toggle_startup, checked=is_startup_enabled),
            pystray.MenuItem("Open Settings File", on_open_settings),
        )),
        pystray.Menu.SEPARATOR,
        pystray.MenuItem("Quit", on_quit),
    )

    if icon is None:
        icon = pystray.Icon("TantuSpank", img, title=tooltip, menu=menu)
        log_output("[STEP 3] System tray icon created. Right-click to manage.")
    else:
        icon.title = tooltip
        icon.menu = menu
        icon.update_menu()


def get_project_dir():
    """Get the absolute path to the directory containing the project files.
    When frozen (exe), resources like sounds/ and icon.png live next to the exe,
    NOT inside _MEIPASS (since datas=[] in the spec).
    """
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.abspath(__file__))


def get_data_dir():
    """Get the directory for user data (settings, output, etc.) that is writable."""
    if getattr(sys, "frozen", False):
        data_dir = os.path.join(os.environ.get("LOCALAPPDATA", os.path.expanduser("~")), "TantuSpank")
        os.makedirs(data_dir, exist_ok=True)
        return data_dir
    return os.path.dirname(os.path.abspath(__file__))


OUTPUT_FILE = os.path.join(get_data_dir(), "OUTPUT.md")
ROADMAP_FILE = os.path.join(get_data_dir(), "ROADMAP.md")


def log_output(message):
    # Safe print that handles Unicode encoding issues on Windows
    try:
        print(message)
    except UnicodeEncodeError:
        # Fallback: replace problematic characters
        print(message.encode("cp1252", errors="replace").decode("cp1252"))
    with open(OUTPUT_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")


def init_files():
    if not os.path.exists(ROADMAP_FILE):
        with open(ROADMAP_FILE, "w", encoding="utf-8") as f:
            f.write(
                "# TantuSpank Roadmap\n\n## âœ… Done\n- Step 1: Detection engine\n- Step 2: Sound playback\n- Step 3: System tray icon\n- Step 4: Sound pack switcher\n- Step 5: Settings\n- Step 6: Spank counter\n- Step 7: Auto-start\n- Step 8: Package as .exe\n- Step 9: Installer\n\n## ðŸ”„ In Progress\n- Optimizations (OPT-1 to OPT-5)\n"
            )
    if not os.path.exists(OUTPUT_FILE):
        with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
            f.write("")


def main():
    global sounds, sound_pack_name, last_trigger_time
    global successful_knock_count, performance_tracking, performance_start_time
    global pygame_initialized, sound_enabled, performance_peak_ram
    init_files()
    load_config()

    # Initialize performance tracking for this session
    performance_tracking = True
    performance_start_time = time.time()
    successful_knock_count = 0
    pygame_initialized = False
    last_trigger_time = 0

    log_output("[PERF] Performance tracking started")

    # OPT-6: Lazy load pygame - don't initialize mixer at startup
    sound_enabled = False
    pygame_initialized = False
    # Get all available sound packs
    available_packs = get_available_packs()
    log_output(f"[STEP 2] Available sound packs: {available_packs}")
    if not available_packs:
        log_output("[STEP 2] Warning: No sound packs found in sounds/ directory")
    else:
        # Try to load the last used pack if it's still available, otherwise use the first available pack
        with config_lock:
            current_pack = sound_pack_name
        pack_to_load = (
            current_pack if current_pack in available_packs else available_packs[0]
        )
        load_pack(pack_to_load)
        sound_enabled = len(sounds) > 0
        # Safely encode pack name for logging to avoid Unicode errors
        safe_pack_name = repr(sound_pack_name)[1:-1]
        if sound_enabled:
            log_output(
                f"[STEP 2] Sound pack loaded ({len(sounds)} sound(s) from pack '{safe_pack_name}') - mixer will initialize on first spank"
            )
        else:
            log_output(
                f"[STEP 2] Warning: No sound files found in pack '{safe_pack_name}'"
            )

    # OPT-3: Startup Speed (Device Caching)
    target_device_index = None

    if "last_device_index" in config:
        cached_index = config["last_device_index"]
        try:
            sd.check_input_settings(device=cached_index, samplerate=44100, channels=1)
            target_device_index = cached_index
            log_output(f"[STEP 1] Using cached device index {cached_index}")
        except Exception as e:
            log_output(f"[STEP 1] Cached device invalid: {e}")
            target_device_index = None

    if target_device_index is None:
        log_output("[STEP 1] Starting device discovery...")
        devices = sd.query_devices()
        realtek_devices = [
            i
            for i, d in enumerate(devices)
            if d["max_input_channels"] > 0 and "realtek" in d["name"].lower()
        ]

        SAMPLE_RATE = 44100
        # Try Realtek first
        for idx in realtek_devices:
            try:
                sd.check_input_settings(device=idx, samplerate=SAMPLE_RATE, channels=1)
                target_device_index = idx
                config["last_device_index"] = target_device_index
                save_config()
                log_output(f"[STEP 1] Found working Realtek device at index {idx}")
                break
            except sd.PortAudioError:
                continue

        if target_device_index is None:
            # Fall back to default
            target_device_index = sd.default.device[0]
            try:
                sd.check_input_settings(
                    device=target_device_index, samplerate=SAMPLE_RATE, channels=1
                )
            except sd.PortAudioError:
                # Find ANY working input
                for idx, dev in enumerate(devices):
                    if dev["max_input_channels"] > 0:
                        try:
                            sd.check_input_settings(
                                device=idx, samplerate=SAMPLE_RATE, channels=1
                            )
                            target_device_index = idx
                            break
                        except sd.PortAudioError:
                            continue
                else:
                    log_output("[STEP 1] FATAL: No working input devices found!")
                    sys.exit(1)

        # Cache the found device
        config["last_device_index"] = target_device_index
        save_config()

    log_output(
        f"[STEP 1] Active device: {sd.query_devices(target_device_index)['name']}"
    )

    SAMPLE_RATE = 44100
    BLOCK_DURATION = 0.020
    BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_DURATION)

    # State variables
    history_length = int(2.0 / BLOCK_DURATION)
    ambient_history = deque(maxlen=history_length)

    def process_audio(indata, frames, time_info, status):
        nonlocal ambient_history
        global \
            is_enabled, \
            sounds, \
            last_trigger_time, \
            successful_knock_count, \
            performance_tracking, \
            performance_peak_ram, \
            sound_enabled, \
            pygame_initialized

        if not is_enabled:
            return

        current_time = time.time()
        audio_data = indata[:, 0]

        # OPT-1: CPU Pre-filter (RMS check)
        raw_rms = np.sqrt(np.mean(audio_data**2))
        if raw_rms < 0.001:
            if len(ambient_history) < history_length:
                ambient_history.append(raw_rms)
            return

        # Low pass filter (< 300Hz)
        fft_data = np.fft.rfft(audio_data)
        freqs = np.fft.rfftfreq(len(audio_data), 1 / SAMPLE_RATE)
        filtered_fft = fft_data * (freqs < 300)
        filtered_audio = np.fft.irfft(filtered_fft)

        rms = np.sqrt(np.mean(filtered_audio**2))

        if len(ambient_history) < history_length:
            ambient_history.append(rms)
            return

        avg_floor = sum(ambient_history) / len(ambient_history)
        if rms < avg_floor * 3.0:
            ambient_history.append(rms)

        # SENSITIVITY FIX: 1.0 is highly sensitive (low threshold), 0.0 is least sensitive (high threshold)
        with config_lock:
            sens = config.get("sensitivity", 0.75)
        
        # multiplier ranges from 10.0 (at sens=0.0) down to 2.0 (at sens=1.0)
        multiplier = 10.0 - (sens * 8.0)
        # Fix Laptop vibration issue: Higher base floor, scaling with sensitivity
        base_floor = 0.20 - (sens * 0.16) # sens=1.0 -> 0.04 (picks up tap), sens=0.0 -> 0.20 (requires hard hit)
        trigger_threshold = max(base_floor, avg_floor * multiplier)
        
        # Lower cooldown so fast rapid Spanks are not skipped
        cooldown_seconds = config.get("cooldown_ms", 150) / 1000.0

        # LOCKOUT FIX: Simple lockout prevents double-counting one transient
        if rms > trigger_threshold and current_time - last_trigger_time > cooldown_seconds:
            last_trigger_time = current_time
            intensity = min(rms / 0.15, 1.0)

            # Performance tracking
            if performance_tracking:
                successful_knock_count += 1

            log_output(f"[STEP 2] Knock detected! Intensity: {intensity:.2f}")

            # Process Spank — ONLY runs on confirmed triggers
            global spanks_since_save
            with config_lock:
                config["total_spanks"] += 1
                spanks_since_save += 1

            if spanks_since_save >= 5:
                threading.Thread(target=save_config, daemon=True).start()
                with config_lock:
                    spanks_since_save = 0

            if icon:
                threading.Thread(target=update_tray_menu, daemon=True).start()

            with sounds_lock:
                current_sounds = sounds.copy()

            if sound_enabled and current_sounds:
                # OPT-6: Lazy initialize pygame mixer on first Spank
                if not pygame_initialized:
                    try:
                        pygame.mixer.init()
                        pygame.mixer.set_num_channels(16)  # More channels = no drops
                        pygame_initialized = True
                        _cache_sounds()  # Pre-load sounds now that mixer is ready
                        log_output(
                            "[STEP 2] Sound system initialized (lazy load, 16 channels)"
                        )
                    except Exception as e:
                        log_output(
                            f"[STEP 2] Warning: Could not initialize sound system: {e}"
                        )
                        sound_enabled = False
                        pygame_initialized = True  # Prevent retry loop

                if pygame_initialized and sound_enabled:
                    volume = max(
                        0.10, min(intensity * config["global_volume"], 1.0)
                    )
                    # Use pre-cached sound objects — zero file I/O in callback
                    with cached_sounds_lock:
                        ready_sounds = cached_sound_objects.copy()
                    if ready_sounds:
                        snd = random.choice(ready_sounds)
                        try:
                            channel = snd.play()
                            if channel is not None:
                                channel.set_volume(volume)
                            log_output(
                                f"[STEP 2] Played sound ({int(volume * 100)}% vol)"
                            )
                        except Exception as e:
                            log_output(
                                f"[STEP 2] Warning: Failed to play sound: {e}"
                            )
                    else:
                        # Cache empty — sounds may have changed, rebuild cache
                        _cache_sounds()

        # Update performance metrics every block (cheap checks)
        if performance_tracking:
            # Update peak RAM
            mem = psutil.Process().memory_info().rss / (1024 * 1024)
            if mem > performance_peak_ram:
                performance_peak_ram = mem

    # OPT-7: Silent crash recovery - wrap audio stream in retry loop
    while True:  # Keep retrying on failure
        try:
            with sd.InputStream(
                device=target_device_index,
                samplerate=SAMPLE_RATE,
                blocksize=BLOCK_SIZE,
                channels=1,
                callback=process_audio,
            ):
                log_output("[STEP 1] Engine ready.")
                setup_tray_and_run()
                # If we reach here, the stream ended normally (user quit)
                break
        except Exception as e:
            import traceback
            error_msg = f"[ERROR] Mic lost:\n{traceback.format_exc()}\n— retrying in 3s"
            log_output(error_msg)
            # Wait 3 seconds before retrying
            time.sleep(3)
            # Continue loop to retry

    # Performance tracking report (outside the retry loop)
    if performance_tracking:
        session_duration = time.time() - performance_start_time

        log_output("\n[PERF] === TantuSpank PERFORMANCE REPORT ===")
        log_output(f"[PERF] Session duration: {session_duration:.1f} seconds")
        log_output(f"[PERF] Peak RAM usage: {performance_peak_ram:.2f} MB")
        log_output(f"[PERF] Successful knocks: {successful_knock_count}")
        log_output("[PERF] ==================================")

    if sound_enabled:
        pygame.mixer.quit()


if __name__ == "__main__":
    main()
