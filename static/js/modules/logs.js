// logs.js — модуль цветных логов

let lastLogCount = 0;
let logInterval = null;

// Классификация логов по типам
export function classifyLog(log) {
    log = log.toLowerCase();

    if (log.includes("вибрация")) return "vibration";
    if (log.includes("колесо")) return "wheel";
    if (log.includes("действие")) return "action";
    if (log.includes("вошёл") || log.includes("вошел")) return "entry";
    if (log.includes("вышел")) return "exit";
    return "system";
}

// Загрузка логов
export async function loadLogs() {
    const box = document.getElementById("logbox");
    if (!box) return;

    const res = await fetch("/logs_data");
    const data = await res.json();

    const logs = data.logs || [];
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

export function initLogButtons(showToast) {
    const clearLogsBtn = document.getElementById("clearLogsBtn");
    if (!clearLogsBtn) return;

    clearLogsBtn.onclick = () => {
        resetLogsCounter();
        document.getElementById("logbox").innerHTML = "";

        fetch("/clear_logs", { method: "POST" })
            .then(() => showToast("Логи очищены ✅"))
            .catch(() => showToast("❌ Ошибка при очистке логов"));
    };
}


// Автообновление логов
export function startLogAutoUpdate() {
    if (logInterval) clearInterval(logInterval);
    logInterval = setInterval(loadLogs, 2000);
}
export function resetLogsCounter() {
    lastLogCount = 0;
}
