import { state, authFetch, API_BASE } from "../state.js";
import { startAutoListening, stopAutoListening, parseVoiceIntent } from "../recording.js";
import { submitChoice } from "./engine.js";

export function initVoiceControls() {
  const btnVoice = document.getElementById("btn-voice-record");
  if (btnVoice) {
    btnVoice.addEventListener("click", toggleVoiceRecording);
  }

  const fileInput = document.getElementById("input-voice-file");
  if (fileInput) {
    fileInput.addEventListener("change", async (e) => {
      const file = e.target.files[0];
      if (file) await uploadAndTranscribeAudio(file);
    });
  }

  document.addEventListener("allAudioEnded", () => {
    if (state.appSettings && state.appSettings.voiceEnabled === false) return;
    if (state.currentGameState && state.currentGameState.choices && state.currentGameState.choices.length > 0) {
      triggerAutoVoiceListening();
    }
  });
}

export function triggerAutoVoiceListening() {
  if (state.appSettings && state.appSettings.voiceEnabled === false) return;
  const choices = state.currentGameState ? state.currentGameState.choices || [] : [];
  if (choices.length === 0) return;

  updateVoiceUI(true, "🎙️ Escuchando respuesta por voz...");

  startAutoListening({
    onSpeechStart: () => {
      updateVoiceUI(true, "🗣️ Hablando...");
    },
    onSilenceDetected: () => {
      updateVoiceUI(true, "⏳ Procesando con Whisper...");
    },
    onTranscribed: async (transcriptText) => {
      updateVoiceUI(false);
      if (!transcriptText) return;

      const toast = document.getElementById("transcription-toast");
      const textEl = document.getElementById("transcription-text");
      if (toast) toast.classList.remove("hidden");
      if (textEl) textEl.textContent = `Voz reconocida: "${transcriptText}"`;
      setTimeout(() => { if (toast) toast.classList.add("hidden"); }, 3500);

      const intent = await parseVoiceIntent(transcriptText, choices);
      if (intent.matched && intent.choice) {
        console.log(`Voice intent matched choice [${intent.choice.choice_id}] via ${intent.method}: "${transcriptText}"`);
        await submitChoice(intent.choice.choice_id, intent.choice.target_node, transcriptText);
      } else {
        await submitChoice(null, null, transcriptText);
      }
    },
    onError: (err) => {
      updateVoiceUI(false);
      console.warn("Auto-listening skipped/stopped:", err);
    }
  });
}

export async function toggleVoiceRecording() {
  if (state.isRecording) {
    stopAutoListening();
    state.isRecording = false;
    updateVoiceUI(false);
  } else {
    triggerAutoVoiceListening();
    state.isRecording = true;
  }
}

export function updateVoiceUI(recording, statusMsg = null) {
  const btn = document.getElementById("btn-voice-record");
  const status = document.getElementById("voice-status");
  const label = document.getElementById("voice-label");

  if (recording) {
    if (btn) btn.classList.add("recording");
    if (status) {
      status.classList.remove("hidden");
      if (statusMsg) status.textContent = statusMsg;
    }
    if (label) label.textContent = "Detener Grabación";
  } else {
    if (btn) btn.classList.remove("recording");
    if (status) status.classList.add("hidden");
    if (label) label.textContent = "Responder por Voz";
  }
}

export async function uploadAndTranscribeAudio(file) {
  const toast = document.getElementById("transcription-toast");
  const textEl = document.getElementById("transcription-text");
  
  if (toast) toast.classList.remove("hidden");
  if (textEl) textEl.textContent = "Procesando voz con Whisper AI...";

  const formData = new FormData();
  formData.append("file", file);

  try {
    const res = await authFetch(`${API_BASE}/api/voice/transcribe`, {
      method: "POST",
      body: formData
    });

    const data = await res.json();
    if (data.status === "success" && data.text) {
      if (textEl) textEl.textContent = `Voz reconocida: "${data.text}"`;
      setTimeout(() => { if (toast) toast.classList.add("hidden"); }, 3000);
      await submitChoice(null, null, data.text);
    } else {
      if (textEl) textEl.textContent = "No se pudo interpretar el audio.";
      setTimeout(() => { if (toast) toast.classList.add("hidden"); }, 3000);
    }
  } catch (err) {
    console.error("Transcribe error:", err);
    if (textEl) textEl.textContent = "Error de conexión al transcribir voz.";
    setTimeout(() => { if (toast) toast.classList.add("hidden"); }, 3000);
  }
}
