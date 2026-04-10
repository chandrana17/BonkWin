# TantuSpank - Development Report

## Project Overview
TantuSpank is an innovative Python-based background audio engine. It captures audio input from external hardware (such as physical taps on a laptop chassis), analyzes the analog energy curves in real-time, and plays corresponding sound effects globally using a transparent background system tray integration.

## Development Milestones

### 1. Audio Engine & Detection Logic
- Built a robust audio energy calculation function using `numpy` and `sounddevice`.
- Implemented dual-threshold volume detection to accurately differentiate between a "high" bonk and a "low" bonk.
- Created debounce mechanisms to prevent glitchy repetitive sound overlapping.

### 2. Multi-Pack Architecture
- Integrated a modular `.wav`/`.mp3` asset handling system.
- Implemented `pygame.mixer` over older libraries like `playsound` for low-latency asynchronous audio playback, ensuring zero audio stuttering.
- Scaled up the file structure to support user-driven pack switching (`pack_default`, `pack_nature`, `pack_retro`, `memes soundpack`, etc.).

### 3. Custom Audio Integration
- Solved file-chooser limitations and dynamically allowed the user to manually select custom audio `.wav/.mp3` files globally on the user's hard drive.
- Implemented quick cache switching for 1-click favorite custom audios directly in the tray.

### 4. Background Service & User Interface
- Created a background tray application using `pystray`.
- Removed all persistent terminal windows by converting the deployment to `--noconsole` within PyInstaller.
- Developed an aesthetic transparent `icon.ico` design, cleanly integrating directly into the Windows 11 system tray using the high-quality Hammer asset.

### 5. Deployment & Security Patching
- Handled Windows 11 Smart App Control interference by converting the software to run purely out of a compiled `.exe`.
- Redesigned the data persistence hierarchy:
  - System read-only files (`TantuSpank.exe`) can reside in `Program Files` or any root folder.
  - User read-write files (`settings.json`, `ROADMAP.md`) are automatically routed to the hidden `%LOCALAPPDATA%\TantuSpank` folder.
- Deployed a final Inno Setup installer (`TantuSpank_Setup.exe`) configured to use lowest privileges to ensure 100% compliance with Windows Smart App Control out of the box, supplemented by a Portable `.zip` version for easy and robust distribution.

### 6. Technical Polish
- Overhauled and wiped legacy references to old codebases ("BonkWin").
- Replaced the placeholder tray icons with the main `TantuSpank` transparent hammer logo.
- Cleaned up development temporary python scripts and logging outputs, and stabilized the production branch.

## Status
**Completed.** The application is production-ready, highly modular, fast, and elegantly installed in the background context without triggering aggressive permission errors.
