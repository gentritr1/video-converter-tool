# Roadmap

This roadmap keeps the tool local-first, free, and FFmpeg-driven. The target user is a creator or small team that has horizontal or full-screen video and wants clean vertical exports for TikTok, Instagram Reels, YouTube Shorts, and similar feeds without uploading raw footage to a paid service.

## Local-First Constraints

This is not intended to be a deployed cloud service. The default product shape is a local app that runs on the user's own machine.

- Bind to `127.0.0.1` by default.
- Keep uploads, temporary files, previews, and outputs on local disk.
- Use local FFmpeg/ffprobe for all processing.
- Avoid paid APIs and remote video processing.
- Prefer local dependencies and optional local models for advanced features.
- Treat deployment support as out of scope unless explicitly requested later.

Efficiency work should assume local CPU, disk, memory, and battery constraints. The app should avoid launching too many FFmpeg jobs at once, avoid full encodes when a preview will answer the user's question, and make heavyweight features opt-in.

## Current Baseline

The app already has the core conversion loop:

- Single upload for `.mp4`, `.mov`, `.webm`, and `.mkv`.
- Three 9:16 conversion modes: blur background, crop, and fit with padding.
- Exact `1080x1920` MP4 output with H.264 video, AAC audio, square pixels, and `+faststart`.
- FFmpeg progress polling, output validation, temporary local storage, and one-hour cleanup.
- Safe process execution through argument arrays with `shell=False`.

The current baseline is intentionally small. The next steps should improve workflow speed, preview confidence, and creative control before adding heavier AI features.

## Research Notes

Platform compatibility still supports the current baseline. YouTube recommends MP4, Fast Start, H.264, progressive scan, 4:2:0 chroma, and matching source frame rate where possible. TikTok's current ad specs recommend vertical 9:16 video at at least `540x960`, with `.mp4` and `.mov` accepted for common vertical placements. Meta/Instagram public specs are harder to fetch consistently without login, but `1080x1920` H.264/AAC MP4 remains the practical shared target for Reels.

Relevant FFmpeg capabilities are already in the toolchain:

- `scale`, `crop`, `pad`, `overlay`, and blur filters cover the current visual modes.
- `drawtext`, subtitles, trim filters, audio filters, and metadata probing make creator-focused enhancements possible without paid APIs.
- `ffprobe` JSON output can drive better validation, previews, duration checks, stream diagnostics, and source warnings.

Sources:

