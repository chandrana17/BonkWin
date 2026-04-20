# 🔨 TantuSpank

**Your laptop fights back.** Knock on your desk — it screams, cracks, and counts every hit.

Windows tray app that detects physical knocks via microphone FFT analysis and plays sound effects. No internet. No AI. No telemetry. Fully local, privacy-first.

---

## ✨ Features

- 🎯 **Real-time knock detection** — FFT analysis with dual-threshold (soft/hard hits)
- 🔊 **7 built-in sound packs** — Dank, Default, Gamer, Indian Brainrot, Ouch, Rizz, Sigma
- 🔀 **Full-rotation shuffle** — No repeat until every sound has played
- 💥 **Screen crack overlay** — Transparent, click-through crack effect on hard hits
- 🔥 **Streak combos** — 3+ rapid knocks trigger special combo sounds
- 🎚️ **Live sensitivity slider** — Adjust detection from quiet room to noisy room
- 🔞 **18+ content filter** — Global toggle + per-file control for adult audio
- ⭐ **Favorites** — Quick-access to your preferred sound packs
- 📊 **Stats** — Total spanks, daily count, personal best
- 🚀 **Launch at startup** — One-click toggle, no admin required
- 🔧 **Auto-calibration** — Measures ambient noise on first launch
- ⚡ **0% idle CPU** — RMS pre-filter skips FFT when no sound detected

## 📦 Installation

### Portable (No Install)
1. Download `TantuSpank_Portable.zip` from [Releases](https://github.com/chandrana17/TantuSpank/releases)
2. Extract anywhere
3. Run `TantuSpank.exe`

### Installer
1. Download `TantuSpank_Setup_v1.0.0.exe` from [Releases](https://github.com/chandrana17/TantuSpank/releases)
2. Run installer — installs to `%LOCALAPPDATA%\TantuSpank`
3. No admin required

## 🎵 Sound Packs

Sound packs live in the `sound-packs/` directory. Each pack has:
```
sound-packs/
├── ouch/
│   ├── pack-manifest.json
│   ├── sound1.mp3
│   └── sound2.mp3
├── combo/          ← streak combo sounds
└── ...
```

### pack-manifest.json
```json
{
  "id": "ouch",
  "name": "Ouch",
  "adult": false,
  "warning": ""
}
```

### Adding Custom Packs
1. Create a folder in `sound-packs/`
2. Drop `.mp3`, `.wav`, or `.ogg` files inside
3. A manifest is auto-created on next launch
4. Or use **Select Custom File** from the tray menu

## 🔒 Privacy

- **No internet** — Zero network calls, zero telemetry
- **No recording** — Audio processed in-memory, discarded after each 20ms block
- **No cloud** — All settings stored locally at `%LOCALAPPDATA%\TantuSpank\`
- **No admin** — Runs entirely in user space
- **Security audited** — See `security_audit_report.txt`

## 🛠️ Building from Source

### Prerequisites
- Python 3.12+
- Windows 10/11

### Setup
```bash
git clone https://github.com/chandrana17/TantuSpank.git
cd TantuSpank
pip install -r requirements.txt
python detect.py
```

### Build Executable
```bash
pip install pyinstaller
pyinstaller TantuSpank.spec
```
Output: `dist/TantuSpank.exe`

### Build Installer
1. Install [Inno Setup](https://jrsoftware.org/isinfo.php)
2. Build exe first (above)
3. Compile `installer.iss`

## 📋 Dependencies

| Package | Version | Purpose |
|---|---|---|
| pygame | 2.6.1 | Audio playback |
| Pillow | 12.2.0 | Tray icon + overlay images |
| psutil | 7.2.2 | RAM monitoring |
| numpy | 2.4.3 | FFT analysis |
| sounddevice | 0.5.5 | Microphone input |
| pystray | latest | System tray UI |

## 📄 License

MIT — See [LICENSE](LICENSE)

## 🤝 Credits

Made by [TantuCore](https://github.com/chandrana17)
