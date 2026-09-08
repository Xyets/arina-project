// sidebar.js — отвечает только за сворачивание/разворачивание боковой панели

export function initSidebar() {
    const sidebar = document.getElementById("sidebar");
    const sidebarLogo = document.getElementById("sidebarLogo");

    if (sidebar && sidebarLogo) {
        sidebarLogo.onclick = () => sidebar.classList.toggle("collapsed");
    }
}
