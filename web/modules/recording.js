/**
 * Voice Recording & Auto-Listening Module (recording.js)
 * Supports Voice Activity Detection (VAD) / Silence Detection,
 * WebAudio audio chime, Whisper transcription, and scalable LLM intent parsing.
 */

import { API_BASE, state } from "./state.js";

// VAD & Listening Configuration
const VOICE_THRESHOLD = 0.02;     // RMS Audio Energy threshold to detect speech
const SILENCE_DURATION_MS = 900;   // Silence duration (ms) to auto-stop recording
const MAX_RECORDING_MS = 12000;    // Maximum recording safety limit (12 seconds)

let audioCtx = null;
let analyserNode = null;
let micStream = null;
let mediaRecorder = null;
let audioChunks = [];

let isListening = false;
let hasSpoken = false;
let silenceTimer = null;
let maxTimer = null;
let vadCheckInterval = null;

/**
 * Synthesizes a pleasant audio chime ("ding!") using Web Audio API
 */
export function playChimeSound() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();

    osc.type = "sine";
    osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
    osc.frequency.exponentialRampToValueAtTime(880, ctx.currentTime + 0.1); // A5

    gain.gain.setValueAtTime(0.15, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.35);

    osc.connect(gain);
    gain.connect(ctx.destination);

    osc.start();
    osc.stop(ctx.currentTime + 0.35);
  } catch (err) {
    console.log("Audio chime playback skipped:", err);
  }
}

/**
 * Starts automatic voice listening with Voice Activity Detection (VAD)
 * @param {Object} options Configuration callbacks
 * @param {Function} options.onSpeechStart Called when user starts speaking
 * @param {Function} options.onSilenceDetected Called when silence is detected
 * @param {Function} options.onTranscribed Called with Whisper transcription result
 * @param {Function} options.onError Called on error
 */
export async function startAutoListening(options = {}) {
  if (isListening) stopAutoListening();

  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("El micrófono requiere una conexión HTTPS o localhost.");
    }

    micStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // Play chime to signal listening start
    playChimeSound();

    // Set up Web Audio API VAD Analyser
    audioCtx = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioCtx.createMediaStreamSource(micStream);
    analyserNode = audioCtx.createAnalyser();
    analyserNode.fftSize = 512;
    source.connect(analyserNode);

    // Set up MediaRecorder
    audioChunks = [];
    mediaRecorder = new MediaRecorder(micStream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) audioChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      cleanupAudioContext();

      if (audioChunks.length === 0) {
        if (options.onError) options.onError("No audio recorded.");
        return;
      }

      const audioBlob = new Blob(audioChunks, { type: "audio/webm" });
      const file = new File([audioBlob], "voice_input.webm", { type: "audio/webm" });

      try {
        const result = await uploadAndTranscribe(file);
        if (options.onTranscribed) {
          options.onTranscribed(result.text || "", result);
        }
      } catch (err) {
        if (options.onError) options.onError(err.message || "Transcription error");
      }
    };

    mediaRecorder.start();
    isListening = true;
    hasSpoken = false;

    // Monitor audio volume for speech and silence
    const dataArray = new Uint8Array(analyserNode.frequencyBinCount);

    vadCheckInterval = setInterval(() => {
      if (!isListening || !analyserNode) return;

      analyserNode.getByteTimeDomainData(dataArray);

      // Compute Root Mean Square (RMS) energy
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) {
        const norm = (dataArray[i] - 128) / 128;
        sum += norm * norm;
      }
      const rms = Math.sqrt(sum / dataArray.length);

      if (rms > VOICE_THRESHOLD) {
        if (!hasSpoken) {
          hasSpoken = true;
          if (options.onSpeechStart) options.onSpeechStart();
        }
        // Reset silence timer while user is actively speaking
        if (silenceTimer) {
          clearTimeout(silenceTimer);
          silenceTimer = null;
        }
      } else if (hasSpoken && !silenceTimer) {
        // User finished speaking -> Start silence timer
        silenceTimer = setTimeout(() => {
          if (options.onSilenceDetected) options.onSilenceDetected();
          stopAutoListening();
        }, SILENCE_DURATION_MS);
      }
    }, 50);

    // Maximum safety timer to prevent endless recording
    maxTimer = setTimeout(() => {
      if (isListening) {
        stopAutoListening();
      }
    }, MAX_RECORDING_MS);

  } catch (err) {
    console.warn("Could not start auto-listening:", err);
    cleanupAudioContext();
    if (options.onError) options.onError(err.message || "Microphone error");
  }
}

