import { updateAdminBook, confirmAdminBookImport, uploadAdminBookCover } from "./books-api.js";

async function readResponse(response, fallbackMessage) {
  const contentType = response.headers.get("content-type") || "";
  const data = contentType.includes("application/json") ? await response.json() : {};
  if (!response.ok) {
    if (response.status === 401 || response.status === 403) {
      throw new Error("Sesión expirada o sin permisos de administración. Vuelve a iniciar sesión.");
    }
    throw new Error(data.detail || fallbackMessage);
  }
  return data;
}

export async function submitBookEdit(config) {
  const data = await readResponse(await updateAdminBook(config.editBookId, {
    title: config.title,
    author: config.author,
    language: config.language,
    start_node: config.startNode,
    narrator_id: config.narratorId,
    tier_id: config.tierId,
    regenerate_audios: config.regenCheck,
  }), "Error al actualizar libro.");
  if (config.coverFile) {
    const formData = new FormData();
    formData.append("file", config.coverFile);
    await readResponse(await uploadAdminBookCover(config.editBookId, formData), "Error al subir portada.");
  }
  return data;
}

export async function submitBookImport(config) {
  const data = await readResponse(await confirmAdminBookImport({
    temp_file_id: config.tempFileId,
    title: config.title,
    author: config.author,
    language: config.language,
    narrator_id: config.narratorId,
    start_node: config.startNode,
    tier_id: config.tierId,
    generate_audios: config.generateAudios,
  }), "Error al importar libro.");
  if (data.book_id && config.coverFile) {
    const formData = new FormData();
    formData.append("file", config.coverFile);
    await readResponse(await uploadAdminBookCover(data.book_id, formData), "Error al subir portada.");
  }
  return data;
}
