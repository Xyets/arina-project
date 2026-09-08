import {
    initRulesPage,
    initRuleForms,
    initRuleModals,
    updateRuleEditFields,
    updateNewRuleFields,
    updateSegmentFields,
    sendRuleCommand,
    createDeleteRule,
    createDeleteSegment
} from "/static/js/modules/rules.js";

let CURRENT_PAGE_URL = "/beta";

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

        const profile_key = CURRENT_PROFILE || `${CURRENT_USER}_${CURRENT_MODE}`;

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
    // Глобальные функции для HTML onclick
    window.deleteRule = createDeleteRule(socket, CURRENT_PROFILE, reloadInnerContent, showToast);
    window.deleteSegment = createDeleteSegment(socket, CURRENT_PROFILE, reloadInnerContent, showToast);

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
        updateGoalCircle(data.goal);
        return;
    }


    if (data.rules_update) {
        reloadInnerContent(() => {
            if (document.querySelector(".rules-page")) {
                initRuleForms(CURRENT_PROFILE, socket, reloadInnerContent, showToast);
                initRuleModals();
            }
        });
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

window.addEventListener("load", () => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
        connectWS();
    }
    initHandlers();
    initSidebarNavigation();
    loadQR();
    loadGoalFromServer();   // ← исправлено

    initTypeSelector();   // ← ДОБАВИТЬ
});


/* ============================================================
   📦 SPA навигация
============================================================ */
function initSidebarNavigation() {
    const links = document.querySelectorAll(".sidebar-menu .sidebar-item");

    links.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const url = link.getAttribute("href");
            navigateSPA(url);
        });
    });
}

function navigateSPA(url) {
    CURRENT_PAGE_URL = url;

    const container = document.querySelector(".content-inner");
    if (!container) {
        window.location.href = url;
        return;
    }

    container.style.opacity = "0";

    fetch(url + "?mode=" + CURRENT_MODE)
        .then(r => r.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");
            const newContent = doc.querySelector(".content-inner").innerHTML;

            container.innerHTML = newContent;

            setTimeout(() => {
                container.style.opacity = "1";

                if (document.querySelector(".rules-page")) {
                    initRulesPage(socket, showToast);
                    initRuleForms(CURRENT_PROFILE, socket, reloadInnerContent, showToast);
                    initRuleModals();
                    updateNewRuleFields();

                }

                loadLogs();
                updateQueueUI();
                loadQR();
                loadGoalFromServer();
                initTypeSelector();
                updateGoalVisibility();

            }, 50);
        });
}


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
                updateGoalVisibility();
                CURRENT_PROFILE = `${CURRENT_USER}_${CURRENT_MODE}`;

                // 🔥 сразу загружаем актуальную цель
                loadGoalFromServer();

                socket.send(JSON.stringify({
                    type: "hello",
                    role: "panel",
                    profile_key: CURRENT_PROFILE
                }));

                reloadInnerContent(() => {
                    updateGoalVisibility();

                    // 🔥 сразу обновляем логи после смены режима
                    loadLogs();

                    if (document.querySelector(".rules-page")) {
                        initRulesPage(socket, showToast);   // ← обязательно
                        initRuleForms(CURRENT_PROFILE, socket, reloadInnerContent, showToast);
                        initRuleModals();
                    }
                });
                showToast(`Режим переключен: ${newMode}`);
            }

        });
    };
}

/* ============================================================
   🔄 Мгновенное обновление внутреннего контента
============================================================ */
function reloadInnerContent(callback) {
    const container = document.querySelector(".content-inner");
    if (!container) return;

    container.style.opacity = "0";

    fetch(CURRENT_PAGE_URL + "?mode=" + CURRENT_MODE)
        .then(r => r.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");

            const newContent = doc.querySelector(".content-inner").innerHTML;
            container.innerHTML = newContent;

            setTimeout(() => {
                container.style.opacity = "1";

                if (callback) {
                    callback();
                } else {
                    if (document.querySelector(".rules-page")) {
                        initRulesPage(socket, showToast);   // ← ДОБАВИТЬ ЭТУ СТРОКУ
                        initRuleForms(CURRENT_PROFILE, socket, reloadInnerContent, showToast);
                        initRuleModals();
                        updateNewRuleFields();
                    }
                }

                loadLogs();
                updateQueueUI();
                loadQR();
                loadGoalFromServer();
                initTypeSelector();
                updateGoalVisibility();

            }, 50);
        });
}


