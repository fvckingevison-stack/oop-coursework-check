import heapq
import itertools
import random
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor, as_completed

from items import create_item
from rules import evaluate_items


class TaskCancelled(Exception):
    pass


def weather_filter(item_dicts, temp, season):
    return [d for d in item_dicts
            if d["season"] == season and d["temp_min"] <= temp <= d["temp_max"]]


def evaluate_chunk(args):
    base_tops, outer_tops, bottoms, shoes, temp, season, max_combos, top_n, min_score = args

    def build(ds):
        return [create_item(d["category"], d["id"], d["name"], d["color"], d["season"],
                            d["temp_min"], d["temp_max"], "", d.get("gender", "Унісекс")) for d in ds]

    BT, OT, B, S = build(base_tops), build(outer_tops), build(bottoms), build(shoes)
    if max_combos is not None:
        for group in (BT, OT, B, S):
            random.shuffle(group)
    heap, checked = [], 0

    iterator = itertools.product(BT, B, S) if season == "Літо" else itertools.product(BT, OT, B, S)

    for combo in itertools.islice(iterator, max_combos):
        checked += 1
        score = evaluate_items(combo, temp, season)
        if score >= min_score:
            entry = (score, random.random(), combo)
            if len(heap) < top_n:
                heapq.heappush(heap, entry)
            elif score > heap[0][0]:
                heapq.heapreplace(heap, entry)

    result = []
    for sc, _, combo in sorted(heap, reverse=True, key=lambda e: (e[0], e[1])):
        if len(combo) == 3:
            bt, b, s = combo
            ids = [bt.item_id, b.item_id, s.item_id]
            name = f"Образ: {bt.name} + {b.name} + {s.name}"
        else:
            bt, ot, b, s = combo
            ids = [ot.item_id, bt.item_id, b.item_id, s.item_id]
            name = f"Образ: {ot.name} та {bt.name} + {b.name} + {s.name}"

        models = [f"{x.category}|{x.name}" for x in combo]
        result.append({"id": f"gen_{'_'.join(ids)}", "name": name, "items": ids, "score": round(sc, 2),
                       "models": models})

    return checked, result


def make_chunks(groups, parts, max_combos, top_n, min_score, temp, season):
    btops = groups["Базовий верх"]
    k = max(1, min(parts, len(btops)))

    ot_len = len(groups.get("Верхній одяг", [])) if season != "Літо" else 1
    total = len(btops) * ot_len * len(groups["Низ"]) * len(groups["Взуття"])

    base, rem = divmod(max_combos, k)
    pool_size = min(max(top_n * 8, 300), 3000)
    chunks = []
    for i in range(k):
        limit = None if total <= max_combos else max(1, base + (1 if i < rem else 0))
        chunks.append(
            (btops[i::k], groups.get("Верхній одяг", []), groups["Низ"], groups["Взуття"], temp, season, limit,
             pool_size, min_score))
    return chunks


DIVERSITY_PENALTY = 0.02
DIVERSITY_POOL = 3000


def diversify(candidates, top_n):
    pool = sorted(candidates, key=lambda r: (r["score"], random.random()), reverse=True)[:DIVERSITY_POOL]
    used, chosen = {}, []
    while pool and len(chosen) < top_n:
        best_i, best_v = 0, None
        for i, r in enumerate(pool):
            v = r["score"] - DIVERSITY_PENALTY * sum(used.get(m, 0) for m in r["models"])
            if best_v is None or v > best_v:
                best_i, best_v = i, v
        r = pool.pop(best_i)
        chosen.append(r)
        for m in r["models"]:
            used[m] = used.get(m, 0) + 1
    chosen.sort(key=lambda r: r["score"], reverse=True)
    return chosen


def run_chunks(mode, chunks, workers, progress_cb=None, cancel=None, top_n=None, varied=False):
    outs = []
    if mode == "sequential":
        for c in chunks:
            if cancel is not None and cancel.is_set():
                raise TaskCancelled()
            outs.append(evaluate_chunk(c))
            if progress_cb:
                progress_cb(len(outs) / len(chunks))
    else:
        pool_cls = ThreadPoolExecutor if mode == "threads" else ProcessPoolExecutor
        ex = pool_cls(max_workers=workers)
        try:
            futures = [ex.submit(evaluate_chunk, c) for c in chunks]
            for fut in as_completed(futures):
                if cancel is not None and cancel.is_set():
                    raise TaskCancelled()
                outs.append(fut.result())
                if progress_cb:
                    progress_cb(len(outs) / len(chunks))
        finally:
            ex.shutdown(wait=True, cancel_futures=True)
    top_n = top_n or chunks[0][7]
    all_results = [r for _, res in outs for r in res]
    if varied:
        merged = diversify(all_results, top_n)
    else:
        merged = heapq.nlargest(top_n, all_results, key=lambda r: (r["score"], random.random()))
    return merged, sum(c for c, _ in outs)