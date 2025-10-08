import tkinter as tk
from tkinter import ttk, messagebox
import json

RULES_FILE = "rules.json"

def load_rules():
    try:
        with open(RULES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except:
        return {"default": [1, 5], "rules": []}

def save_rules(data):
    with open(RULES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

class RulesPanel(tk.Frame):
    def __init__(self, master):
        super().__init__(master)
        self.rules_data = load_rules()
        self.create_widgets()
        self.populate_table()

    def create_widgets(self):
        self.tree = ttk.Treeview(
            self,
            columns=("min", "max", "strength", "duration", "action"),
            show="headings"
        )
        for col in self.tree["columns"]:
            self.tree.heading(col, text=col.capitalize())
            self.tree.column(col, width=100)
        self.tree.pack(padx=10, pady=10, fill="both", expand=True)

        btn_frame = tk.Frame(self)
        btn_frame.pack(pady=5)

        tk.Button(btn_frame, text="➕ Добавить", command=self.add_rule).pack(side="left", padx=5)
        tk.Button(btn_frame, text="✏️ Изменить", command=self.edit_rule).pack(side="left", padx=5)
        tk.Button(btn_frame, text="❌ Удалить", command=self.delete_rule).pack(side="left", padx=5)
        tk.Button(btn_frame, text="💾 Сохранить", command=self.save_all).pack(side="left", padx=5)

    def populate_table(self):
        self.tree.delete(*self.tree.get_children())
        for rule in self.rules_data["rules"]:
            self.tree.insert(
                "",
                "end",
                values=(
                    rule.get("min", ""),
                    rule.get("max", ""),
                    rule.get("strength", ""),
                    rule.get("duration", ""),
                    rule.get("action", "")
                )
            )

    def add_rule(self):
        self.open_editor()

    def edit_rule(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Выбор", "Выберите правило для редактирования")
            return
        values = self.tree.item(selected[0])["values"]
        self.open_editor(values, selected[0])

    def delete_rule(self):
        selected = self.tree.selection()
        if not selected:
            messagebox.showwarning("Выбор", "Выберите правило для удаления")
            return
        index = self.tree.index(selected[0])
        del self.rules_data["rules"][index]
        self.populate_table()

    def save_all(self):
        self.rules_data["rules"] = []
        for item in self.tree.get_children():
            values = self.tree.item(item)["values"]
            self.rules_data["rules"].append({
                "min": int(values[0]),
                "max": int(values[1]),
                "strength": int(values[2]) if values[2] else None,
                "duration": int(values[3]) if values[3] else None,
                "action": values[4] if values[4] else None
            })
        save_rules(self.rules_data)
        messagebox.showinfo("Сохранено", "Правила сохранены!")

    def open_editor(self, values=None, item_id=None):
        win = tk.Toplevel(self)
        win.title("Редактирование правила")

        labels = ["Мин", "Макс", "Сила", "Время", "Действие"]
        entries = []

        for i, label in enumerate(labels):
            tk.Label(win, text=label).grid(row=i, column=0, padx=5, pady=5)
            entry = tk.Entry(win)
            entry.grid(row=i, column=1, padx=5, pady=5)
            if values:
                entry.insert(0, values[i])
            entries.append(entry)

        def save():
            try:
                new_values = [
                    int(entries[0].get()),
                    int(entries[1].get()),
                    int(entries[2].get()) if entries[2].get() else "",
                    int(entries[3].get()) if entries[3].get() else "",
                    entries[4].get()
                ]
                if item_id:
                    self.tree.item(item_id, values=new_values)
                else:
                    self.tree.insert("", "end", values=new_values)
                win.destroy()
            except:
                messagebox.showerror("Ошибка", "Введите корректные числа")

        tk.Button(win, text="Сохранить", command=save).grid(row=5, columnspan=2, pady=10)
