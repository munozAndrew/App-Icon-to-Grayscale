# Minimal App Icon Generator

This is a small Flask server that automatically generates **minimal, dark app icons** for iOS Shortcuts.

I use custom icons to keep my home screen clean and consistent. I originally made these icons by hand, but it didn’t scale. This project automates the entire process.

---

## What It Does

- Detects apps installed on my iPhone
- Fetches their official App Store icons
- Converts them into a dark, minimal style
- Saves them with clean filenames
- Returns everything as a ZIP file

---

## How It Works

### App Detection

- Uses `ideviceinstaller` to list installed iPhone apps
- Since I’m on Windows, this is set up through **MSYS2 / mingw64** so it can run as a `.exe`

### Icon Fetching

- Uses the **iTunes Search API**
- Searches by app name
- Retrieves the highest-resolution icon available
- Includes retries to handle rate limits

### Icon Processing

- Icons are resized to **1024×1024**
- Converted to RGBA
- Bright regions become the icon color
- Dark regions become the background color
- Keeps logos readable while staying minimal

> Note: This logic can be improved. A future idea is experimenting with **CycleGAN** for smarter logo/background separation.

Colors are configurable in `config.py`.

### Output

- Icons are saved with readable names (e.g. `Instagram_dark.png`)
- Stored in a timestamped folder
- Zipped and returned from the API

---

## API Endpoints

### `GET /latest`

Runs the full pipeline and returns a ZIP of generated icons.

### `GET /health`

Simple health check.

---

## Tech Stack

- Python  
- Flask  
- Pillow (PIL)  
- NumPy  
- Requests  
- iTunes Search API  
- ideviceinstaller  
- MSYS2 / mingw64 (Windows setup)

---

## Setup Notes

You’ll need to set the path to `ideviceinstaller`:

```bash
IDEVICEINSTALLER_PATH=path/to/ideviceinstaller.exe

## How I Use This

1. Plug in my iPhone  
2. Start the server  
3. Hit `/latest` (I made a Shortcut for this on my iPhone)  
4. Download the ZIP  
5. Assign icons in Shortcuts  

If I install new apps, I just rerun it.

---

## Why I Built This

I wanted a **minimal home screen** without manually editing icons every time something changed. This automates a process I actually use.

---

## Next Changes

- Save a manifest so icons are only created for new apps
- Support multiple themes
- Smarter logo/background separation (CycleGAN experiment)
