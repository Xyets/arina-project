import {
    initRulesPage,
    initRuleForms,
    initRuleModals,
    updateNewRuleFields
} from "/static/js/modules/rules.js";

import {
    initWebSocket,
    socket,
    updateQueueUI
} from "/static/js/modules/websocket.js";

import { initVipPage } from "/static/js/modules/vip.js";
import { initQueueButtons } from "/static/js/modules/queue.js";

import {
    loadQR,
    initLogButtons,
    initTypeSelector,
    initSearchEnter,
    loadLogs
} from "/static/js/modules/core.js";

import {
    updateGoalVisibility,
    updateGoalCircle,
    initGoalModal,
    loadGoalFromServer
} from "/static/js/modules/goal.js";

import { initSidebarCollapse, initSidebarNavigation } from "/static/js/modules/sidebar.js";
import { showToast } from "/static/js/modules/toast.js";

let CURRENT_PAGE_URL = "/beta";

/* ============================================================
   📌 0. Инициализация данных из HTML
============================================================ */
const app = document.getElementById("app");
const CURRENT_USER = app?.dataset.user || "";
let CURRENT_MODE = app?.dataset.mode || "public";
let CURRENT_PROFILE = app?.dataset.profile || "";

/* ============================================================
   📦 3. Инициализация обработчиков
============================================================ */
function initHandlers() {
    initSidebarCollapse();
    initModeSwitch();
    initLogButtons(showToast);
    initQueueButtons(CURRENT_USER, CURRENT_MODE, CURRENT_PROFILE);
    initGoalModal(loadGoalFromServer, showToast);
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
    initSidebarNavigation(navigateSPA);
    loadQR();
    loadGoalFromServer(CURRENT_MODE, updateGoalCircle);
    initTypeSelector(updateNewRuleFields);
    initSearchEnter(doSearch);
});

/* ============================================================
   📦 SPA навигация
============================================================ */
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

            initSearchEnter(doSearch);

            if (document.getElementById("logbox")) {
                lastLogCount = 0;
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
                loadGoalFromServer(CURRENT_MODE, updateGoalCircle);
                initTypeSelector(updateNewRuleFields);
                updateGoalVisibility(CURRENT_MODE);

                initLogButtons(showToast);
                initQueueButtons(CURRENT_USER, CURRENT_MODE, CURRENT_PROFILE);

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
                updateGoalVisibility(CURRENT_MODE);
                CURRENT_PROFILE = `${CURRENT_USER}_${CURRENT_MODE}`;

                loadGoalFromServer(CURRENT_MODE, updateGoalCircle);

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

            initSearchEnter(doSearch);

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
                loadGoalFromServer(CURRENT_MODE, updateGoalCircle);
                initTypeSelector(updateNewRuleFields);
                updateGoalVisibility(CURRENT_MODE);

                initLogButtons(showToast);
                initQueueButtons(CURRENT_USER, CURRENT_MODE, CURRENT_PROFILE);

                if (document.querySelector(".vip-grid")) initVipPage();

            }, 50);
        });
}
