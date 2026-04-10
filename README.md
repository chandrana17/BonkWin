# TantuSpank ðŸ”¨

**Bonk your laptop. It bonks back. Works on ANY Windows laptop.**

TantuSpank is a lightweight Windows system tray utility that transforms your laptop into an interactive, audio-reactive device. It listens for physical knocks, taps, or thuds on your laptop chassis or desk and responds with satisfying sound effects. No special hardware requiredâ€”just your built-in microphone and a bit of FFT magic.

---

## âœ¨ Features

- ðŸŽ¤ **Smart Detection** â€” Advanced FFT filtering isolates physical impacts from speech and background noise.
- ðŸ”Š **Sound Packs** â€” Swap between built-in packs (Default, Retro, Nature) or add your own .wav files.
- âš¡ **0% Idle CPU** â€” Optimized RMS pre-filtering ensures the detection engine sleeps when you're silent.
- ðŸ“Š **Bonk Counter** â€” Persistent tracking of your lifetime "bonks" with milestone stats.
- ðŸš€ **Auto-Start** â€” One-click toggle from the tray to launch at Windows startup.
- ðŸ–¥ï¸ **System Tray** â€” Lives quietly in your taskbar with a polished hammer iconâ€”right-click to manage everything.

---

## ðŸš€ Installation

You have two easy ways to get TantuSpank:

### Option 1 (Recommended: Portable)
1. Go to the [Releases](https://github.com/chandrana17/TantuSpank/releases) page.
2. Download `TantuSpank_Portable.zip`.
3. Extract it to your Desktop or Documents folder.
4. Double-click `TantuSpank.exe` to run. No installation required!

### Option 2 (Windows Installer)
1. Download and run `TantuSpank_Setup.exe`.
2. Proceed through the setup wizard (installs natively to your local AppData for maximum compatibility).

Once running, TantuSpank will appear in your system tray. Give your desk a solid knock to test!

---

## ðŸ§  How It Works

TantuSpank uses real-time digital signal processing (DSP) to distinguish physical shocks from airborne sound:
- **Low-Pass Filtering**: Isolates frequencies below 300Hz (where thuds live).
- **Double-Hit Confirmation**: Prevents false triggers from single sharp noises like keyboard clicks.
- **Adaptive Baseline**: Maintains a rolling 2-second ambient noise average to maintain sensitivity in different environments.
- **Silent Crash Recovery**: Automatically reconnects to the microphone if the input is lost or the system wakes from sleep.

---

## ðŸ“‚ Sound Packs

Swap packs via the tray menu to change the vibe:
- `pack_default`: Classic percussion thuds.
- `pack_retro`: 8-bit style arcade bleeps.
- `pack_nature`: Organic wood and stone impact sounds.

**Custom Sounds**: You can dynamically select ANY `.wav` or `.mp3` file from anywhere on your PC! Just right-click the tray icon and navigate to **Custom Audio -> Select Custom Audio...**. Once selected, the engine will permanently remember your custom sound.

---

## ðŸ¤ Contributing

Contributions are welcome! If you have optimized detection algorithms or new sound packs, feel free to open a Pull Request.

---

## ðŸ“„ License

This project is licensed under the **MIT License**.

---

**Made with ðŸ”¨ and way too many desk knocks.**
