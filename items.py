"""Модель: речі гардеробу (ООП: абстракція, успадкування, поліморфізм, інкапсуляція)."""
from abc import ABC, abstractmethod

from config import GENDERS, SEASONS


class ClothingItem(ABC):
    CATEGORY = ""

    def __init__(self, item_id, name, color, season, temp_min, temp_max, image="", gender="Унісекс"):
        self.item_id = str(item_id)
        self._name = ""
        self._color = ""
        self._temp_min = 0
        self._temp_max = 0
        self.name = name
        self.color = color
        self.season = season
        self.gender = gender
        self.image = str(image or "")
        self.temp_min = temp_min
        self.temp_max = temp_max
        self.validate()

    @property
    def name(self) -> str:
        return self._name

    @name.setter
    def name(self, value):
        value = str(value).strip()
        if not value:
            raise ValueError("Назва та колір є обов'язковими полями.")
        self._name = value

    @property
    def color(self) -> str:
        return self._color

    @color.setter
    def color(self, value):
        value = str(value).strip()
        if not value:
            raise ValueError("Назва та колір є обов'язковими полями.")
        self._color = value

    @property
    def temp_min(self) -> int:
        return self._temp_min

    @temp_min.setter
    def temp_min(self, value):
        self._temp_min = self._to_temp(value)

    @property
    def temp_max(self) -> int:
        return self._temp_max

    @temp_max.setter
    def temp_max(self, value):
        self._temp_max = self._to_temp(value)

    @staticmethod
    def _to_temp(value) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            raise ValueError("Температури мають бути цілими числами.") from None

    @property
    def category(self) -> str:
        return self.CATEGORY

    @abstractmethod
    def is_allowed_in(self, season: str) -> bool:
        pass

    def validate(self):
        if self.gender not in GENDERS:
            raise ValueError(f"Невідома стать: {self.gender!r}.")
        if self.season not in SEASONS:
            raise ValueError(f"Невідомий сезон: {self.season!r}.")
        if self.temp_min > self.temp_max:
            raise ValueError(f"'{self.name}': мінімальна температура вища за максимальну.")

    def to_dict(self) -> dict:
        return {"id": self.item_id, "name": self.name, "category": self.category, "color": self.color,
                "season": self.season, "temp_min": self.temp_min, "temp_max": self.temp_max,
                "image": self.image, "gender": self.gender}


class Top(ClothingItem):
    pass


class BaseTop(Top):
    CATEGORY = "Базовий верх"
    LIGHT_KEYWORDS = ("футболка", "майка", "кроп-топ", "топ")

    def is_allowed_in(self, season: str) -> bool:
        if season == "Зима":
            return not any(k in self.name.lower() for k in self.LIGHT_KEYWORDS)
        return True


class Outerwear(Top):
    CATEGORY = "Верхній одяг"

    def is_allowed_in(self, season: str) -> bool:
        return True


class Bottom(ClothingItem):
    CATEGORY = "Низ"

    def is_allowed_in(self, season: str) -> bool:
        return True


class Footwear(ClothingItem):
    CATEGORY = "Взуття"

    def is_allowed_in(self, season: str) -> bool:
        return True


ITEM_CLASSES = {"Базовий верх": BaseTop, "Верхній одяг": Outerwear, "Низ": Bottom, "Взуття": Footwear}


def create_item(category, item_id, name, color, season, temp_min, temp_max, image="", gender="Унісекс") -> ClothingItem:
    cls = ITEM_CLASSES.get(category)
    if cls is None:
        raise ValueError(f"Невідома категорія: {category!r}")
    return cls(item_id, name, color, season, temp_min, temp_max, image, gender)