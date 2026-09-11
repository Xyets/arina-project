// static/js/modules/member_card.js

/* ============================================================
   🧩 Вспомогательная функция — гарантирует существование карточки
============================================================ */

function ensureMemberCard() {
    let card = document.getElementById("memberCard");

    // Если SPA перерисовала страницу и карточка исчезла — создаём заново
    if (!card) {
        card = document.createElement("div");
        card.id = "memberCard";
        card.classList.add("member-card", "hidden");

        // Можно изменить контейнер, если хочешь другое место
        document.body.appendChild(card);
    }

    return card;
}

/* ============================================================
   👤 Показ карточки мембера
============================================================ */

export function showMemberCard(data) {
    const card = ensureMemberCard();

    const oldTips = card.dataset.tips ? Number(card.dataset.tips) : null;
    const newTips = Number(data.tips || 0);

    card.innerHTML = `
        <div class="member-header">
            <span class="member-name">${data.username}</span>
            <button class="member-close-btn" id="memberCloseBtn">✕</button>
        </div>

        <div class="member-info">
            <div class="member-row">
                <span class="icon">📝</span>
                <span class="value">${data.note || "—"}</span>
            </div>

            <div class="member-row">
                <span class="icon">🕒</span>
                <span class="value">${data.last_seen || "—"}</span>
            </div>

            <div class="member-row tips-row">
                <span class="icon">💗</span>
                <span class="value" id="memberTips">${newTips} ¥</span>
            </div>
        </div>
    `;

    // навешиваем обработчик закрытия
    const closeBtn = card.querySelector("#memberCloseBtn");
    closeBtn.onclick = hideMemberCard;

    card.classList.remove("hidden");

    // обновляем dataset
    card.dataset.tips = newTips;

    // анимация изменения чаевых
    if (oldTips !== null && newTips !== oldTips) {
        const tipsEl = card.querySelector("#memberTips");
        tipsEl.classList.remove("pulse");
        void tipsEl.offsetWidth; // перезапуск анимации
        tipsEl.classList.add("pulse");
    }
}

/* ============================================================
   👤 Скрытие карточки мембера
============================================================ */

export function hideMemberCard() {
    const card = document.getElementById("memberCard");
    if (!card) return;

    card.classList.add("hidden");
}