/* ============================================================
   📜 Цветные логи
============================================================ */

function classifyLog(log) {
    log = log.toLowerCase();

    if (log.includes("вибрация")) return "vibration";
    if (log.includes("колесо")) return "wheel";
    if (log.includes("действие")) return "action";
    if (log.includes("вошёл") || log.includes("вошел")) return "entry";
    if (log.includes("вышел")) return "exit";
    return "system";
}

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
        const type = classifyLog(log);
        div.className = `event-item ${type}`;
        div.textContent = log;

        box.appendChild(div);
        box.scrollTop = box.scrollHeight;
    });
}

/* ============================================================
   🔁 Очередь вибраций — стеклянный стиль
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
        .map((v, i) => `
            <div class="queue-item">
                <strong>#${i + 1}</strong> • сила ${v.strength}, ${v.duration}s
            </div>
        `)
        .join("");
}

function initQueueButtons() {
    const clearQueueBtn = document.getElementById("clearQueueBtn");
    if (!clearQueueBtn) return;

    clearQueueBtn.onclick = () => {
        const profile_key = CURRENT_PROFILE || `${CURRENT_USER}_${CURRENT_MODE}`;

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
   ⏱ Таймер вибрации
============================================================ */
function startVibrationTimer(duration, strength) {

    if (window._vibrationTimerActive) {
        console.warn("Таймер уже активен — второй не запускаем");
        return;
    }
    window._vibrationTimerActive = true;

    const container = document.getElementById("vibrationOverlay");
    if (!container) return;

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
            window._vibrationTimerActive = false;
        } else {
            timeSpan.textContent = Math.ceil(remaining);
            progressFill.style.width = `${(remaining / duration) * 100}%`;
        }
    }, 1000);

    box.querySelector(".vibration-stop-btn").onclick = () => {
        sendStop();
        clearInterval(interval);
        box.remove();
        window._vibrationTimerActive = false;
    };
}

function sendStop() {
    const profile_key = CURRENT_PROFILE || `${CURRENT_USER}_${CURRENT_MODE}`;

    socket.send(JSON.stringify({
        type: "stop",
        user: CURRENT_USER,
        profile_key
    }));
}

/* ============================================================
   🔔 Popup
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
   🔔 Toast
============================================================ */
function showToast(msg) {
    const toast = document.getElementById("toast");
    toast.textContent = msg;
    toast.classList.add("show");
    setTimeout(() => toast.classList.remove("show"), 3000);
}


function updateGoalVisibility() {
    const circle = document.getElementById("goalCircle");

    if (!circle) return;

    if (CURRENT_MODE === "public") {
        circle.style.display = "flex";
    } else {
        circle.style.display = "none";
    }
}

/* ============================================================
   🎯 Постоянная цель
============================================================ */
/* ============================================================
   🎯 Круглая цель — Apple Ring
============================================================ */
function updateGoalCircle(newGoal = null) {
    if (newGoal) goal = newGoal;
    if (CURRENT_MODE !== "public") return;


    const ring = document.querySelector(".goal-progress-ring");
    const cur = document.getElementById("goalCurrent");
    const tgt = document.getElementById("goalTarget");
    const title = document.getElementById("goalCircleTitle");

    if (!ring || !cur || !tgt || !title) return;

    const percent = goal.target > 0 ? (goal.current / goal.target) : 0;
    const circumference = 264; // r = 42
    const offset = circumference - (circumference * percent);


    ring.style.strokeDashoffset = offset;
    cur.textContent = goal.current;
    tgt.textContent = goal.target;
    title.textContent = goal.title || "Цель";
}




