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

    card.dataset.tips = newTips;

    if (oldTips !== null && newTips !== oldTips) {
        const tipsEl = document.getElementById("memberTips");
        tipsEl.classList.remove("pulse");
        void tipsEl.offsetWidth;
        tipsEl.classList.add("pulse");
    }
}

export function hideMemberCard() {
    const card = document.getElementById("memberCard");
    if (!card) return;

    card.classList.add("hidden");
}
