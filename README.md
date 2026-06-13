# Local 9:16 Video Converter

A free local web app that uses FFmpeg to convert one uploaded video into a 1080x1920 MP4 for TikTok, Reels, and Shorts.

## Local-Only Approach

This project is designed to run on your own machine, not as a hosted SaaS app.

- The app binds to `127.0.0.1` in the documented run command, so it is only reachable from the local computer by default.
- Uploaded videos and converted outputs stay in the local `storage/` folder.
- FFmpeg and ffprobe run locally and do the actual media processing.
- No video is uploaded to cloud services by the app.
- No paid APIs are required.
- Temporary job files are cleaned up after the configured TTL.

The public GitHub repository is for source code distribution only. It is not a deployment target for processing videos.

## Features

- Accepts `.mp4`, `.mov`, `.webm`, and `.mkv` uploads
- Exports H.264/AAC MP4 at exactly `1080x1920`
- Keeps audio when present
- Uses `-movflags +faststart` for social upload compatibility
- Supports Crop, Fit with padding, and Blur Background modes
- Shows FFmpeg progress while converting
- Stores files locally and removes job files after 1 hour

## Requirements

- Python 3.10+
- FFmpeg and ffprobe installed locally

On macOS with Homebrew:

```bash
brew install ffmpeg
```

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## Run

```bash
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

Do not run this with `--host 0.0.0.0` unless you intentionally want other devices on your network to reach the app.

## Configuration

Environment variables:

- `MAX_UPLOAD_MB`: maximum upload size in MB, default `2048`
- `JOB_TTL_SECONDS`: how long converted files stay available, default `3600`
- `FFMPEG_BIN`: FFmpeg binary path, default `ffmpeg`
- `FFPROBE_BIN`: ffprobe binary path, default `ffprobe`

## Conversion Modes

- **Blur Background**: default. Creates a blurred 9:16 background from the video and centers the full original video on top.
- **Crop**: fills the whole vertical frame with a center crop.
- **Fit**: keeps the whole video visible and adds black padding.

The FFmpeg wrapper uses argument lists with `shell=False`; raw user input is never concatenated into a shell command.

## Roadmap

See [docs/ROADMAP.md](docs/ROADMAP.md) for researched feature ideas and implementation plans for the next development phases.
