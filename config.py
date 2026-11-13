import logging
import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "wardrobe.log")
logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    encoding="utf-8",
)

DEFAULT_FILE = os.path.join(BASE_DIR, "wardrobe.json")
PHOTO_DIR = os.path.join(BASE_DIR, "photos")

SEASONS = ["Зима", "Весна", "Літо", "Осінь"]
GENDERS = ["Чоловіче", "Жіноче", "Унісекс"]

CATEGORIES = ["Верхній одяг", "Базовий верх", "Низ", "Взуття"]
COLORS = ["Чорний", "Білий", "Сірий", "Бежевий", "Синій", "Блакитний", "Червоний", "Бордовий", "Зелений",
          "Жовтий", "Помаранчевий", "Рожевий", "Фіолетовий", "Коричневий"]
ALL_CAT, ALL_SEASON, ALL_COLOR, ALL_GENDER = "Усі категорії", "Усі сезони", "Усі кольори", "Будь-яка стать"
TEMP_LIMITS = (-60, 60)

SEASON_RANGES = {"Зима": (-30, 5), "Весна": (5, 20), "Літо": (18, 45), "Осінь": (0, 18)}
DEFAULT_TEMP_MAP = {"Зима": -5, "Весна": 15, "Літо": 28, "Осінь": 10}
BENCH_RUNS = 3

SEASON_ICON = {"Зима": "❄️", "Весна": "🌸", "Літо": "☀️", "Осінь": "🍂"}
SEL_COLOR = "#1f6aa5"
RED, RED_H = "#c0392b", "#992d22"
GREEN, GREEN_H = "#2e8b57", "#256f46"