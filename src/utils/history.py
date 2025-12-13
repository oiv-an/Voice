import json
from pathlib import Path
from typing import List, Dict, Optional
from loguru import logger
from datetime import datetime

class HistoryManager:
    """
    Управляет историей распознаваний.
    Сохраняет последние N записей в JSON файл.
    Каждая запись содержит:
    - timestamp: время записи
    - raw_text: исходный текст
    - processed_text: обработанный текст
    """
    def __init__(self, base_dir: Path, max_items: int = 50):
        self.history_file = base_dir / "history.json"
        self.max_items = max_items
        self._history: List[Dict[str, str]] = self._load_history()

    def _load_history(self) -> List[Dict[str, str]]:
        if not self.history_file.exists():
            return []
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    # Миграция старого формата (список строк) в новый (список словарей)
                    migrated_data = []
                    for item in data:
                        if isinstance(item, str):
                            migrated_data.append({
                                "timestamp": "",
                                "raw_text": "",
                                "processed_text": item
                            })
                        elif isinstance(item, dict):
                            migrated_data.append(item)
                    return migrated_data
                return []
        except Exception as e:
            logger.error(f"Failed to load history: {e}")
            return []

    def _save_history(self):
        try:
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump(self._history, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def add_item(self, raw_text: str, processed_text: str):
        if not processed_text or not processed_text.strip():
            return
        
        # Убираем дубликаты, если новый текст совпадает с последним
        if self._history and self._history[0].get("processed_text") == processed_text:
            return

        entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "raw_text": raw_text.strip(),
            "processed_text": processed_text.strip()
        }

        self._history.insert(0, entry)
        
        if len(self._history) > self.max_items:
            self._history = self._history[:self.max_items]
            
        self._save_history()

    def get_items(self) -> List[Dict[str, str]]:
        return self._history

    def clear(self):
        self._history = []
        self._save_history()