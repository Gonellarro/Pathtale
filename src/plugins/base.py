from typing import Dict, Any, List

class BasePlugin:
    def name(self) -> str:
        return "base_plugin"

    def on_node_enter(self, user_id: int, node_data: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Hook called when entering a node. Can modify state or node display."""
        return state

    def evaluate_choices(self, user_id: int, choices: List[Dict[str, Any]], state: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Hook called to filter or alter available choices based on inventory/stats."""
        return choices

    def on_choice_made(self, user_id: int, chosen: Dict[str, Any], state: Dict[str, Any]) -> Dict[str, Any]:
        """Hook called when a choice is selected."""
        return state
