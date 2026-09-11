/* ============================================================
   📊 ИНИЦИАЛИЗАЦИЯ СТРАНИЦЫ СТАТИСТИКИ
============================================================ */
function initStatsPage() {
    initChart();
    initModal();
}

/* ============================================================
   📈 ГРАФИК Chart.js — стеклянный стиль FlowTip
============================================================ */
function initChart() {
    if (typeof Chart === "undefined") {
        console.error("Chart.js не загружен!");
        return;
    }

    const raw = document.getElementById("stats-data").textContent;
    const stats = JSON.parse(raw);

    const labels = Object.keys(stats);

    const vibrations = labels.map(d => parseInt(stats[d].vibrations || 0));
    const actions    = labels.map(d => parseInt(stats[d].actions || 0));
    const other      = labels.map(d => parseInt(stats[d].other || 0));
    const total      = labels.map(d => parseInt(stats[d].total || 0));

    const ctx = document.getElementById("statsChart").getContext("2d");

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
                    pointRadius: 4,
                    pointBackgroundColor: "#74c0e3"
                },
                {
                    label: "Действия",
                    data: actions,
                    borderColor: "rgba(129,199,132,1)",
                    backgroundColor: "rgba(129,199,132,0.25)",
                    tension: 0.35,
                    borderWidth: 3,
                    pointRadius: 4,
                    pointBackgroundColor: "#81c784"
                },
                {
                    label: "Иное",
                    data: other,
                    borderColor: "rgba(255,183,77,1)",
                    backgroundColor: "rgba(255,183,77,0.25)",
                    tension: 0.35,
                    borderWidth: 3,
                    pointRadius: 4,
                    pointBackgroundColor: "#ffb74d"
                },
                {
                    label: "Всего поинтов",
                    data: total,
                    borderColor: "rgba(242,132,151,1)",
                    backgroundColor: "rgba(242,132,151,0.25)",
                    tension: 0.35,
                    borderWidth: 3,
                    pointRadius: 4,
                    pointBackgroundColor: "#f28497"
                }
            ]
        },
        options: {
            responsive: true,
            plugins: {
                legend: {
                    position: "top",
                    labels: {
                        color: "#fff",
                        font: { size: 14 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `${ctx.dataset.label}: ${Math.round(ctx.parsed.y)}`
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
                        callback: (v) => parseInt(v)
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

    window.showConfirm = () => {
        overlay.style.display = "block";
        modal.style.display = "block";
    };

    window.hideConfirm = () => {
        overlay.style.display = "none";
        modal.style.display = "none";
    };
}
