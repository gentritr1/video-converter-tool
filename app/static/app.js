const form = document.querySelector("#convertForm");
const fileInput = document.querySelector("#fileInput");
const fileName = document.querySelector("#fileName");
const submitButton = document.querySelector("#submitButton");
const statusLabel = document.querySelector("#statusLabel");
const progressText = document.querySelector("#progressText");
const progressBar = document.querySelector("#progressBar");
const message = document.querySelector("#message");
const downloadLink = document.querySelector("#downloadLink");

let pollTimer = null;

function setProgress(value) {
  const normalized = Math.max(0, Math.min(100, Number(value) || 0));
  progressBar.style.width = `${normalized}%`;
  progressText.textContent = `${Math.round(normalized)}%`;
}

function setStatus(label, text) {
  statusLabel.textContent = label;
  message.textContent = text;
}

function resetDownload() {
  downloadLink.hidden = true;
  downloadLink.removeAttribute("href");
}

fileInput.addEventListener("change", () => {
  const file = fileInput.files[0];
  fileName.textContent = file ? file.name : "Choose a video";
});

async function pollJob(jobId) {
  const response = await fetch(`/api/jobs/${jobId}`);
  if (!response.ok) {
    throw new Error("Unable to read conversion status.");
  }
  const job = await response.json();
  setProgress(job.progress);

  if (job.status === "queued") {
    setStatus("Queued", "Waiting for FFmpeg.");
  } else if (job.status === "probing") {
    setStatus("Reading video", "Checking the uploaded file.");
  } else if (job.status === "converting") {
    setStatus("Converting", "FFmpeg is creating the vertical MP4.");
  } else if (job.status === "completed") {
    window.clearInterval(pollTimer);
    pollTimer = null;
    submitButton.disabled = false;
    setProgress(100);
    setStatus("Done", "Your 1080x1920 MP4 is ready.");
    downloadLink.href = job.download_url;
    downloadLink.hidden = false;
  } else if (job.status === "failed") {
    window.clearInterval(pollTimer);
    pollTimer = null;
    submitButton.disabled = false;
    setProgress(0);
    setStatus("Failed", job.error || "Conversion failed.");
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  resetDownload();
  setProgress(0);

  if (!fileInput.files.length) {
    setStatus("Missing file", "Choose a video file first.");
    return;
  }

  const body = new FormData(form);
  submitButton.disabled = true;
  setStatus("Uploading", "Sending the video to the local converter.");

  try {
    const response = await fetch("/api/convert", {
      method: "POST",
      body,
    });

    const payload = await response.json();
    if (!response.ok) {
      throw new Error(payload.detail || "Upload failed.");
    }

    setStatus("Queued", "Starting FFmpeg.");
    pollTimer = window.setInterval(() => {
      pollJob(payload.job_id).catch((error) => {
        window.clearInterval(pollTimer);
        pollTimer = null;
        submitButton.disabled = false;
        setStatus("Error", error.message);
      });
    }, 1000);
    await pollJob(payload.job_id);
  } catch (error) {
    submitButton.disabled = false;
    setProgress(0);
    setStatus("Error", error.message || "Upload failed.");
  }
});
