// ===== ГЛОБАЛЬНЫЙ ПЕРЕХВАТ ВСЕХ ОШИБОК =====
window.onerror = function(message, source, lineno, colno, error) {
    console.error("GLOBAL ERROR:", { message, source, lineno, colno, error });
};

window.addEventListener("unhandledrejection", function(event) {
    console.error("UNHANDLED PROMISE REJECTION:", event.reason);
});

/* ============================================================
   📦 Импорты модулей
============================================================ */
import {
    initRulesPage,
    initRuleForms,
    initRuleModals,
    updateNewRuleFields
} from "/static/js/modules/rules.js";

import {
    initWebSocket,
    socket,
    vibrationQueue,
    updateQueueUI
} from "/static/js/modules/websocket.js";

import { initVipPage } from "/static/js/modules/vip.js";
import { initSidebar } from "/static/js/modules/sidebar.js";

import {
    loadLogs,
    initLogButtons,
    startLogAutoUpdate,
    resetLogsCounter
} from "/static/js/modules/logs.js";

import {
    updateGoalVisibility,
    updateGoalCircle,
    initGoalModal,
    openGoalModal,
    closeGoalModal,
    loadGoalFromServer
} from "/static/js/modules/goal.js";

import {
    showEntryPopup,
    hideEntryPopup,
    showToast
} from "/static/js/modules/ui.js";

import { initReactionsPage } from "/static/js/modules/reactions.js";
import { loadQR, refreshQR } from "/static/js/modules/qr.js";
import { initQueueButtons } from "/static/js/modules/queue.js";
import { initTypeSelector } from "/static/js/modules/type_selector.js";
import { showMemberCard, hideMemberCard } from "/static/js/modules/member_card.js";
import { initStatsPage } from "/static/js/modules/stats.js";
import { initModelSelector } from "/static/js/modules/model_selector.js";

/* ============================================================
   🌍 Глобальные функции для HTML
============================================================ */
window.showEntryPopup = showEntryPopup;
window.hideEntryPopup = hideEntryPopup;
window.showToast = showToast;
window.refreshQR = () => refreshQR(showToast);
window.openGoalModal = openGoalModal;
window.closeGoalModal = closeGoalModal;
window.hideMemberCard = hideMemberCard;
window.showMemberCard = showMemberCard;

/* ============================================================
   📌 Глобальные переменные
============================================================ */
let CURRENT_PAGE_URL = "/beta";

const app = document.getElementById("app");
const CURRENT_USER = app?.dataset.user || "";
let CURRENT_MODE = app?.dataset.mode || "public";
let CURRENT_PROFILE = app?.dataset.profile || "";

/* ============================================================
   🔧 Инициализация глобальных обработчиков
============================================================ */
function initHandlers() {
    initSidebar();
    initModeSwitch();

    initGoalModal(showToast, () =>
        loadGoalFromServer(updateGoalCircle, CURRENT_MODE)// FIXED
    );
}

/* ============================================================
   🧩 Инициализация контента после загрузки SPA
============================================================ */
function initPageAfterContent() {
    console.log("SPA: initPageAfterContent START");

    initSearchEnter();

    updateGoalVisibility(CURRENT_MODE);
    loadGoalFromServer(updateGoalCircle, CURRENT_MODE)// FIXED

    loadQR();
    initTypeSelector(updateNewRuleFields);

    if (document.getElementById("logbox")) {
        loadLogs();
        initLogButtons(showToast);
    }

    updateQueueUI();
    initQueueButtons(
        socket,
        vibrationQueue,
        updateQueueUI,
        showToast,
        CURRENT_USER,
        CURRENT_MODE,
        CURRENT_PROFILE
    );

    if (document.querySelector(".rules-page")) {
        initRulesPage(socket, showToast);
        initRuleForms(CURRENT_PROFILE, socket, reloadInnerContent, showToast);
        initRuleModals();
        updateNewRuleFields();
        loadLogs();
    }

    if (document.querySelector(".vip-grid")) {
        initVipPage();
    }

    if (document.querySelector(".reactions-page")) {
        initReactionsPage(showToast);
    }

    if (document.querySelector(".stats-page")) {
        initStatsPage();
    }

    initModelSelector();
}

/* ============================================================
   🚀 Старт приложения
============================================================ */
window.addEventListener("load", () => {
    initWebSocket(
        CURRENT_USER,
        CURRENT_MODE,
        CURRENT_PROFILE,
        reloadInnerContent,
        showToast
    );

    initHandlers();
    initSidebarNavigation();
    initPageAfterContent();
    startLogAutoUpdate();
});

