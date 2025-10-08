import tkinter as tk
from tkinter import ttk, scrolledtext
import json
import subprocess
import winsound
from main_lov import get_qr_code

FILES_TO_CLEAR = [
    "donations.log",
    "vibration_queue.json",
    "vip_donaters.json",
    "toy_status.json",
]


def clear_all_files():
    for file in FILES_TO_CLEAR:
        try:
            if file == "vip_donaters.json":
                try:
                    with open(file, "r", encoding="utf-8") as f:
                        vip_data = json.load(f)
                except:
                    vip_data = {}

                new_data = {}
                for uid, info in vip_data.items():
                    if info.get("starred"):
                        info["total"] = 0
                        new_data[uid] = info

                with open(file, "w", encoding="utf-8") as f:
                    json.dump(new_data, f, indent=2, ensure_ascii=False)
            else:
                with open(file, "w", encoding="utf-8") as f:
                    if file.endswith(".json"):
                        f.write("{}")
                    else:
                        f.write("")
        except:
            pass

    # 👉 создаём флажок для main_lov
    with open("reset.flag", "w") as f:
        f.write("reset")

    print("🧹 Все файлы очищены (звёздочные донатеры сохранены)")



from rules_panel import RulesPanel
from vip_panel import VIPPanel

LOG_FILE = "donations.log"
TOY_STATUS_FILE = "toy_status.json"
QUEUE_FILE = "vibration_queue.json"
VIP_CFG = "vip_config.json"

main_process = None


# --- VIP порог ---
def get_vip_threshold():
    try:
        with open(VIP_CFG, "r", encoding="utf-8") as f:
            return json.load(f).get("vip_threshold", 3000)
    except:
        return 3000


# --- Обновление лога и VIP сообщений ---
def refresh_log(log_text):
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()[-300:]  # показываем только последние 300 строк

            # 👉 проверяем, был ли скролл внизу
            at_bottom = log_text.yview()[1] == 1.0

            log_text.delete(1.0, tk.END)

            # Цвета
            log_text.tag_config("blue", foreground="deepskyblue")
            log_text.tag_config("green", foreground="green")
            log_text.tag_config("red", foreground="red")
            log_text.tag_config("gold", foreground="gold", font=("Consolas", 10, "bold"))
            log_text.tag_config(
                "action",
                background="pink",
                foreground="black",
                font=("Consolas", 10, "bold")
            )

            # 👉 теперь вставляем строки В КОНЕЦ
            for line in lines:
                if "ДЕЙСТВИЕ:" in line:
                    log_text.insert(tk.END, line.strip() + "\n", "action")
                    continue

                parts = line.strip().split("|")
                if len(parts) >= 2:
                    try:
                        amount = int(parts[1].strip())
                    except:
                        amount = 0

                    if amount < 500:
                        tag = "blue"
                    elif amount < 1500:
                        tag = "green"
                    elif amount < 3000:
                        tag = "red"
                    else:
                        tag = "gold"

                    log_text.insert(tk.END, line.strip() + "\n", tag)
                else:
                    log_text.insert(tk.END, line.strip() + "\n")

            # 👉 если пользователь был внизу — автопрокрутка вниз
            if at_bottom:
                log_text.see(tk.END)

    except:
        log_text.delete(1.0, tk.END)


import webbrowser

def log_link(log_text, url):
    # создаём стиль для ссылок (синий + подчёркнутый)
    log_text.tag_config("link", foreground="blue", underline=True)

    # вставляем ссылку в конец лога
    log_text.insert(tk.END, f"Подключитесь к Lovense: {url}\n", "link")
    log_text.see(tk.END)

    # делаем её кликабельной
    def open_link(event):
        webbrowser.open(url)

    log_text.tag_bind("link", "<Button-1>", open_link)


# --- Обновление статуса игрушки ---
def update_status(status_label):
    try:
        with open(TOY_STATUS_FILE, "r", encoding="utf-8") as f:
            status = json.load(f)
            status_label.config(
                text=f"🔗 Подключено: {status['toy_id']} @ {status['domain']}:{status['port']}"
            )
    except:
        status_label.config(text="🔌 Игрушка не подключена")


