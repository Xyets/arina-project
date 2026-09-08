// spa.js — модуль SPA навигации и обновления контента

export function initSidebarNavigation(navigateSPA) {
    const links = document.querySelectorAll(".sidebar-menu .sidebar-item");

    links.forEach(link => {
        link.addEventListener("click", (e) => {
            e.preventDefault();
            const url = link.getAttribute("href");
            if (!url) return;
            navigateSPA(url);
        });
    });
}

export function navigateSPA(
    url,
    CURRENT_MODE,
    CURRENT_PROFILE,
    initSearchEnter,
    initRulesPage,
    initRuleForms,
    initRuleModals,
    updateNewRuleFields,
    loadLogs,
    updateQueueUI,
    loadQR,
    loadGoalFromServer,
    initTypeSelector,
    updateGoalVisibility,
    initLogButtons,
    initQueueButtons,
    initVipPage,
    socket,
    showToast,
    reloadInnerContent
) {
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
                loadGoalFromServer();
                initTypeSelector();
                updateGoalVisibility();

                initLogButtons();
                initQueueButtons();
                if (document.querySelector(".vip-grid")) initVipPage();

            }, 50);
        });
}

export function reloadInnerContent(
    CURRENT_PAGE_URL,
    CURRENT_MODE,
    CURRENT_PROFILE,
    initSearchEnter,
    initRulesPage,
    initRuleForms,
    initRuleModals,
    updateNewRuleFields,
    loadLogs,
    updateQueueUI,
    loadQR,
    loadGoalFromServer,
    initTypeSelector,
    updateGoalVisibility,
    initLogButtons,
    initQueueButtons,
    initVipPage,
    socket,
    showToast,
    callback
) {
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

                initLogButtons();
                initQueueButtons();
                if (document.querySelector(".vip-grid")) initVipPage();

            }, 50);
        });
}
