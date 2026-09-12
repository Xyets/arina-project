/* ============================================================
   📊 ИНИЦИАЛИЗАЦИЯ СТРАНИЦЫ СТАТИСТИКИ (ES‑модуль)
============================================================ */
export function initStatsPage() {
    try {
        initChart();
    } catch (err) {
        console.error("Ошибка при построении графика:", err);
    }

    try {
        initModal();
    } catch (err) {
        console.error("Ошибка при инициализации модалки:", err);
    }
}

/* ============================================================
   🛡 Безопасное преобразование чисел
============================================================ */
function safeNum(v) {
    const n = Number(v);
    return isNaN(n) ? 0 : n;
}

/* ============================================================
   📈 ГРАФИК Chart.js
============================================================ */
function initChart() {
    if (typeof Chart === "undefined") {
        console.error("Chart.js не загружен!");
        return;
    }

    const rawEl = document.getElementById("stats-data");
    if (!rawEl) {
        console.warn("stats-data не найден");
        return;
    }

    let stats;
    try {
        stats = JSON.parse(rawEl.textContent);
    } catch (err) {
        console.error("Ошибка парсинга JSON статистики:", err);
        return;
    }

    const labels = Object.keys(stats);
    if (!labels.length) {
        console.warn("Нет данных для графика");
        return;
    }

    const vibrations = labels.map(d => safeNum(stats[d].vibrations));
    const actions    = labels.map(d => safeNum(stats[d].actions));
    const other      = labels.map(d => safeNum(stats[d].other));
    const total      = labels.map(d => safeNum(stats[d].total));

    const canvas = document.getElementById("statsChart");
    if (!canvas) {
        console.warn("statsChart не найден");
        return;
    }

    const ctx = canvas.getContext("2d");

    new Chart(ctx, {
        type: "line",
        data: {
            labels,
            datasets: [
                {
                    label: "Вибрации",
                    data: vibrations,
                    borderColor: "rgba(116,192,227,1)",
                    backgroundColor: "rgba(116,192,227,0.25)",
                    tension: 0.35,
                    borderWidth: 3,
                    pointRadius: 3
                },
                {
                    label: "Действия",
                    data: actions,
                    borderColor: "rgba(129,199,132,1)",
                    backgroundColor: "rgba(129,199,132,0.25)",
                    tension: 0.35,
                    borderWidth: 3,
                    pointRadius: 3
                },
                {
                    label: "Иное",
                    data: other,
                    borderColor: "rgba(255,183,77,1)",
                    backgroundColor: "rgba(255,183,77,0.25)",
                    tension: 0.35,
                    borderWidth: 3,
                    pointRadius: 3
                },
                {
                    label: "Всего",
                    data: total,
                    borderColor: "rgba(242,132,151,1)",
                    backgroundColor: "rgba(242,132,151,0.25)",
                    tension: 0.35,
                    borderWidth: 3,
                    pointRadius: 3
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    labels: {
                        color: "#fff",
                        font: { size: 14 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: ctx => `${ctx.dataset.label}: ${safeNum(ctx.parsed.y)}`
                    }
                }
            },
            scales: {
                x: {
                    ticks: { color: "#fff" },
                    grid: { color: "rgba(255,255,255,0.1)" }
                },
                y: {
                    beginAtZero: true,
                    ticks: {
                        color: "#fff",
                        callback: v => safeNum(v)
                    },
                    grid: { color: "rgba(255,255,255,0.1)" }
                }
            }
        }
    });
}

/* ============================================================
   🧊 МОДАЛКА «Завершить период»
============================================================ */
function initModal() {
    const overlay = document.getElementById("modalOverlay");
    const modal = document.getElementById("confirmModal");

    if (!overlay || !modal) return;

    window.showConfirm = () => {
        overlay.style.display = "block";
        modal.style.display = "block";
    };

    window.hideConfirm = () => {
        overlay.style.display = "none";
        modal.style.display = "none";
    };

    window.submitClosePeriod = () => {
        hideConfirm();

        const start = document.getElementById("periodStart")?.value || "";
        const end   = document.getElementById("periodEnd")?.value || "";

        fetch("/close_period", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ start, end })
        }).then(() => {
            navigateSPA("/stats_history");
        });
    };
}
