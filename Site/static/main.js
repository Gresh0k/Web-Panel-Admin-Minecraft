/* ==========================================================================
   УПРАВЛЕНИЕ МОДАЛЬНЫМИ ОКНАМИ И ФОНОМ (OVERLAY)
   ========================================================================== */

let mouseDownTarget = null;

// Закрытие модальных окон при клике на темный фон (overlay)
window.addEventListener('mousedown', function (e) {
    mouseDownTarget = e.target;
});

window.addEventListener('mouseup', function (e) {
    if (mouseDownTarget && mouseDownTarget.classList.contains('modal-bg') && e.target === mouseDownTarget) {
        mouseDownTarget.style.display = 'none';
    }
    mouseDownTarget = null;
});

/* ==========================================================================
   КОНСОЛЬ RCON
   ========================================================================== */

function openCommandModal() {
    document.getElementById('commandModal').style.display = 'flex';
}

function closeCommandModal() {
    document.getElementById('commandModal').style.display = 'none';
}

/* ==========================================================================
   КИК ИГРОКОВ
   ========================================================================== */

async function openPlayersModal() {
    const container = document.getElementById("playersList");
    container.innerHTML = "<p style='color: #a4b0be;'>Загрузка...</p>";
    document.getElementById("playersModal").style.display = "flex";

    try {
        const resp = await fetch("/kick_list");
        const players = await resp.json();
        container.innerHTML = "";

        if (!players || players.length === 0) {
            container.innerHTML = "<p style='color: #a4b0be;'>Нет игроков онлайн</p>";
        } else {
            players.forEach(p => {
                container.innerHTML += `
                    <div class="player-item">
                        <span class="player-name">${p}</span>
                        <button onclick="selectPlayer('${p}')" class="btn-logout btn-item-action">Кик</button>
                    </div>
                `;
            });
        }
    } catch (err) {
        container.innerHTML = "<p style='color: #e74c3c;'>Ошибка загрузки списка</p>";
    }
}

function closePlayersModal() {
    document.getElementById("playersModal").style.display = "none";
}

function selectPlayer(name) {
    document.getElementById("kickPlayerName").value = name;
    closePlayersModal();
    document.getElementById("reasonModal").style.display = "flex";
}

function closeReasonModal() {
    document.getElementById("reasonModal").style.display = "none";
}

/* ==========================================================================
   БАН ИГРОКОВ (ИЗ ОПЦИЙ МЕНЮ)
   ========================================================================== */

async function openBanPlayersModal() {
    const container = document.getElementById("banPlayersList");
    container.innerHTML = "<p style='color: #a4b0be;'>Загрузка...</p>";
    document.getElementById("banPlayersModal").style.display = "flex";

    try {
        const resp = await fetch("/kick_list");
        const players = await resp.json();
        container.innerHTML = "";

        if (!players || players.length === 0) {
            container.innerHTML = "<p style='color: #a4b0be;'>Нет игроков онлайн</p>";
        } else {
            players.forEach(p => {
                container.innerHTML += `
                    <div class="player-item">
                        <span class="player-name">${p}</span>
                        <button onclick="selectBanPlayer('${p}')" class="btn-logout btn-item-action">Бан</button>
                    </div>
                `;
            });
        }
    } catch (err) {
        container.innerHTML = "<p style='color: #e74c3c;'>Ошибка загрузки списка</p>";
    }
}

function closeBanPlayersModal() {
    document.getElementById("banPlayersModal").style.display = "none";
}

function selectBanPlayer(name) {
    document.getElementById("banPlayerName").value = name;
    closeBanPlayersModal();
    document.getElementById("banReasonModal").style.display = "flex";
}

function closeBanReasonModal() {
    document.getElementById("banReasonModal").style.display = "none";
}

function closeBanModalOnOverlay(event) {
    if (event.target.id === 'banReasonModal') {
        closeBanReasonModal();
    }
}

function toggleDurationInputs() {
    const isPermanent = document.getElementById('is_permanent').checked;
    const amountInput = document.getElementById('duration_amount');
    const unitSelect = document.getElementById('duration_unit');

    amountInput.disabled = isPermanent;
    unitSelect.disabled = isPermanent;

    if (isPermanent) {
        amountInput.style.opacity = '0.3';
        unitSelect.style.opacity = '0.3';
        amountInput.style.cursor = 'not-allowed';
        unitSelect.style.cursor = 'not-allowed';
    } else {
        amountInput.style.opacity = '1';
        unitSelect.style.opacity = '1';
        amountInput.style.cursor = 'text';
        unitSelect.style.cursor = 'pointer';
    }
}

/* ==========================================================================
   СПИСОК ЗАБАНЕННЫХ И РАЗБАН
   ========================================================================== */

let playerToUnban = '';

function openBannedListModal() {
    document.getElementById('bannedListModal').style.display = 'flex';
    loadBannedPlayers();
}

function closeBannedListModal() {
    document.getElementById('bannedListModal').style.display = 'none';
}

function loadBannedPlayers() {
    const container = document.getElementById('bannedContainer');
    container.innerHTML = '<p style="color: #a4b0be;">Загрузка списка...</p>';

    fetch('/api/banned_players')
        .then(res => res.json())
        .then(data => {
            if (!data || data.length === 0) {
                container.innerHTML = '<p style="color: #a4b0be;">Забаненных игроков нет.</p>';
                return;
            }

            let html = `
                <table class="banned-table">
                    <thead>
                        <tr>
                            <th>Никнейм</th>
                            <th>Причина</th>
                            <th>Срок</th>
                            <th>Действие</th>
                        </tr>
                    </thead>
                    <tbody>
            `;

            data.forEach(item => {
                html += `
                    <tr>
                        <td><strong>${item.name}</strong></td>
                        <td>${item.reason}</td>
                        <td><span style="color: ${item.duration === 'Перманентно' ? '#e74c3c' : '#f1c40f'};">${item.duration}</span></td>
                        <td>
                            <button class="btn-unban" onclick="openUnbanConfirmModal('${item.name}')">Разбанить</button>
                        </td>
                    </tr>
                `;
            });

            html += '</tbody></table>';
            container.innerHTML = html;
        })
        .catch(() => {
            container.innerHTML = '<p style="color: #e74c3c;">Ошибка при загрузке списка банов.</p>';
        });
}

