/* ============================================================
   📌 0. Инициализация данных из HTML
============================================================ */
const app = document.getElementById("app");
const CURRENT_USER = app?.dataset.user || "";
let CURRENT_MODE = app?.dataset.mode || "public";
let CURRENT_PROFILE = app?.dataset.profile || "";

// глобальная цель
let goal = {
    title: "",
    current: 0,
    target: 0
};

/* ============================================================
   📡 1. WebSocket подключение
============================================================ */
let socket = null;
let wsReconnectAttempts = 0;
const WS_MAX_RECONNECT = 10;

function connectWS() {
    if (socket && socket.readyState === WebSocket.OPEN) return;

    const wsUrl = `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/ws`;
    socket = new WebSocket(wsUrl);

    socket.onopen = () => {
        console.log("WS connected");
        wsReconnectAttempts = 0;

        const profile_key = `${CURRENT_USER}_${CURRENT_MODE}`;

        socket.send(JSON.stringify({
            type: "hello",
            role: "panel",
            profile_key
        }));

        if (socket._pingInterval) clearInterval(socket._pingInterval);
        socket._pingInterval = setInterval(() => {
            if (socket.readyState === WebSocket.OPEN) {
                socket.send(JSON.stringify({ type: "ping" }));
            }
        }, 30000);
    };

    socket.onclose = () => {
        console.log("WS closed");

        if (socket._pingInterval) clearInterval(socket._pingInterval);

        if (wsReconnectAttempts < WS_MAX_RECONNECT) {
            wsReconnectAttempts++;
            setTimeout(connectWS, 2000);
        }
    };

    socket.onmessage = (event) => {
        let data;
        try { data = JSON.parse(event.data); }
        catch { return; }

        handleWSMessage(data);
    };
}

connectWS();

/* ============================================================
   📡 2. Обработка входящих WS сообщений
============================================================ */
function handleWSMessage(data) {
    console.log("WS:", data);

    if (data.type === "refresh_logs") {
        loadLogs();
        return;
    }

    if (data.status === "hello_ok") {
        socket.send(JSON.stringify({
            type: "get_queue",
            profile_key: `${CURRENT_USER}_${CURRENT_MODE}`
        }));
        return;
    }

    if (data.vibration) {
        startVibrationTimer(data.vibration.duration, data.vibration.strength);
        return;
    }

    if (data.queue_update) {
        vibrationQueue = (data.queue || []).map(v => ({
            strength: v[0],
            duration: v[1]
        }));
        updateQueueUI();
        return;
    }

    if (data.entry) {
        showEntryPopup(`
            👤 <strong>${data.entry.name}</strong><br>
            🔢 Визитов: ${data.entry.visits}<br>
            💗 Чаевых всего: ${data.entry.total_tips}<br>
            📝 Заметки: ${data.entry.notes || "нет"}
        `);
        return;
    }

    if (data.goal_update) {
        updateGoalUI(data.goal);
        return;
    }
}

/* ============================================================
   📦 3. Инициализация обработчиков
============================================================ */
function initHandlers() {
    initSidebarCollapse();
    initModeSwitch();
    initLogButtons();
    initQueueButtons();
    initGoalModal();
}

window.addEventListener("load", initHandlers);

/* ============================================================
   📦 Sidebar collapse
============================================================ */
function initSidebarCollapse() {
    const sidebar = document.getElementById("sidebar");
    const sidebarLogo = document.getElementById("sidebarLogo");

    if (sidebar && sidebarLogo) {
        sidebarLogo.onclick = () => sidebar.classList.toggle("collapsed");
    }
}

/* ============================================================
   🔄 Переключатель режима
============================================================ */
function initModeSwitch() {
    const modeSwitch = document.getElementById("modeSwitch");
    if (!modeSwitch) return;

    modeSwitch.onchange = () => {
        const newMode = modeSwitch.checked ? "private" : "public";

        socket.send(JSON.stringify({
            type: "set_mode",
            user: CURRENT_USER,
            mode: newMode
        }));

        fetch("/set_mode", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ mode: newMode })
        })
        .then(r => r.json())
        .then(data => {
            if (data.status === "ok") {
                CURRENT_MODE = newMode;
                reloadInnerContent();
                showToast(`Режим переключен: ${newMode}`);
            }
        });
    };
}

/* ============================================================
   🔄 Мгновенное обновление внутреннего контента
============================================================ */
function reloadInnerContent() {
    const container = document.querySelector(".content-inner");
    if (!container) return;

    container.style.opacity = "0";

    fetch(window.location.pathname)
        .then(r => r.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");

            const newContent = doc.querySelector(".content-inner").innerHTML;

            container.innerHTML = newContent;

            setTimeout(() => {
                container.style.opacity = "1";
            }, 50);

            initHandlers();
            loadLogs();
            updateQueueUI();
        });
}

/* ============================================================
   📜 4. Логи
============================================================ */
let lastLogCount = 0;
let logInterval = setInterval(loadLogs, 2000);