function initGoalModal() {
    const modal = document.getElementById("goalModal");
    if (!modal) return;

    const form = document.getElementById("goalForm");

    form.onsubmit = async (e) => {
        e.preventDefault();

        const formData = new FormData(form);

        const res = await fetch("/goal_new", {
            method: "POST",
            body: formData
        });

        const data = await res.json();

        if (data.status === "ok") {
            closeGoalModal();
            showToast("Цель обновлена 🎯");

            // 🔥 сразу подтягиваем актуальную цель с сервера
            loadGoalFromServer();
        } else {
            showToast(data.message || "Ошибка сохранения цели");
        }
    };
}



function openGoalModal() {
    document.getElementById("goalModal").classList.add("show");
}

function closeGoalModal() {
    document.getElementById("goalModal").classList.remove("show");
}

async function loadGoalFromServer() {
    if (CURRENT_MODE !== "public") return;
    try {
        const res = await fetch("/goal_data");
        const data = await res.json();

        // data: { title, current, target }
        updateGoalCircle(data);   // ← правильный вызов
    } catch (e) {
        console.error("Ошибка загрузки цели:", e);
    }
}



/* ============================================================
   📱 QR-код — стабильный
============================================================ */
let savedQR = localStorage.getItem("qr_code");

function loadQR() {
    const img = document.getElementById("qrImage");
    if (!img) return;

    if (savedQR) {
        img.src = savedQR;
        return;
    }

    fetch("/qr_generate")
        .then(r => r.json())
        .then(data => {
            savedQR = data.qr;
            localStorage.setItem("qr_code", savedQR);
            img.src = savedQR;
        });
}