function openUnbanConfirmModal(playerName) {
    playerToUnban = playerName;
    document.getElementById('unbanConfirmText').innerText = `Вы действительно хотите разбанить ${playerName}?`;
    document.getElementById('unbanConfirmModal').style.display = 'flex';
}

function closeUnbanConfirmModal() {
    playerToUnban = '';
    document.getElementById('unbanConfirmModal').style.display = 'none';
}

/* ==========================================================================
   ЛИЧНЫЕ СООБЩЕНИЯ (MSG)
   ========================================================================== */

function closeMsgModal() {
    document.getElementById('msgModal').style.display = 'none';
}

/* ==========================================================================
   ИНТЕРАКТИВНАЯ КАРТА (DYNMAP / PLAYER MODAL)
   ========================================================================== */

let selectedPlayer = '';

function openPlayerModal(playerName) {
    document.getElementById('modalPlayerTitle').innerText = `Игрок: ${playerName}`;
    document.getElementById('playerModal').style.display = 'flex';
}

function closePlayerModal() {
    document.getElementById('playerModal').style.display = 'none';
}

function executePlayerAction(type) {
    const reason = document.getElementById('actionReason').value || 'Без причины';

    if (type === 'kick') {
        fetch('/kick_player', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ 'player': selectedPlayer, 'reason': reason })
        }).then(() => alert(`Игрок ${selectedPlayer} кикнут!`));
    } else if (type === 'ban') {
        fetch('/ban_player', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({ 'player': selectedPlayer, 'reason': reason, 'is_permanent': 'on' })
        }).then(() => alert(`Игрок ${selectedPlayer} забанен навсегда!`));
    } else if (type === 'tempban') {
        const amount = document.getElementById('tempbanAmount').value;
        const unit = document.getElementById('tempbanUnit').value;
        fetch('/ban_player', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            body: new URLSearchParams({
                'player': selectedPlayer,
                'reason': reason,
                'duration_amount': amount,
                'duration_unit': unit
            })
        }).then(() => alert(`Игрок ${selectedPlayer} забанен на ${amount}${unit}!`));
    }

    closePlayerModal();
}

window.sendAdminAction = function (action, playerName) {
    if (action === 'msg') {
        document.getElementById('msgPlayerTitle').innerText = playerName;
        document.getElementById('msgTextInput').value = '';
        document.getElementById('msgModal').style.display = 'flex';
    } else if (action === 'kick') {
        if (typeof selectPlayerForKick === 'function') {
            selectPlayerForKick(playerName);
        } else {
            document.getElementById('kickPlayerName').value = playerName;
            document.getElementById('reasonModal').style.display = 'flex';
        }
    } else if (action === 'ban') {
        if (typeof selectBanPlayer === 'function') {
            selectBanPlayer(playerName);
        } else {
            document.getElementById('banPlayerName').value = playerName;
            document.getElementById('banReasonModal').style.display = 'flex';
        }
    }
};

/* ==========================================================================
   ИНИЦИАЛИЗАЦИЯ И СОБЫТИЯ ПОСЛЕ ЗАГРУЗКИ DOM
   ========================================================================== */

document.addEventListener("DOMContentLoaded", function () {
    // Подтверждение разбана
    const unbanBtn = document.getElementById('unbanConfirmBtn');
    if (unbanBtn) {
        unbanBtn.onclick = function () {
            if (!playerToUnban) return;

            fetch('/execute_command', {
                method: 'POST',
                headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
                body: new URLSearchParams({ 'command': `pardon ${playerToUnban}` })
            }).then(() => {
                closeUnbanConfirmModal();
                loadBannedPlayers();
            });
        };
    }

    // Форма личных сообщений
    const msgForm = document.getElementById('msgForm');
    if (msgForm) {
        msgForm.addEventListener('submit', function () {
            const player = document.getElementById('msgPlayerTitle').innerText;
            const text = document.getElementById('msgTextInput').value;
            document.getElementById('msgFullCommand').value = `msg ${player} ${text}`;
        });
    }

    // Слушатель сообщений от DynMap (iframe)
    window.addEventListener('message', function (event) {
        if (event.data && event.data.type === 'DYNMAP_ADMIN_ACTION') {
            sendAdminAction(event.data.action, event.data.playerName);
        }
    });

    // Клик по игрокам на Dynmap
    const mapContainer = document.getElementById('mcmap') || document.body;
    mapContainer.addEventListener('click', function (e) {
        const playerElement = e.target.closest('.dynmap-player-icon, .playerlayer, .leaflet-marker-icon');

        if (playerElement) {
            let playerName = playerElement.getAttribute('title') || playerElement.innerText;
            if (playerName) {
                selectedPlayer = playerName.trim();
                openPlayerModal(selectedPlayer);
            }
        }
    });
});

let toastTimeout;

function showToast(title, message) {
    const toast = document.getElementById('toastNotification');
    if (!toast) return;

    if (title) toast.querySelector('.toast-title').innerText = title;
    if (message) toast.querySelector('.toast-message').innerText = message;

    toast.classList.add('show');

    clearTimeout(toastTimeout);

    toastTimeout = setTimeout(() => {
        toast.classList.remove('show');
    }, 5000);
}