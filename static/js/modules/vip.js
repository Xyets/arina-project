import { showToast } from "./toast.js";

let VIP_SORT = "total";
let VIP_DELETE_ID = null;

/* ------------------------------------------------------------
   ИНИЦИАЛИЗАЦИЯ СТРАНИЦЫ VIP
------------------------------------------------------------ */
export function initVipPage() {
    if (!document.querySelector(".vip-grid")) return;

    initVipForms();
    initVipSortButtons();
    initVipSearch();
    initVipModals();

    loadVipList();
}

/* ------------------------------------------------------------
   ЗАГРУЗКА СПИСКА VIP
------------------------------------------------------------ */
async function loadVipList() {
    try {
        const res = await fetch("/vip_data");
        const data = await res.json();

        renderVipCards(Object.entries(data.members));
        sortVipList(VIP_SORT);
    } catch (e) {
        console.error("VIP load error", e);
    }
}

/* ------------------------------------------------------------
   РЕНДЕР КАРТОЧЕК
------------------------------------------------------------ */
function renderVipCards(list) {
    const grid = document.getElementById("vipGrid");
    grid.innerHTML = "";

    list.forEach(([user_id, info]) => {
        const rawDate = info.last_login || "";
        const d = rawDate ? new Date(rawDate.replace(" ", "T")) : null;

        const formattedDate =
            d && !isNaN(d.getTime())
                ? d.toLocaleString("ru-RU", {
                      day: "numeric",
                      month: "long",
                      hour: "2-digit",
                      minute: "2-digit"
                  })
                : rawDate;

        const card = document.createElement("div");
        card.className = "vip-card" + (info.blocked ? " blocked" : "");
        card.id = "vip_" + user_id;

        card.innerHTML = `
            <form class="vip-form" data-id="${user_id}">
                <input type="text" name="name" value="${info.name}" placeholder="Имя">
                <input type="text" name="notes" value="${info.notes || ""}" placeholder="Заметки">

                <div class="meta">
                    💗 ${info.total} | 📅 ${info.login_count} входов<br>
                    🕒 Последний визит:
                    <span class="date" data-last-login="${rawDate}">${formattedDate}</span><br>
                    🆔 ID: <code>${user_id}</code>
                </div>

                <div class="actions">
                    <button type="submit">💾 Сохранить</button>
                    <button type="button" class="vip-delete-btn" data-id="${user_id}">🗑️ Удалить</button>
                </div>
            </form>
        `;

        grid.appendChild(card);
    });

    initVipForms();
    initVipDeleteButtons();
}

/* ------------------------------------------------------------
   СОХРАНЕНИЕ VIP
------------------------------------------------------------ */
function initVipForms() {
    document.querySelectorAll(".vip-form").forEach(form => {

        // удаляем старые обработчики
        const newForm = form.cloneNode(true);
        form.replaceWith(newForm);

        newForm.addEventListener("submit", async (e) => {
            e.preventDefault();

            const userId = newForm.dataset.id;
            const formData = new FormData(newForm);

            try {
                const res = await fetch("/vip", {
                    method: "POST",
                    body: formData
                });

                if (res.ok) {
                    await refreshVipCard(userId);
                    sortVipList(VIP_SORT);
                    showToast("Сохранено");
                } else {
                    showToast("Ошибка сохранения");
                }
            } catch {
                showToast("Ошибка сохранения");
            }
        });
    });
}

/* ------------------------------------------------------------
   ОБНОВЛЕНИЕ ОДНОЙ КАРТОЧКИ
------------------------------------------------------------ */
async function refreshVipCard(userId) {
    try {
        const res = await fetch("/vip_data");
        const data = await res.json();
        const info = data.members[userId];
        if (!info) return;

        const rawDate = info.last_login || "";
        const d = rawDate ? new Date(rawDate.replace(" ", "T")) : null;

        const formattedDate =
            d && !isNaN(d.getTime())
                ? d.toLocaleString("ru-RU", {
                      day: "numeric",
                      month: "long",
                      hour: "2-digit",
                      minute: "2-digit"
                  })
                : rawDate;

        const card = document.getElementById("vip_" + userId);

        card.innerHTML = `
            <form class="vip-form" data-id="${userId}">
                <input type="text" name="name" value="${info.name}" placeholder="Имя">
                <input type="text" name="notes" value="${info.notes || ""}" placeholder="Заметки">

                <div class="meta">
                    💗 ${info.total} | 📅 ${info.login_count} входов<br>
                    🕒 Последний визит:
                    <span class="date" data-last-login="${rawDate}">${formattedDate}</span><br>
                    🆔 ID: <code>${userId}</code>
                </div>

                <div class="actions">
                    <button type="submit">💾 Сохранить</button>
                    <button type="button" class="vip-delete-btn" data-id="${userId}">🗑️ Удалить</button>
                </div>
            </form>
        `;

        initVipForms();
        initVipDeleteButtons();
    } catch (e) {
        console.error("VIP refresh error", e);
    }
}

