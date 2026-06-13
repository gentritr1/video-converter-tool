from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles


BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "app" / "static"
STORAGE_DIR = BASE_DIR / "storage"
UPLOADS_DIR = STORAGE_DIR / "uploads"
OUTPUTS_DIR = STORAGE_DIR / "outputs"

FFMPEG_BIN = os.getenv("FFMPEG_BIN", "ffmpeg")
FFPROBE_BIN = os.getenv("FFPROBE_BIN", "ffprobe")
MAX_UPLOAD_BYTES = int(os.getenv("MAX_UPLOAD_MB", "2048")) * 1024 * 1024
JOB_TTL_SECONDS = int(os.getenv("JOB_TTL_SECONDS", "3600"))
OUTPUT_WIDTH = 1080
OUTPUT_HEIGHT = 1920
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".webm", ".mkv"}

Mode = Literal["blur", "crop", "fit"]
Quality = Literal["high", "balanced", "small"]

QUALITY_CRF = {
    "high": 16,
    "balanced": 18,
    "small": 24,
}

FILTERS = {
    "crop": (
        "scale=1080:1920:force_original_aspect_ratio=increase:"
        "force_divisible_by=2:reset_sar=1,crop=1080:1920,setsar=1"
    ),
    "fit": (
        "scale=1080:1920:force_original_aspect_ratio=decrease:"
        "force_divisible_by=2:reset_sar=1,"
        "pad=1080:1920:(ow-iw)/2:(oh-ih)/2:black,setsar=1"
    ),
    "blur": (
        "[0:v]split=2[base][copy];"
        "[base]scale=1080:1920:force_original_aspect_ratio=increase:"
        "force_divisible_by=2:reset_sar=1,"
        "crop=1080:1920,boxblur=30:1[bg];"
        "[copy]scale=1080:1920:force_original_aspect_ratio=decrease:"
        "force_divisible_by=2:reset_sar=1[fg];"
        "[bg][fg]overlay=(W-w)/2:(H-h)/2,setsar=1[v]"
    ),
}


@dataclass
class Job:
    id: str
    status: str
    mode: str
    quality: str
    progress: float
    created_at: float
    updated_at: float
    input_path: str | None = None
    output_path: str | None = None
    download_name: str | None = None
    duration: float | None = None
    has_audio: bool | None = None
    error: str | None = None


app = FastAPI(title="Local 9:16 Video Converter")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

jobs: dict[str, Job] = {}
jobs_lock = threading.Lock()
executor = ThreadPoolExecutor(max_workers=max(1, min(2, os.cpu_count() or 1)))


def ensure_storage() -> None:
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)


def now() -> float:
    return time.time()


def sanitize_stem(filename: str) -> str:
    stem = Path(filename).stem.lower()
    stem = re.sub(r"[^a-z0-9._-]+", "-", stem).strip(".-")
    return stem or "converted-video"


def validate_extension(filename: str) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        allowed = ", ".join(sorted(ALLOWED_EXTENSIONS))
        raise HTTPException(status_code=400, detail=f"Unsupported file type. Use {allowed}.")
    return suffix


def validate_choice(value: str, allowed: set[str], label: str) -> str:
    if value not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid {label}.")
    return value


