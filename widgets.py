import logging
import os
import shutil
import uuid
from tkinter import ttk, filedialog

import customtkinter as ctk

from config import CATEGORIES, COLORS, GENDERS, PHOTO_DIR, SEASONS, SEASON_ICON
from images import IMAGES
from items import ClothingItem, create_item
from wardrobe import Outfit, Wardrobe


class _UkMessageBox:
    parent = None
    ICONS = {"info": "ℹ️", "warning": "⚠️", "error": "❌", "question": "❓"}

    def _show(self, title, text, kind, buttons):
        result = {"v": False}
        win = ctk.CTkToplevel(self.parent)
        win.title(title)
        win.resizable(False, False)
        if self.parent is not None:
            win.transient(self.parent)
        ctk.CTkLabel(win, text=f"{self.ICONS[kind]}  {title}", font=("Segoe UI", 16, "bold"),
                     anchor="w").pack(fill="x", padx=24, pady=(18, 4))
        ctk.CTkLabel(win, text=str(text), wraplength=460, justify="left", anchor="w").pack(fill="x", padx=24, pady=8)
        bar = ctk.CTkFrame(win, fg_color="transparent")
        bar.pack(pady=(4, 16))

        def choose(v):
            result["v"] = v
            win.destroy()

        for label, value, color in buttons:
            kw = {"fg_color": color} if color else {}
            ctk.CTkButton(bar, text=label, width=110, command=lambda v=value: choose(v), **kw).pack(side="left", padx=6)
        win.update_idletasks()
        w, h = max(win.winfo_reqwidth(), 420), win.winfo_reqheight()
        if self.parent is not None:
            x = self.parent.winfo_rootx() + (self.parent.winfo_width() - w) // 2
            y = self.parent.winfo_rooty() + (self.parent.winfo_height() - h) // 2
            win.geometry(f"{w}x{h}+{max(x, 0)}+{max(y, 0)}")
        win.protocol("WM_DELETE_WINDOW", lambda: choose(False))
        win.after(100, lambda: (win.lift(), win.focus_force(), win.grab_set()))
        win.wait_window()
        return result["v"]

    def showinfo(self, title, text):
        self._show(title, text, "info", [("Гаразд", True, None)])

    def showwarning(self, title, text):
        self._show(title, text, "warning", [("Гаразд", True, None)])

    def showerror(self, title, text):
        self._show(title, text, "error", [("Гаразд", True, "#c0392b")])

    def askyesno(self, title, text):
        return self._show(title, text, "question", [("Так", True, None), ("Ні", False, "gray40")])


messagebox = _UkMessageBox()