/* ============================================================
   📦 SPA навигация
============================================================ */
function initSidebarNavigation() {
    const links = document.querySelectorAll(".sidebar-menu .sidebar-item");

    links.forEach(link => {
        link.addEventListener("click", e => {
            e.preventDefault();
            const href = link.getAttribute("href");
            if (!href) return;
            navigateSPA(href);
        });
    });
}

function navigateSPA(url) {
    console.log("SPA: navigate to", url);

    // --- Обновляем профиль при выборе модели ---
    const modelMatch = url.match(/model=([^&]+)/);
    if (modelMatch) {
        const selectedModel = modelMatch[1];
        CURRENT_PROFILE = `${selectedModel}_${CURRENT_MODE}`;
        console.log("SPA: switched profile →", CURRENT_PROFILE);
    }

    CURRENT_PAGE_URL = url;

    const container = document.querySelector(".content-inner");
    if (!container) {
        window.location.href = url;
        return;
    }

    container.style.opacity = "0";

    fetch(url)
        .then(r => {
            console.log("SPA: response status", r.status);
            return r.text();
        })
        .then(html => {
            console.log("SPA: HTML loaded, length =", html.length);

            const doc = new DOMParser().parseFromString(html, "text/html");
            const inner = doc.querySelector(".content-inner");

            if (!inner) {
                console.error("SPA: inner content NOT FOUND in loaded HTML");
                console.log("SPA: loaded HTML:", html);
                return;
            }

            // Вставляем только внутренний контент
            container.innerHTML = inner.innerHTML;
            
            // FIX: обновляем профиль после загрузки новой страницы
            const newApp = document.getElementById("app");
            if (newApp) {
                CURRENT_PROFILE = newApp.dataset.profile || CURRENT_PROFILE;
            }
            setTimeout(() => {
                console.log("SPA: calling initPageAfterContent()");
                initPageAfterContent();

                // --- Обновляем цель после загрузки ---
                updateGoalVisibility(CURRENT_MODE);
                loadGoalFromServer(updateGoalCircle, CURRENT_MODE);

                container.style.opacity = "1";
            }, 50);
        })
        .catch(err => {
            console.error("SPA FETCH ERROR:", err);
        });
}


window.navigateSPA = navigateSPA;

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
            if (data.status !== "ok") return;

            CURRENT_MODE = newMode;
            CURRENT_PROFILE = `${CURRENT_USER}_${CURRENT_MODE}`;

            updateGoalVisibility(CURRENT_MODE);
            loadGoalFromServer(updateGoalCircle, CURRENT_MODE)   // FIXED

            socket.send(JSON.stringify({
                type: "hello",
                role: "panel",
                profile_key: CURRENT_PROFILE
            }));

            reloadInnerContent(() => {
                updateGoalVisibility(CURRENT_MODE);
                loadLogs();

                if (document.querySelector(".rules-page")) {
                    initRulesPage(socket, showToast);
                    initRuleForms(CURRENT_PROFILE, socket, reloadInnerContent, showToast);
                    initRuleModals();
                    updateNewRuleFields();
                }

                if (document.querySelector(".vip-grid")) {
                    initVipPage();
                }

                if (document.querySelector(".reactions-page")) {
                    initReactionsPage(showToast);
                }
            });

            showToast(`Режим переключен: ${newMode}`);
        });
    };
}

/* ============================================================
   🔄 Обновление внутреннего контента
============================================================ */
function reloadInnerContent(callback) {
    const container = document.querySelector(".content-inner");
    if (!container) return;

    container.style.opacity = "0";

    fetch(CURRENT_PAGE_URL)   // FIXED — removed ?mode=
        .then(r => r.text())
        .then(html => {
            const doc = new DOMParser().parseFromString(html, "text/html");
            const inner = doc.querySelector(".content-inner");
            if (!inner) return;

            container.innerHTML = inner.innerHTML;

            setTimeout(() => {
                container.style.opacity = "1";

                if (callback) callback();

                initPageAfterContent();
            }, 50);
        });
}

window.reloadInnerContent = reloadInnerContent;

/* ============================================================
   🔍 Поиск по Enter
============================================================ */
function initSearchEnter() {
    const searchInput = document.querySelector('input[name="q"]');
    if (!searchInput) return;

    searchInput.addEventListener("keydown", e => {
        if (e.key === "Enter") {
            e.preventDefault();
            doSearch();
        }
    });
}