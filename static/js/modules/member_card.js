export function showMemberCard(data) {
    const card = document.getElementById("memberCard");
    if (!card) return;

    const oldTips = card.dataset.tips ? Number(card.dataset.tips) : null;
    const newTips = Number(data.tips || 0);

    card.innerHTML = `
        <div class="close-btn" onclick="hideMemberCard()">✕</div>
        <h3>${data.username}</h3>

        <p>📝 <strong>${data.note || "—"}</strong></p>
        <p>🕒 ${data.last_seen || "—"}</p>

        <p class="tips" id="memberTips">💗 ${newTips} ¥</p>
    `;

    card.classList.remove("hidden");

    // сохраняем значение чаевых
    card.dataset.tips = newTips;

    // если чаевые изменились → запускаем анимацию
    if (oldTips !== null && newTips !== oldTips) {
        const tipsEl = document.getElementById("memberTips");
        tipsEl.classList.remove("pulse");
        void tipsEl.offsetWidth; // перезапуск анимации
        tipsEl.classList.add("pulse");
    }
}
