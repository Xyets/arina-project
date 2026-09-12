export function initModelSelector() {
    const select = document.getElementById("modelSelect");
    const options = document.getElementById("modelOptions");

    if (!select || !options) return;

    // Открытие списка только при клике на display
    const display = select.querySelector(".select-display");
    if (!display) return;

    display.onclick = (e) => {
        e.stopPropagation();
        options.style.display =
            options.style.display === "flex" ? "none" : "flex";
    };

    // Клик по опциям — НЕ должен вызывать select.onclick
    const items = options.querySelectorAll(".option");
    items.forEach(item => {
        item.onclick = (e) => {
            e.stopPropagation();
            const value = item.dataset.value;
            navigateSPA(`/stats_beta?model=${value}`);
        };
    });

    // Закрытие при клике вне
    document.addEventListener("click", () => {
        options.style.display = "none";
    }, { once: true });
}
