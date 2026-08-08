import { regenerateBookAudios, updateAdminBook } from "./books-api.js";

let eventsBound = false;

export function openPostUploadModal(book, onUpdated = () => {}) {
  const modal = document.getElementById("modal-post-upload");
  if (!modal) return;
  document.getElementById("post-upload-book-id").value = book.book_id || "";
  document.getElementById("post-upload-title").value = book.title || "";
  document.getElementById("post-upload-author").value = book.author || "";
  document.getElementById("post-upload-language").value = book.language || "es";
  document.getElementById("post-upload-start-node").value = book.start_node || "sec_001";
  document.getElementById("post-upload-narrator").value = book.narrator_id || "1";
  document.getElementById("post-upload-tier").value = book.tier_id || "1";
  bindEvents(onUpdated);
  modal.classList.add("open");
}

function bindEvents(onUpdated) {
  if (eventsBound) return;
  eventsBound = true;
  const modal = document.getElementById("modal-post-upload");
  const close = () => modal.classList.remove("open");
  document.getElementById("btn-close-modal-post-upload")?.addEventListener("click", close);
  document.getElementById("btn-cancel-post-upload")?.addEventListener("click", async () => {
    await savePostUploadMetadata(false, onUpdated);
    close();
  });
  document.getElementById("form-post-upload")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    await savePostUploadMetadata(true, onUpdated);
    close();
  });
}

async function savePostUploadMetadata(synthesizeAudios, onUpdated) {
  const bookId = document.getElementById("post-upload-book-id").value;
  const title = document.getElementById("post-upload-title").value.trim();
  const errorBox = document.getElementById("post-upload-error");
  const payload = {
    title,
    author: document.getElementById("post-upload-author").value.trim(),
    language: document.getElementById("post-upload-language").value,
    start_node: document.getElementById("post-upload-start-node").value.trim(),
    narrator_id: parseInt(document.getElementById("post-upload-narrator").value, 10),
    tier_id: parseInt(document.getElementById("post-upload-tier").value, 10),
  };
  try {
    const response = await updateAdminBook(bookId, payload);
    if (!response.ok) throw new Error("Error al guardar cambios de metadatos.");
    if (synthesizeAudios) {
      alert(`🎙️ Iniciando sintetización de audios para '${title}' (${payload.language})...`);
      await regenerateBookAudios(bookId);
    } else {
      alert("✅ Metadatos guardados correctamente.");
    }
    await onUpdated();
  } catch (error) {
    if (errorBox) {
      errorBox.classList.remove("hidden");
      errorBox.textContent = error.message;
    }
    throw error;
  }
}
