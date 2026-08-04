import re
from typing import Any, Dict, Optional


class GameNavigationResolver:
    """Resolves section IDs from direct IDs or displayed section numbers."""

    @staticmethod
    def resolve(nodes: Dict[str, Dict[str, Any]], target: str) -> Optional[str]:
        target_str = str(target).strip()
        if target_str in nodes:
            return target_str
        numbers = re.findall(r"\d+", target_str)
        if not numbers:
            return None
        number = int(numbers[0])
        for node_id, node in nodes.items():
            if node.get("display_number") == number:
                return node_id
        for candidate in (f"sec_{number:03d}", f"sec_{number}"):
            if candidate in nodes:
                return candidate
        return None
