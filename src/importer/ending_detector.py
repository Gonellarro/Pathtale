import re
from typing import Dict, Any, List

def detect_ending_nodes(nodes: Dict[str, Any], start_node_id: str) -> List[Dict[str, str]]:
    """Analyzes narrative nodes to identify story ending nodes (FIN keyword, zero choices, restart links)."""
    endings_detected = []
    for n_id, n_data in nodes.items():
        text_upper = (n_data.get("text") or "").upper()
        title_upper = (n_data.get("title") or "").upper()
        n_choices = n_data.get("choices") or []

        has_fin_keyword = bool(re.search(r'\b(FIN|EL FIN|FIN DE LA AVENTURA)\b', text_upper) or re.search(r'\b(FIN|EL FIN)\b', title_upper))
        has_zero_choices = len(n_choices) == 0
        has_restart_choice = False

        if len(n_choices) == 1:
            target = n_choices[0].get("target_node")
            c_text = (n_choices[0].get("text") or "").lower()
            if target in (start_node_id, "sec_001", "sec001") and any(kw in c_text for kw in ("retorna", "principio", "volver", "inicio", "reiniciar", "comenzar")):
                has_restart_choice = True

        if has_fin_keyword or has_zero_choices or has_restart_choice:
            label = "Final de la aventura"
            if "VICTORIA" in text_upper or "CONSIGUES" in text_upper or "VICTORIOSO" in text_upper:
                label = "Final Victorioso"
            elif "MUERTE" in text_upper or "CAES" in text_upper or "PERDISTE" in text_upper or "TRÁGICO" in text_upper:
                label = "Final Trágico"

            endings_detected.append({
                "node_id": n_id,
                "label": label
            })
    return endings_detected
