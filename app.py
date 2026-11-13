import logging
import os
import queue
import tkinter as tk
from tkinter import ttk, filedialog

import customtkinter as ctk

from config import (ALL_CAT, ALL_COLOR, ALL_GENDER, ALL_SEASON, CATEGORIES, DEFAULT_FILE, DEFAULT_TEMP_MAP,
                    GENDERS, GREEN, GREEN_H, RED, RED_H, SEASONS, SEASON_ICON, SEL_COLOR, TEMP_LIMITS)
from controller import WardrobeController
from images import IMAGES
from widgets import DataTable, ItemDialog, OutfitDialog, OutfitPreview, messagebox
from wardrobe import Wardrobe

ctk.set_appearance_mode("System")
ctk.set_default_color_theme("blue")

GUIDE = """ШВИДКА ДОВІДКА

ПОГОДА
- У лівій панелі оберіть сезон і введіть температуру, °C (від -60 до 60). Натисніть Enter або перейдіть в інше поле.

- Речі для підбору відбираються за сезоном І за температурою: температура має входити в діапазон речі.

- Оцінка комплекту залежить від поточної погоди. Після зміни погоди натисніть «Перерахувати оцінки».


КОМПЛЕКТИ
- Зима, Весна, Осінь – 4 речі (з верхнім одягом). Літо – 3 речі (без куртки).

- Футболки та майки взимку заборонені: правило LayeringRule дає комплекту оцінку 0.


РЕЧІ ТА ДАНІ
- Галерея: клік – вибрати, подвійний клік – редагувати. Пошук за назвою, фільтри за категорією, сезоном, кольором, статтю.

- Імпорт/експорт JSON – кнопки ліворуч. Експорт найкращих комплектів для поточної погоди в XML – на вкладці «Комплекти».

- Якщо wardrobe.json пошкоджено, програма збереже його як wardrobe.json.bak і запуститься з порожнім гардеробом.

- Усі дії та помилки записуються у файл wardrobe.log.


АВТО-ПІДБІР І БЕНЧМАРК
- Підбір до 1 000 000 комбінацій виконується у процесах (ProcessPoolExecutor) під керуванням окремого потоку. Кнопка «Скасувати» в рядку стану зупиняє задачу.

- Бенчмарк порівнює послідовний режим (T1), ThreadPoolExecutor і ProcessPoolExecutor: кожен режим запускається кілька разів, береться середнє. S = T1/Tn, ефективність E = S/n.

- Через GIL потоки Python не прискорюють обчислення на CPU (S близьке до 1 або менше), а процеси – прискорюють.

"""


class WardrobeApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        messagebox.parent = self
        self.title("Менеджер гардеробу з підбором комплектів")
        self.geometry("1650x920")
        self.minsize(1250, 720)

        self.wardrobe = Wardrobe()
        self.controller = WardrobeController(self.wardrobe)
        self.tables, self.pages, self.nav_buttons, self.busy_buttons = [], {}, {}, []
        self.generated = {}
        self.load_failed = False
        startup_errors = self.load_initial_data()

        self.build_layout()
        self.apply_tree_theme()
        self.refresh_all()
        self.show_page("items")
        self.protocol("WM_DELETE_WINDOW", self.on_close)
        self.after(100, self.poll_queue)
        if startup_errors:
            self.show_import_errors("Під час завантаження wardrobe.json виявлено проблеми", startup_errors)

    def load_initial_data(self):
        try:
            return self.controller.load_or_create_default()
        except (OSError, ValueError) as e:
            logging.exception("Не вдалося завантажити %s", DEFAULT_FILE)
            self.load_failed = True
            backup = DEFAULT_FILE + ".bak"
            try:
                os.replace(DEFAULT_FILE, backup)
                note = f"Копію збережено як {os.path.basename(backup)}."
            except OSError:
                logging.exception("Не вдалося зберегти копію пошкодженого файлу")
                note = "Копію зробити не вдалося."
            return [f"Файл {os.path.basename(DEFAULT_FILE)} не вдалося прочитати ({e}). "
                    f"{note} Запущено порожній гардероб."]

    def on_close(self):
        if self.controller.busy:
            if not messagebox.askyesno("Підтвердження", "Фонова задача ще виконується. Закрити програму?"):
                return
            self.controller.cancel()
        try:
            self.controller.export_json(DEFAULT_FILE)
        except OSError:
            logging.exception("Не вдалося зберегти %s під час закриття", DEFAULT_FILE)
        self.destroy()

    def build_layout(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self.build_sidebar()

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.grid(row=0, column=1, sticky="nsew", padx=(0, 14), pady=14)
        right.grid_rowconfigure(0, weight=1)
        right.grid_columnconfigure(0, weight=1)
        self.container = ctk.CTkFrame(right, fg_color="transparent")
        self.container.grid(row=0, column=0, sticky="nsew")

        bar = ctk.CTkFrame(right, height=40, corner_radius=8)
        bar.grid(row=1, column=0, sticky="ew", pady=(10, 0))
        self.lbl_status = ctk.CTkLabel(bar, text="Готово", anchor="w")
        self.lbl_status.pack(side="left", padx=14, pady=8)
        self.btn_cancel = ctk.CTkButton(bar, text="✖ Скасувати", width=110, fg_color=RED, hover_color=RED_H,
                                        state="disabled", command=self.cancel_task)
        self.btn_cancel.pack(side="right", padx=(0, 14))
        self.progress = ctk.CTkProgressBar(bar, width=320)
        self.progress.set(0)
        self.progress.pack(side="right", padx=14)

        self.build_items_page()
        self.build_outfits_page()
        self.build_generator_page()
        self.build_bench_page()
        self.build_help_page()

    def build_sidebar(self):
        sb = ctk.CTkFrame(self, width=240, corner_radius=0)
        sb.grid(row=0, column=0, sticky="nsw")
        sb.grid_propagate(False)
        ctk.CTkLabel(sb, text="👗 Гардероб", font=("Segoe UI", 24, "bold")).pack(pady=(22, 2))
        ctk.CTkLabel(sb, text="підбір комплектів одягу", text_color="gray60").pack(pady=(0, 16))

        for key, text in [("items", "👕  Речі"), ("outfits", "🧥  Комплекти"), ("gen", "⚙️  Авто-підбір"),
                          ("bench", "📊  Бенчмарк"), ("help", "❓  Довідка")]:
            b = ctk.CTkButton(sb, text=text, anchor="w", height=38, fg_color="transparent",
                              text_color=("gray10", "gray90"), hover_color=("gray75", "gray30"),
                              command=lambda k=key: self.show_page(k))
            b.pack(fill="x", padx=14, pady=3)
            self.nav_buttons[key] = b

        box = ctk.CTkFrame(sb)
        box.pack(fill="x", padx=14, pady=(20, 0))
        ctk.CTkLabel(box, text="🌤 Погода та стать", font=("Segoe UI", 14, "bold")).pack(pady=(10, 6))

        ctk.CTkLabel(box, text="Сезон:", anchor="w").pack(fill="x", padx=12, pady=(0, 0))
        self.var_wseason = tk.StringVar(value="Зима")
        ctk.CTkOptionMenu(box, values=SEASONS, variable=self.var_wseason,
                          command=self.on_season_change).pack(fill="x", padx=12, pady=(2, 6))

        ctk.CTkLabel(box, text="Температура, °C:", anchor="w").pack(fill="x", padx=12, pady=(4, 0))
        self.var_wtemp = tk.StringVar(value=str(DEFAULT_TEMP_MAP["Зима"]))
        self.ent_wtemp = ctk.CTkEntry(box, textvariable=self.var_wtemp)
        self.ent_wtemp.pack(fill="x", padx=12, pady=(2, 6))
        self.ent_wtemp.bind("<Return>", lambda e: self.on_weather_change())
        self.ent_wtemp.bind("<FocusOut>", lambda e: self.on_weather_change(silent=True))

        ctk.CTkLabel(box, text="Стать (для підбору):", anchor="w").pack(fill="x", padx=12, pady=(4, 0))
        self.var_wgender = tk.StringVar(value="Усі")
        ctk.CTkOptionMenu(box, values=["Усі", "Чоловіче", "Жіноче"], variable=self.var_wgender,
                          command=lambda _: self.on_weather_change(silent=True)).pack(fill="x", padx=12, pady=(2, 12))

        self.btn_import = ctk.CTkButton(sb, text="📂  Імпорт JSON", command=self.import_json)
        self.btn_import.pack(fill="x", padx=14, pady=(20, 4))
        self.busy_buttons.append(self.btn_import)
        ctk.CTkButton(sb, text="💾  Експорт JSON", command=self.export_json).pack(fill="x", padx=14, pady=4)

        self.var_theme = tk.StringVar(value="Системна")
        ctk.CTkSegmentedButton(sb, values=["Світла", "Темна", "Системна"], variable=self.var_theme,
                               command=self.change_theme).pack(side="bottom", fill="x", padx=14, pady=16)

    def show_page(self, key):
        for p in self.pages.values():
            p.pack_forget()
        self.pages[key].pack(fill="both", expand=True)
        for k, b in self.nav_buttons.items():
            b.configure(fg_color=("gray78", "gray28") if k == key else "transparent")

    def new_page(self, key, title, subtitle=""):
        page = ctk.CTkFrame(self.container, fg_color="transparent")
        self.pages[key] = page
        ctk.CTkLabel(page, text=title, font=("Segoe UI", 22, "bold"), anchor="w").pack(fill="x", padx=6)
        if subtitle:
            ctk.CTkLabel(page, text=subtitle, text_color="gray60", anchor="w").pack(fill="x", padx=6, pady=(0, 8))
        return page

    def add_table(self, parent, columns, widths, on_double_click=None, height=12, on_select=None):
        t = DataTable(parent, columns, widths, on_double_click, height, on_select)
        t.pack(fill="both", expand=True, padx=6, pady=6)
        self.tables.append(t)
        return t

    PAGE_SIZE = 15
    GAL_COLS = 5

    def build_items_page(self):
        page = self.new_page("items", "Речі гардеробу", "Галерея з фото, пошук, фільтри, додавання та редагування")
        self.sel_items, self.gal_cards, self.found_items, self.gal_page = set(), {}, [], 0
        f = ctk.CTkFrame(page, corner_radius=12)
        f.pack(fill="x", padx=6, pady=4)
        self.var_search, self.var_cat = tk.StringVar(), tk.StringVar(value=ALL_CAT)
        self.var_season, self.var_color = tk.StringVar(value=ALL_SEASON), tk.StringVar(value=ALL_COLOR)
        self.var_gender = tk.StringVar(value=ALL_GENDER)
        self.var_search.trace_add("write", self.on_filter_change)
        ctk.CTkEntry(f, textvariable=self.var_search, placeholder_text="🔍 Пошук за назвою…", width=190).pack(
            side="left", padx=8, pady=8)
        cb = lambda _=None: self.on_filter_change()
        ctk.CTkOptionMenu(f, values=[ALL_CAT] + CATEGORIES, variable=self.var_cat, command=cb, width=120).pack(
            side="left", padx=4)
        ctk.CTkOptionMenu(f, values=[ALL_SEASON] + SEASONS, variable=self.var_season, command=cb, width=120).pack(
            side="left", padx=4)
        ctk.CTkOptionMenu(f, values=[ALL_GENDER] + GENDERS, variable=self.var_gender, command=cb, width=120).pack(
            side="left", padx=4)
        self.opt_color = ctk.CTkOptionMenu(f, values=[ALL_COLOR], variable=self.var_color, command=cb, width=120)
        self.opt_color.pack(side="left", padx=4)
        ctk.CTkButton(f, text="✖ Скинути", width=90, fg_color="gray40", hover_color="gray30",
                      command=self.reset_filters).pack(side="left", padx=8)
        self.var_view = tk.StringVar(value="🖼 Галерея")

        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=6, pady=(4, 0))
        ctk.CTkButton(bar, text="➕ Додати", command=self.add_item).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="✏️ Редагувати", command=self.edit_item).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="🗑 Видалити", fg_color=RED, hover_color=RED_H, command=self.delete_items).pack(
            side="left", padx=4)
        ctk.CTkSegmentedButton(bar, values=["🖼 Галерея", "📋 Таблиця"], variable=self.var_view,
                               command=self.set_items_view).pack(side="right", padx=4)
        self.lbl_count = ctk.CTkLabel(bar, text="")
        self.lbl_count.pack(side="right", padx=12)

        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True)
        self.gal_box = ctk.CTkFrame(body, fg_color="transparent")
        self.gal_scroll = ctk.CTkScrollableFrame(self.gal_box, fg_color="transparent")
        self.gal_scroll.pack(fill="both", expand=True)
        pager = ctk.CTkFrame(self.gal_box, fg_color="transparent")
        pager.pack(fill="x", pady=(4, 0))
        self.btn_prev = ctk.CTkButton(pager, text="◀", width=40, command=lambda: self.change_gallery_page(-1))
        self.btn_prev.pack(side="left", padx=6)
        self.lbl_page = ctk.CTkLabel(pager, text="Сторінка 1 / 1")
        self.lbl_page.pack(side="left", padx=6)
        self.btn_next = ctk.CTkButton(pager, text="▶", width=40, command=lambda: self.change_gallery_page(1))
        self.btn_next.pack(side="left", padx=6)
        ctk.CTkLabel(pager, text="Клік – вибрати (можна кілька), подвійний клік – редагувати",
                     text_color="gray60").pack(side="right", padx=8)

        self.tbl_box = ctk.CTkFrame(body, fg_color="transparent")
        self.tbl_items = self.add_table(self.tbl_box,
                                        ["Код", "Назва", "Категорія", "Стать", "Колір", "Сезон", "Температури"],
                                        [100, 230, 110, 100, 110, 110, 130], self.edit_item, height=14)
        self.set_items_view()

    def set_items_view(self, _=None):
        self.gal_box.pack_forget()
        self.tbl_box.pack_forget()
        (self.gal_box if "Галерея" in self.var_view.get() else self.tbl_box).pack(fill="both", expand=True)

    def on_filter_change(self, *_):
        self.gal_page = 0
        self.refresh_items()

    def reset_filters(self):
        self.var_cat.set(ALL_CAT)
        self.var_season.set(ALL_SEASON)
        self.var_color.set(ALL_COLOR)
        self.var_gender.set(ALL_GENDER)
        self.var_search.set("")
        self.on_filter_change()

    def refresh_items(self):
        all_items = self.wardrobe.snapshot_items()
        colors = [ALL_COLOR] + sorted({i.color for i in all_items})
        self.opt_color.configure(values=colors)
        if self.var_color.get() not in colors:
            self.var_color.set(ALL_COLOR)
        pick = lambda v, all_: None if v == all_ else v
        self.found_items = self.wardrobe.search_items(self.var_search.get(), pick(self.var_cat.get(), ALL_CAT),
                                                      pick(self.var_season.get(), ALL_SEASON),
                                                      pick(self.var_color.get(), ALL_COLOR),
                                                      pick(self.var_gender.get(), ALL_GENDER))
        self.sel_items &= {i.item_id for i in all_items}
        self.tbl_items.set_rows(
            [(i.item_id, i.name, i.category, i.gender, i.color, i.season, f"{i.temp_min}..{i.temp_max}°C") for i in
             self.found_items])
        self.lbl_count.configure(text=f"Показано {len(self.found_items)} з {len(all_items)}")
        self.render_gallery()

    def render_gallery(self):
        pages = max(1, -(-len(self.found_items) // self.PAGE_SIZE))
        self.gal_page = max(0, min(self.gal_page, pages - 1))
        start = self.gal_page * self.PAGE_SIZE
        for w in self.gal_scroll.winfo_children():
            w.destroy()
        self.gal_cards = {}
        for c in range(self.GAL_COLS):
            self.gal_scroll.grid_columnconfigure(c, weight=1, uniform="card")
        for n, it in enumerate(self.found_items[start:start + self.PAGE_SIZE]):
            border = SEL_COLOR if it.item_id in self.sel_items else ("gray80", "gray30")
            card = ctk.CTkFrame(self.gal_scroll, corner_radius=14, border_width=2, border_color=border)
            card.grid(row=n // self.GAL_COLS, column=n % self.GAL_COLS, padx=6, pady=6, sticky="n")
            img = ctk.CTkLabel(card, text="", image=IMAGES.get(it, 130))
            img.pack(padx=10, pady=(10, 4))
            name = ctk.CTkLabel(card, text=it.name, font=("Segoe UI", 13, "bold"), wraplength=140)
            name.pack(padx=8)
            info = ctk.CTkLabel(card, text=f"{it.color} · {it.gender}", text_color="gray55", wraplength=150)
            info.pack()
            temp = ctk.CTkLabel(card,
                                text=f"{SEASON_ICON.get(it.season, '🌍')} {it.season} · {it.temp_min}…{it.temp_max} °C",
                                text_color="gray55", wraplength=150)
            temp.pack(pady=(0, 10))
            for w in (card, img, name, info, temp):
                w.bind("<Button-1>", lambda e, i=it.item_id: self.toggle_card(i))
                w.bind("<Double-Button-1>", lambda e, i=it.item_id: self.open_item(i))
            self.gal_cards[it.item_id] = card
        self.lbl_page.configure(text=f"Сторінка {self.gal_page + 1} / {pages}")
        self.btn_prev.configure(state="normal" if self.gal_page > 0 else "disabled")
        self.btn_next.configure(state="normal" if self.gal_page < pages - 1 else "disabled")

    def change_gallery_page(self, delta):
        self.gal_page += delta
        self.render_gallery()

    def toggle_card(self, item_id):
        self.sel_items.symmetric_difference_update({item_id})
        card = self.gal_cards.get(item_id)
        if card:
            card.configure(border_color=SEL_COLOR if item_id in self.sel_items else ("gray80", "gray30"))

    def open_item(self, item_id):
        self.sel_items = {item_id}
        self.edit_item()

    def selected_item_ids(self):
        if "Галерея" in self.var_view.get():
            return sorted(self.sel_items)
        return self.tbl_items.selected()

    def add_item(self):
        ItemDialog(self, lambda obj: self._save_item(obj, False))

    def edit_item(self):
        sel = self.selected_item_ids()
        if not sel:
            return messagebox.showwarning("Увага", "Оберіть річ для редагування.")
        item = self.wardrobe.get_item(sel[0])
        if item:
            ItemDialog(self, lambda obj: self._save_item(obj, True), item)

    def _save_item(self, obj, edit):
        self.controller.save_item(obj, edit)
        self.refresh_all()
        self.set_status(f"Річ «{obj.name}» збережено.")

    def delete_items(self):
        sel = self.selected_item_ids()
        if not sel:
            return messagebox.showwarning("Увага", "Оберіть річ для видалення.")
        if messagebox.askyesno("Підтвердження", f"Видалити обрані речі ({len(sel)})?"):
            self.controller.delete_items(sel)
            self.sel_items.clear()
            self.refresh_all()
            self.set_status(f"Видалено речей: {len(sel)}.")

    def build_outfits_page(self):
        page = self.new_page("outfits", "Комплекти одягу")
        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=6, pady=(4, 0))
        ctk.CTkButton(bar, text="➕ Створити", command=self.add_outfit).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="✏️ Редагувати", command=self.edit_outfit).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="🗑 Видалити", fg_color=RED, hover_color=RED_H, command=self.delete_outfits).pack(
            side="left", padx=4)
        ctk.CTkButton(bar, text="🔄 Перерахувати оцінки", fg_color="gray40", hover_color="gray30",
                      command=self.rescore).pack(side="left", padx=14)
        ctk.CTkButton(bar, text="⭐ За оцінкою", command=lambda: self.tbl_outfits.sort_by("Оцінка", True)).pack(
            side="left", padx=4)
        ctk.CTkButton(bar, text="📤 Експорт XML", fg_color=GREEN, hover_color=GREEN_H, command=self.export_xml).pack(
            side="right", padx=4)
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True)
        self.outfit_preview = OutfitPreview(body, self.wardrobe, size=140)
        self.outfit_preview.pack(side="right", fill="y", padx=(8, 6), pady=6)

        self.tbl_outfits = self.add_table(body,
                                          ["Код", "Назва", "Верхній одяг", "Базовий верх", "Низ", "Взуття", "Оцінка",
                                           "Статус"], [80, 130, 110, 110, 110, 110, 60, 90], self.edit_outfit,
                                          height=14, on_select=self.on_outfit_select)
        self.tbl_outfits.sort_by("Оцінка", True)

    def find_outfit(self, oid):
        return next((o for o in self.wardrobe.snapshot_outfits() if o.outfit_id == oid), None)

    def on_outfit_select(self):
        sel = self.tbl_outfits.selected()
        o = self.find_outfit(sel[0]) if sel else None
        if o:
            self.outfit_preview.show(o.name, o.item_ids, o.score)
        else:
            self.outfit_preview.show("", [], None)

    def refresh_outfits(self):
        rows = []
        for o in self.wardrobe.snapshot_outfits():
            by_cat = {c: "—" for c in CATEGORIES}
            for iid in o.item_ids:
                it = self.wardrobe.get_item(iid)
                if it:
                    by_cat[it.category] = it.name
            rows.append(
                (o.outfit_id, o.name, by_cat["Верхній одяг"], by_cat["Базовий верх"], by_cat["Низ"], by_cat["Взуття"],
                 f"{o.score:.2f}", "✓ повний" if not self.wardrobe.outfit_problem(o) else "⚠ неповний"))
        self.tbl_outfits.set_rows(rows)
        self.on_outfit_select()

    def score_ids(self, ids):
        return self.wardrobe.evaluate(ids, *self.controller.weather)

    def add_outfit(self):
        OutfitDialog(self, self.wardrobe, self.score_ids, lambda o: self._save_outfit(o, False))

    def edit_outfit(self):
        sel = self.tbl_outfits.selected()
        if not sel:
            return messagebox.showwarning("Увага", "Оберіть комплект для редагування.")
        outfit = self.find_outfit(sel[0])
        if outfit:
            OutfitDialog(self, self.wardrobe, self.score_ids, lambda o: self._save_outfit(o, True), outfit)

    def _save_outfit(self, outfit, edit):
        self.controller.save_outfit(outfit, edit)
        self.refresh_outfits()

    def delete_outfits(self):
        sel = self.tbl_outfits.selected()
        if not sel:
            return messagebox.showwarning("Увага", "Оберіть комплект для видалення.")
        if messagebox.askyesno("Підтвердження", f"Видалити обрані комплекти ({len(sel)})?"):
            self.controller.delete_outfits(sel)
            self.refresh_outfits()

    def rescore(self):
        if not self.on_weather_change():
            return
        self.controller.rescore()
        self.refresh_outfits()
        self.set_status("Оцінки перераховано для поточної погоди.")

    def export_xml(self):
        if not self.on_weather_change():
            return
        path = filedialog.asksaveasfilename(defaultextension=".xml", initialfile="best_outfits.xml",
                                            filetypes=[("XML", "*.xml")])
        if not path:
            return
        try:
            n = self.controller.export_best_xml(path)
            messagebox.showinfo("Успіх", f"Експортовано комплектів: {n}\n{path}")
        except (ValueError, OSError) as e:
            logging.exception("Помилка експорту XML")
            messagebox.showerror("Помилка", str(e))

    def build_generator_page(self):
        page = self.new_page("gen", "Авто-підбір комплектів")
        f = ctk.CTkFrame(page)
        f.pack(fill="x", padx=6, pady=4)
        self.ent_max = self.labeled_entry(f, "Макс. комбінацій:", "1000000", 100)
        self.ent_top = self.labeled_entry(f, "Найкращих:", "50", 60)
        self.ent_min = self.labeled_entry(f, "Мін. оцінка:", "0.6", 60)
        self.btn_gen = ctk.CTkButton(f, text="▶ Запустити підбір", fg_color=GREEN, hover_color=GREEN_H,
                                     command=self.start_generation)
        self.btn_gen.pack(side="right", padx=10, pady=8)
        self.busy_buttons.append(self.btn_gen)

        f2 = ctk.CTkFrame(page)
        f2.pack(fill="x", padx=6, pady=4)
        self.ent_per_cat = self.labeled_entry(f2, "Тестові речі: по", "100", 60)
        ctk.CTkLabel(f2, text="кожної категорії").pack(side="left")
        ctk.CTkButton(f2, text="🧪 Створити тестові речі", fg_color="gray40", hover_color="gray30",
                      command=self.make_test_items).pack(side="left", padx=12)
        ctk.CTkButton(f2, text="📦 Додати каталог одягу", command=self.add_catalog).pack(side="left", padx=4)

        self.lbl_gen_stats = ctk.CTkLabel(page, text="", anchor="w")
        self.lbl_gen_stats.pack(fill="x", padx=8, pady=(6, 0))
        bar = ctk.CTkFrame(page, fg_color="transparent")
        bar.pack(side="bottom", fill="x", padx=6, pady=(4, 0))
        ctk.CTkButton(bar, text="➕ Додати обрані", command=lambda: self.save_generated(True)).pack(side="left", padx=4)
        ctk.CTkButton(bar, text="➕ Додати всі", command=lambda: self.save_generated(False)).pack(side="left", padx=4)
        body = ctk.CTkFrame(page, fg_color="transparent")
        body.pack(fill="both", expand=True)
        self.gen_preview = OutfitPreview(body, self.wardrobe, size=115)
        self.gen_preview.pack(side="right", fill="y", padx=(8, 6), pady=6)
        self.tbl_gen = self.add_table(body, ["Код", "Назва комплекту", "Оцінка"], [190, 400, 70], height=10,
                                      on_select=self.on_gen_select)

    def on_gen_select(self):
        sel = self.tbl_gen.selected()
        r = self.generated.get(sel[0]) if sel else None
        if r:
            self.gen_preview.show(r["name"], r["items"], r["score"])
        else:
            self.gen_preview.show("", [], None)

    @staticmethod
    def labeled_entry(parent, label, default, width):
        ctk.CTkLabel(parent, text=label).pack(side="left", padx=(10, 4), pady=8)
        e = ctk.CTkEntry(parent, width=width)
        e.insert(0, default)
        e.pack(side="left")
        return e

    @staticmethod
    def read_number(entry, name, lo, hi, cast=int):
        try:
            v = cast(entry.get().strip().replace(",", "."))
        except ValueError:
            raise ValueError(f"«{name}»: введіть число.") from None
        if not lo <= v <= hi:
            raise ValueError(f"«{name}» має бути в межах {lo}..{hi}.")
        return v

    def make_test_items(self):
        try:
            n = self.read_number(self.ent_per_cat, "Кількість речей", 1, 500)
        except ValueError as e:
            return messagebox.showerror("Помилка", str(e))
        self.controller.generate_test_items(n)
        self.refresh_all()
        self.set_status(f"Додано тестових речей: {n * len(CATEGORIES)}.")

    def add_catalog(self):
        n = self.controller.add_catalog()
        if not n:
            return messagebox.showinfo("Каталог", "Усі речі з каталогу вже є у вашому гардеробі.")
        self.refresh_all()
        self.set_status(f"Додано речей з каталогу: {n}.")

    def start_generation(self):
        try:
            max_c = self.read_number(self.ent_max, "Макс. комбінацій", 1, 1_000_000)
            top_n = self.read_number(self.ent_top, "Найкращих", 1, 1000)
            min_s = self.read_number(self.ent_min, "Мін. оцінка", 0.0, 1.0, float)
        except ValueError as e:
            return messagebox.showerror("Помилка", str(e))
        if not self.on_weather_change():
            return
        if not self.controller.start_generation(max_c, top_n, min_s):
            return messagebox.showwarning("Увага", "Фонова задача ще виконується.")
        self.set_busy(True)

    def save_generated(self, only_selected):
        ids = self.tbl_gen.selected() if only_selected else list(self.generated)
        results = [self.generated[g] for g in ids if g in self.generated]
        if not results:
            return messagebox.showwarning("Увага", "Немає комплектів для додавання.")
        added = self.controller.save_generated(results)
        self.refresh_outfits()
        messagebox.showinfo("Успіх", f"Додано комплектів до гардероба: {added}")

    def build_bench_page(self):
        page = self.new_page("bench", "Порівняння продуктивності")
        f = ctk.CTkFrame(page)
        f.pack(fill="x", padx=6, pady=4)
        self.ent_bmax = self.labeled_entry(f, "Комбінацій:", "300000", 100)
        self.ent_bw = self.labeled_entry(f, "Потоків/процесів:", str(min(4, os.cpu_count() or 2)), 50)
        self.btn_bench = ctk.CTkButton(f, text="▶ Запустити бенчмарк", command=self.start_benchmark)
        self.btn_bench.pack(side="right", padx=10, pady=8)
        self.busy_buttons.append(self.btn_bench)
        self.txt_bench = ctk.CTkTextbox(page, font=("Consolas", 13), wrap="word")
        self.txt_bench.pack(fill="both", expand=True, padx=6, pady=6)

    def start_benchmark(self):
        try:
            n = self.read_number(self.ent_bmax, "Комбінацій", 1000, 1_000_000)
            w = self.read_number(self.ent_bw, "Потоків/процесів", 2, 32)
        except ValueError as e:
            return messagebox.showerror("Помилка", str(e))
        if not self.on_weather_change():
            return
        if not self.controller.start_benchmark(n, w):
            return messagebox.showwarning("Увага", "Фонова задача ще виконується.")
        self.set_busy(True)

    def build_help_page(self):
        page = self.new_page("help", "Довідка")
        box = ctk.CTkTextbox(page, wrap="word", font=("Segoe UI", 14))
        box.pack(fill="both", expand=True, padx=6, pady=6)
        box.insert("1.0", GUIDE)
        box.configure(state="disabled")

    def import_json(self):
        path = filedialog.askopenfilename(filetypes=[("JSON", "*.json")])
        if path and self.controller.start_import(path):
            self.set_busy(True)

    def export_json(self):
        path = filedialog.asksaveasfilename(defaultextension=".json", initialfile="wardrobe.json",
                                            filetypes=[("JSON", "*.json")])
        if path:
            try:
                self.controller.export_json(path)
                self.set_status(f"Експортовано в {path}")
            except OSError as e:
                logging.exception("Помилка експорту JSON")
                messagebox.showerror("Помилка", str(e))

    def show_import_errors(self, title, errors):
        shown = "\n".join(f"• {e}" for e in errors[:10])
        more = f"\n… і ще {len(errors) - 10}" if len(errors) > 10 else ""
        messagebox.showwarning(title, f"Пропущено/виправлено записів: {len(errors)}\n\n{shown}{more}")

    def on_season_change(self, season=None):
        self.var_wtemp.set(str(DEFAULT_TEMP_MAP.get(self.var_wseason.get(), 15)))
        self.on_weather_change()

    def on_weather_change(self, _=None, silent=False) -> bool:
        lo, hi = TEMP_LIMITS
        try:
            t = int(self.var_wtemp.get().strip())
            if not lo <= t <= hi:
                raise ValueError
        except ValueError:
            if silent:
                self.var_wtemp.set(str(self.controller.weather[0]))
            else:
                messagebox.showerror("Помилка", f"Температура має бути цілим числом від {lo} до {hi} °C.")
            return False
        self.controller.weather = (t, self.var_wseason.get())
        self.controller.gender = self.var_wgender.get()
        return True

    def change_theme(self, mode):
        ctk.set_appearance_mode({"Світла": "Light", "Темна": "Dark", "Системна": "System"}[mode])
        self.after(150, self.apply_tree_theme)

    def apply_tree_theme(self):
        dark = ctk.get_appearance_mode() == "Dark"
        bg, alt, fg = ("#2b2b2b", "#343638", "#e6e6e6") if dark else ("#ffffff", "#eef2f8", "#1a1a1a")
        head = "#3d3f41" if dark else "#d9e1ee"
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", background=bg, fieldbackground=bg, foreground=fg, rowheight=30, borderwidth=0,
                        font=("Segoe UI", 11))
        style.configure("Treeview.Heading", background=head, foreground=fg, relief="flat",
                        font=("Segoe UI", 11, "bold"))
        style.map("Treeview", background=[('selected', ("#1f538d" if dark else "#3a7ebf"))],
                  foreground=[('selected', "#ffffff")])
        for t in self.tables:
            t.apply_theme(bg, alt, fg)

    def set_status(self, text):
        self.lbl_status.configure(text=text)

    def refresh_all(self):
        self.refresh_items()
        self.refresh_outfits()

    def set_busy(self, busy):
        state = "disabled" if busy else "normal"
        for b in self.busy_buttons:
            b.configure(state=state)
        self.btn_cancel.configure(state="normal" if busy else "disabled")
        if not busy:
            self.progress.set(0)

    def cancel_task(self):
        self.controller.cancel()
        self.set_status("Скасування…")

    def poll_queue(self):
        try:
            while True:
                msg = self.controller.queue.get_nowait()
                self.handle_msg(msg)
        except queue.Empty:
            pass
        self.after(100, self.poll_queue)

    def handle_msg(self, msg):
        kind, *data = msg
        if kind == "progress":
            val, text = data[0], data[1]
            self.progress.set(val)
            self.set_status(text)
        elif kind == "gen_done":
            results, stats = data[0], data[1]
            self.set_busy(False)
            self.generated = {r["id"]: r for r in results}
            self.tbl_gen.set_rows([(r["id"], r["name"], f"{r['score']:.2f}") for r in results])
            self.lbl_gen_stats.configure(
                text=f"Перевірено комбінацій: {stats['checked']:,} · Знайдено: {len(results)} · Час: {stats['time']:.2f} с")
            self.set_status("Підбір завершено.")
        elif kind == "bench_done":
            rows, stats = data[0], data[1]
            self.set_busy(False)
            text = f"Бенчмарк ({stats['workers']} воркерів, {stats['runs']} запусків):\n"
            for label, avg, speedup, eff, _ in rows:
                text += f"• {label}: середній час {avg:.3f} с (Прискорення S={speedup:.2f}, Ефективність E={eff:.2f})\n"
            self.txt_bench.delete("1.0", "end")
            self.txt_bench.insert("1.0", text)
            self.set_status("Бенчмарк завершено.")
        elif kind == "import_done":
            items, outfits, errors = data[0], data[1], data[2]
            self.set_busy(False)
            self.refresh_all()
            if errors:
                self.show_import_errors("Помилки імпорту", errors)
            messagebox.showinfo("Імпорт", f"Успішно завантажено речей: {len(items)}, комплектів: {len(outfits)}")
            self.set_status("Імпорт завершено.")
        elif kind == "error":
            err_text = data[0]
            self.set_busy(False)
            messagebox.showerror("Помилка", err_text)
            self.set_status("Сталася помилка.")
        elif kind == "cancelled":
            name = data[0]
            self.set_busy(False)
            self.set_status(f"Задачу «{name}» скасовано.")