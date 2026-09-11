// static/js/modules/logs.js

/* ============================================================
   Логи — состояние
============================================================ */

let lastLogCount = 0;
let logInterval = null;

/* ============================================================
   Классификация логов
============================================================ */

export function classifyLog(log) {
    log = log.toLowerCase();

    if (log.includes("вибрация")) return "vibration";
    if (log.includes("колесо")) return "wheel";
    if (log.includes("действие")) return "action";
    if (log.includes("вошёл") || log.includes("вошел")) return "entry";
    if (log.includes("вышел")) return "exit";
    return "system";
}

/* ============================================================
   Загрузка логов (без дублирования)
============================================================ */

export async function loadLogs() {
    const box = document.getElementById("logbox");
    if (!box) return; // SPA может перерисовать страницу

    const res = await fetch("/logs_data");
    const data = await res.json();

    const logs = data.logs || [];

    // если logbox пустой — сбрасываем счётчик
    if (box.children.length === 0) {
        lastLogCount = 0;
    }

    const newLogs = logs.slice(lastLogCount);
    lastLogCount = logs.length;

    newLogs.forEach(log => {
        const div = document.createElement("div");
        const type = classifyLog(log);
        div.className = `event-item ${type}`;
        div.textContent = log;

        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    });
}

/* ============================================================
   Кнопки логов
============================================================ */

export function initLogButtons(showToast) {
    const clearLogsBtn = document.getElementById("clearLogsBtn");
    if (!clearLogsBtn) return;

    clearLogsBtn.onclick = () => {
        resetLogsCounter();

        const box = document.getElementById("logbox");
        if (box) box.innerHTML = "";

        fetch("/clear_logs", { method: "POST" })
            .then(() => showToast("Логи очищены ✅"))
            .catch(() => showToast("❌ Ошибка при очистке логов"));
    };
}

/* ============================================================
   Автообновление — запускается только один раз
============================================================ */

export function startLogAutoUpdate() {
    if (logInterval) return; // предотвращаем дублирование таймеров

    logInterval = setInterval(() => {
        const box = document.getElementById("logbox");
        if (box) loadLogs();
    }, 2000);
}

/* ============================================================
   Сброс счётчика
============================================================ */

export function resetLogsCounter() {
    lastLogCount = 0;
}
