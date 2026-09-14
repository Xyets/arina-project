export function initModelSelector() {
    console.log("MODEL: initModelSelector()");

    const select = document.getElementById("modelSelect");
    const options = document.getElementById("modelOptions");

    if (!select || !options) {
        console.warn("MODEL: selector elements NOT FOUND");
        return;
    }

    const display = select.querySelector(".select-display");
    if (!display) return;

    // Открытие списка
    display.onclick = (e) => {
        console.log("MODEL: display clicked");
        e.stopPropagation();
        options.style.display =
            options.style.display === "flex" ? "none" : "flex";
    };

    // Клик по опциям
    const items = options.querySelectorAll(".option");
    items.forEach(item => {
        item.style.display = "flex";   // ← ВАЖНО: НИЧЕГО НЕ СКРЫВАЕМ

        item.onclick = (e) => {
            e.stopPropagation();
            const value = item.dataset.value;
            console.log("MODEL: option selected =", value);
            navigateSPA(`/stats_beta?model=${value}`);
        };
    });

    // Закрытие при клике вне
    document.addEventListener("click", () => {
        console.log("MODEL: outside click → closing options");
        options.style.display = "none";
    });
}