class DataTable(ctk.CTkFrame):
    def __init__(self, master, columns, widths, on_double_click=None, height=12, on_select=None):
        super().__init__(master, fg_color="transparent")
        self.columns = list(columns)
        self.sort_col, self.sort_rev = None, False
        self.tree = ttk.Treeview(self, columns=self.columns, show="headings", selectmode="extended", height=height)
        sb = ctk.CTkScrollbar(self, command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        for c, w in zip(self.columns, widths):
            self.tree.heading(c, text=c, command=lambda c=c: self.sort_by(c))
            self.tree.column(c, width=w, minwidth=60, anchor="w")
        if on_double_click:
            self.tree.bind("<Double-1>", lambda e: on_double_click())
        if on_select:
            self.tree.bind("<<TreeviewSelect>>", lambda e: on_select())

    def set_rows(self, rows):
        keep = set(self.tree.selection())
        self.tree.delete(*self.tree.get_children())
        for r in rows:
            self.tree.insert("", "end", iid=str(r[0]), values=r)
        present = [i for i in keep if self.tree.exists(i)]
        if present:
            self.tree.selection_set(present)
        self._apply_sort()

    def sort_by(self, col, reverse=None):
        if reverse is None:
            reverse = (not self.sort_rev) if self.sort_col == col else False
        self.sort_col, self.sort_rev = col, reverse
        self._apply_sort()

    def _apply_sort(self):
        if self.sort_col:
            def key(iid):
                v = self.tree.set(iid, self.sort_col)
                try:
                    return (0, float(v), "")
                except ValueError:
                    return (1, 0.0, v.lower())

            for pos, iid in enumerate(sorted(self.tree.get_children(), key=key, reverse=self.sort_rev)):
                self.tree.move(iid, "", pos)
        for pos, iid in enumerate(self.tree.get_children()):
            self.tree.item(iid, tags=("odd" if pos % 2 else "even",))
        for c in self.columns:
            arrow = (" ▼" if self.sort_rev else " ▲") if c == self.sort_col else ""
            self.tree.heading(c, text=c + arrow)

    def selected(self) -> list:
        return list(self.tree.selection())

    def apply_theme(self, bg, alt, fg):
        self.tree.tag_configure("even", background=bg, foreground=fg)
        self.tree.tag_configure("odd", background=alt, foreground=fg)


class BaseDialog(ctk.CTkToplevel):
    def __init__(self, master, title, size):
        super().__init__(master)
        self.title(title)
        self.geometry(size)
        self.resizable(False, False)
        self.transient(master)
        self.after(150, self._take_focus)
        self.lbl_error = ctk.CTkLabel(self, text="", text_color="#e74c3c", wraplength=380)

    def _take_focus(self):
        self.lift()
        self.focus_force()
        self.grab_set()

    def row(self, text, widget_factory):
        ctk.CTkLabel(self, text=text, anchor="w").pack(fill="x", padx=25, pady=(10, 0))
        w = widget_factory()
        w.pack(fill="x", padx=25, pady=(2, 0))
        return w

    def pair(self, t1, f1, t2, f2):
        fr = ctk.CTkFrame(self, fg_color="transparent")
        fr.pack(fill="x", padx=25, pady=(10, 0))
        fr.grid_columnconfigure((0, 1), weight=1, uniform="pair")
        out = []
        for col, (t, f) in enumerate(((t1, f1), (t2, f2))):
            pad = (0, 8) if col == 0 else (8, 0)
            ctk.CTkLabel(fr, text=t, anchor="w").grid(row=0, column=col, sticky="w", padx=pad)
            w = f(fr)
            w.grid(row=1, column=col, sticky="ew", padx=pad)
            out.append(w)
        return out

    def footer(self, on_ok):
        self.lbl_error.pack(pady=(10, 0))
        bar = ctk.CTkFrame(self, fg_color="transparent")
        bar.pack(pady=12)
        ctk.CTkButton(bar, text="Зберегти", width=130, command=on_ok).pack(side="left", padx=6)
        ctk.CTkButton(bar, text="Скасувати", width=130, fg_color="gray40", hover_color="gray30",
                      command=self.destroy).pack(side="left", padx=6)


class OutfitPreview(ctk.CTkFrame):
    def __init__(self, master, wardrobe, size=110, horizontal=False):
        super().__init__(master, corner_radius=14)
        self.wardrobe, self.size, self.horizontal = wardrobe, size, horizontal
        self.lbl_title = ctk.CTkLabel(self, text="Оберіть комплект", font=("Segoe UI", 17, "bold"), wraplength=400)
        self.lbl_title.pack(padx=14, pady=(14, 2))
        self.lbl_score = ctk.CTkLabel(self, text="", font=("Segoe UI", 15, "bold"))
        self.lbl_score.pack(pady=(0, 8))
        if horizontal:
            holder = ctk.CTkFrame(self, fg_color="transparent")
            holder.pack(padx=10, pady=(0, 14))
        else:
            holder = ctk.CTkScrollableFrame(self, fg_color="transparent", width=400)
            holder.pack(fill="both", expand=True, padx=6, pady=(0, 10))

        self.slots = []
        for n, cat in enumerate(CATEGORIES):
            cell = ctk.CTkFrame(holder, fg_color="transparent")
            img = ctk.CTkLabel(cell, text="", image=IMAGES.empty(size))
            txt = ctk.CTkLabel(cell, text=cat, justify="left" if not horizontal else "center",
                               anchor="w" if not horizontal else "center", wraplength=140 if horizontal else 250,
                               font=("Segoe UI", 13) if not horizontal else None)

            if horizontal:
                cell.grid(row=0, column=n, padx=6)
                img.pack()
                txt.pack(pady=(4, 0))
            else:
                cell.grid(row=n, column=0, pady=4, sticky="w")
                img.pack(side="left")
                txt.pack(side="left", padx=10)
            self.slots.append((cell, img, txt))

    def show(self, title, item_ids, score=None):
        self.lbl_title.configure(text=title or "Оберіть комплект")
        found = [it for it in (self.wardrobe.get_item(i) for i in item_ids) if it]

        for (cell, img, txt), cat in zip(self.slots, CATEGORIES):
            it = next((i for i in found if i.category == cat), None)
            if it:
                cell.grid()
                img.configure(image=IMAGES.get(it, self.size))
                txt.configure(text=f"{cat}\n{it.name}\n{it.color} · {SEASON_ICON.get(it.season, '🌍')} {it.season}")
            else:
                if cat == "Верхній одяг":
                    cell.grid_remove()
                else:
                    cell.grid()
                    img.configure(image=IMAGES.empty(self.size))
                    txt.configure(text=f"{cat}\n—")

        if score is None:
            self.lbl_score.configure(text="")
        else:
            color = "#2e8b57" if score >= 0.8 else "#e08e0b" if score >= 0.6 else "#c0392b"
            self.lbl_score.configure(text=f"Оцінка: {score:.2f}", text_color=color)


class ItemDialog(BaseDialog):
    def __init__(self, master, on_save, item: ClothingItem = None):
        super().__init__(master, "Редагування речі" if item else "Нова річ", "470x640")
        self.on_save, self.item = on_save, item
        self.photo_path = item.image if item else ""
        self.photo_new_src = None

        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=25, pady=(16, 0))
        self.lbl_photo = ctk.CTkLabel(top, text="", width=110, height=110)
        self.lbl_photo.pack(side="left")
        side = ctk.CTkFrame(top, fg_color="transparent")
        side.pack(side="left", padx=18)
        ctk.CTkButton(side, text="📷 Обрати фото…", command=self.pick_photo).pack(pady=(4, 6))
        ctk.CTkButton(side, text="✖ Прибрати фото", fg_color="gray40", hover_color="gray30",
                      command=self.clear_photo).pack()
        ctk.CTkLabel(side, text="Без фото показується\nсилует за кольором", text_color="gray60", justify="left").pack(
            pady=(8, 0))

        self.e_name = self.row("Назва *", lambda: ctk.CTkEntry(self, placeholder_text="Напр.: Светр вовняний"))
        self.e_name.bind("<KeyRelease>", lambda e: self.update_preview())
        self.c_cat, self.c_season = self.pair(
            "Категорія *", lambda p: ctk.CTkOptionMenu(p, values=CATEGORIES, command=lambda _: self.update_preview()),
            "Сезон *", lambda p: ctk.CTkOptionMenu(p, values=SEASONS))
        self.c_color, self.c_gender = self.pair(
            "Колір *", lambda p: ctk.CTkComboBox(p, values=COLORS, command=lambda _: self.update_preview()),
            "Стать *", lambda p: ctk.CTkOptionMenu(p, values=GENDERS))
        self.c_color.bind("<KeyRelease>", lambda e: self.update_preview())

        self.e_tmin, self.e_tmax = self.pair("Мін. температура, °C *", lambda p: ctk.CTkEntry(p),
                                             "Макс. температура, °C *", lambda p: ctk.CTkEntry(p))
        if item:
            self.e_name.insert(0, item.name)
            self.c_cat.set(item.category)
            self.c_color.set(item.color)
            self.c_season.set(item.season)
            self.c_gender.set(item.gender)
            self.e_tmin.insert(0, str(item.temp_min))
            self.e_tmax.insert(0, str(item.temp_max))
        else:
            self.c_color.set("")
            self.c_season.set("Зима")
            self.c_gender.set("Унісекс")
            self.e_tmin.insert(0, "-10")
            self.e_tmax.insert(0, "5")
        self.update_preview()
        self.footer(self.save)

    def update_preview(self):
        path = self.photo_new_src or self.photo_path
        self.lbl_photo.configure(image=IMAGES.make(self.c_cat.get(), self.c_color.get(), path, 110, self.e_name.get()))

    def pick_photo(self):
        path = filedialog.askopenfilename(parent=self,
                                          filetypes=[("Зображення", "*.png *.jpg *.jpeg *.webp *.bmp *.gif"),
                                                     ("Усі файли", "*.*")])
        if path:
            self.photo_new_src = path
            self.update_preview()

    def clear_photo(self):
        self.photo_new_src, self.photo_path = None, ""
        self.update_preview()

    @staticmethod
    def _store_photo(src, item_id):
        try:
            os.makedirs(PHOTO_DIR, exist_ok=True)
            name = f"{item_id}_{uuid.uuid4().hex[:4]}{os.path.splitext(src)[1].lower()}"
            shutil.copy2(src, os.path.join(PHOTO_DIR, name))
            return f"photos/{name}"
        except OSError as e:
            logging.exception("Не вдалося скопіювати фото %s", src)
            raise ValueError(f"Не вдалося скопіювати фото: {e}") from None

    def save(self):
        try:
            item_id = self.item.item_id if self.item else f"item_{uuid.uuid4().hex[:6]}"
            obj = create_item(self.c_cat.get(), item_id, self.e_name.get(), self.c_color.get(),
                              self.c_season.get(), self.e_tmin.get(), self.e_tmax.get(), self.photo_path,
                              self.c_gender.get())
            if self.photo_new_src:
                obj.image = self._store_photo(self.photo_new_src, item_id)
            self.on_save(obj)
            self.destroy()
        except (ValueError, KeyError) as e:
            self.lbl_error.configure(text=str(e))


