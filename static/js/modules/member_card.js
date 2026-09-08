// member_card.js — карточка мембера

export function showMemberCard(data) {
    const card = document.getElementById("memberCard");
    if (!card) return;

    card.innerHTML = `
        <div class="close-btn" onclick="hideMemberCard()">✕</div>
        <h3>${data.username}</h3>

        <p><strong>Заметка:</strong> ${data.note || "—"}</p>
        <p><strong>Последний вход:</strong> ${data.last_seen || "—"}</p>

        <p class="tips">💗 Чаевые: ${data.tips || 0} ¥</p>
    `;

    card.classList.remove("hidden");
}

export function hideMemberCard() {
    const card = document.getElementById("memberCard");
    if (!card) return;

    card.classList.add("hidden");
}