/* ------------------------------------------------------------
   СОРТИРОВКА
------------------------------------------------------------ */
function initVipSortButtons() {
    document.querySelectorAll(".vip-sort-btn").forEach(btn => {
        btn.onclick = () => {
            VIP_SORT = btn.dataset.sort;
            sortVipList(VIP_SORT);
        };
    });
}

function sortVipList(sortBy) {
    const grid = document.getElementById("vipGrid");
    const cards = Array.from(grid.children);

    cards.sort((a, b) => {
        const dateA = new Date(a.querySelector(".date")?.dataset.lastLogin?.replace(" ", "T") || 0);
        const dateB = new Date(b.querySelector(".date")?.dataset.lastLogin?.replace(" ", "T") || 0);

        const metaA = a.querySelector(".meta").textContent;
        const metaB = b.querySelector(".meta").textContent;

        const visitsA = parseInt((metaA.match(/📅\s*(\d+)\s*вход/) || [])[1]);
        const visitsB = parseInt((metaB.match(/📅\s*(\d+)\s*вход/) || [])[1]);

        const totalA = parseFloat((metaA.match(/💗\s*([\d\.]+)/) || [])[1]);
        const totalB = parseFloat((metaB.match(/💗\s*([\d\.]+)/) || [])[1]);

        if (sortBy === "last_login") return dateB - dateA;
        if (sortBy === "login_count") return (visitsB || 0) - (visitsA || 0);
        if (sortBy === "total") return (totalB || 0) - (totalA || 0);

        return 0;
    });

    grid.innerHTML = "";
    cards.forEach(c => grid.appendChild(c));
}

/* ------------------------------------------------------------
   ПОИСК
------------------------------------------------------------ */
function initVipSearch() {
    const input = document.getElementById("vipSearchInput");
    const btn = document.getElementById("vipSearchBtn");

    btn.onclick = doVipSearch;
    input.oninput = () => {
        if (input.value.trim() === "") loadVipList();
    };
}

async function doVipSearch() {
    const q = document.getElementById("vipSearchInput").value.trim().toLowerCase();
    if (!q) return loadVipList();

    const res = await fetch("/vip_data");
    const data = await res.json();

    const filtered = Object.entries(data.members).filter(([id, info]) => {
        const text = (id + " " + info.name + " " + info.notes).toLowerCase();
        return text.includes(q);
    });

    renderVipCards(filtered);
    sortVipList(VIP_SORT);
}

/* ------------------------------------------------------------
   МОДАЛКА УДАЛЕНИЯ
------------------------------------------------------------ */
function initVipModals() {
    const yesBtn = document.getElementById("vipDeleteYes");
    yesBtn.onclick = () => {
        if (!VIP_DELETE_ID) return;
        deleteVipMember(VIP_DELETE_ID);
        closeVipDeleteModal();
    };
}

function initVipDeleteButtons() {
    document.querySelectorAll(".vip-delete-btn").forEach(btn => {
        btn.onclick = () => {
            VIP_DELETE_ID = btn.dataset.id;
            openVipDeleteModal();
        };
    });
}

function openVipDeleteModal() {
    document.getElementById("vipDeleteModal").classList.add("show");
}

function closeVipDeleteModal() {
    document.getElementById("vipDeleteModal").classList.remove("show");
    VIP_DELETE_ID = null;
}

/* ------------------------------------------------------------
   УДАЛЕНИЕ VIP
------------------------------------------------------------ */
async function deleteVipMember(userId) {
    try {
        const res = await fetch("/remove_member", {
            method: "POST",
            headers: { "Content-Type": "application/x-www-form-urlencoded" },
            body: "user_id=" + encodeURIComponent(userId)
        });

        const data = await res.json();

        if (data.status === "ok") {
            document.getElementById("vip_" + userId)?.remove();
            sortVipList(VIP_SORT);
            showToast("Удалено");
        } else {
            showToast("Ошибка удаления");
        }
    } catch {
        showToast("Ошибка удаления");
    }
}

/* ------------------------------------------------------------
   WEBSOCKET — обновление VIP
------------------------------------------------------------ */
export function vipWebSocketUpdate(data) {
    if (data.vip_update) {
        loadVipList();
    }
}
