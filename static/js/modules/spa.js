// spa.js — модуль SPA навигации и обновления контента

// ---------------------------------------------
// Sidebar navigation
// ---------------------------------------------
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


// ---------------------------------------------
// SPA page loader
// ---------------------------------------------
export function navigateSPA(
    url,
    state,                 // { pageURL, mode, profile }
    deps                   // { all functions }
) {
    // обновляем текущий URL
    state.pageURL = url;

    const container = document.querySelector(".content-inner");
    if (!container) {
        window.location.href = url;
        return;
    }

    container.style.opacity = "0";

    fetch(url + "?mode=" + state.mode)
        .then(r => r.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");
            const newContent = doc.querySelector(".content-inner").innerHTML;

            container.innerHTML = newContent;

            deps.initSearchEnter();

            if (document.getElementById("logbox")) {
                deps.lastLogCount.value = 0;
            }

            setTimeout(() => {
                container.style.opacity = "1";

                // Rules page
                if (document.querySelector(".rules-page")) {
                    deps.initRulesPage(deps.socket, deps.showToast);
                    deps.initRuleForms(state.profile, deps.socket, deps.reloadInnerContent, deps.showToast);
                    deps.initRuleModals();
                    deps.updateNewRuleFields();
                    deps.loadLogs();
                }

                // Common updates
                deps.loadLogs();
                deps.updateQueueUI();
                deps.loadQR();
                deps.loadGoalFromServer();
                deps.initTypeSelector();
                deps.updateGoalVisibility();

                deps.initLogButtons();
                deps.initQueueButtons();

                if (document.querySelector(".vip-grid")) deps.initVipPage();

            }, 50);
        });
}


// ---------------------------------------------
// Reload inner content
// ---------------------------------------------
export function reloadInnerContent(
    state,
    deps,
    callback = null
) {
    const container = document.querySelector(".content-inner");
    if (!container) return;

    container.style.opacity = "0";

    fetch(state.pageURL + "?mode=" + state.mode)
        .then(r => r.text())
        .then(html => {
            const parser = new DOMParser();
            const doc = parser.parseFromString(html, "text/html");

            const newContent = doc.querySelector(".content-inner").innerHTML;
            container.innerHTML = newContent;

            deps.initSearchEnter();

            setTimeout(() => {
                container.style.opacity = "1";

                if (callback) {
                    callback();
                } else {
                    if (document.querySelector(".rules-page")) {
                        deps.initRulesPage(deps.socket, deps.showToast);
                        deps.initRuleForms(state.profile, deps.socket, deps.reloadInnerContent, deps.showToast);
                        deps.initRuleModals();
                        deps.updateNewRuleFields();
                    }
                }

                setTimeout(deps.loadLogs, 10);
                deps.updateQueueUI();
                deps.loadQR();
                deps.loadGoalFromServer();
                deps.initTypeSelector();
                deps.updateGoalVisibility();

                deps.initLogButtons();
                deps.initQueueButtons();

                if (document.querySelector(".vip-grid")) deps.initVipPage();

            }, 50);
        });
}