async function loadLogs() {
    const box = document.getElementById("logbox");
    if (!box) return;

    const res = await fetch("/logs_data");
    const data = await res.json();

    const logs = data.logs || [];
    const newLogs = logs.slice(lastLogCount);
    lastLogCount = logs.length;

    newLogs.forEach(log => {
        const div = document.createElement("div");
        div.className = "event-item";
        div.textContent = log;
        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    });
}

/* ============================================================
   🔁 5. Очередь вибраций
============================================================ */
let vibrationQueue = [];

function updateQueueUI() {
    const box = document.getElementById("queuebox");
    if (!box) return;

    if (vibrationQueue.length === 0) {
        box.innerHTML = `<div class="empty">Очередь пуста</div>`;
        return;
    }

    box.innerHTML = vibrationQueue
        .map((v, i) => `<div>#${i + 1} → сила: ${v.strength}, время: ${v.duration}s</div>`)
        .join("");
}

function initQueueButtons() {
    const clearQueueBtn = document.getElementById("clearQueueBtn");
    if (!clearQueueBtn) return;

    clearQueueBtn.onclick = () => {
        const profile_key = `${CURRENT_USER}_${CURRENT_MODE}`;

        socket.send(JSON.stringify({
            type: "clear_queue",
            profile_key
        }));

        vibrationQueue = [];
        updateQueueUI();
        showToast("Очередь очищена ✅");
    };
}

/* ============================================================
   ⏱ 6. Таймер вибрации
============================================================ */
function startVibrationTimer(duration, strength) {
    const container = document.getElementById("vibrationTimersContainer");
    const box = document.createElement("div");
    box.className = "vibration-timer";

    box.innerHTML = `
        <div class="vibration-title">💖 Вибрация • Сила ${strength}</div>
        <div class="vibration-time">Осталось: <span class="time">${Math.ceil(duration)}</span> сек</div>
        <div class="vibration-progress"><div class="vibration-progress-fill"></div></div>
        <button class="vibration-stop-btn">Остановить</button>
    `;

    container.appendChild(box);

    let remaining = duration;
    const timeSpan = box.querySelector(".time");
    const progressFill = box.querySelector(".vibration-progress-fill");

    const interval = setInterval(() => {
        remaining -= 1;

        if (remaining <= 0) {
            clearInterval(interval);
            box.remove();
        } else {
            timeSpan.textContent = Math.ceil(remaining);
            progressFill.style.width = `${(remaining / duration) * 100}%`;
        }
    }, 1000);

    box.querySelector(".vibration-stop-btn").onclick = () => {
        sendStop();
        clearInterval(interval);
        box.remove();
    };
}

function sendStop() {
    const profile_key = `${CURRENT_USER}_${CURRENT_MODE}`;

    socket.send(JSON.stringify({
        type: "stop",
        user: CURRENT_USER,
        profile_key
    }));
}

/* ============================================================
   🔔 7. Popup
============================================================ */
function showEntryPopup(message) {
    const popup = document.getElementById("entryPopup");
    popup.innerHTML = `<div>${message}</div><button onclick="hideEntryPopup()">ОК</button>`;
    popup.classList.add("show");

    let hideTimer = setTimeout(hideEntryPopup, 8000);

    popup.onmouseenter = () => clearTimeout(hideTimer);
    popup.onmouseleave = () => hideTimer = setTimeout(hideEntryPopup, 8000);
}

function hideEntryPopup() {
    const popup = document.getElementById("entryPopup");
    popup.classList.remove("show");
}

/* ============================================================
   🔔 8. Toast
============================================================ */
function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3000);
}

/* ============================================================
   🎯 9. Цель
============================================================ */
function updateGoalUI(newGoal = null) {
    if (newGoal) goal = newGoal;

    const fillV = document.getElementById("goalFillVertical");
    const cur = document.getElementById("goalCurrent");
    const tgt = document.getElementById("goalTarget");

    if (!fillV || !cur || !tgt) return;

    const percent = goal.target > 0 ? (goal.current / goal.target) * 100 : 0;

    fillV.style.height = Math.min(percent, 100) + "%";
    cur.textContent = goal.current;
    tgt.textContent = goal.target;
}

function initGoalModal() {
    const modal = document.getElementById("goalModal");
    if (!modal) return;

    const form = document.getElementById("goalForm");
    form.onsubmit = (e) => {
        e.preventDefault();

        const formData = new FormData(form);
        const title = formData.get("title");
        const target = Number(formData.get("target"));

        socket.send(JSON.stringify({
            type: "set_goal",
            user: CURRENT_USER,
            title,
            target
        }));

        closeGoalModal();
    };
}

function openGoalModal() {
    document.getElementById("goalModal").classList.add("show");
}

function closeGoalModal() {
    document.getElementById("goalModal").classList.remove("show");
}

/* ============================================================
   🧹 10. Очистка логов
============================================================ */
function initLogButtons() {
    const clearLogsBtn = document.getElementById("clearLogsBtn");
    if (!clearLogsBtn) return;

    clearLogsBtn.onclick = () => {
        lastLogCount = 0;
        document.getElementById("logbox").innerHTML = "";

        fetch("/clear_logs", { method: "POST" })
            .then(() => showToast("Логи очищены ✅"))
            .catch(() => showToast("❌ Ошибка при очистке логов"));
    };
}
