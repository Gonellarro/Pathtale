import re
import json
import logging
import requests
from typing import List, Dict, Any, Optional
from rapidfuzz import fuzz, process
from config import LLM_API_URL, LLM_MODEL_NAME, USE_LLM_FALLBACK

logger = logging.getLogger("VoiceParser")

# Spanish word to digit mapping
SPANISH_NUMBERS = {
    "uno": 1, "una": 1, "un": 1, "primero": 1, "primera": 1, "1º": 1, "1a": 1,
    "dos": 2, "segundo": 2, "segunda": 2, "2º": 2, "2a": 2,
    "tres": 3, "tercero": 3, "tercera": 3, "3º": 3, "3a": 3,
    "cuatro": 4, "cuarto": 4, "cuarta": 4, "4º": 4, "4a": 4,
    "cinco": 5, "quinto": 5, "quinta": 5,
    "seis": 6, "sexto": 6, "sexta": 6,
    "siete": 7, "séptimo": 7, "séptima": 7,
    "ocho": 8, "octavo": 8, "octava": 8,
    "nueve": 9, "noveno": 9, "novena": 9,
    "diez": 10, "décimo": 10, "décima": 10,
    "quince": 15, "diecisiete": 17, "veintidós": 22, "veintitres": 23,
    "cuarenta y cinco": 45, "cuarenta y seis": 46, "cuarenta y nueve": 49
}

class VoiceParser:
    def parse_intent(self, user_text: str, choices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        """
        Parses user text/voice input against current available choices.
        Returns the chosen choice dict, or None if match failed/ambiguous.
        """
        if not user_text or not choices:
            return None

        clean_input = user_text.lower().strip()
        logger.info(f"Parsing intent for input: '{clean_input}' with {len(choices)} choices")

        # Layer 1: Direct number / digit matching
        matched_choice = self._layer1_number_matching(clean_input, choices)
        if matched_choice:
            logger.info(f"Layer 1 matched choice #{matched_choice['choice_id']}")
            return matched_choice

        # Layer 2: Fuzzy String Matching on option text
        matched_choice = self._layer2_fuzzy_matching(clean_input, choices)
        if matched_choice:
            logger.info(f"Layer 2 fuzzy matched choice #{matched_choice['choice_id']}")
            return matched_choice

        # Layer 3: Optional LLM Semantic Router (Ollama / Local LLM)
        if USE_LLM_FALLBACK:
            matched_choice = self._layer3_llm_matching(clean_input, choices)
            if matched_choice:
                logger.info(f"Layer 3 LLM matched choice #{matched_choice['choice_id']}")
                return matched_choice

        logger.warning(f"Could not parse intent for input: '{user_text}'")
        return None

    def _layer1_number_matching(self, text: str, choices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        # Check for literal digits
        digits = re.findall(r'\b\d+\b', text)
        if digits:
            num = int(digits[0])

            # Check if num matches choice_id (1, 2, 3...)
            for choice in choices:
                if choice.get("choice_id") == num:
                    return choice

            # Check if num matches target_display_number (e.g. page 15 or page 17)
            for choice in choices:
                if choice.get("target_display_number") == num:
                    return choice

        # Check for spanish number words
        for word, val in SPANISH_NUMBERS.items():
            if re.search(r'\b' + re.escape(word) + r'\b', text):
                # Try matching index
                for choice in choices:
                    if choice.get("choice_id") == val:
                        return choice
                # Try matching page number
                for choice in choices:
                    if choice.get("target_display_number") == val:
                        return choice

        return None

    def _layer2_fuzzy_matching(self, text: str, choices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        best_choice = None
        highest_score = 0.0

        for choice in choices:
            choice_text = choice.get("text", "").lower()
            # Calculate fuzzy ratio
            score = fuzz.token_set_ratio(text, choice_text)
            if score > highest_score:
                highest_score = score
                best_choice = choice

        # Threshold score (e.g. 60%)
        if highest_score >= 60.0 and best_choice:
            return best_choice

        return None

    def _layer3_llm_matching(self, text: str, choices: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        try:
            choices_formatted = "\n".join([
                f"- Opción {c['choice_id']}: \"{c['text']}\"" for c in choices
            ])
            prompt = (
                f"El usuario ha dicho: \"{text}\"\n"
                f"Las opciones disponibles son:\n{choices_formatted}\n\n"
                f"Responde únicamente con el número de la opción elegida (ejemplo: 1 o 2). "
                f"Si ninguna opción coincide, responde 0."
            )
            payload = {
                "model": LLM_MODEL_NAME,
                "prompt": prompt,
                "stream": False
            }
            resp = requests.post(LLM_API_URL, json=payload, timeout=3.0)
            if resp.status_code == 200:
                result_text = resp.json().get("response", "").strip()
                match = re.search(r'\b\d+\b', result_text)
                if match:
                    num = int(match.group(0))
                    for choice in choices:
                        if choice.get("choice_id") == num:
                            return choice
        except Exception as e:
            logger.debug(f"LLM matching skipped: {e}")
        return None
