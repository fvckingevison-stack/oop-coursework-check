import logging
import os

import customtkinter as ctk
from PIL import Image, ImageDraw, ImageOps

from config import BASE_DIR

COLOR_HEX = {"чорний": "#2b2b2b", "білий": "#fafafa", "сірий": "#9e9e9e", "бежевий": "#d8c3a5",
             "синій": "#2f5fb3", "червоний": "#c0392b", "зелений": "#2e8b57", "коричневий": "#7b4a2d",
             "жовтий": "#f1c40f", "рожевий": "#f48fb1", "помаранчевий": "#e67e22",
             "блакитний": "#5dade2", "фіолетовий": "#8e44ad", "бордовий": "#7b1e3a"}

TEE = [(.30, .20), (.40, .20), (.45, .27), (.55, .27), (.60, .20), (.70, .20), (.88, .36), (.78, .48), (.70, .42),
       (.70, .82), (.30, .82), (.30, .42), (.22, .48), (.12, .36)]
TANK = [(.34, .14), (.42, .14), (.46, .28), (.54, .28), (.58, .14), (.66, .14), (.68, .40), (.70, .84), (.30, .84),
        (.32, .40)]
DRESS = [(.38, .12), (.44, .12), (.50, .18), (.56, .12), (.62, .12), (.74, .24), (.66, .34), (.70, .90), (.30, .90),
         (.34, .34), (.26, .24)]
JACKET = [(.34, .16), (.42, .13), (.50, .17), (.58, .13), (.66, .16), (.82, .24), (.90, .62), (.79, .64), (.72, .40),
          (.72, .86), (.28, .86), (.28, .40), (.21, .64), (.10, .62), (.18, .24)]
COAT = [(.34, .12), (.42, .10), (.50, .15), (.58, .10), (.66, .12), (.82, .20), (.90, .62), (.79, .64), (.72, .36),
        (.76, .92), (.24, .92), (.28, .36), (.21, .64), (.10, .62), (.18, .20)]
SWEAT = [(.36, .20), (.44, .18), (.56, .18), (.64, .20), (.80, .28), (.88, .64), (.77, .66), (.72, .44), (.72, .80),
         (.28, .80), (.28, .44), (.23, .66), (.12, .64), (.20, .28)]
HOOD = [(.35, .20), (.33, .10), (.40, .04), (.50, .02), (.60, .04), (.67, .10), (.65, .20), (.50, .28)]
TROUSERS = [(.30, .15), (.70, .15), (.74, .85), (.56, .85), (.50, .38), (.44, .85), (.26, .85)]
SHORTS = [(.28, .20), (.72, .20), (.78, .62), (.54, .62), (.50, .40), (.46, .62), (.22, .62)]
SKIRT = [(.34, .20), (.66, .20), (.80, .80), (.20, .80)]
LEGGINGS = [(.36, .15), (.64, .15), (.62, .88), (.52, .88), (.50, .40), (.48, .88), (.38, .88)]


def kind_of(category: str, name: str) -> str:
    n = name.lower()
    has = lambda *w: any(x in n for x in w)
    if category in ("Базовий верх", "Верхній одяг"):
        hood = "капюшон" in n and "без" not in n
        if has("пуховик", "пухова"):
            return "puffer_hood" if hood else "puffer"
        if has("пальто", "дублянка", "шуба", "тренч"):
            return "coat"
        if has("куртка", "парка", "аляска", "вітровка", "бомбер", "бушлат"):
            return "jacket_hood" if hood or has("парка", "аляска", "вітровка", "лижна") else "jacket"
        if has("худі") or ("кофта" in n and hood):
            return "hoodie"
        if has("кардиган", "в'язана"):
            return "cardigan"
        if has("кофта"):
            return "zipsweat" if has("змійц", "флісов") else "sweatshirt"
        if has("водолазка", "з горлом"):
            return "turtleneck"
        if has("светр"):
            return "sweater"
        if has("лонгслів"):
            return "longsleeve"
        if has("сорочка", "блуз"):
            return "shirt"
        if has("поло"):
            return "polo"
        if has("майка", "топ"):
            return "tank"
        if has("плаття"):
            return "dress"
        return "tee"
    if category == "Низ":
        if has("шорти"):
            return "shorts"
        if has("спідниця"):
            return "skirt"
        if has("легінс"):
            return "leggings"
        if has("джинси"):
            return "jeans"
        return "trousers"
    if has("чоботи"):
        return "tallboot"
    if has("черевики", "берці", "дутики", "челсі", "уггі"):
        return "ankleboot"
    if has("сандалі"):
        return "sandal"
    if has("шльопанці"):
        return "flipflop"
    if has("туфлі"):
        return "heel"
    if has("балетки", "мокасини"):
        return "flat"
    return "sneaker"