async def save_upload(upload: UploadFile, destination: Path) -> int:
    total = 0
    with destination.open("wb") as out:
        while True:
            chunk = await upload.read(1024 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_UPLOAD_BYTES:
                out.close()
                destination.unlink(missing_ok=True)
                limit_mb = MAX_UPLOAD_BYTES // (1024 * 1024)
                raise HTTPException(status_code=413, detail=f"File is larger than {limit_mb} MB.")
            out.write(chunk)
    if total == 0:
        destination.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    return total


def run_json_command(args: list[str]) -> dict:
    try:
        completed = subprocess.run(
            args,
            check=True,
            capture_output=True,
            text=True,
            shell=False,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg or ffprobe was not found. Check your installation.") from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "Unable to inspect video.").strip()
        raise RuntimeError(detail[-800:]) from exc

    return json.loads(completed.stdout or "{}")


def probe_video(path: Path) -> tuple[float, bool]:
    data = run_json_command(
        [
            FFPROBE_BIN,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    streams = data.get("streams") or []
    if not any(stream.get("codec_type") == "video" for stream in streams):
        raise RuntimeError("No video stream was found in the uploaded file.")
    has_audio = any(stream.get("codec_type") == "audio" for stream in streams)
    duration_raw = data.get("format", {}).get("duration")
    try:
        duration = float(duration_raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Unable to read video duration.") from exc
    if duration <= 0:
        raise RuntimeError("Video duration must be greater than zero.")
    return duration, has_audio


def probe_output(path: Path, expect_audio: bool, expected_duration: float) -> None:
    data = run_json_command(
        [
            FFPROBE_BIN,
            "-v",
            "error",
            "-show_entries",
            "stream=codec_type,codec_name,width,height,sample_aspect_ratio,pix_fmt:format=duration",
            "-of",
            "json",
            str(path),
        ]
    )
    streams = data.get("streams") or []
    video_streams = [stream for stream in streams if stream.get("codec_type") == "video"]
    audio_streams = [stream for stream in streams if stream.get("codec_type") == "audio"]
    if not video_streams:
        raise RuntimeError("Converted output has no video stream.")
    stream = video_streams[0]
    if stream.get("width") != OUTPUT_WIDTH or stream.get("height") != OUTPUT_HEIGHT:
        raise RuntimeError("Converted output is not 1080x1920.")
    if stream.get("codec_name") != "h264":
        raise RuntimeError("Converted output is not H.264 video.")
    if stream.get("sample_aspect_ratio") not in {"1:1", None}:
        raise RuntimeError("Converted output does not use square pixels.")
    if stream.get("pix_fmt") != "yuv420p":
        raise RuntimeError("Converted output is not yuv420p.")
    if expect_audio:
        if not audio_streams:
            raise RuntimeError("Converted output is missing the original audio.")
        if any(audio.get("codec_name") != "aac" for audio in audio_streams):
            raise RuntimeError("Converted output audio is not AAC.")
    output_duration_raw = data.get("format", {}).get("duration")
    try:
        output_duration = float(output_duration_raw)
    except (TypeError, ValueError) as exc:
        raise RuntimeError("Unable to read converted output duration.") from exc
    if abs(output_duration - expected_duration) > max(1.0, expected_duration * 0.02):
        raise RuntimeError("Converted output duration does not match the input.")


def parse_progress_seconds(key: str, value: str) -> float | None:
    if key in {"out_time_ms", "out_time_us"}:
        try:
            return float(value) / 1_000_000
        except ValueError:
            return None
    if key == "out_time":
        match = re.match(r"(?P<h>\d+):(?P<m>\d+):(?P<s>\d+(?:\.\d+)?)", value)
        if not match:
            return None
        return (
            int(match.group("h")) * 3600
            + int(match.group("m")) * 60
            + float(match.group("s"))
        )
    return None


def build_ffmpeg_args(input_path: Path, output_path: Path, mode: str, crf: int) -> list[str]:
    args = [
        FFMPEG_BIN,
        "-y",
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "error",
        "-progress",
        "pipe:1",
        "-i",
        str(input_path),
    ]

    if mode == "blur":
        args.extend(
            [
                "-filter_complex",
                FILTERS[mode],
                "-map",
                "[v]",
                "-map",
                "0:a?",
            ]
        )
    else:
        args.extend(
            [
                "-map",
                "0:v:0",
                "-map",
                "0:a?",
                "-vf",
                FILTERS[mode],
            ]
        )

    args.extend(
        [
            "-sn",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            str(crf),
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(output_path),
        ]
    )
    return args


def update_job(job_id: str, **changes: object) -> None:
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            return
        for key, value in changes.items():
            setattr(job, key, value)
        job.updated_at = now()


def convert_job(job_id: str) -> None:
    with jobs_lock:
        job = jobs[job_id]
        input_path = Path(job.input_path or "")
        output_path = Path(job.output_path or "")
        mode = job.mode
        quality = job.quality

    try:
        partial_output_path = output_path.with_suffix(".partial.mp4")
        update_job(job_id, output_path=str(partial_output_path), status="probing", progress=2)
        duration, has_audio = probe_video(input_path)
        update_job(job_id, duration=duration, has_audio=has_audio, status="converting", progress=5)
        args = build_ffmpeg_args(input_path, partial_output_path, mode, QUALITY_CRF[quality])

        process = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            shell=False,
        )
        assert process.stdout is not None
        assert process.stderr is not None

        for raw_line in process.stdout:
            line = raw_line.strip()
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            seconds = parse_progress_seconds(key, value)
            if seconds is not None and duration:
                progress = min(99, max(5, (seconds / duration) * 100))
                update_job(job_id, progress=round(progress, 1))
            elif key == "progress" and value == "end":
                update_job(job_id, progress=100)

        stderr = process.stderr.read()
        return_code = process.wait()
        if return_code != 0:
            message = (stderr or "FFmpeg conversion failed.").strip()
            raise RuntimeError(message[-1200:])

        probe_output(partial_output_path, has_audio, duration)
        partial_output_path.replace(output_path)
        update_job(job_id, output_path=str(output_path), status="completed", progress=100)
    except Exception as exc:
        output_path.unlink(missing_ok=True)
        output_path.with_suffix(".partial.mp4").unlink(missing_ok=True)
        update_job(job_id, status="failed", error=str(exc), progress=0)
    finally:
        input_path.unlink(missing_ok=True)


def cleanup_old_jobs() -> None:
    while True:
        cutoff = now() - JOB_TTL_SECONDS
        expired: list[str] = []
        with jobs_lock:
            for job_id, job in jobs.items():
                if job.created_at < cutoff or job.updated_at < cutoff:
                    expired.append(job_id)
            expired_jobs = [jobs.pop(job_id) for job_id in expired]

        for job in expired_jobs:
            for path_value in (job.input_path, job.output_path):
                if path_value:
                    Path(path_value).unlink(missing_ok=True)
        time.sleep(300)


@app.on_event("startup")
def on_startup() -> None:
    ensure_storage()
    threading.Thread(target=cleanup_old_jobs, daemon=True).start()


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.post("/api/convert")
async def convert(
    file: UploadFile = File(...),
    mode: str = Form("blur"),
    quality: str = Form("balanced"),
) -> dict[str, str]:
    ensure_storage()
    mode = validate_choice(mode, {"blur", "crop", "fit"}, "mode")
    quality = validate_choice(quality, set(QUALITY_CRF), "quality")
    suffix = validate_extension(file.filename or "")

    job_id = uuid.uuid4().hex
    input_path = UPLOADS_DIR / f"{job_id}{suffix}"
    output_name = f"{sanitize_stem(file.filename or 'video')}-9x16.mp4"
    output_path = OUTPUTS_DIR / f"{job_id}.mp4"

    await save_upload(file, input_path)
    await file.close()

    job = Job(
        id=job_id,
        status="queued",
        mode=mode,
        quality=quality,
        progress=0,
        created_at=now(),
        updated_at=now(),
        input_path=str(input_path),
        output_path=str(output_path),
        download_name=output_name,
    )
    with jobs_lock:
        jobs[job_id] = job

    executor.submit(convert_job, job_id)
    return {"job_id": job_id}


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> dict:
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        payload = asdict(job)
    payload.pop("input_path", None)
    payload.pop("output_path", None)
    if payload["status"] == "completed":
        payload["download_url"] = f"/api/jobs/{job_id}/download"
    return payload


@app.get("/api/jobs/{job_id}/download")
def download(job_id: str) -> FileResponse:
    with jobs_lock:
        job = jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")
        if job.status != "completed" or not job.output_path:
            raise HTTPException(status_code=409, detail="Job is not ready.")
        path = Path(job.output_path)
        download_name = job.download_name or "converted-9x16.mp4"

    if not path.exists():
        raise HTTPException(status_code=404, detail="Converted file has expired.")
    return FileResponse(path, media_type="video/mp4", filename=download_name)