/**
 * Stops auto-listening and finishes current recording cycle
 */
export function stopAutoListening() {
  isListening = false;
  hasSpoken = false;

  if (vadCheckInterval) {
    clearInterval(vadCheckInterval);
    vadCheckInterval = null;
  }
  if (silenceTimer) {
    clearTimeout(silenceTimer);
    silenceTimer = null;
  }
  if (maxTimer) {
    clearTimeout(maxTimer);
    maxTimer = null;
  }

  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
  }
}

/**
 * Cleans up WebAudio and stream tracks
 */
function cleanupAudioContext() {
  if (micStream) {
    micStream.getTracks().forEach(t => t.stop());
    micStream = null;
  }
  if (audioCtx && audioCtx.state !== "closed") {
    audioCtx.close().catch(() => {});
    audioCtx = null;
  }
  analyserNode = null;
}

/**
 * Uploads recorded audio file to backend Whisper endpoint
 * @param {File} file Audio file
 * @returns {Promise<{status: string, text: string}>}
 */
export async function uploadAndTranscribe(file) {
  const formData = new FormData();
  formData.append("file", file);

  const headers = {};
  if (state.authToken) {
    headers["Authorization"] = `Bearer ${state.authToken}`;
  }

  const res = await fetch(`${API_BASE}/api/voice/transcribe`, {
    method: "POST",
    headers,
    body: formData
  });

  const data = await res.json();
  if (!res.ok || data.status !== "success") {
    throw new Error(data.detail || "Error al transcribir audio");
  }
  return data;
}

/**
 * Extensible Voice Intent Parser
 * Parses transcript text and matches against available choices.
 * Designed to seamlessly route to LLM backend (/api/voice/intent) in the future.
 * 
 * @param {string} transcript Transcribed text from Whisper
 * @param {Array<{choice_id: number, text: string, target_node: string}>} choices Available node choices
 * @param {Object} options Optional LLM override options
 * @returns {Promise<{matched: boolean, choice: Object|null, confidence: number, method: string}>}
 */
export async function parseVoiceIntent(transcript, choices = [], options = {}) {
  const text = (transcript || "").trim().toLowerCase();
  if (!text || !choices || choices.length === 0) {
    return { matched: false, choice: null, confidence: 0, method: "none" };
  }

  // Optional Future LLM Route hook
  if (options.useLLM && options.llmEndpoint) {
    try {
      const res = await fetch(`${API_BASE}${options.llmEndpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ transcript: text, choices })
      });
      const data = await res.json();
      if (data.matched_choice_id) {
        const choice = choices.find(c => String(c.choice_id) === String(data.matched_choice_id));
        if (choice) {
          return { matched: true, choice, confidence: data.confidence || 0.95, method: "llm" };
        }
      }
    } catch (err) {
      console.warn("LLM intent parsing fallback to local matcher:", err);
    }
  }

  // 1. Exact or Word Number Matching ("1", "opcion 1", "uno", "primera")
  const numberWordsMap = {
    "uno": 1, "primera": 1, "primero": 1, "1": 1,
    "dos": 2, "segunda": 2, "segundo": 2, "2": 2,
    "tres": 3, "tercera": 3, "tercero": 3, "3": 3,
    "cuatro": 4, "cuarta": 4, "cuarto": 4, "4": 4,
    "cinco": 5, "quinta": 5, "quinto": 5, "5": 5
  };

  for (const [word, num] of Object.entries(numberWordsMap)) {
    if (text.includes(word)) {
      const choice = choices.find(c => Number(c.choice_id) === num);
      if (choice) {
        return { matched: true, choice, confidence: 0.9, method: "number_keyword" };
      }
    }
  }

  // 2. Fuzzy Text Keyword Matching
  for (const choice of choices) {
    const choiceText = (choice.text || "").toLowerCase();
    const words = choiceText.split(/\s+/).filter(w => w.length > 3);
    
    // Check if key words of the choice appear in transcript
    let matchCount = 0;
    for (const word of words) {
      if (text.includes(word)) matchCount++;
    }

    if (words.length > 0 && matchCount / words.length >= 0.4) {
      return { matched: true, choice, confidence: 0.8, method: "fuzzy_keywords" };
    }
  }

  return { matched: false, choice: null, confidence: 0, method: "unmatched" };
}