def resolve_photo(path: str) -> str:
    if not path:
        return ""
    return path if os.path.isabs(path) else os.path.join(BASE_DIR, path)


def _darker(hex_color, k=0.65):
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return "#%02x%02x%02x" % (int(r * k), int(g * k), int(b * k))


def _poly(d, S, poly, fill, line):
    p = [(x * S, y * S) for x, y in poly]
    d.polygon(p, fill=fill)
    d.line(p + [p[0]], fill=line, width=max(2, S // 70), joint="curve")


def _ln(d, S, pts, line, thick=90):
    d.line([(x * S, y * S) for x, y in pts], fill=line, width=max(2, S // thick), joint="curve")


def _box(d, S, x0, y0, x1, y1, line, fill=None):
    d.rounded_rectangle((x0 * S, y0 * S, x1 * S, y1 * S), radius=S // 30, fill=fill, outline=line,
                        width=max(2, S // 90))


def _dots(d, S, pts, line, r=.014):
    for x, y in pts:
        d.ellipse(((x - r) * S, (y - r) * S, (x + r) * S, (y + r) * S), fill=line)


def _strap(d, S, pts, fill, line):
    p = [(x * S, y * S) for x, y in pts]
    d.line(p, fill=line, width=S // 13, joint="curve")
    d.line(p, fill=fill, width=S // 20, joint="curve")


def _arc(d, S, box, line):
    d.arc(tuple(v * S for v in box), 0, 180, fill=line, width=max(2, S // 90))


def _cuffs(d, S, line):
    _ln(d, S, [(.13, .60), (.235, .62)], line)
    _ln(d, S, [(.765, .62), (.87, .60)], line)


def _hood_open(d, S, fill, line):
    d.ellipse((round(0.42 * S), round(0.07 * S), round(0.58 * S), round(0.22 * S)),
              fill=_darker(fill, 0.55), outline=line, width=max(2, S // 90))
    _ln(d, S, [(.46, .24), (.46, .36)], line)
    _ln(d, S, [(.54, .24), (.54, .36)], line)


def _draw_clothes(d, S, kind, fill, line):
    if kind in ("jacket", "jacket_hood", "puffer", "puffer_hood"):
        hooded, puffer = kind.endswith("hood"), kind.startswith("puffer")
        if hooded:
            _poly(d, S, HOOD, fill, line)
        _poly(d, S, JACKET, fill, line)
        _ln(d, S, [(.50, .17), (.50, .86)], line)
        if puffer:
            for y in (.30, .43, .56, .69, .80):
                _ln(d, S, [(.28, y), (.72, y)], line)
        else:
            _box(d, S, .31, .64, .41, .73, line)
            _box(d, S, .59, .64, .69, .73, line)
        if hooded:
            _hood_open(d, S, fill, line)
        else:
            _ln(d, S, [(.42, .13), (.50, .25), (.58, .13)], line)
    elif kind == "coat":
        _poly(d, S, COAT, fill, line)
        _ln(d, S, [(.42, .10), (.50, .40), (.58, .10)], line)
        _ln(d, S, [(.50, .40), (.50, .92)], line)
        _dots(d, S, [(.55, .50), (.55, .62), (.55, .74)], line)
    elif kind == "hoodie":
        _poly(d, S, HOOD, fill, line)
        _poly(d, S, SWEAT, fill, line)
        _hood_open(d, S, fill, line)
        _poly(d, S, [(.33, .58), (.67, .58), (.71, .74), (.29, .74)], fill, line)
        _ln(d, S, [(.28, .77), (.72, .77)], line)
        _cuffs(d, S, line)
    elif kind in ("sweatshirt", "zipsweat", "cardigan", "sweater", "turtleneck", "longsleeve"):
        _poly(d, S, SWEAT, fill, line)
        _cuffs(d, S, line)
        if kind == "cardigan":
            _ln(d, S, [(.44, .18), (.50, .36), (.56, .18)], line)
            _ln(d, S, [(.50, .36), (.50, .80)], line)
            _dots(d, S, [(.53, .46), (.53, .56), (.53, .66), (.53, .74)], line)
        elif kind == "zipsweat":
            _ln(d, S, [(.50, .12), (.50, .80)], line)
            _box(d, S, .43, .10, .57, .20, line, fill)
            _box(d, S, .31, .60, .40, .70, line)
            _box(d, S, .60, .60, .69, .70, line)
        elif kind == "turtleneck":
            _box(d, S, .41, .08, .59, .22, line, fill)
            for x in (.45, .50, .55):
                _ln(d, S, [(x, .09), (x, .21)], line, 140)
        else:
            _arc(d, S, (.42, .14, .58, .30), line)
        if kind in ("sweatshirt", "sweater", "turtleneck"):
            if kind == "sweatshirt":
                _ln(d, S, [(.28, .75), (.72, .75)], line)
            else:
                for i in range(9):
                    _ln(d, S, [(round(0.32 + 0.045 * i, 3), .74), (round(0.32 + 0.045 * i, 3), .80)], line, 140)
    elif kind == "shirt":
        _poly(d, S, SWEAT, fill, line)
        _cuffs(d, S, line)
        _poly(d, S, [(.42, .17), (.50, .22), (.45, .31)], fill, line)
        _poly(d, S, [(.58, .17), (.50, .22), (.55, .31)], fill, line)
        _ln(d, S, [(.50, .22), (.50, .80)], line)
        _dots(d, S, [(.53, .38), (.53, .49), (.53, .60), (.53, .71)], line)
    elif kind == "polo":
        _poly(d, S, TEE, fill, line)
        _poly(d, S, [(.43, .20), (.50, .26), (.45, .33)], fill, line)
        _poly(d, S, [(.57, .20), (.50, .26), (.55, .33)], fill, line)
        _ln(d, S, [(.50, .26), (.50, .46)], line)
        _dots(d, S, [(.53, .34), (.53, .42)], line)
    elif kind == "tank":
        _poly(d, S, TANK, fill, line)
    elif kind == "dress":
        _poly(d, S, DRESS, fill, line)
        _ln(d, S, [(.34, .34), (.66, .34)], line)
    elif kind == "tee":
        _poly(d, S, TEE, fill, line)
        _arc(d, S, (.43, .20, .57, .34), line)
    elif kind in ("trousers", "jeans", "leggings", "shorts"):
        shape = {"trousers": TROUSERS, "jeans": TROUSERS, "leggings": LEGGINGS, "shorts": SHORTS}[kind]
        _poly(d, S, shape, fill, line)
        _ln(d, S, [(.30 if kind != "leggings" else .36, .22), (.70 if kind != "leggings" else .64, .22)], line)
        if kind == "jeans":
            _ln(d, S, [(.50, .15), (.50, .38)], line)
            _ln(d, S, [(.32, .26), (.38, .36), (.46, .28)], line)
            _ln(d, S, [(.68, .26), (.62, .36), (.54, .28)], line)
        elif kind in ("trousers", "shorts"):
            _ln(d, S, [(.50, .15), (.50, .36)], line)
    elif kind == "skirt":
        _poly(d, S, SKIRT, fill, line)
        _ln(d, S, [(.34, .26), (.66, .26)], line)
        _ln(d, S, [(.45, .26), (.40, .80)], line)
        _ln(d, S, [(.55, .26), (.60, .80)], line)


def _sole(d, S, line, color="#3a3a3a", y0=.78, y1=.88):
    d.rounded_rectangle((round(0.20 * S), round(y0 * S), round(0.90 * S), round(y1 * S)),
                        radius=S // 30, fill=color, outline=line, width=max(2, S // 90))


def _draw_shoes(d, S, kind, fill, line):
    if kind == "ankleboot":
        _poly(d, S, [(.22, .16), (.46, .16), (.48, .50), (.62, .56), (.84, .64), (.88, .74), (.88, .80), (.22, .80)],
              fill, line)
        _sole(d, S, line)
        _ln(d, S, [(.22, .24), (.47, .24)], line)
        for y in (.32, .39, .46):
            _ln(d, S, [(.37, y), (.48, y)], line)
    elif kind == "tallboot":
        _poly(d, S, [(.24, .06), (.50, .06), (.52, .56), (.66, .62), (.86, .70), (.90, .78), (.90, .82), (.24, .82)],
              fill, line)
        _sole(d, S, line, y0=.80, y1=.90)
        _ln(d, S, [(.24, .14), (.50, .14)], line)
    elif kind == "sneaker":
        _poly(d, S, [(.12, .62), (.12, .40), (.30, .40), (.38, .52), (.62, .58), (.86, .64), (.90, .74), (.90, .78),
                     (.12, .78)], fill, line)
        _sole(d, S, line, "#fdfdfd", .76, .85)
        for x, y in ((.34, .46), (.40, .51), (.46, .56)):
            _ln(d, S, [(x, y), (x + .08, y)], line)
        _ln(d, S, [(.70, .60), (.70, .77)], line)
    elif kind == "sandal":
        d.rounded_rectangle((round(0.10 * S), round(0.72 * S), round(0.90 * S), round(0.82 * S)),
                            radius=S // 25, fill="#c9b79c", outline=line, width=max(2, S // 90))
        _strap(d, S, [(.30, .72), (.42, .50), (.54, .72)], fill, line)
        _strap(d, S, [(.50, .58), (.78, .62), (.84, .72)], fill, line)
    elif kind == "flipflop":
        d.ellipse((round(0.30 * S), round(0.10 * S), round(0.70 * S), round(0.90 * S)),
                  fill="#d9cbb5", outline=line, width=max(2, S // 90))
        _strap(d, S, [(.34, .54), (.50, .28), (.66, .54)], fill, line)
    elif kind == "heel":
        _poly(d, S, [(.14, .46), (.30, .46), (.40, .62), (.70, .64), (.88, .74), (.88, .78), (.14, .78)], fill, line)
        _poly(d, S, [(.14, .78), (.25, .78), (.21, .92), (.15, .92)], _darker(fill, .6), line)
    else:
        _poly(d, S, [(.14, .56), (.34, .52), (.46, .60), (.70, .62), (.88, .72), (.88, .78), (.14, .78)], fill, line)
        _sole(d, S, line, "#3a3a3a", .76, .83)
        _ln(d, S, [(.52, .62), (.68, .66)], line)


def draw_placeholder(category, color, size, name=""):
    S = size * 4
    img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((0, 0, S - 1, S - 1), radius=S // 8, fill="#EEF1F6")
    fill = COLOR_HEX.get(color.strip().lower(), "#9aa5b1")
    line = _darker(fill)
    kind = kind_of(category, name)
    (_draw_shoes if category == "Взуття" else _draw_clothes)(d, S, kind, fill, line)
    return img.resize((size * 2, size * 2), Image.LANCZOS)


def load_photo(path, size):
    try:
        with Image.open(path) as im:
            im = ImageOps.fit(ImageOps.exif_transpose(im).convert("RGB"), (size * 2, size * 2), Image.LANCZOS)
    except (OSError, ValueError):
        logging.warning("Не вдалося відкрити фото %s", path)
        return None
    mask = Image.new("L", im.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle((0, 0, im.size[0] - 1, im.size[1] - 1), radius=size // 4, fill=255)
    out = im.convert("RGBA")
    out.putalpha(mask)
    return out


class ImageStore:
    def __init__(self):
        self._cache = {}

    def make(self, category, color, image_path, size, name=""):
        key = (kind_of(category, name), color.strip().lower(), image_path, size)
        if key not in self._cache:
            pil, real = None, resolve_photo(image_path)
            if real and os.path.exists(real):
                pil = load_photo(real, size)
            if pil is None:
                pil = draw_placeholder(category, color, size, name)
            self._cache[key] = ctk.CTkImage(light_image=pil, dark_image=pil, size=(size, size))
        return self._cache[key]

    def get(self, item, size=120):
        return self.make(item.category, item.color, item.image, size, item.name)

    def empty(self, size):
        key = ("empty", size)
        if key not in self._cache:
            S = size * 2
            img = Image.new("RGBA", (S, S), (0, 0, 0, 0))
            ImageDraw.Draw(img).rounded_rectangle((2, 2, S - 3, S - 3), radius=S // 8, fill="#E6E9EF",
                                                  outline="#C3C9D3", width=3)
            self._cache[key] = ctk.CTkImage(light_image=img, dark_image=img, size=(size, size))
        return self._cache[key]


IMAGES = ImageStore()