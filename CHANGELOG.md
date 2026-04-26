# Changelog

## [1.0.0] — 2026-04-26

### 🎉 The "Stealth" Release

#### 🛡️ Security & Distribution
- **Bypass Smart App Control**: Switched to Nuitka Stealth Build to prevent Windows 11 from blocking the app as "unknown".
- **Binary Metadata**: Added official "TantuCore Studio" signatures and versioning info to the EXE properties.
- **Portable ZIP**: Provided a standalone version that doesn't trigger "Installer" heuristics.
- **Stealth Device Detection**: Replaced PowerShell-based polling with native Win32 Raw Input API via `ctypes` to eliminate security pop-outs.

#### 🔊 Device Connect Sounds
- Added automatic sound playback when USB microphones, audio devices, or HID mice are connected.
- Background device enumeration thread with 2-second polling.
- New "Device Connect Sounds" toggle in the Settings menu.
- Dedicated `device_connect` sound pack folder.

#### 🎯 Core Detection Engine
- Real-time FFT knock detection with dual-threshold (soft/hard hits).
- RMS pre-filter for 0% idle CPU — FFT only runs when sound detected.
- Dynamic volume scaling based on hit force.
- Auto-reconnect on microphone disconnect.
- Ambient noise floor tracking with rolling 2-second window.

#### 🔊 Sound System
- 7 built-in sound packs: Dank, Default, Gamer, Indian Brainrot, Ouch, Rizz, Sigma.
- Manifest-driven pack discovery via `pack-manifest.json`.
- Full-rotation shuffle — no repeat until all sounds played.
- Custom WAV/MP3/OGG file picker.
- Per-file enable/disable within any pack.
- Combo sounds on 3+ hit streaks.

#### 🔞 18+ Content Filtering
- Global toggle for adult audio content.
- File-level markers (`18+`, `nsfw`, `adult` in filename).
- Pack-level adult flag in manifest.
- Modal age verification dialog.

#### 🖥️ UI / UX
- System tray with grouped submenus.
- Live sensitivity slider (0–100%).
- Favorites system with quick-access submenu.
- Recent files history (last 5).
- Stats display: total spanks, today count, personal best.
- File count per pack with 18+ indicator.
- About dialog with QR code and website link.
- Donation popup with UPI QR code.

#### 💥 Prank Effects
- Screen crack overlay on hard hits (transparent, click-through, multi-monitor aware).
- Keyboard-triggered pranks (Spacebar → crack, Enter → hacker terminals).
- Base64-obfuscated PowerShell scripts to avoid AV false-positives.
- Configurable prank cooldown (10s – 60min).

#### ⚙️ Settings & Persistence
- All settings saved to `%LOCALAPPDATA%\TantuSpank\settings.json`.
- Atomic config writes (temp file + rename) for crash safety.
- Auto-calibration on first launch (5-second ambient measurement).
- Launch at startup toggle (user-scoped, no admin required).

#### 🔄 Auto-Update Check
- Background GitHub Releases API check on startup.
- Manual "Check for Updates" menu option.
- Privacy-first: only pings public API, sends zero user data.

#### 🔒 Security & Privacy
- Fully offline — zero telemetry.
- No admin privileges required.
- Audio processed in-memory only, never recorded or stored.
