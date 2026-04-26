"""
constants.py — TantuSpank v1.0.0
Central configuration constants. Single source of truth.
"""

# ═══════════════════════════════════════════════════════════════
# APPLICATION
# ═══════════════════════════════════════════════════════════════
APP_VERSION = "1.0.0"
APP_NAME = "TantuSpank"
APP_URL = "https://tantucore.online"
UPI_ID = "samarjeet2000@fam"
DONATE_POPUP_SIZE = (300, 400)

# ═══════════════════════════════════════════════════════════════
# AUDIO ENGINE
# ═══════════════════════════════════════════════════════════════
SAMPLE_RATE = 44100
BLOCK_DURATION = 0.020          # seconds per FFT block
BLOCK_SIZE = int(SAMPLE_RATE * BLOCK_DURATION)
RMS_FLOOR = 0.001               # below this = silence, skip FFT
FREQ_CUTOFF = 300               # Hz — knock band upper limit
AMBIENT_HISTORY_SECONDS = 2.0   # rolling noise floor window
AMBIENT_MULTIPLIER = 3.0        # RMS < floor * this → update floor

# ═══════════════════════════════════════════════════════════════
# KNOCK DETECTION
# ═══════════════════════════════════════════════════════════════
MIN_SOUNDS_PER_PACK = 1
DEFAULT_SENSITIVITY = 0.75
DEFAULT_COOLDOWN_MS = 300
COOLDOWN_MIN_MS = 100
COOLDOWN_MAX_MS = 3000
HARD_HIT_MULTIPLIER = 2.0      # trigger * this = hard hit
MIN_VOLUME = 0.3                # volume floor for soft hits

# ═══════════════════════════════════════════════════════════════
# STREAK / COMBO
# ═══════════════════════════════════════════════════════════════
STREAK_WINDOW_MS = 2000
STREAK_MIN_KNOCKS = 3
STREAK_COOLDOWN_S = 3.0
MAX_STREAK_NOTIFICATIONS = 3
STREAK_DEQUE_MAXLEN = 10

# ═══════════════════════════════════════════════════════════════
# OVERLAY
# ═══════════════════════════════════════════════════════════════
CRACK_DURATION_MS = 500
CRACK_ALPHA = 0.85

# ═══════════════════════════════════════════════════════════════
# PRANK EFFECTS
# ═══════════════════════════════════════════════════════════════
PRANK_COOLDOWN_DEFAULT = 300    # 5 minutes
PRANK_COOLDOWN_MIN = 10         # 10 seconds
PRANK_COOLDOWN_MAX = 3600       # 60 minutes

# ═══════════════════════════════════════════════════════════════
# CALIBRATION
# ═══════════════════════════════════════════════════════════════
CALIBRATION_SECONDS = 5
CALIBRATION_BLOCK_MS = 0.020    # 20ms blocks during calibration
CALIBRATION_DEFAULT_RMS = 0.001
CALIBRATION_BASELINE_MIN = 1.0
CALIBRATION_BASELINE_MAX = 1.5
CALIBRATION_RMS_DIVISOR = 0.002

# ═══════════════════════════════════════════════════════════════
# PERSISTENCE
# ═══════════════════════════════════════════════════════════════
STATS_SAVE_INTERVAL = 5         # save config every N knocks
SETTINGS_FILENAME = "settings.json"
OUTPUT_FILENAME = "OUTPUT.md"
LOG_FILENAME = "tantuspank.log"
LOG_MAX_BYTES = 1_048_576       # 1 MB
LOG_BACKUP_COUNT = 3
MIN_FILE_SIZE = 100             # bytes — skip files smaller than this

# ═══════════════════════════════════════════════════════════════
# TRAY ICON FALLBACK
# ═══════════════════════════════════════════════════════════════
ICON_SIZE = 64
ICON_FONT_SIZE = 40
ICON_BG_COLOR = (255, 69, 0)    # OrangeRed
ICON_TEXT_COLOR = (255, 255, 255)
ICON_TEXT = "T"

# ═══════════════════════════════════════════════════════════════
# MIXER
# ═══════════════════════════════════════════════════════════════
MIXER_CHANNELS = 16
COMBO_VOLUME = 0.8
RECENT_AUDIO_LIMIT = 5

# ═══════════════════════════════════════════════════════════════
# CONFIG DEFAULTS
# ═══════════════════════════════════════════════════════════════
DEFAULT_CONFIG = {
    "sensitivity": DEFAULT_SENSITIVITY,
    "cooldown_ms": DEFAULT_COOLDOWN_MS,
    "global_volume": 1.0,
    "last_used_pack": "ouch",
    "total_spanks": 0,
    "today_count": 0,
    "today_date": "",
    "best_day": 0,
    "custom_packs": [],
    "favorites": [],
    "adult_confirmed": False,
    "allow_adult_audio": False,
    "disabled_files": {},
    "streak_enabled": True,
    "crack_enabled": True,
    "calibration_done": False,
    "baseline_multiplier": 1.0,
    "streak_notif_count": 0,
    "first_launch_done": False,
    "prank_crack_enabled": True,
    "prank_hacked_enabled": True,
    "prank_cooldown_seconds": 300,
    "device_connect_enabled": True,
}

# ═══════════════════════════════════════════════════════════════
# FILE MARKERS
# ═══════════════════════════════════════════════════════════════
ADULT_MARKERS = ("18+", "nsfw", "adult")
AUDIO_EXTENSIONS = (".mp3", ".wav", ".ogg")
AUDIO_GLOBS = ("*.wav", "*.mp3", "*.ogg")
