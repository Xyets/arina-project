// spa.js — только навигация sidebar (SPA)

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
