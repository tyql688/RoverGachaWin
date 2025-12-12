# RoverGacha - Wuthering Waves Gacha URL Finder

A simple, modern GUI tool to automatically locate the Gacha (Convene) History URL for Wuthering Waves on Windows.

## Features
- **Auto Scan**: Automatically searches common paths, registry, MUI cache, and firewall rules.
- **Modern UI**: Dark-themed interface built with PySide6.
- **Robust Parsing**: Extracts URL from `Client.log` or `debug.log`.
- **Clipboard**: One-click copy.

## Prerequisites
- Windows 10/11
- Python 3.10+
- [uv](https://github.com/astral-sh/uv) (Recommended)

## Setup

1. **Install Dependencies**
   Run in the project root:
   ```powershell
   uv sync
   ```

## Compile (Build EXE)

To create the standalone `RoverGacha.exe` in the `dist/` folder:

```powershell
uv run python build.py
```

## Usage
1. Open Wuthering Waves -> Convene -> History (wait for page to load).
2. Run `RoverGacha.exe`.
3. Click **Auto Scan**.
4. Click **Copy URL**.
