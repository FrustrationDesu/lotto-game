const statusEl = document.getElementById("status");
const textEl = document.getElementById("text");
const languageEl = document.getElementById("language");
const providerEl = document.getElementById("provider");
const errorEl = document.getElementById("error");
const startBtn = document.getElementById("startBtn");
const stopBtn = document.getElementById("stopBtn");

let mediaRecorder;
let chunks = [];
let stream;

const UIState = {
  IDLE: "idle",
  RECORDING: "recording",
  UPLOADING: "uploading",
  TRANSCRIBED: "transcribed",
  ERROR: "error",
};

function setState(state, errorMessage = "") {
  statusEl.textContent = state;
  errorEl.textContent = errorMessage;

  if (state === UIState.RECORDING) {
    startBtn.disabled = true;
    stopBtn.disabled = false;
    return;
  }

  if (state === UIState.UPLOADING) {
    startBtn.disabled = true;
    stopBtn.disabled = true;
    return;
  }

  startBtn.disabled = false;
  stopBtn.disabled = true;
}

async function startRecording() {
  textEl.textContent = "—";
  languageEl.textContent = "—";
  providerEl.textContent = "—";

  try {
    stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    chunks = [];
    mediaRecorder = new MediaRecorder(stream, { mimeType: "audio/webm" });

    mediaRecorder.addEventListener("dataavailable", (event) => {
      if (event.data.size > 0) {
        chunks.push(event.data);
      }
    });

    mediaRecorder.addEventListener("stop", async () => {
      const blob = new Blob(chunks, { type: "audio/webm" });
      await uploadAudio(blob);
      stream.getTracks().forEach((track) => track.stop());
    });

    mediaRecorder.start();
    setState(UIState.RECORDING);
  } catch (error) {
    setState(
      UIState.ERROR,
      "Не удалось получить доступ к микрофону. Проверьте разрешения браузера.",
    );
    console.error(error);
  }
}

function stopRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
    setState(UIState.UPLOADING);
  }
}

async function uploadAudio(audioBlob) {
  const formData = new FormData();
  formData.append("file", audioBlob, "recording.webm");

  try {
    const response = await fetch("/speech/transcribe", {
      method: "POST",
      body: formData,
    });

    if (!response.ok) {
      throw new Error(`HTTP ${response.status}`);
    }

    const payload = await response.json();
    textEl.textContent = payload.text ?? "—";
    languageEl.textContent = payload.language ?? "—";
    providerEl.textContent = payload.provider ?? "—";
    setState(UIState.TRANSCRIBED);
  } catch (error) {
    setState(UIState.ERROR, "Ошибка при отправке записи на сервер.");
    console.error(error);
  }
}

startBtn.addEventListener("click", startRecording);
stopBtn.addEventListener("click", stopRecording);
setState(UIState.IDLE);