function refreshQR() {
    const img = document.getElementById("qrImage");
    if (!img) return;

    fetch("/qr_generate?refresh=1")
        .then(r => r.json())
        .then(data => {
            savedQR = data.qr;
            localStorage.setItem("qr_code", savedQR);
            img.src = savedQR;
            showToast("QR‑код обновлён");
        });
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
/* ============================================================
   🎛 Кастомный селект типа (всегда активный)
============================================================ */
function initTypeSelector() {
    const typeSelect = document.getElementById("typeSelect");
    const typeDisplay = document.getElementById("typeDisplay");
    const typeOptions = document.getElementById("typeOptions");

    if (!typeSelect || !typeDisplay || !typeOptions) return;

    typeDisplay.onclick = () => {
        typeOptions.style.display =
            typeOptions.style.display === "flex" ? "none" : "flex";
    };

    typeOptions.querySelectorAll(".option").forEach(opt => {
        opt.onclick = () => {
            const value = opt.dataset.value;
            typeDisplay.textContent = opt.textContent;
            typeOptions.style.display = "none";

            document.getElementById("new_action_type").value = value;
            updateNewRuleFields();
        };
    });

    function typeSelectorGlobalHandler(e) {
        if (!typeSelect.contains(e.target)) {
            typeOptions.style.display = "none";
        }
    }

    document.removeEventListener("click", typeSelectorGlobalHandler);
    document.addEventListener("click", typeSelectorGlobalHandler);

}
/* ============================================================
   👑 VIP — модуль для vip_beta.html
============================================================ */

let VIP_SORT = "total";
let VIP_DELETE_ID = null;

/* ------------------------------------------------------------
   ИНИЦИАЛИЗАЦИЯ СТРАНИЦЫ VIP
------------------------------------------------------------ */
function initVipPage() {
    if (!document.querySelector(".vip-grid")) return;

    initVipForms();
    initVipSortButtons();
    initVipSearch();
    initVipModals();

    loadVipList();
}

/* ------------------------------------------------------------
   ЗАГРУЗКА СПИСКА VIP
------------------------------------------------------------ */
async function loadVipList() {
    try {
        const res = await fetch("/vip_data");
        const data = await res.json();

        renderVipCards(Object.entries(data.members));
        sortVipList(VIP_SORT);
    } catch (e) {
        console.error("VIP load error", e);
    }
}

/* ------------------------------------------------------------
   РЕНДЕР КАРТОЧЕК
------------------------------------------------------------ */
function renderVipCards(list) {
    const grid = document.getElementById("vipGrid");
    grid.innerHTML = "";

    list.forEach(([user_id, info]) => {
        const rawDate = info.last_login || "";
        const d = rawDate ? new Date(rawDate.replace(" ", "T")) : null;

        const formattedDate =
            d && !isNaN(d.getTime())
                ? d.toLocaleString("ru-RU", {
                      day: "numeric",
                      month: "long",
                      hour: "2-digit",
                      minute: "2-digit"
                  })
                : rawDate;

        const card = document.createElement("div");
        card.className = "vip-card" + (info.blocked ? " blocked" : "");
        card.id = "vip_" + user_id;

        card.innerHTML = `
            <form class="vip-form" data-id="${user_id}">
                <input type="text" name="name" value="${info.name}" placeholder="Имя">

                <input type="text" name="notes" value="${info.notes || ""}" placeholder="Заметки">

                <div class="meta">
                    💗 ${info.total} | 📅 ${info.login_count} входов<br>
                    🕒 Последний визит:
                    <span class="date" data-last-login="${rawDate}">${formattedDate}</span><br>
                    🆔 ID: <code>${user_id}</code>
                </div>

                <div class="actions">
                    <button type="submit">💾 Сохранить</button>
                    <button type="button" class="vip-delete-btn" data-id="${user_id}">🗑️ Удалить</button>
                </div>
            </form>
        `;

        grid.appendChild(card);
    });

    initVipForms();
    initVipDeleteButtons();
}

/* ------------------------------------------------------------
   СОХРАНЕНИЕ VIP
------------------------------------------------------------ */
function initVipForms() {
    document.querySelectorAll(".vip-form").forEach(form => {
        form.addEventListener("submit", async (e) => {
            e.preventDefault();

            const userId = form.dataset.id;
            const formData = new FormData(form);

            try {
                const res = await fetch("/vip", {
                    method: "POST",
                    body: formData
                });

                if (res.ok) {
                    await refreshVipCard(userId);
                    sortVipList(VIP_SORT);
                    showToast("Сохранено");
                } else {
                    showToast("Ошибка сохранения");
                }
            } catch {
                showToast("Ошибка сохранения");
            }
        });
    });
}

/* ------------------------------------------------------------
   ОБНОВЛЕНИЕ ОДНОЙ КАРТОЧКИ
------------------------------------------------------------ */
async function refreshVipCard(userId) {
    try {
        const res = await fetch("/vip_data");
        const data = await res.json();
        const info = data.members[userId];
        if (!info) return;

        const rawDate = info.last_login || "";
        const d = rawDate ? new Date(rawDate.replace(" ", "T")) : null;

        const formattedDate =
            d && !isNaN(d.getTime())
                ? d.toLocaleString("ru-RU", {
                      day: "numeric",
                      month: "long",
                      hour: "2-digit",
                      minute: "2-digit"
                  })
                : rawDate;

        const card = document.getElementById("vip_" + userId);

        card.innerHTML = `
            <form class="vip-form" data-id="${userId}">
                <input type="text" name="name" value="${info.name}" placeholder="Имя">

                <input type="text" name="notes" value="${info.notes || ""}" placeholder="Заметки">

                <div class="meta">
                    💗 ${info.total} | 📅 ${info.login_count} входов<br>
                    🕒 Последний визит:
                    <span class="date" data-last-login="${rawDate}">${formattedDate}</span><br>
                    🆔 ID: <code>${userId}</code>
                </div>

                <div class="actions">
                    <button type="submit">💾 Сохранить</button>
                    <button type="button" class="vip-delete-btn" data-id="${userId}">🗑️ Удалить</button>
                </div>
            </form>
        `;

        initVipForms();
        initVipDeleteButtons();
    } catch (e) {}
}

/* ------------------------------------------------------------
   СОРТИРОВКА
------------------------------------------------------------ */
function initVipSortButtons() {
    document.querySelectorAll(".vip-sort-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            VIP_SORT = btn.dataset.sort;
            sortVipList(VIP_SORT);
        });
    });
}

