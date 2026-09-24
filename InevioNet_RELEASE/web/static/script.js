const socket = io();
let trafficChart;
let currentUser = null;

function initChart() {
    const ctx = document.getElementById('trafficChart').getContext('2d');
    trafficChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: Array(10).fill(''),
            datasets: [{
                label: 'Пакеты/сек',
                data: Array(10).fill(0),
                borderColor: '#00ff9c',
                backgroundColor: 'rgba(0, 255, 156, 0.1)',
                tension: 0.4,
                fill: true
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: { legend: { display: false } },
            scales: {
                y: { beginAtZero: true, grid: { color: '#2a2a4a' }, ticks: { color: '#8888aa' } },
                x: { grid: { display: false } }
            }
        }
    });
}

function addLog(msg, type = 'info') {
    const container = document.getElementById('logContainer');
    if (!container) return;
    const entry = document.createElement('div');
    entry.className = `log-entry ${type}`;
    const time = new Date().toLocaleTimeString();
    entry.textContent = `[${time}] ${msg}`;
    container.appendChild(entry);
    container.scrollTop = container.scrollHeight;
}

function clearLogs() {
    const container = document.getElementById('logContainer');
    if (container) container.innerHTML = '';
    addLog('Лог очищен', 'info');
}

// ===== AUTH =====
document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        const tab = btn.dataset.tab;
        document.getElementById('loginForm').style.display = tab === 'login' ? 'flex' : 'none';
        document.getElementById('registerForm').style.display = tab === 'register' ? 'flex' : 'none';
        document.getElementById('authError').textContent = '';
    });
});

async function doLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;
    if (!username || !password) {
        document.getElementById('authError').textContent = 'Заполните все поля';
        return;
    }
    try {
        const res = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (data.success) {
            currentUser = data.user;
            showMainScreen();
            addLog(`✅ Вход выполнен: ${username}`, 'success');
        } else {
            document.getElementById('authError').textContent = data.error || 'Ошибка входа';
        }
    } catch (e) {
        document.getElementById('authError').textContent = `Ошибка: ${e.message}`;
    }
}

async function doRegister() {
    const username = document.getElementById('regUsername').value.trim();
    const password = document.getElementById('regPassword').value;
    const password2 = document.getElementById('regPassword2').value;
    if (!username || !password) {
        document.getElementById('authError').textContent = 'Заполните все поля';
        return;
    }
    if (password !== password2) {
        document.getElementById('authError').textContent = 'Пароли не совпадают';
        return;
    }
    if (password.length < 4) {
        document.getElementById('authError').textContent = 'Пароль минимум 4 символа';
        return;
    }
    try {
        const res = await fetch('/api/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });
        const data = await res.json();
        if (data.success) {
            currentUser = data.user;
            showMainScreen();
            addLog(`✅ Регистрация: ${username} (node_id: ${data.node_id})`, 'success');
        } else {
            document.getElementById('authError').textContent = data.error || 'Ошибка';
        }
    } catch (e) {
        document.getElementById('authError').textContent = `Ошибка: ${e.message}`;
    }
}

async function doLogout() {
    await fetch('/api/logout', { method: 'POST' });
    currentUser = null;
    document.getElementById('mainScreen').style.display = 'none';
    document.getElementById('authScreen').style.display = 'flex';
    document.getElementById('loginUsername').value = '';
    document.getElementById('loginPassword').value = '';
    addLog('🚪 Выход выполнен', 'info');
}

function showMainScreen() {
    document.getElementById('authScreen').style.display = 'none';
    document.getElementById('mainScreen').style.display = 'block';
    document.getElementById('currentUsername').textContent = currentUser.username;
    document.getElementById('currentUserNode').textContent = currentUser.node_id;
    loadContacts();
}

// ===== QR & CONTACTS =====
async function generateQR() {
    try {
        const res = await fetch('/api/qr');
        const data = await res.json();
        if (data.success) {
            const img = document.getElementById('qrImage');
            img.src = data.qr_url + '?t=' + Date.now();
            img.style.display = 'block';
            document.getElementById('qrPlaceholder').style.display = 'none';
            addLog(' QR-код сгенерирован', 'success');
        }
    } catch (e) {
        addLog(`❌ Ошибка QR: ${e.message}`, 'error');
    }
}

function copyNodeId() {
    if (!currentUser) return;
    navigator.clipboard.writeText(currentUser.node_id).then(() => {
        addLog(`📋 Node ID скопирован: ${currentUser.node_id}`, 'success');
    }).catch(() => {
        addLog('❌ Не удалось скопировать', 'error');
    });
}

async function addContactFromQR() {
    const raw = document.getElementById('qrImportData').value.trim();
    if (!raw) {
        addLog('❌ Вставьте JSON из QR', 'error');
        return;
    }
    try {
        const qrData = JSON.parse(raw);
        const res = await fetch('/api/contacts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ qr_data: qrData })
        });
        const data = await res.json();
        if (data.success) {
            if (data.added) {
                addLog(`✅ Контакт добавлен: ${qrData.username || 'unknown'}`, 'success');
            } else {
                addLog('ℹ️  Контакт уже существует', 'warn');
            }
            loadContacts();
        } else {
            addLog(`❌ ${data.error}`, 'error');
        }
    } catch (e) {
        addLog(`❌ Неверный JSON: ${e.message}`, 'error');
    }
}

