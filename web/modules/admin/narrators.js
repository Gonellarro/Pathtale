import { authFetch, escapeHtml, API_BASE } from "../state.js";

export async function loadAdminNarrators() {
  const container = document.getElementById("admin-narrators-grid");
  const countLbl = document.getElementById("admin-narrators-count");
  if (!container) return;

  try {
    const res = await authFetch(`${API_BASE}/api/admin/narrators`);
    const data = await res.json();
    const narrators = data.narrators || [];

    if (countLbl) countLbl.textContent = `Total: ${narrators.length} narrador${narrators.length === 1 ? '' : 's'}`;

    container.innerHTML = narrators.map(n => {
      const isGoogle = (n.engine_code || '').toLowerCase() === 'google';
      const engineBadge = isGoogle 
        ? `<span class="badge" style="background:rgba(59, 130, 246, 0.15); color:#60a5fa; border:1px solid rgba(59, 130, 246, 0.3);">⚡ Google Cloud</span>`
        : `<span class="badge" style="background:rgba(16, 185, 129, 0.15); color:#34d399; border:1px solid rgba(16, 185, 129, 0.3);">🎙️ Piper ONNX</span>`;

      const langFlag = (n.language && n.language.toLowerCase().startsWith("en")) ? "🇬🇧 EN" : "🇪🇸 ES";
      const hasDownloadUrl = Boolean(n.download_url);

      return `
        <div class="narrator-card">
          <img src="${n.avatar_url || '/assets/narrator_davefx.jpg'}" alt="${escapeHtml(n.name)}" class="narrator-avatar">
          <div class="narrator-info">
            <h3 class="narrator-name">${escapeHtml(n.display_name || n.name)}</h3>
            <p class="narrator-specialty">${escapeHtml(n.specialty || '-')}</p>
            <div style="display:flex; gap:0.4rem; margin-top:0.3rem; font-size:0.75rem; flex-wrap:wrap;">
              ${engineBadge}
              <span class="badge" style="background:rgba(255, 255, 255, 0.08); color:var(--text-primary);">${langFlag}</span>
            </div>
            <p class="narrator-stories-count" style="margin-top:0.4rem;">
              <span>🎧 ${n.book_count || n.story_count || 0} libros</span>
            </p>
          </div>
          <div style="display:flex; flex-direction:column; gap:0.3rem; align-items:flex-end;">
            ${hasDownloadUrl ? `
              <button class="btn-secondary btn-sm btn-download-model" data-id="${n.narrator_id}" title="Descargar modelo ONNX a disco">⬇️ Model</button>
            ` : ''}
            <button class="btn-secondary btn-sm btn-delete-narrator" data-id="${n.narrator_id}" style="color:#ff6b6b">🗑️</button>
          </div>
        </div>
      `;
    }).join("");

    container.querySelectorAll(".btn-delete-narrator").forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const nid = btn.getAttribute("data-id");
        if (confirm(`¿Eliminar narrador ID #${nid}?`)) {
          deleteNarrator(nid);
        }
      };
    });

    container.querySelectorAll(".btn-download-model").forEach(btn => {
      btn.onclick = (e) => {
        e.stopPropagation();
        const nid = btn.getAttribute("data-id");
        downloadNarratorModel(nid);
      };
    });

    const btnAdd = document.getElementById("btn-admin-add-narrator");
    if (btnAdd) {
      btnAdd.onclick = () => promptCreateNarrator();
    }
  } catch (err) {
    console.error("Error loading admin narrators:", err);
  }
}

async function promptCreateNarrator() {
  const name = prompt("Identificador técnico (ej: google_carmen u ONNX davefx):");
  if (!name) return;
  const displayName = prompt("Nombre visible (ej: CARMEN DELGADO):") || name.toUpperCase();
  const engineType = prompt("Motor TTS (Escribe '1' para Piper Local ONNX, o '2' para Google Cloud):", "1");
  const engineId = engineType === "2" ? 2 : 1;
  const voiceCode = prompt(
    engineId === 2 
      ? "Código de voz de Google Cloud (ej: es-ES-Neural2-A):" 
      : "Nombre de archivo del modelo ONNX (ej: es_ES-davefx-medium.onnx):", 
    engineId === 2 ? "es-ES-Neural2-A" : "es_ES-davefx-medium.onnx"
  );
  if (!voiceCode) return;

  const language = prompt("Idioma ('es' o 'en'):", "es") || "es";
  const specialty = prompt("Especialidad (ej: Español · Drama):") || "Español · General";
  const downloadUrl = engineId === 1 ? prompt("URL de descarga de HuggingFace (opcional para Piper):") : null;

  try {
    const res = await authFetch(`${API_BASE}/api/admin/narrators`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        name,
        display_name: displayName,
        engine_id: engineId,
        voice_code: voiceCode,
        language: language,
        specialty: specialty,
        download_url: downloadUrl || null,
        avatar_url: "/assets/narrator_davefx.jpg"
      })
    });
    if (res.ok) loadAdminNarrators();
    else {
      const err = await res.json();
      alert(`Error al crear narrador: ${err.detail || 'Operación fallida'}`);
    }
  } catch (err) {
    alert("Error al crear narrador.");
  }
}

async function downloadNarratorModel(narratorId) {
  try {
    alert("⏳ Descargando modelo ONNX en segundo plano... Por favor espera unos segundos.");
    const res = await authFetch(`${API_BASE}/api/admin/narrators/${narratorId}/download`, { method: "POST" });
    const data = await res.json();
    if (res.ok) {
      alert(`✅ ¡Éxito! ${data.message}`);
    } else {
      alert(`❌ ${data.detail}`);
    }
  } catch (err) {
    alert("Error al descargar modelo del narrador.");
  }
}

async function deleteNarrator(narratorId) {
  try {
    const res = await authFetch(`${API_BASE}/api/admin/narrators/${narratorId}`, { method: "DELETE" });
    const data = await res.json();
    if (res.ok) {
      loadAdminNarrators();
    } else {
      alert(`❌ ${data.detail}`);
    }
  } catch (err) {
    alert("Error al eliminar narrador.");
  }
}