- [YouTube recommended upload encoding settings](https://support.google.com/youtube/answer/1722171?hl=en)
- [TikTok Auction In-Feed Ads specs](https://ads.tiktok.com/help/article/tiktok-auction-in-feed-ads?lang=en)
- [FFmpeg filter documentation](https://ffmpeg.org/ffmpeg-filters.html)
- [FFmpeg CLI documentation](https://ffmpeg.org/ffmpeg.html)
- [ffprobe documentation](https://ffmpeg.org/ffprobe.html)

## Product Direction

The strongest product position is not "another converter." It should become a local creator prep station:

- Convert quickly without cloud upload.
- See what will be cropped before spending time converting.
- Batch process many clips with consistent settings.
- Add optional creator polish such as safe zones, captions, thumbnails, and audio normalization.
- Keep advanced AI features local and optional.

## Local Efficiency Plan

The goal is not maximum server throughput. The goal is fast, predictable local use on a creator's machine.

1. **Bounded conversion queue**
   Run one FFmpeg job by default, with a configurable concurrency limit for powerful machines.

2. **Preview before encode**
   Generate lightweight preview frames before full conversion so the user does not waste time on the wrong mode.

3. **Avoid unnecessary work**
   Reuse probed metadata, cache previews during a session, and clean up expired files.

4. **Use sane defaults**
   Keep `libx264`, CRF-based encoding, AAC audio, `yuv420p`, and `+faststart` as the compatibility baseline.

5. **Optional hardware acceleration later**
   Explore platform-specific encoders such as VideoToolbox on macOS only as optional presets. Keep software H.264 as the quality/compatibility default because hardware encoders can be faster but less consistent at the same apparent bitrate.

6. **Clear diagnostics**
   Show FFmpeg/ffprobe versions, active queue state, and per-job errors locally so users can fix setup issues without logs from a remote service.

## Priority Matrix

| Priority | Feature | User value | Build risk | Recommendation |
| --- | --- | --- | --- | --- |
| P0 | Conversion hardening | Prevents failed or stuck jobs | Low | Do first |
| P1 | Batch queue | Saves repeated upload/convert work | Medium | Build next |
| P1 | Preview frames | Prevents bad crops before export | Medium | Build after queue foundation |
| P1 | Source metadata warnings | Explains bad inputs early | Low | Build with previews |
| P2 | Manual crop/focal point | Fixes off-center subjects | Medium | Build before AI reframing |
| P2 | Safe-zone overlay | Protects captions/products/faces from app UI | Low | Build with preview UI |
| P2 | Background style controls | Makes blur mode look more intentional | Low | Good creative upgrade |
| P2 | Trimming | Covers common short-form prep | Medium | Add after preview |
| P3 | Captions/subtitle burn-in | Strong creator value | Medium | Start with uploaded subtitle files |
| P3 | Audio normalization | Improves polish | Low | Keep opt-in |
| P3 | Cover frame export | Useful posting asset | Low | Add with preview thumbnails |
| P4 | Desktop packaging | Expands audience | Medium-high | Do after workflow stabilizes |
| P4 | Local AI reframing | Differentiating feature | High | Do after manual controls |
| P4 | Local transcription | High value but dependency-heavy | High | Keep optional |

## Creative Differentiators

These ideas make the app feel like a creator tool instead of a plain converter:

- **Before/after swipe preview**: compare original frame and vertical output frame.
- **Safe-zone presets**: show TikTok/Reels/Shorts-style overlays for captions and action areas.
- **Product mode**: softer blur, darker background, and more center-safe composition for product demos.
- **Gameplay/screen-recording mode**: sharper foreground, darker background, optional top/bottom title bars.
- **Talking-head mode**: manual face/focal point controls first, then optional local face tracking later.
- **Batch recipe**: save settings as a reusable local preset, then apply to a folder of clips.
- **Export pack**: output MP4 plus cover JPG, metadata text file, and optional captions file in one ZIP.
- **Quality estimator**: show expected file size range and warn when a selected profile may be too large.
- **No-cloud badge**: make privacy/local processing visible in the UI and README.

## Recommended Sequence

1. **Immediate conversion hardening**
   Drain FFmpeg `stderr` while progress is being read, introduce a clearer job state machine, and avoid unbounded queued work.

2. **Workflow reliability and batch conversion**
   Convert multiple files, queue jobs, cancel stuck jobs, and download results individually or as a ZIP.

3. **Preview before conversion**
   Show source metadata, generated preview frames, safe-zone overlays, and mode previews so users can avoid bad crops.

4. **Manual framing controls**
   Let users choose focal point, crop position, blur strength, background style, and trim ranges.

5. **Creator polish**
   Add thumbnails, captions/subtitles, loudness normalization, and platform export profiles.

6. **Local desktop packaging**
   Ship a double-click app that bundles or locates FFmpeg, with a simple updater/release path.

7. **Optional local intelligence**
   Add face/object-aware auto-reframe and local transcription only after the queue, preview, and manual controls are stable.

## Roadmap

### Phase 0: Conversion Hardening

**Drain FFmpeg diagnostics safely**

- Keep `-progress pipe:1` for structured progress.
- Drain `stderr` concurrently into a bounded string buffer, temp log file, or worker thread.
- Preserve the final diagnostic text for failed jobs.
- Add a test that simulates a subprocess writing both progress and diagnostics.

Why it matters: the current worker reads progress from `stdout` and reads `stderr` only after FFmpeg exits. That is simple, but a noisy FFmpeg process can block if its `stderr` pipe fills.

**Explicit job state machine**

- Add statuses such as `queued`, `probing`, `converting`, `completed`, `failed`, `cancel_requested`, `canceled`, and `expired`.
- Keep status transitions in one `JobManager` instead of spreading updates across route and worker code.
- Include `stage`, `queue_position`, `speed`, and `eta_seconds` fields later.

Why it matters: better state makes cancellation, batch conversion, retry, and refresh recovery much easier.

**Bounded queue**

- Replace implicit executor queueing with an explicit bounded queue.
- Return a clear `429` or "queue full" response when the local machine is already busy.
- Make concurrency configurable, but default to one active FFmpeg job for predictable CPU usage.

Why it matters: local FFmpeg jobs are CPU-heavy. Unlimited queue submission can overload the machine and make progress feel broken.

### Phase 1: Workflow Upgrade

**Batch upload and queue**

- Allow multiple videos in one upload.
- Add a visible queue with one row per job.
- Show mode, filename, source duration, progress, status, errors, and download links.
- Keep concurrency low by default, for example one active FFmpeg process and the rest queued.
- Add "Convert all", "Cancel", and "Clear completed" controls.

Why it matters: creators usually process clips in groups. Batch conversion is the highest-value upgrade because it saves repeated manual work without changing the core encoder.

**Persistent job state**

- Store job metadata in a small SQLite database instead of only in memory.
- Survive server reloads and show recent completed jobs until their files expire.
- Track uploaded file path, output path, source metadata, selected mode, quality, status, and error message.

Why it matters: in-memory jobs are fine for a prototype, but conversion can take minutes for large videos. Users should not lose status if the browser refreshes.

**Cancellation**

- Keep a process handle for active jobs.
- Add `POST /api/jobs/{job_id}/cancel`.
- Send FFmpeg a graceful termination first, then force-kill only if needed.
- Mark canceled jobs separately from failed jobs.

Why it matters: accidental large conversions and wrong mode selections should be easy to stop.

### Phase 2: Preview and Confidence

**Source analysis panel**

- Show duration, dimensions, frame rate, rotation metadata, video codec, audio codec, and estimated output mode impact.
- Warn about unusual cases: no audio, very long videos, huge dimensions, unsupported codecs, interlaced input, HDR/wide-color input, or files above configured limits.
- Capture file size, bitrate, format name, pixel format, audio channels, and selected stream index.

Why it matters: most conversion surprises are predictable from ffprobe before running FFmpeg.

**Mode preview frames**

- Generate low-resolution preview JPGs for Crop, Fit, and Blur Background.
- Use a frame from the middle of the video by default.
- Show previews before full conversion and let the user compare modes.

Why it matters: the user can see whether important text or faces will be cropped before waiting on a full encode.

**Safe-zone overlay**

- Add toggleable overlays for common vertical UI danger zones.
- Keep overlays as guides only; do not burn them into the output.
- Include top/bottom caption/action areas and a center-safe framing guide.

Why it matters: TikTok/Reels/Shorts UI can cover captions, product details, and faces. A guide prevents avoidable placement mistakes.

### Phase 3: Framing Controls

**Manual crop/focal point**

- For Crop mode, let the user choose center, top, bottom, left, right, or custom focal point.
- Convert focal point into FFmpeg crop expressions.
- Add preview generation so this is visual, not just numeric.

Why it matters: center crop is reliable but not always correct. Manual focal point is a lightweight alternative to full AI tracking.

**Blur/background controls**

- Add blur strength, background brightness, background saturation, and optional solid/neutral color.
- Add a "soft background" preset for product clips and a "high contrast" preset for gameplay/screen captures.

Why it matters: blurred backgrounds can look too busy or too washed out. Small controls can make exports feel more intentional.

**Trim controls**

- Add start and end time inputs.
- Use FFmpeg `-ss` and `-to` or trim filters depending on accuracy needs.
- Keep default behavior as full-duration conversion.

Why it matters: short-form clips often need a quick head/tail trim before export.

### Phase 4: Creator Polish

**Platform export profiles**

- Add profiles for General Vertical, TikTok, Reels, Shorts, and Small File.
- Profiles should set dimensions, codec, audio bitrate, CRF, max upload size warnings, and optional safe-zone defaults.
- Keep "General Vertical" as the default to avoid overfitting to changing platform rules.

Why it matters: profiles make the app easier for non-technical users while keeping FFmpeg settings explicit.

**Captions and subtitles**

- First add user-uploaded `.srt`/`.vtt` subtitle burn-in.
- Later add optional local transcription using a local Whisper-compatible tool.
- Support caption style presets: high-contrast, minimal, boxed, and lower-third.

Why it matters: captions are often essential for short-form retention and accessibility. Start with uploaded subtitle files before adding transcription complexity.

**Audio normalization**

- Add a toggle for speech-friendly loudness normalization.
- Use FFmpeg audio filters such as loudness normalization and limiting.
- Keep original audio by default unless the user opts in.

Why it matters: clips from different sources often have inconsistent volume. Optional normalization improves perceived quality.

**Thumbnail and cover frame**

- Generate thumbnails from selected timestamps.
- Let users download a `.jpg` cover frame alongside the video.
- Later add simple title text overlay for the cover image only.

Why it matters: creators often need a cover frame for posting workflows.

### Phase 5: Packaging and Distribution

**Desktop app**

- Package the local web app as a desktop app.
- Recommended path: keep FastAPI as the engine, then wrap it with a small desktop shell only after the web workflow is stable.
- Evaluate Tauri, Electron, and PyInstaller. The best choice depends on whether we want a real browser UI shell or a simpler local executable.

Why it matters: many users will not want to run terminal commands.

**Local launch mode**

- Provide a command or package entry point that starts the server on `127.0.0.1`.
- Optionally open the browser automatically after startup.
- Keep network exposure opt-in and documented.

Why it matters: local-only behavior should be the default even after packaging.

**FFmpeg discovery**

- Detect FFmpeg and ffprobe at startup.
- Show a clear setup screen if binaries are missing.
- Support `FFMPEG_BIN` and `FFPROBE_BIN` overrides.
- Document licensing implications before bundling FFmpeg binaries.

Why it matters: the most common install failure will be missing FFmpeg.

**Release workflow**

- Add GitHub Actions for tests.
- Add versioned releases with packaged artifacts when packaging exists.
- Keep source distribution simple until packaging is stable.

Why it matters: public repos need repeatable checks and predictable releases.

### Phase 6: Optional Local Intelligence

**Face/object-aware reframing**

- Add optional local detection using OpenCV, MediaPipe, or another local model.
- Generate a crop path that follows faces or selected subjects.
- Smooth crop movement to avoid jitter.
- Always allow manual override.

Why it matters: it can make horizontal videos feel native in 9:16, but it is higher complexity and should not block the simpler manual controls.

**Scene detection**

- Detect hard cuts and generate preview frames per scene.
- Avoid using one preview frame for a video whose framing changes dramatically.
- Later, allow splitting a long video into scene-based clips.

Why it matters: creators often start with longer footage and need short clips.

**Watch folder**

- Monitor a local folder and auto-convert new videos with a selected preset.
- Save outputs to a configured destination.
- Keep it opt-in and clearly local.

Why it matters: useful for repeat workflows such as camera exports, screen recordings, and game clips.

## Implementation Plans

### Plan 0: Harden the Current Conversion Worker

**Goal**

Remove subprocess deadlock risk and establish job state foundations before larger features.

**Backend changes**

- Add a small `JobStatus` enum or constants.
- Add `stderr` draining while the worker reads FFmpeg `stdout` progress.
- Store only the last N KB of diagnostics in memory, or write full diagnostics to a temp per-job log.
- Add a bounded queue configuration such as `MAX_QUEUE_SIZE`.
- Return a clear error when the queue is full.

**Frontend changes**

- Show failed-job diagnostics in a compact expandable area.
- Keep the existing one-second polling for now.

**Tests**

- Unit test progress parsing.
- Unit test stderr draining using a small Python subprocess fixture.
- Unit test queue-full behavior once the explicit queue exists.

**Acceptance criteria**

- A noisy failed FFmpeg command cannot deadlock the worker.
- Failed jobs preserve useful diagnostic text.
- Job statuses are consistent and documented.

### Plan A: Batch Conversion and Queue

**Goal**

Convert multiple files in one session while keeping safe local execution and clear progress.

**Backend changes**

- Change `/api/convert` to accept multiple `UploadFile` values or add `/api/batch`.
- Introduce a `JobStore` abstraction instead of direct global `jobs` access.
- Represent batch IDs separately from job IDs.
- Limit active conversions with a queue worker rather than submitting every file directly to `ThreadPoolExecutor`.
- Add `GET /api/jobs` and `GET /api/batches/{batch_id}`.
- Add optional ZIP creation for completed batch outputs.

**Frontend changes**

- Change the file input to `multiple`.
- Replace the single status panel with a queue table or compact job list.
- Keep one global mode/quality selector first; per-file settings can come later.
- Show per-job progress and download links.

**Tests**

- Unit test queue state transitions.
- Unit test that each generated FFmpeg command uses its own UUID paths.
- Integration test two small sample videos through the queue.

**Acceptance criteria**

- Uploading three videos creates three jobs.
- Only the configured number of jobs runs at once.
- Each completed job downloads as a valid `1080x1920` MP4.
- Failed jobs do not block the remaining queue.

### Plan B: Job Persistence and Cancellation

**Goal**

Make conversions resilient to browser refreshes and easy to stop.

**Backend changes**

- Add SQLite with a lightweight schema for jobs and batches.
- Store job status, timestamps, selected settings, source metadata, output filename, and error text.
- Track active FFmpeg process handles in memory while preserving durable job records in SQLite.
- Add `POST /api/jobs/{job_id}/cancel`.
- Add statuses: `queued`, `probing`, `converting`, `completed`, `failed`, `canceled`, `expired`.

**Frontend changes**

- Add a cancel button for queued/converting jobs.
- Keep polling after refresh by reading recent jobs from `/api/jobs`.
- Show canceled jobs distinctly from failed jobs.

**Tests**

- Unit test SQLite job create/update/list.
- Unit test cancellation state changes.
- Integration test cancellation with a generated longer sample video.

**Acceptance criteria**

- Refreshing the page does not lose visible job status.
- Canceling a running job stops FFmpeg and deletes partial output.
- Canceled jobs do not show as failures.

### Plan C: Preview Frames and Safe Zones

**Goal**

Let users see likely output before running a full encode.

**Backend changes**

- Add `/api/preview` or `/api/jobs/{job_id}/preview`.
- Use FFmpeg to generate low-resolution JPG previews for each mode.
- Store previews in a separate temp folder with the same TTL.
- Add source metadata endpoint based on ffprobe JSON.

**Frontend changes**

- Show metadata after upload.
- Show three preview tiles for Crop, Fit, and Blur.
- Add a safe-zone overlay toggle on preview tiles.
- Let preview selection update the conversion mode.

**Tests**

- Test preview command generation.
- Probe preview output dimensions.
- Browser check desktop and mobile preview layout.

**Acceptance criteria**

- Preview generation finishes much faster than full conversion for normal clips.
- Every mode preview visually matches the eventual mode.
- Safe-zone overlay is visible in the UI but not burned into exported video.

### Plan D: Manual Crop and Background Controls

**Goal**

Give users creative control without making the app feel like a full video editor.

**Backend changes**

- Replace fixed filter strings with a filter builder that accepts typed options.
- Supported options: crop anchor, custom focal point, blur amount, background brightness, background saturation, and background color.
- Validate every option against numeric bounds or enums.

**Frontend changes**

- Add a mode-specific options panel.
- Crop mode: segmented controls for center/top/bottom/left/right and later a draggable focal point.
- Blur mode: sliders for blur and background brightness.
- Fit mode: background color selector.

**Tests**

- Unit test filter builder output for every supported option.
- Integration test crop anchors on landscape and portrait sample clips.

**Acceptance criteria**

- All options produce valid FFmpeg argv arrays.
- No option allows shell injection or arbitrary filter text.
- Output remains exactly `1080x1920`.

### Plan E: Captions, Audio, and Covers

**Goal**

Add creator polish that fits short-form posting workflows.

**Backend changes**

- Accept optional `.srt` or `.vtt` subtitle file.
- Burn captions with FFmpeg subtitle filters and controlled style presets.
- Add optional audio normalization pipeline.
- Add cover frame generation endpoint.

**Frontend changes**

- Add optional subtitle upload.
- Add caption style selector.
- Add audio normalization toggle.
- Add cover frame timestamp input and download button.

**Tests**

- Test subtitle file validation.
- Test caption command generation with safe temp paths.
- Test output with and without audio normalization.

**Acceptance criteria**

- User-provided captions can be burned into output.
- Audio normalization is opt-in.
- Cover JPG downloads independently from the MP4.

### Plan F: Desktop Packaging

**Goal**

Make the tool usable without terminal knowledge.

**Implementation path**

- First add startup health checks for FFmpeg/ffprobe.
- Add a clear missing-FFmpeg UI state.
- Then evaluate packaging:
  - PyInstaller for a simple Python executable.
  - Tauri for a lightweight desktop shell.
  - Electron if Node-based packaging and auto-update become more important.
- Decide whether to bundle FFmpeg or require local installation. Document GPL/licensing implications before bundling `libx264` builds.

**Acceptance criteria**

- A non-technical user can launch the app and see the converter.
- Missing FFmpeg produces an actionable setup screen.
- Packaged app can convert a sample video on a clean machine with documented prerequisites.

## Backlog Ideas

- Drag-and-drop upload area with file validation before upload.
- CLI mode: `python -m app.convert input.mp4 --mode blur --output out.mp4`.
- Watch folder auto-converter.
- Export history with "re-run with same settings."
- Custom output resolution: `720x1280`, `1080x1920`, `1440x2560`.
- Optional bitrate cap for predictable file size.
- Auto-rotate and orientation metadata repair.
- HDR-to-SDR warning or conversion preset.
- Scene split and highlight extraction.
- Side-by-side before/after comparison.
- Simple branded templates with user-owned logo overlay, disabled by default.
- Internationalized UI strings.
- Docker image for server-style local use.

## Not Recommended Yet

- Cloud upload or paid APIs. It would weaken the privacy/local-first value.
- Deploying this as a public hosted converter. The current product strategy is local processing, not server-side processing of user videos.
- Full timeline editing. That turns the app into a video editor and dilutes the focused converter workflow.
- AI auto-reframe before manual focal point and previews. Manual controls solve many cases with less complexity.
- Bundling FFmpeg before licensing and platform packaging are decided.

## Next Best Implementation Target

Start with **Plan A: Batch Conversion and Queue**, then **Plan C: Preview Frames and Safe Zones**.

That order gives the biggest practical improvement while preserving the current architecture. Batch conversion improves throughput immediately. Preview frames reduce bad exports and create the foundation for manual crop, safe zones, and creative controls.
