import { classifyLog } from "./utils.js";

let lastLogCount = 0;

if (!window._logsIntervalStarted) {
    window._logsIntervalStarted = true;
    setInterval(loadLogs, 2000);
}


export function loadLogs() {
    const box = document.getElementById("logbox");
    if (!box) return;

    fetch("/logs_data")
        .then(r => r.json())
        .then(data => {
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
        });
}

export function classifyLog(log) {
    log = log.toLowerCase();

    if (log.includes("вибрация")) return "vibration";
    if (log.includes("колесо")) return "wheel";
    if (log.includes("действие")) return "action";
    if (log.includes("вошёл") || log.includes("вошел")) return "entry";
    if (log.includes("вышел")) return "exit";
    return "system";
}
