/* ============================================================
   🌐 MAIN — модульная сборка FlowTip 3.0
============================================================ */

/* ---------- CORE ---------- */
import { CURRENT_MODE } from "./modules/core.js";

/* ---------- WEBSOCKET ---------- */
import { connectWS } from "./modules/websocket.js";

/* ---------- SPA ---------- */
import { initSidebarNavigation, navigateSPA } from "./modules/spa.js";

/* ---------- SIDEBAR ---------- */
import { initSidebarCollapse, initModeSwitch } from "./modules/sidebar.js";

/* ---------- LOGS ---------- */
import { loadLogs } from "./modules/logs.js";

/* ---------- QUEUE ---------- */
import { updateQueueUI, initQueueButtons, startVibrationTimer } from "./modules/queue.js";

/* ---------- POPUP ---------- */
import { showEntryPopup } from "./modules/popup.js";

/* ---------- TOAST ---------- */
import { showToast } from "./modules/toast.js";

/* ---------- GOAL ---------- */
import {
    updateGoalVisibility,
    initGoalModal,
    loadGoalFromServer,
    openGoalModal,
    closeGoalModal
} from "./modules/goal.js";

/* ---------- QR ---------- */
import { loadQR, refreshQR } from "./modules/qr.js";

/* ---------- RULES ---------- */
import {
    initRulesPage,
    initRuleForms,
    initRuleModals,
    sendRuleCommand,
    deleteRule,
    deleteSegment,
    updateSegmentFields
} from "./modules/rules.js";

/* ---------- UTILS ---------- */
import { initTypeSelector } from "./modules/utils.js";

/* ---------- VIP ---------- */
import { initVipPage, vipWebSocketUpdate } from "./modules/vip.js";


/* ============================================================
   🌟 ГЛОБАЛЬНЫЕ ФУНКЦИИ ДЛЯ HTML
============================================================ */

window.refreshQR = refreshQR;
window.openGoalModal = openGoalModal;
window.closeGoalModal = closeGoalModal;
window.updateSegmentFields = updateSegmentFields;
window.navigateSPA = navigateSPA;


/* ============================================================
   🌟 ГЛОБАЛЬНЫЙ ОБРАБОТЧИК WS
============================================================ */
window.handleWSMessage = (data) => {

    // VIP обновления
    vipWebSocketUpdate(data);

    // Popup входа
    if (data.entry) {
        showEntryPopup(`
            👤 <strong>${data.entry.name}</strong><br>
            🔢 Визитов: ${data.entry.visits}<br>
            💗 Чаевых всего: ${data.entry.total_tips}<br>
            📝 Заметки: ${data.entry.notes || "нет"}
        `);
    }

    // Вибрация
    if (data.vibration) {
        startVibrationTimer(data.vibration.duration, data.vibration.strength);
    }
};


/* ============================================================
   🌟 ИНИЦИАЛИЗАЦИЯ ПРИ ЗАГРУЗКЕ
============================================================ */
window.addEventListener("load", () => {

    /* WebSocket */
    connectWS();

    /* Sidebar */
    initSidebarCollapse();
    initModeSwitch();
    initSidebarNavigation();

    /* Goal */
    initGoalModal();
    loadGoalFromServer();
    updateGoalVisibility();

    /* Logs */
    loadLogs();

    /* Queue */
    initQueueButtons();
    updateQueueUI();

    /* QR */
    loadQR();

    /* Rules */
    if (document.querySelector(".rules-page")) {
        initRulesPage();
        initRuleForms();
        initRuleModals();
    }

    /* Utils */
    initTypeSelector();

    /* VIP */
    if (document.querySelector(".vip-grid")) {
        initVipPage();
    }
});


/* ============================================================
   🌟 SPA ПЕРЕХОДЫ — корректная версия
============================================================ */
window.navigateSPA = (url) => {
    navigateSPA(url);

    setTimeout(() => {

        if (document.querySelector(".rules-page")) {
            initRulesPage();
            initRuleForms();
            initRuleModals();
        }

        if (document.querySelector(".vip-grid")) {
            initVipPage();
        }

        loadGoalFromServer();
        updateGoalVisibility();

        loadLogs();
        updateQueueUI();
        loadQR();
        initTypeSelector();

    }, 50);
};