function sortVipList(sortBy) {
    const grid = document.getElementById("vipGrid");
    const cards = Array.from(grid.children);

    cards.sort((a, b) => {
        const dateA = new Date(a.querySelector(".date")?.dataset.lastLogin?.replace(" ", "T") || 0);
        const dateB = new Date(b.querySelector(".date")?.dataset.lastLogin?.replace(" ", "T") || 0);

        const metaA = a.querySelector(".meta").textContent;
        const metaB = b.querySelector(".meta").textContent;

        const visitsA = parseInt((metaA.match(/📅\s*(\d+)\s*вход/) || [])[1]);
        const visitsB = parseInt((metaB.match(/📅\s*(\d+)\s*вход/) || [])[1]);

        const totalA = parseFloat((metaA.match(/💗\s*([\d\.]+)/) || [])[1]);
        const totalB = parseFloat((metaB.match(/💗\s*([\d\.]+)/) || [])[1]);

        if (sortBy === "last_login") return dateB - dateA;
        if (sortBy === "login_count") return (visitsB || 0) - (visitsA || 0);
        if (sortBy === "total") return (totalB || 0) - (totalA || 0);

        return 0;
    });

    grid.innerHTML = "";
    cards.forEach(c => grid.appendChild(c));
}

/* ------------------------------------------------------------
   ПОИСК
------------------------------------------------------------ */
function initVipSearch() {
    const input = document.getElementById("vipSearchInput");
    const btn = document.getElementById("vipSearchBtn");

    btn.onclick = doVipSearch;
    input.oninput = () => {
        if (input.value.trim() === "") loadVipList();
    };
}

async function doVipSearch() {
    const q = document.getElementById("vipSearchInput").value.trim().toLowerCase();
    if (!q) return loadVipList();

    const res = await fetch("/vip_data");
    const data = await res.json();

    const filtered = Object.entries(data.members).filter(([id, info]) => {
        const text = (id + " " + info.name + " " + info.notes).toLowerCase();
        return text.includes(q);
    });

    renderVipCards(filtered);
    sortVipList(VIP_SORT);
}

/* ------------------------------------------------------------
   МОДАЛКА УДАЛЕНИЯ
------------------------------------------------------------ */
function initVipModals() {
    const yesBtn = document.getElementById("vipDeleteYes");
    yesBtn.onclick = () => {
        if (!VIP_DELETE_ID) return;
        deleteVipMember(VIP_DELETE_ID);
        closeVipDeleteModal();
    };
}

function initVipDeleteButtons() {
    document.querySelectorAll(".vip-delete-btn").forEach(btn => {
        btn.onclick = () => {
            VIP_DELETE_ID = btn.dataset.id;
            openVipDeleteModal();
        };
    });
}

function openVipDeleteModal() {
    document.getElementById("vipDeleteModal").classList.add("show");
}

function closeVipDeleteModal() {
    document.getElementById("vipDeleteModal").classList.remove("show");
    VIP_DELETE_ID = null;
}

/* ------------------------------------------------------------
   УДАЛЕНИЕ VIP
------------------------------------------------------------ */
async function deleteVipMember(userId) {
    try {
        const res = await fetch("/remove_member", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: "user_id=" + encodeURIComponent(userId)
        });

        const data = await res.json();

        if (data.status === "ok") {
            document.getElementById("vip_" + userId)?.remove();
            sortVipList(VIP_SORT);
            showToast("Удалено");
        } else {
            showToast("Ошибка удаления");
        }
    } catch {
        showToast("Ошибка удаления");
    }
}

/* ------------------------------------------------------------
   WEBSOCKET — обновление VIP
------------------------------------------------------------ */
function vipWebSocketUpdate(data) {
    if (data.vip_update) {
        loadVipList();
    }
}