import json
import logging
import os
import threading

from items import ClothingItem, create_item
from rules import evaluate_items


class Outfit:
    def __init__(self, outfit_id, name, item_ids, score=0.0):
        self.outfit_id = str(outfit_id)
        self.name = str(name).strip()
        self.item_ids = list(item_ids)
        self.score = float(score)

    def to_dict(self):
        return {"id": self.outfit_id, "name": self.name, "items": self.item_ids, "score": self.score}


class Wardrobe:
    def __init__(self):
        self._items: dict[str, ClothingItem] = {}
        self._outfits: dict[str, Outfit] = {}
        self.lock = threading.Lock()

    def add_item(self, item: ClothingItem):
        with self.lock:
            if item.item_id in self._items:
                raise ValueError(f"Річ {item.item_id} уже існує.")
            self._items[item.item_id] = item
        logging.info("Додано річ: %s (%s)", item.name, item.item_id)

    def add_items(self, items):
        with self.lock:
            for it in items:
                self._items[it.item_id] = it
        logging.info("Додано речей пакетом: %d", len(items))

    def update_item(self, item: ClothingItem):
        with self.lock:
            if item.item_id not in self._items:
                raise KeyError(f"Річ {item.item_id} не знайдено.")
            self._items[item.item_id] = item
        logging.info("Змінено річ: %s (%s)", item.name, item.item_id)

    def remove_item(self, item_id: str):
        with self.lock:
            if self._items.pop(item_id, None) is None:
                return
            for o in self._outfits.values():
                if item_id in o.item_ids:
                    o.item_ids.remove(item_id)
                    logging.warning("З комплекту %s вилучено видалену річ %s", o.outfit_id, item_id)
        logging.info("Видалено річ: %s", item_id)

    def get_item(self, item_id):
        with self.lock:
            return self._items.get(item_id)

    def snapshot_items(self) -> list:
        with self.lock:
            return list(self._items.values())

    def search_items(self, query="", category=None, season=None, color=None, gender=None) -> list:
        q = query.strip().lower()
        with self.lock:
            return [i for i in self._items.values()
                    if (not q or q in i.name.lower())
                    and (not category or i.category == category)
                    and (not season or i.season == season)
                    and (not color or i.color.lower() == color.lower())
                    and (not gender or i.gender == gender)]

    def _problem(self, outfit: Outfit):
        cats = sorted([self._items[i].category for i in outfit.item_ids if i in self._items])
        req_summer = sorted(["Базовий верх", "Низ", "Взуття"])
        req_other = sorted(["Верхній одяг", "Базовий верх", "Низ", "Взуття"])
        if len(cats) != len(outfit.item_ids):
            return "у комплекті є річ, якої немає в гардеробі"
        if cats not in (req_summer, req_other):
            return "неправильна структура (потрібен Базовий верх, Низ, Взуття + опціонально Верхній одяг)"
        return None

    def outfit_problem(self, outfit: Outfit):
        with self.lock:
            return self._problem(outfit)

    def add_outfit(self, outfit: Outfit, replace=False):
        with self.lock:
            if not outfit.name:
                raise ValueError("Назва комплекту обов'язкова.")
            if outfit.outfit_id in self._outfits and not replace:
                raise ValueError("Комплект уже існує.")
            problem = self._problem(outfit)
            if problem:
                raise ValueError(f"Комплект '{outfit.name}': {problem}.")
            self._outfits[outfit.outfit_id] = outfit
        logging.info("Збережено комплект: %s (%s)", outfit.name, outfit.outfit_id)

    def remove_outfit(self, outfit_id: str):
        with self.lock:
            self._outfits.pop(outfit_id, None)
        logging.info("Видалено комплект: %s", outfit_id)

    def snapshot_outfits(self) -> list:
        with self.lock:
            return list(self._outfits.values())

    def evaluate(self, item_ids, temp, season) -> float:
        with self.lock:
            return self._evaluate_ids(item_ids, temp, season)

    def _evaluate_ids(self, ids, temp, season):
        objs = [self._items[i] for i in ids if i in self._items]
        if not objs or len(objs) != len(ids):
            return 0.0
        return round(evaluate_items(objs, temp, season), 2)

    def rescore_all(self, temp, season):
        with self.lock:
            for o in self._outfits.values():
                o.score = self._evaluate_ids(o.item_ids, temp, season)

    def save_to_json(self, filepath: str):
        with self.lock:
            data = {"items": [i.to_dict() for i in self._items.values()],
                    "outfits": [o.to_dict() for o in self._outfits.values()]}
        tmp = filepath + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        os.replace(tmp, filepath)
        logging.info("Гардероб збережено у %s (речей: %d)", filepath, len(data["items"]))

    def replace_all(self, items, outfits):
        with self.lock:
            self._items = {i.item_id: i for i in items}
            self._outfits = {o.outfit_id: o for o in outfits}


def parse_wardrobe_file(path: str):
    if not os.path.exists(path):
        raise FileNotFoundError(f"Файл {path} не знайдено.")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception as e:
        raise ValueError(f"Пошкоджений JSON-файл: {e}") from None
    if not isinstance(data, dict) or not isinstance(data.get("items", []), list) \
            or not isinstance(data.get("outfits", []), list):
        raise ValueError("Пошкоджений JSON-файл: очікується об'єкт зі списками «items» і «outfits».")

    errors, items, outfits = [], {}, []
    for raw in data.get("items", []):
        try:
            category = raw.get("category")
            season = raw.get("season", "Весна")
            name = raw.get("name", "").lower()

            if category == "Верх":
                if any(x in name for x in
                       ["куртка", "светр", "худі", "пальто", "бомбер", "пуховик", "світшот", "кардиган"]):
                    category = "Верхній одяг"
                else:
                    category = "Базовий верх"

            if season in ["Всесезон", "Демісезон"]:
                if "футболка" in name or "шорти" in name or "майка" in name:
                    season = "Літо"
                else:
                    season = "Весна"

            obj = create_item(category, raw["id"], raw["name"], raw["color"],
                              season, raw["temp_min"], raw["temp_max"], raw.get("image", ""),
                              raw.get("gender", "Унісекс"))
            items[obj.item_id] = obj
        except Exception as e:
            rid = raw.get("id", "?") if isinstance(raw, dict) else "?"
            reason = f"відсутнє поле {e}" if isinstance(e, KeyError) else str(e)
            errors.append(f"Річ {rid}: {reason}")

    for raw in data.get("outfits", []):
        try:
            ids = list(raw["items"])
            valid = [i for i in ids if i in items]
            missing = [i for i in ids if i not in items]
            if missing:
                errors.append(f"Комплект {raw.get('id', '?')}: відсутні речі {missing} – комплект позначено неповним.")
            outfits.append(Outfit(raw["id"], raw["name"], valid, raw.get("score", 0.0)))
        except Exception as e:
            rid = raw.get("id", "?") if isinstance(raw, dict) else "?"
            reason = f"відсутнє поле {e}" if isinstance(e, KeyError) else str(e)
            errors.append(f"Комплект {rid}: {reason}")

    return list(items.values()), outfits, errors