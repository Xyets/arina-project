/* ============================================================
   📊 ИНИЦИАЛИЗАЦИЯ СТРАНИЦЫ СТАТИСТИКИ (ES‑модуль)
============================================================ */
export function initStatsPage() {
    initChart();
    initModal();
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
    if (!rawEl) return;

    const raw = rawEl.textContent;
    const stats = JSON.parse(raw);

    const labels = Object.keys(stats);

    const vibrations = labels.map(d => parseInt(stats[d].vibrations || 0));
    const actions    = labels.map(d => parseInt(stats[d].actions || 0));
    const other      = labels.map(d => parseInt(stats[d].other || 0));
    const total      = labels.map(d => parseInt(stats[d].total || 0));

    const canvas = document.getElementById("statsChart");
    if (!canvas) return;

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
                    tension: 0.35
                },
                {
                    label: "Действия",
                    data: actions,
                    borderColor: "rgba(129,199,132,1)",
                    backgroundColor: "rgba(129,199,132,0.25)",
                    tension: 0.35
                },
                {
                    label: "Иное",
                    data: other,
                    borderColor: "rgba(255,183,77,1)",
                    backgroundColor: "rgba(255,183,77,0.25)",
                    tension: 0.35
                },
                {
                    label: "Всего",
                    data: total,
                    borderColor: "rgba(242,132,151,1)",
                    backgroundColor: "rgba(242,132,151,0.25)",
                    tension: 0.35
                }
            ]
        },
        options: {
            responsive: true
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

    // Глобальные функции для HTML
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

        const start = document.getElementById("periodStart").value;
        const end = document.getElementById("periodEnd").value;

        fetch("/close_period", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ start, end })
        }).then(() => {
            window.location.href = "/stats_history";
        });
    };
}