async function removeContact(nodeId) {
    try {
        const res = await fetch(`/api/contacts/${nodeId}`, { method: 'DELETE' });
        const data = await res.json();
        if (data.success) {
            addLog(`🗑️ Контакт удалён: ${nodeId}`, 'info');
            loadContacts();
        }
    } catch (e) {
        addLog(`❌ Ошибка: ${e.message}`, 'error');
    }
}

async function loadContacts() {
    try {
        const res = await fetch('/api/contacts');
        const data = await res.json();
        const list = document.getElementById('contactsList');
        const contacts = data.contacts || [];
        document.getElementById('contactsCount').textContent = contacts.length;
        
        if (contacts.length === 0) {
            list.innerHTML = '<div class="empty-state">Нет контактов</div>';
            return;
        }
        
        list.innerHTML = contacts.map(c => `
            <div class="contact-item">
                <div>
                    <div class="contact-name">👤 ${c.username || 'unknown'}</div>
                    <div class="contact-node">${c.node_id || ''}</div>
                </div>
                <button class="contact-remove" onclick="removeContact('${c.node_id}')" title="Удалить">🗑️</button>
            </div>
        `).join('');
    } catch (e) {
        console.error(e);
    }
}

// ===== NETWORK =====
async function sendMessage() {
    const receiver = document.getElementById('receiver').value;
    const message = document.getElementById('message').value;
    const guarantee = document.getElementById('guaranteeCheck').checked;
    if (!receiver || !message) {
        addLog('❌ Заполните получателя и сообщение', 'error');
        return;
    }
    addLog(` Отправка -> ${receiver}...`, 'info');
    try {
        const res = await fetch('/api/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ receiver, message, guarantee })
        });
        const data = await res.json();
        if (data.success) {
            addLog(`✅ Отправлено! ID: ${data.packet_id ? data.packet_id.substring(0, 16) : 'ok'}...`, 'success');
        } else {
            addLog(`❌ ${data.error || 'Ошибка'}`, 'error');
        }
    } catch (e) {
        addLog(`❌ ${e.message}`, 'error');
    }
}

async function probeNetwork() {
    const target = document.getElementById('probeTarget').value;
    if (!target) return;
    addLog(`📡 Зондирование ${target}...`, 'info');
    try {
        const res = await fetch('/api/probe', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ target })
        });
        const data = await res.json();
        if (data.successful !== undefined) {
            addLog(`✅ Найдено каналов: ${data.successful}/${data.total}`, 'success');
        } else {
            addLog(`❌ ${data.error || 'Ошибка'}`, 'error');
        }
    } catch (e) {
        addLog(`❌ ${e.message}`, 'error');
    }
}

// ===== SOCKET.IO =====
socket.on('connect', () => {
    document.getElementById('statusDot').classList.add('connected');
    document.getElementById('statusText').textContent = 'Подключено к InevioNet';
    addLog('🔌 WebSocket подключён', 'success');
    socket.emit('request_stats');
});

socket.on('disconnect', () => {
    document.getElementById('statusDot').classList.remove('connected');
    document.getElementById('statusText').textContent = 'Отключено';
    addLog('🔌 Соединение разорвано', 'error');
});

socket.on('stats_update', (stats) => {
    document.getElementById('statSent').textContent = stats.packets_sent || 0;
    document.getElementById('statDelivered').textContent = stats.packets_delivered || 0;
    document.getElementById('statFailed').textContent = stats.packets_failed || 0;
    const uptime = stats.uptime || 0;
    const mins = Math.floor(uptime / 60);
    const secs = Math.floor(uptime % 60);
    document.getElementById('statUptime').textContent = `${mins}m ${secs}s`;
    if (trafficChart) {
        const newData = trafficChart.data.datasets[0].data;
        newData.shift();
        newData.push(stats.packets_sent || 0);
        trafficChart.update('none');
    }
});

// Проверка авторизации при загрузке страницы
async function checkAuth() {
    try {
        const res = await fetch('/api/me');
        const data = await res.json();
        if (data.success) {
            currentUser = data.user;
            showMainScreen();
            addLog('✅ Сессия восстановлена: ' + currentUser.username, 'success');
        } else {
            document.getElementById('authScreen').style.display = 'flex';
            document.getElementById('mainScreen').style.display = 'none';
        }
    } catch (e) {
        document.getElementById('authScreen').style.display = 'flex';
        document.getElementById('mainScreen').style.display = 'none';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initChart();
    addLog('🧬 InevioNet Dashboard загружен', 'info');
    checkAuth();
});

