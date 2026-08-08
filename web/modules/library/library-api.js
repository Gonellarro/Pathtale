import { API_BASE, authFetch, state } from "../state.js";

export async function fetchLibraryBooks() {
  const userId = state.currentUser?.user_id || 1;
  const response = await authFetch(`${API_BASE}/api/books?user_id=${userId}`);
  if (!response.ok) throw new Error("No se pudo cargar el catálogo.");
  const data = await response.json();
  return data.books || [];
}
