/* ============================================================
   MODEL SELECTOR — SPA‑совместимый селектор моделей
============================================================ */

export function initModelSelector() {
    const select = document.getElementById("modelSelect");
    const options = document.getElementById("modelOptions");

    if (!select || !options) return;

    // Открытие / закрытие списка
    select.onclick = () => {
        options.style.display =
            options.style.display === "flex" ? "none" : "flex";
    };

    // Закрытие при клике вне селектора
    document.addEventListener("click", (e) => {
        if (!select.contains(e.target)) {
            options.style.display = "none";
        }
    });
}
