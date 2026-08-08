import { authFetch, API_BASE } from "../state.js";

export async function fetchAdminBooks() {
  return authFetch(`${API_BASE}/api/admin/books`);
}

export async function updateAdminBook(bookId, payload) {
  return authFetch(`${API_BASE}/api/admin/books/${encodeURIComponent(bookId)}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function deleteAdminBook(bookId, hard = false) {
  const suffix = hard ? "?hard=true" : "";
  return authFetch(`${API_BASE}/api/admin/books/${encodeURIComponent(bookId)}${suffix}`, { method: "DELETE" });
}

export async function inspectAdminBook(formData) {
  return authFetch(`${API_BASE}/api/admin/books/inspect`, { method: "POST", body: formData });
}

export async function fetchAdminNarrators() {
  return authFetch(`${API_BASE}/api/admin/narrators`);
}

export async function confirmAdminBookImport(payload) {
  return authFetch(`${API_BASE}/api/admin/books/confirm_import`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export async function uploadAdminBookCover(bookId, formData) {
  return authFetch(`${API_BASE}/api/admin/books/${encodeURIComponent(bookId)}/cover`, {
    method: "POST",
    body: formData,
  });
}

export async function regenerateBookAudios(bookId) {
  return updateAdminBook(bookId, { regenerate_audios: true });
}
