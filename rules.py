from abc import ABC, abstractmethod


class CompatibilityRule(ABC):
    @abstractmethod
    def score(self, items, weather_temp: int, weather_season: str) -> float:
        pass


class SeasonRule(CompatibilityRule):
    def score(self, items, weather_temp, weather_season):
        ok = sum(1 for i in items if i.season == weather_season)
        return 1.0 if ok == len(items) else 0.4


class TemperatureRule(CompatibilityRule):
    def score(self, items, weather_temp, weather_season):
        return 1.0 if all(i.temp_min <= weather_temp <= i.temp_max for i in items) else 0.2


class ColorRule(CompatibilityRule):
    NEUTRAL = {"чорний", "білий", "сірий", "бежевий"}

    def score(self, items, weather_temp, weather_season):
        colors = [i.color.lower() for i in items]
        if len(set(colors)) == 1:
            return 0.8
        if any(c in self.NEUTRAL for c in colors):
            return 1.0
        return 0.6


class GenderRule(CompatibilityRule):
    def score(self, items, weather_temp, weather_season):
        genders = {i.gender for i in items if i.gender != "Унісекс"}
        return 0.0 if len(genders) > 1 else 1.0


class LayeringRule(CompatibilityRule):
    def score(self, items, weather_temp, weather_season):
        return 0.0 if any(not i.is_allowed_in(weather_season) for i in items) else 1.0


RULES = [SeasonRule(), TemperatureRule(), ColorRule(), GenderRule(), LayeringRule()]


def evaluate_items(items, temp, season) -> float:
    scores = [r.score(items, temp, season) for r in RULES]
    if 0.0 in scores:
        return 0.0
    return sum(scores) / len(RULES)