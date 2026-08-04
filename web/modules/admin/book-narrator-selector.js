import { escapeHtml } from "../state.js";
import { fetchAdminNarrators } from "./books-api.js";

export async function populateBookNarrators(select, language, selectedNarratorId = null) {
  if (!select) return;
  try {
    const response = await fetchAdminNarrators();
    const data = await response.json();
    const narrators = data.narrators || [];
    const filtered = narrators.filter((narrator) => (
      !narrator.language || narrator.language.toLowerCase().startsWith(language.toLowerCase())
    ));
    const options = filtered.length ? filtered : narrators;
    select.innerHTML = options.map((narrator) => {
      const engineTag = narrator.engine_name || (narrator.engine_code ? narrator.engine_code.toUpperCase() : "TTS");
      return `<option value="${narrator.narrator_id}" data-narrator-id="${narrator.narrator_id}">${escapeHtml(narrator.display_name)} (${engineTag})</option>`;
    }).join("");
    if (selectedNarratorId !== null) {
      const selected = Array.from(select.options).find((option) => (
        option.getAttribute("data-narrator-id") == selectedNarratorId
      ));
      if (selected) selected.selected = true;
    }
  } catch (error) {
    console.warn("Could not fetch DB narrators for dropdown:", error);
  }
}
