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
import { initWebSocket, socket, vibrationQueue, updateQueueUI } from "/static/js/modules/websocket.js";
import {
    initVipPage,
    loadVipList
} from "/static/js/modules/vip.js";
import { initSidebar } from "/static/js/modules/sidebar.js";
import { classifyLog, loadLogs, initLogButtons, startLogAutoUpdate } from "/static/js/modules/logs.js";


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
   📦 3. Инициализация обработчиков
============================================================ */
function initHandlers() {
    initSidebar();
    initModeSwitch();
    initLogButtons(showToast);
    initQueueButtons();
    initGoalModal();
}

window.addEventListener("load", () => {

    // --- WebSocket ---
    initWebSocket(
        CURRENT_USER,
        CURRENT_MODE,
        CURRENT_PROFILE,
        reloadInnerContent,
        showToast
    );

    // --- Глобальные обработчики ---
    initHandlers();

    // --- SPA навигация ---
    initSidebarNavigation();

    // --- UI и данные ---
    loadQR();
    loadGoalFromServer();
    initTypeSelector();

    // --- Автообновление логов ---
    startLogAutoUpdate();

    // --- ENTER запускает поиск ---
    initSearchEnter();
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
            initSearchEnter(); 
            if (document.getElementById("logbox")) {
                lastLogCount = 0;   // ← ВАЖНО
            }


            setTimeout(() => {
                container.style.opacity = "1";

                if (document.querySelector(".rules-page")) {
                    initRulesPage(socket, showToast);
                    initRuleForms(CURRENT_PROFILE, socket, reloadInnerContent, showToast);
                    initRuleModals();
                    updateNewRuleFields();
                    loadLogs();
                }

                loadLogs();
                updateQueueUI();
                loadQR();
                loadGoalFromServer();
                initTypeSelector();
                updateGoalVisibility();

                initLogButtons();      // ← ДОБАВИТЬ
                initQueueButtons();    // ← ДОБАВИТЬ
                if (document.querySelector(".vip-grid")) initVipPage();

            }, 50);


        });
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
            initSearchEnter(); 
            setTimeout(() => {
                container.style.opacity = "1";

                if (callback) {
                    callback();
                } else {
                    if (document.querySelector(".rules-page")) {
                        initRulesPage(socket, showToast);
                        initRuleForms(CURRENT_PROFILE, socket, reloadInnerContent, showToast);
                        initRuleModals();
                        updateNewRuleFields();
                    }
                }

                setTimeout(loadLogs, 10);
                updateQueueUI();
                loadQR();
                loadGoalFromServer();
                initTypeSelector();
                updateGoalVisibility();

                initLogButtons();      // ← ДОБАВИТЬ
                initQueueButtons();    // ← ДОБАВИТЬ
                if (document.querySelector(".vip-grid")) initVipPage();

            }, 50);

        });
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

        vibrationQueue.length = 0;
        updateQueueUI();
        showToast("Очередь очищена ✅");
    };
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

window.refreshQR = refreshQR;
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
function initSearchEnter() {
    const searchInput = document.querySelector('input[name="q"]');
    if (!searchInput) return;

    searchInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
            e.preventDefault();
            doSearch();
        }
    });
}