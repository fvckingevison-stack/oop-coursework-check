import logging
import os
import queue
import random
import threading
import time
import xml.etree.ElementTree as ET
from concurrent.futures import ProcessPoolExecutor

from catalog import make_catalog_items, make_random_item
from compute import TaskCancelled, make_chunks, run_chunks, weather_filter
from config import BENCH_RUNS, CATEGORIES, DEFAULT_FILE, DEFAULT_TEMP_MAP
from items import ClothingItem
from wardrobe import Outfit, Wardrobe, parse_wardrobe_file


class WardrobeController:
    def __init__(self, wardrobe: Wardrobe):
        self.wardrobe = wardrobe
        self.queue = queue.Queue()
        self.cancel_event = threading.Event()
        self._busy = False
        self._busy_lock = threading.Lock()
        self.weather = (DEFAULT_TEMP_MAP["Зима"], "Зима")
        self.gender = "Усі"

    @property
    def busy(self) -> bool:
        with self._busy_lock:
            return self._busy

    def _begin(self) -> bool:
        with self._busy_lock:
            if self._busy:
                return False
            self._busy = True
        self.cancel_event.clear()
        return True

    def _end(self):
        with self._busy_lock:
            self._busy = False

    def cancel(self):
        self.cancel_event.set()
        logging.info("Користувач запросив скасування фонової задачі")

    def load_or_create_default(self, path=DEFAULT_FILE) -> list:
        if not os.path.exists(path):
            self.wardrobe.add_items(make_catalog_items())
            items = self.wardrobe.snapshot_items()
            by_cat = {c: [i for i in items if i.category == c] for c in CATEGORIES}
            for k in range(1, 7):
                season, gender = ["Зима", "Весна", "Літо"][k % 3], ["Чоловіче", "Жіноче"][k % 2]
                cats_to_pick = ["Верхній одяг", "Базовий верх", "Низ", "Взуття"] if season != "Літо" else [
                    "Базовий верх", "Низ", "Взуття"]

                trio = []
                for c in cats_to_pick:
                    valid = [i for i in by_cat[c] if i.season == season and i.gender in (gender, "Унісекс")]
                    if valid:
                        trio.append(random.choice(valid))

                if len(trio) == len(cats_to_pick):
                    ids = [i.item_id for i in trio]
                    self.wardrobe.add_outfit(Outfit(f"out_{k}", f"{season}: {gender.lower()} комплект {k}", ids,
                                                    self.wardrobe.evaluate(ids, DEFAULT_TEMP_MAP[season], season)))
            self.wardrobe.save_to_json(path)
            logging.info("Створено початковий гардероб (%d речей)", len(items))
            return []
        items, outfits, errors = parse_wardrobe_file(path)
        self.wardrobe.replace_all(items, outfits)
        for e in errors:
            logging.warning("Завантаження %s: %s", path, e)
        logging.info("Завантажено %s: речей %d, комплектів %d", path, len(items), len(outfits))
        return errors

    def save_item(self, item: ClothingItem, edit: bool):
        (self.wardrobe.update_item if edit else self.wardrobe.add_item)(item)

    def delete_items(self, ids):
        for iid in ids:
            self.wardrobe.remove_item(iid)

    def save_outfit(self, outfit: Outfit, edit: bool):
        self.wardrobe.add_outfit(outfit, replace=edit)

    def delete_outfits(self, ids):
        for oid in ids:
            self.wardrobe.remove_outfit(oid)

    def rescore(self):
        self.wardrobe.rescore_all(*self.weather)
        logging.info("Перераховано оцінки комплектів (погода: %s)", self.weather)

    def add_catalog(self) -> int:
        items = make_catalog_items(existing=self.wardrobe.snapshot_items())
        if items:
            self.wardrobe.add_items(items)
        return len(items)

    def generate_test_items(self, per_category: int):
        items = [make_random_item(cat, i + 1) for cat in CATEGORIES for i in range(per_category)]
        self.wardrobe.add_items(items)

    def save_generated(self, results) -> int:
        added = 0
        for r in results:
            try:
                self.wardrobe.add_outfit(Outfit(r["id"], r["name"], r["items"], r["score"]), replace=True)
                added += 1
            except ValueError as e:
                logging.warning("Комплект %s не додано: %s", r.get("id"), e)
        return added

    def export_json(self, path):
        self.wardrobe.save_to_json(path)

    def export_best_xml(self, path, top_n=10):
        temp, season = self.weather
        rated = [(self.wardrobe.evaluate(o.item_ids, temp, season), o)
                 for o in self.wardrobe.snapshot_outfits() if not self.wardrobe.outfit_problem(o)]
        rated.sort(key=lambda x: -x[0])
        best = rated[:top_n]
        if not best:
            raise ValueError("Немає повних комплектів для експорту.")
        root = ET.Element("BestOutfits", temperature=str(temp), season=season)
        for score, o in best:
            oe = ET.SubElement(root, "Outfit", id=o.outfit_id, score=str(score))
            ET.SubElement(oe, "Name").text = o.name
            items_el = ET.SubElement(oe, "Items")
            for iid in o.item_ids:
                it = self.wardrobe.get_item(iid)
                ie = ET.SubElement(items_el, "Item", id=iid, category=it.category if it else "")
                ie.text = it.name if it else ""
        ET.indent(root)
        ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
        logging.info("Експорт XML у %s: комплектів %d (погода %s, %s)", path, len(best), temp, season)
        return len(best)

    def _groups(self, temp, season):
        dicts = [i.to_dict() for i in self.wardrobe.snapshot_items()]
        if self.gender != "Усі":
            dicts = [d for d in dicts if d.get("gender", "Унісекс") in (self.gender, "Унісекс")]

        groups = {c: weather_filter([d for d in dicts if d["category"] == c], temp, season) for c in CATEGORIES}

        for c, g in groups.items():
            if not g and not (season == "Літо" and c == "Верхній одяг"):
                raise ValueError(
                    f"Для сезону «{season}», температури {temp} °C та статі «{self.gender}» "
                    f"немає речей категорії «{c}».\n"
                    f"Додайте відповідні речі або кнопку «Додати каталог одягу».")
        return groups

    def _run_job(self, name, body):
        def job():
            try:
                body()
            except TaskCancelled:
                logging.info("Задачу «%s» скасовано", name)
                self.queue.put(("cancelled", name))
            except Exception as e:
                logging.exception("Помилка в задачі «%s»", name)
                self.queue.put(("error", f"{e}"))
            finally:
                self._end()

        threading.Thread(target=job, daemon=True, name=name).start()

    def start_import(self, path) -> bool:
        if not self._begin():
            return False

        def body():
            logging.info("Старт імпорту: %s", path)
            self.queue.put(("progress", 0.1, "Імпорт…"))
            with ProcessPoolExecutor(max_workers=1) as ex:
                try:
                    items, outfits, errors = ex.submit(parse_wardrobe_file, path).result()
                except (ValueError, FileNotFoundError) as e:
                    raise ValueError(f"Імпорт не вдався: {e}") from None
            for e in errors:
                logging.warning("Імпорт %s: %s", path, e)
            logging.info("Імпорт завершено: речей %d, комплектів %d, проблем %d", len(items), len(outfits),
                         len(errors))
            self.queue.put(("import_done", items, outfits, errors))

        self._run_job("import", body)
        return True

    def start_generation(self, max_combos, top_n, min_score) -> bool:
        if not self._begin():
            return False
        temp, season = self.weather

        def body():
            t0 = time.perf_counter()
            groups = self._groups(temp, season)
            workers = max(2, min(os.cpu_count() or 2, 8))
            logging.info("Старт підбору: %s °C, %s, стать %s, макс. %d, процесів %d",
                         temp, season, self.gender, max_combos, workers)
            chunks = make_chunks(groups, workers * 4, max_combos, top_n, min_score, temp, season)
            results, checked = run_chunks(
                "processes", chunks, workers,
                lambda f: self.queue.put(("progress", f, f"Підбір… {f:.0%}")), self.cancel_event,
                top_n=top_n, varied=True)
            stats = {"checked": checked, "time": time.perf_counter() - t0, "workers": workers,
                     "pool": {c: len(g) for c, g in groups.items()}}
            logging.info("Підбір завершено: перевірено %d, знайдено %d, %.2f с", checked, len(results),
                         stats["time"])
            self.queue.put(("gen_done", results, stats))

        self._run_job("generation", body)
        return True

    def start_benchmark(self, max_combos, workers) -> bool:
        if not self._begin():
            return False
        temp, season = self.weather

        def body():
            groups = self._groups(temp, season)
            chunks = make_chunks(groups, workers * 4, max_combos, 50, 0.6, temp, season)
            modes = [("sequential", "Послідовно (T1)"), ("threads", "ThreadPoolExecutor"),
                     ("processes", "ProcessPoolExecutor")]
            total_steps = len(modes) * BENCH_RUNS
            logging.info("Старт бенчмарку: %d комбінацій, %d воркерів, %d запусків", max_combos, workers, BENCH_RUNS)
            rows, t1, checked, step = [], None, 0, 0
            for mode, label in modes:
                times = []
                for _ in range(BENCH_RUNS):
                    self.queue.put(("progress", step / total_steps, f"Бенчмарк: {label}…"))
                    t0 = time.perf_counter()
                    _, checked = run_chunks(mode, chunks, workers, cancel=self.cancel_event)
                    times.append(time.perf_counter() - t0)
                    step += 1
                avg = sum(times) / len(times)
                t1 = t1 or avg
                n = 1 if mode == "sequential" else workers
                speedup = t1 / avg
                rows.append((label, avg, speedup, speedup / n, times))
                logging.info("Бенчмарк %s: середній %.3f с, S=%.2f, запуски=%s", label, avg, speedup,
                             [round(t, 3) for t in times])
            self.queue.put(("bench_done", rows, {"checked": checked, "workers": workers, "runs": BENCH_RUNS,
                                                 "weather": (temp, season)}))

        self._run_job("benchmark", body)
        return True