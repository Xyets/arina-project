import tkinter as tk
from tkinter import ttk, simpledialog, messagebox
import json
import os

VIP_FILE = "vip_donaters.json"
VIP_CFG = "vip_config.json"
VIP_PERSISTENT = "vip_persistent.json"


def sort_treeview(tree, col, reverse):
    data = [(tree.set(item, col), item) for item in tree.get_children("")]
    try:
        data.sort(key=lambda t: int(t[0]), reverse=reverse)
    except:
        data.sort(reverse=reverse)
    for index, (val, item) in enumerate(data):
        tree.move(item, "", index)
    tree.heading(col, command=lambda: sort_treeview(tree, col, not reverse))


def get_vip_threshold():
    try:
        with open(VIP_CFG, "r", encoding="utf-8") as f:
            return json.load(f).get("vip_threshold", 3000)
    except:
        return 3000


def load_persistent():
    if os.path.exists(VIP_PERSISTENT):
        with open(VIP_PERSISTENT, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_persistent(data):
    with open(VIP_PERSISTENT, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


class VIPPanel(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.create_widgets()
        self.load_vip_data()

    def create_widgets(self):
        self.tree = ttk.Treeview(
            self,
            columns=("id", "name", "alias", "total", "total_all_time", "pinned"),
            show="headings"
        )
        self.tree.heading("id", text="ID")
        self.tree.heading("name", text="Имя (оригинал)")
        self.tree.heading("alias", text="Имя для благодарности")
        self.tree.heading("total", text="Сумма за стрим",
                          command=lambda: sort_treeview(self.tree, "total", False))
        self.tree.heading("total_all_time", text="Всего за всё время")
        self.tree.heading("pinned", text="⭐ Закреплён")

        self.tree.column("id", width=250)
        self.tree.column("name", width=150)
        self.tree.column("alias", width=150)
        self.tree.column("total", width=100)
        self.tree.column("total_all_time", width=130)
        self.tree.column("pinned", width=100)

        self.tree.tag_configure("pinned", background="lightyellow")

        self.tree.pack(padx=10, pady=10, fill="both", expand=True)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=5)

        tk.Button(btn_frame, text="🔄 Обновить", command=self.load_vip_data).pack(side="left", padx=5)
        tk.Button(btn_frame, text="✏️ Изменить имя", command=self.edit_alias).pack(side="left", padx=5)
        tk.Button(btn_frame, text="⭐ Закрепить/Убрать", command=self.toggle_pin).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🎚 Изменить порог", command=self.edit_threshold).pack(side="left", padx=5)
        tk.Button(btn_frame, text="🗑 Удалить", command=self.delete_vip).pack(side="left", padx=5)

    def load_vip_data(self):
        self.tree.delete(*self.tree.get_children())
        threshold = get_vip_threshold()

        try:
            with open(VIP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {}

        persistent = load_persistent()

        for user_id, info in data.items():
            pinned = persistent.get(user_id, {}).get("pinned", False)
            alias = info.get("alias", "")
            total = info.get("total", 0)
            total_all_time = persistent.get(user_id, {}).get("total_all_time", 0) + total
            name = info.get("name", "Неизвестно")

            if total >= threshold or pinned:
                self.tree.insert(
                    "",
                    "end",
                    values=(user_id, name, alias, total, total_all_time, "⭐" if pinned else ""),
                    tags=("pinned",) if pinned else ()
                )

        for user_id, info in persistent.items():
            if user_id not in data:
                self.tree.insert(
                    "",
                    "end",
                    values=(
                        user_id,
                        info.get("name", "Неизвестно"),
                        info.get("alias", ""),
                        0,
                        info.get("total_all_time", 0),
                        "⭐",
                    ),
                    tags=("pinned",)
                )

    def edit_alias(self):
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        user_id = item["values"][0]

        new_alias = simpledialog.askstring("Изменить имя", f"Как называть {user_id}?")
        if new_alias is None:
            return

        try:
            with open(VIP_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        except:
            data = {}

        if user_id in data:
            data[user_id]["alias"] = new_alias
            with open(VIP_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

        persistent = load_persistent()
        if user_id in persistent:
            persistent[user_id]["alias"] = new_alias
            save_persistent(persistent)

        self.load_vip_data()

    def toggle_pin(self):
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        user_id = item["values"][0]

        persistent = load_persistent()
        if user_id in persistent and persistent[user_id].get("pinned"):
            persistent[user_id]["pinned"] = False
        else:
            persistent[user_id] = {
                "name": item["values"][1],
                "alias": item["values"][2],
                "total_all_time": persistent.get(user_id, {}).get("total_all_time", 0) + item["values"][3],
                "pinned": True,
            }
        save_persistent(persistent)
        self.load_vip_data()

    def edit_threshold(self):
        try:
            with open(VIP_CFG, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except:
            cfg = {"vip_threshold": 3000}

        current = cfg.get("vip_threshold", 3000)

        new_value = simpledialog.askinteger(
            "Изменить порог",
            f"Текущий порог: {current}\nВведите новый порог для VIP:",
            minvalue=0,
        )
        if new_value is not None:
            cfg["vip_threshold"] = new_value
            with open(VIP_CFG, "w", encoding="utf-8") as f:
                json.dump(cfg, f, indent=2, ensure_ascii=False)
            self.load_vip_data()

    def delete_vip(self):
        selected = self.tree.selection()
        if not selected:
            return
        item = self.tree.item(selected[0])
        user_id = item["values"][0]

        if messagebox.askyesno("Удаление", f"Удалить донатера {user_id}?"):
            try:
                with open(VIP_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except:
                data = {}
            if user_id in data:
                del data[user_id]
                with open(VIP_FILE, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)

            persistent = load_persistent()
            if user_id in persistent:
                del persistent[user_id]
                save_persistent(persistent)