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
   🔧 Инициализация глобальных обработчиков (то, что не зависит от SPA)
============================================================ */
function initHandlers() {
    initSidebar();
    initModeSwitch();

    // Модал цели — глобальный, не зависит от конкретной вкладки
    initGoalModal(showToast, () =>
        loadGoalFromServer(updateGoalCircle, CURRENT_MODE)
    );
}

/* ============================================================
   🧩 Инициализация контента после загрузки/перерисовки .content-inner
   (единая точка входа для SPA)
============================================================ */
function initPageAfterContent() {
    // Поиск
    initSearchEnter();

    // Видимость цели и сама цель
    updateGoalVisibility(CURRENT_MODE);
    loadGoalFromServer(updateGoalCircle, CURRENT_MODE);

    // QR
    loadQR();

    // Типы правил
    initTypeSelector(updateNewRuleFields);

    // Логи и кнопки логов
    if (document.getElementById("logbox")) {
        loadLogs();
        initLogButtons(showToast);
    }

    // Очередь вибраций
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

    // Страница правил
    if (document.querySelector(".rules-page")) {
        initRulesPage(socket, showToast);
        initRuleForms(CURRENT_PROFILE, socket, reloadInnerContent, showToast);
        initRuleModals();
        updateNewRuleFields();
        loadLogs();
    }

    // Страница VIP
    if (document.querySelector(".vip-grid")) {
        initVipPage();
    }
    // Страница реакций
    if (document.querySelector(".reactions-page")) {
        initReactionsPage(showToast);
    }

    // Страница статистики
    if (document.querySelector(".stats-page")) {
        initStatsPage();
    }

}

/* ============================================================
   🚀 Старт приложения
============================================================ */
window.addEventListener("load", () => {
    // WebSocket — один раз за жизнь страницы
    initWebSocket(
        CURRENT_USER,
        CURRENT_MODE,
        CURRENT_PROFILE,
        reloadInnerContent,
        showToast
    );

    initHandlers();
    initSidebarNavigation();

    // Первичная инициализация контента главной страницы
    initPageAfterContent();

    // Автообновление логов
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
    CURRENT_PAGE_URL = url;

    const container = document.querySelector(".content-inner");
    if (!container) {
        window.location.href = url;
        return;
    }

    container.style.opacity = "0";

    fetch(`${url}?mode=${CURRENT_MODE}`)
        .then(r => r.text())
        .then(html => {
            const doc = new DOMParser().parseFromString(html, "text/html");
            const inner = doc.querySelector(".content-inner");
            if (!inner) return;

            container.innerHTML = inner.innerHTML;

            // Сброс счётчика логов при переходе
            if (document.getElementById("logbox")) {
                resetLogsCounter();
            }

            setTimeout(() => {
                container.style.opacity = "1";
                initPageAfterContent();
            }, 50);
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
            loadGoalFromServer(updateGoalCircle, CURRENT_MODE);

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
                // Страница реакций
                if (document.querySelector(".reactions-page")) {
                    initReactionsPage(showToast);
                }


                initPageAfterContent();
            });

            showToast(`Режим переключен: ${newMode}`);
        });
    };
}

/* ============================================================
   🔄 Обновление внутреннего контента (используется WebSocket и режим)
============================================================ */
function reloadInnerContent(callback) {
    const container = document.querySelector(".content-inner");
    if (!container) return;

    container.style.opacity = "0";

    fetch(`${CURRENT_PAGE_URL}?mode=${CURRENT_MODE}`)
        .then(r => r.text())
        .then(html => {
            const doc = new DOMParser().parseFromString(html, "text/html");
            const inner = doc.querySelector(".content-inner");
            if (!inner) return;

            container.innerHTML = inner.innerHTML;

            setTimeout(() => {
                container.style.opacity = "1";

                // Сначала пользовательский callback (если есть)
                if (callback) {
                    callback();
                }

                // Затем общая инициализация контента
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
