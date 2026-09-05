import { CURRENT_MODE, CURRENT_PAGE_URL } from "./core.js";
import { initRulesPage, initRuleForms, initRuleModals, updateNewRuleFields } from "./rules.js";
import { loadLogs } from "./logs.js";
import { updateQueueUI } from "./queue.js";
import { loadQR } from "./qr.js";
import { loadGoalFromServer, updateGoalVisibility } from "./goal.js";
import { initTypeSelector } from "./utils.js";
import { initVipPage } from "./vip.js";

/* ============================================================
   📦 Sidebar navigation (SPA)
============================================================ */
export function initSidebarNavigation() {
    const links = document.querySelectorAll(".sidebar-menu .sidebar-item");

    links.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const url = link.getAttribute("href");
            navigateSPA(url);
        });
    });
}

/* ============================================================
   📦 SPA page loader
============================================================ */
export function navigateSPA(url) {
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

                /* RULES */
                if (document.querySelector(".rules-page")) {
                    initRulesPage();
                    initRuleForms();
                    initRuleModals();
                    updateNewRuleFields();
                }

                /* VIP */
                if (document.querySelector(".vip-grid")) {
                    initVipPage();
                }

                /* COMMON */
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
   🔄 Reload inner content (used by WebSocket)
============================================================ */
export function reloadInnerContent(callback) {
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

                if (callback) callback();

                /* COMMON */
                loadLogs();
                updateQueueUI();
                loadQR();
                loadGoalFromServer();
                initTypeSelector();
                updateGoalVisibility();

            }, 50);
        });
}