class OutfitDialog(BaseDialog):
    def __init__(self, master, wardrobe: Wardrobe, score_fn, on_save, outfit: Outfit = None):
        super().__init__(master, "Редагування комплекту" if outfit else "Новий комплект", "550x700")
        self.on_save, self.outfit, self.score_fn = on_save, outfit, score_fn
        self.wardrobe = wardrobe
        self.e_name = self.row("Назва комплекту *", lambda: ctk.CTkEntry(self))
        self.maps, self.combos = {}, {}
        items = wardrobe.snapshot_items()

        for cat in CATEGORIES:
            mapping = {f"{i.name} · {i.color} · {i.gender} [{i.item_id}]": i.item_id for i in items if
                       i.category == cat}
            if cat == "Верхній одяг":
                vals = ["— (Без верхнього одягу)"] + list(mapping)
            else:
                vals = list(mapping)

            self.maps[cat] = mapping
            self.combos[cat] = self.row(f"{cat} *", lambda v=vals: ctk.CTkComboBox(self, values=v, state="readonly",
                                                                                   command=lambda
                                                                                       _: self.update_preview()))
            self.combos[cat].set("— (Без верхнього одягу)" if cat == "Верхній одяг" else "")

        self.preview = OutfitPreview(self, wardrobe, size=96, horizontal=True)
        self.preview.pack(padx=25, pady=(16, 0), fill="x")

        if outfit:
            self.e_name.insert(0, outfit.name)
            for cat, mapping in self.maps.items():
                for label, iid in mapping.items():
                    if iid in outfit.item_ids:
                        self.combos[cat].set(label)
        self.update_preview()
        self.footer(self.save)

    def _chosen(self):
        ids = []
        for cat in CATEGORIES:
            label = self.combos[cat].get()
            if label in self.maps[cat]:
                ids.append(self.maps[cat][label])
        return ids

    def update_preview(self):
        ids = self._chosen()
        self.preview.show(self.e_name.get().strip() or "Новий комплект", ids,
                          self.score_fn(ids) if len(ids) >= 3 else None)

    def save(self):
        try:
            ids = self._chosen()
            cats = {self.wardrobe.get_item(i).category for i in ids if self.wardrobe.get_item(i)}

            if "Базовий верх" not in cats or "Низ" not in cats or "Взуття" not in cats:
                raise ValueError("Обов'язкові категорії: Базовий верх, Низ, Взуття.")

            oid = self.outfit.outfit_id if self.outfit else f"out_{uuid.uuid4().hex[:6]}"
            self.on_save(Outfit(oid, self.e_name.get(), ids, self.score_fn(ids)))
            self.destroy()
        except (ValueError, KeyError) as e:
            self.lbl_error.configure(text=str(e))