def update_vip_chat(vip_text):
    vip_text.delete(1.0, tk.END)

    # Цвета
    vip_text.tag_config("gold", foreground="gold", font=("Consolas", 10, "bold"))

    try:
        with open("vip_donaters.json", "r", encoding="utf-8") as vf:
            vip_data = json.load(vf)
    except:
        vip_data = {}

    threshold = get_vip_threshold()
    vip_ids = [  
        uid
        for uid, info in vip_data.items()
        if info.get("total", 0) >= threshold or info.get("starred")
    ]

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                for uid in vip_ids:
                    if uid in line:
                        vip_text.insert("1.0", line.strip() + "\n", "gold")
                        break
    except FileNotFoundError:
        pass


# --- Обновление очереди ---
# def update_queue(queue_text):
#    try:
#        with open(QUEUE_FILE, "r", encoding="utf-8") as f:
#            queue = json.load(f)
#            queue_text.delete(1.0, tk.END)
#            if queue:
#                for i, task in enumerate(queue):
#                    queue_text.insert(
#                        tk.END,
#                        f"{i+1}. Сила: {task['strength']} | Время: {task['duration']} сек\n",
#                    )
#    except:
#        queue_text.delete(1.0, tk.END)


def auto_update(status_label, log_text, vip_text):
    refresh_log(log_text)  # общий лог
    update_vip_chat(vip_text)  # VIP‑чат
    update_status(status_label)  # статус
    # update_queue(queue_text)       # очередь

    status_label.after(10000, lambda: auto_update(status_label, log_text, vip_text))


def launch_main_program():
    global main_process
    if main_process is None or main_process.poll() is not None:
        main_process = subprocess.Popen(["python", "main_lov.py"])
        btn_launch.config(text="🟢 Программа запущена")

        # 👉 получаем ссылку и показываем в логе
        url = get_qr_code("qMGjSjH0zrDh-sgTCv5LLd4w3KQQWiKt8VWSlxHlsTkP5zT1YRh0NDMEhVj-rkOx")
        if url:
            log_link(log_text, url)

# --- Остановка основной программы ---
def stop_main_program():
    global main_process
    if main_process and main_process.poll() is None:
        main_process.terminate()
        main_process = None
        btn_launch.config(text="🚀 Запустить основную программу")


# --- GUI ---
root = tk.Tk()
root.title("Arina Project — GUI")
root.geometry("1000x700")

notebook = ttk.Notebook(root)
notebook.pack(fill="both", expand=True)

# --- 📋 Вкладка логов ---
main_frame = tk.Frame(notebook)
notebook.add(main_frame, text="📋 Лог")

status_label = tk.Label(main_frame, text="🔌 Игрушка не подключена", font=("Arial", 12))
status_label.pack(pady=5)

btn_launch = tk.Button(
    main_frame, text="🚀 Запустить основную программу", command=launch_main_program
)
btn_launch.pack(pady=5)

btn_stop = tk.Button(
    main_frame, text="⏹ Остановить программу", command=stop_main_program
)
btn_stop.pack(pady=5)

btn_clear_all = tk.Button(
    main_frame, text="🧹 Очистить все файлы", command=clear_all_files
)
btn_clear_all.pack(pady=5)

frame_logs = tk.Frame(main_frame)
frame_logs.pack(fill="both", expand=True)

log_text = scrolledtext.ScrolledText(
    frame_logs, width=70, height=25, font=("Consolas", 10)
)
log_text.pack(side="left", padx=10, pady=10, fill="both", expand=True)

vip_text = scrolledtext.ScrolledText(
    frame_logs, width=40, height=25, font=("Consolas", 10)
)
vip_text.pack(side="right", padx=10, pady=10, fill="both", expand=True)
vip_text.insert(tk.END, "🌟 VIP‑сообщения 🌟\n\n")

# --- 🛠️ Вкладка правил ---
rules_frame = RulesPanel(notebook)
notebook.add(rules_frame, text="🛠️ Правила")

# --- 🔁 Вкладка очереди ---
# queue_frame = tk.Frame(notebook)
# notebook.add(queue_frame, text="🔁 Очередь")

# queue_text = scrolledtext.ScrolledText(
#    queue_frame, width=90, height=25, font=("Consolas", 10)
# )
# queue_text.pack(padx=10, pady=10, fill="both", expand=True)

# --- 🌟 Вкладка VIP ---
vip_frame = VIPPanel(notebook)
notebook.add(vip_frame, text="🌟 VIP‑донатеры")

# --- Автообновление --- #queue_text
auto_update(status_label, log_text, vip_text)

root.mainloop()
