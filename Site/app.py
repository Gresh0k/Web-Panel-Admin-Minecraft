import os
import re
import shutil
import subprocess
from functools import wraps
import json
from datetime import datetime

from flask import (
    Flask,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_login import (
    LoginManager,
    UserMixin,
    current_user,
    login_required,
    login_user,
    logout_user,
)
from flask_sqlalchemy import SQLAlchemy
from mcrcon import MCRcon
from waitress import serve
from werkzeug.security import check_password_hash, generate_password_hash

# ==============================================================================
# --- КОНФИГУРАЦИЯ ПУТЕЙ И ПАРАМЕТРОВ (УДОБНО ДЛЯ ПЕРЕНОСА В DOCKER) ---
# ==============================================================================

# Базовая директория app.py (например: /Server_Minecraft/site)
SITE_DIR = os.path.dirname(os.path.abspath(__file__))

# 1. Главная папка сервера Minecraft (универсальный поиск):
# Если есть переменная окружения SERVER_DIR (для Docker), берем её.
# Иначе ищем папку 'server_mohist' (или 'Mohist') на уровень выше от app.py.
DEFAULT_SERVER_DIR = os.path.join(os.path.dirname(SITE_DIR), "server_mohist")
SERVER_DIR = os.environ.get("SERVER_DIR", DEFAULT_SERVER_DIR)

# 2. Путь к скрипту запуска сервера
# Для Windows используется start.bat, для Linux/Docker — start.sh
START_SCRIPT_NAME = "start.sh" if os.name != "nt" else "start.bat"
START_BAT_PATH = os.path.join(SERVER_DIR, START_SCRIPT_NAME)

# 3. База данных SQLite (будет создаваться рядом с app.py в папке сайта)
DATABASE_URI = f"sqlite:///{os.path.join(SITE_DIR, 'admins.db')}"

# 4. Настройки подключения RCON
RCON_HOST = os.environ.get("RCON_HOST", "localhost")
RCON_PORT = int(os.environ.get("RCON_PORT", 25575))
RCON_PASSWORD = os.environ.get("RCON_PASSWORD", "89658965")


def get_safe_path(req_path=""):
    clean_path = req_path.lstrip("/\\")
    target_path = os.path.abspath(os.path.join(SERVER_DIR, clean_path))
    
    # Защита от выхода за пределы рабочей папки сервера
    if not target_path.startswith(os.path.abspath(SERVER_DIR)):
        return None
        
    return target_path


# --- ИНИЦИАЛИЗАЦИЯ ПРИЛОЖЕНИЯ ---
app = Flask(__name__)

# Настройки Flask & SQLAlchemy
app.config['SECRET_KEY'] = os.urandom(24).hex()
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URI
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите в систему.'


# --- МОДЕЛЬ ПОЛЬЗОВАТЕЛЯ ---
class AdminUser(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='admin')


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(AdminUser, int(user_id))


# --- ДЕКОРАТОР ДЛЯ ВЛАДЕЛЬЦА ---
def owner_required(f):
    @wraps(f)
    @login_required
    def decorated_function(*args, **kwargs):
        if current_user.role != 'owner':
            abort(403)
        return f(*args, **kwargs)

    return decorated_function


# --- ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ---
def run_rcon(cmd):
    """Отправка RCON-команды на сервер."""
    try:
        with MCRcon(RCON_HOST, RCON_PASSWORD, port=RCON_PORT) as mcr:
            return mcr.command(cmd)
    except Exception as e:
        print(f"Ошибка RCON: {e}")
        return None


def strip_mc_colors(text: str) -> str:
    return re.sub(r'§.', '', text)


def parse_online_players():
    """Получение списка онлайн игроков через RCON."""
    raw_response = run_rcon("list")
    print(f"=== RAW RCON RESPONSE: {repr(raw_response)} ===")

    if not raw_response or not isinstance(raw_response, str):
        return []

    players = []
    lines = raw_response.strip().splitlines()

    for line in lines:
        if ":" in line:
            _, players_part = line.split(":", 1)
            if players_part.strip():
                found_players = players_part.split(",")
                for p in found_players:
                    clean_name = re.sub(r"§[0-9a-fk-or]", "", p).strip()
                    clean_name = re.sub(r"[^a-zA-Z0-9_]", "", clean_name)
                    if clean_name:
                        players.append(clean_name)

    return players


def get_safe_path(req_path=""):
    """Защита от выхода за пределы рабочей папки (Path Traversal)"""
    safe_path = os.path.abspath(os.path.join(SERVER_DIR, req_path.lstrip('/\\')))
    if not safe_path.startswith(SERVER_DIR):
        return None
    return safe_path

# --- ПОЛУЧЕНИЕ СПИСКА ЗАБАНЕННЫХ ИГРОКОВ ---
def get_banned_players():
    """Считывает файл banned-players.json из папки сервера."""
    banned_json_path = os.path.join(SERVER_DIR, 'banned-players.json')
    banned_list = []

    if os.path.exists(banned_json_path):
        try:
            with open(banned_json_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for entry in data:
                    name = entry.get('name', 'Неизвестно')
                    reason = entry.get('reason', 'Причина не указана')
                    expires_str = entry.get('expires', 'forever')
                    created_str = entry.get('created', '')

                    # Форматирование даты/срока бана
                    if expires_str.lower() == 'forever':
                        duration = 'Перманентно'
                    else:
                        # Пример формата в JSON: "2026-10-05 14:00:00 +0300"
                        duration = f"До {expires_str.split(' ')[0]} {expires_str.split(' ')[1][:5]}"

                    banned_list.append({
                        'name': name,
                        'reason': reason,
                        'duration': duration,
                        'created': created_str.split(' ')[0] if created_str else ''
                    })
        except Exception as e:
            print(f"Ошибка чтения banned-players.json: {e}")

    return banned_list


# --- API / МАРШРУТ ДЛЯ BANLIST ---
@app.get('/api/banned_players')
@login_required
def banned_players_api():
    """Возвращает JSON со списком забаненных игроков."""
    return jsonify(get_banned_players())



# --- МАРШРУТЫ АВТОРИЗАЦИИ ---
@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')

        user = AdminUser.query.filter_by(username=username).first()

        if user and check_password_hash(user.password_hash, password):
            login_user(user)
            return redirect(url_for('index'))
        else:
            flash('Неверный логин или пароль', 'error')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))


# --- ФАЙЛОВЫЙ МЕНЕДЖЕР ---
@app.route('/files')
@login_required
def files_view():
    return render_template('files.html')


@app.route('/api/files/list', methods=['GET'])
@login_required
def list_files():
    req_path = request.args.get('path', '')
    target_path = get_safe_path(req_path)

    if not target_path or not os.path.exists(target_path):
        return jsonify({'error': 'Путь не найден'}), 404

    items = []
    try:
        for entry in os.scandir(target_path):
            stat = entry.stat()
            items.append({
                'name': entry.name,
                'is_dir': entry.is_dir(),
                'size': stat.st_size if not entry.is_dir() else 0,
                'modified': int(stat.st_mtime)
            })
        items.sort(key=lambda x: (not x['is_dir'], x['name'].lower()))
        return jsonify({'current_path': req_path, 'items': items})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/read', methods=['GET'])
@login_required
def read_file():
    req_path = request.args.get('path', '')
    target_path = get_safe_path(req_path)

    if not target_path or not os.path.isfile(target_path):
        return jsonify({'error': 'Файл не найден'}), 404

    try:
        with open(target_path, 'r', encoding='utf-8', errors='ignore') as f:
            content = f.read()
        return jsonify({'content': content})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/save', methods=['POST'])
@login_required
def save_file():
    data = request.json or {}
    req_path = data.get('path', '')
    content = data.get('content', '')
    target_path = get_safe_path(req_path)

    if not target_path:
        return jsonify({'error': 'Недопустимый путь'}), 400

    try:
        with open(target_path, 'w', encoding='utf-8') as f:
            f.write(content)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/upload', methods=['POST'])
@login_required
def upload_file():
    req_path = request.form.get('path', '')
    target_dir = get_safe_path(req_path)

    if not target_dir or not os.path.isdir(target_dir):
        return jsonify({'error': 'Папка назначения не найдена'}), 400

    if 'file' not in request.files:
        return jsonify({'error': 'Файл не передан'}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Пустое имя файла'}), 400

    save_path = os.path.join(target_dir, file.filename)
    file.save(save_path)
    return jsonify({'success': True})


@app.route('/api/files/delete', methods=['POST'])
@login_required
def delete_item():
    data = request.json or {}
    req_path = data.get('path', '')
    target_path = get_safe_path(req_path)

    if not target_path or not os.path.exists(target_path):
        return jsonify({'error': 'Объект не найден'}), 404

    try:
        if os.path.isdir(target_path):
            shutil.rmtree(target_path)
        else:
            os.remove(target_path)
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/files/download', methods=['GET'])
@login_required
def download_file():
    req_path = request.args.get('path', '')
    target_path = get_safe_path(req_path)

    if not target_path or not os.path.isfile(target_path):
        return abort(404)

    return send_file(target_path, as_attachment=True)


# --- УПРАВЛЕНИЕ СОСТОЯНИЕМ СЕРВЕРА (ВКЛ / ВЫКЛ) ---
@app.post('/stop_server')
@login_required
def stop_server():
    """Безопасная остановка сервера Minecraft через RCON."""
    res = run_rcon("stop")
    if res is not None:
        flash("🛑 Команда безопасной остановки сервера отправлена!", "info")
    else:
        flash("⚠️ Не удалось связаться с сервером по RCON (возможно, он уже выключен).", "error")
    return redirect(url_for('index'))


@app.post('/start_server')
@login_required
def start_server():
    """Запуск сервера Minecraft в отдельном консольном окне."""
    try:
        if os.path.exists(START_BAT_PATH):
            subprocess.Popen(
                ['cmd.exe', '/c', 'start', '', START_BAT_PATH],
                cwd=SERVER_DIR,
                shell=True
            )
            flash("▶️ Запрос на запуск отправлен!", "success")
        else:
            flash(f"❌ Файл запуска не найден по пути: {START_BAT_PATH}", "error")
    except Exception as e:
        flash(f"❌ Ошибка при запуске сервера: {e}", "error")

    return redirect(url_for('index'))


# --- УПРАВЛЕНИЕ АДМИНИСТРАТОРАМИ ---
@app.route('/admins', methods=['GET', 'POST'])
@owner_required
def manage_admins():
    """Управление администраторами на одной странице."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Логин и пароль не могут быть пустыми!', 'error')
            return redirect(url_for('manage_admins'))

        if AdminUser.query.filter_by(username=username).first():
            flash('Администратор с таким логином уже существует!', 'error')
            return redirect(url_for('manage_admins'))

        hashed_pw = generate_password_hash(password)
        new_admin = AdminUser(username=username, password_hash=hashed_pw, role='admin')

        try:
            db.session.add(new_admin)
            db.session.commit()
            flash(f"Администратор '{username}' успешно создан!", 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании: {str(e)}', 'error')

        return redirect(url_for('manage_admins'))

    admins_data = [(u.id, u.username, u.role) for u in AdminUser.query.all()]
    return render_template('admins.html', admins=admins_data)


@app.post('/admins/delete/<int:admin_id>')
@owner_required
def delete_admin(admin_id):
    """Удаление администратора."""
    admin_to_delete = AdminUser.query.get_or_404(admin_id)

    if admin_to_delete.role == 'owner':
        flash('Нельзя удалить владельца (owner)!', 'error')
        return redirect(url_for('manage_admins'))

    try:
        db.session.delete(admin_to_delete)
        db.session.commit()
        flash(f"Администратор '{admin_to_delete.username}' удален.", 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Ошибка при удалении: {str(e)}', 'error')

    return redirect(url_for('manage_admins'))


@app.route('/create_admin', methods=['GET', 'POST'])
@owner_required
def create_admin():
    """Форма создания админа (сохранена для совместимости)."""
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')

        if not username or not password:
            flash('Логин и пароль не могут быть пустыми!', 'error')
            return redirect(url_for('create_admin'))

        if AdminUser.query.filter_by(username=username).first():
            flash('Администратор с таким логином уже существует!', 'error')
            return redirect(url_for('create_admin'))

        hashed_pw = generate_password_hash(password)
        new_admin = AdminUser(username=username, password_hash=hashed_pw, role='admin')

        try:
            db.session.add(new_admin)
            db.session.commit()
            flash(f"Администратор '{username}' успешно создан!", 'success')
            return redirect(url_for('index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Ошибка при создании: {str(e)}', 'error')
            return redirect(url_for('create_admin'))

    return render_template('create_admin.html')


# --- ЗАЩИЩЕННЫЕ МАРШРУТЫ ПАНЕЛИ ---
@app.route('/')
@login_required
def index():
    return render_template('index.html', user_role=current_user.role)


@app.route('/kick')
@login_required
def kick_menu():
    players = parse_online_players()
    return render_template('kick.html', players=players, user_role=current_user.role)


@app.get('/kick_list')
@login_required
def kick_list():
    players = parse_online_players()
    return jsonify(players)


@app.post('/kick_player')
@login_required
def kick_player():
    raw_player = request.form.get('player', '')
    player = re.sub(r'[^a-zA-Z0-9_]', '', strip_mc_colors(raw_player))
    reason = request.form.get('reason', 'Не указано').replace('"', '').replace("'", '')

    if player:
        run_rcon(f'kick {player} "{reason}"')

    return redirect(url_for('index'))


@app.post('/ban_player')
@login_required
def ban_player():
    raw_player = request.form.get('player', '')
    player = re.sub(r'[^a-zA-Z0-9_]', '', strip_mc_colors(raw_player))
    reason = request.form.get('reason', 'Не указано').replace('"', '').replace("'", '').strip()
    is_permanent = request.form.get('is_permanent') == 'on'

    if player:
        if is_permanent:
            cmd = f'ban {player} {reason}'
        else:
            amount = request.form.get('duration_amount', '1')
            unit = request.form.get('duration_unit', 'h')
            if not amount.isdigit() or int(amount) <= 0:
                amount = '1'
            duration_str = f'{amount}{unit}'

            cmd = f'tempban {player} {duration_str} {reason}'

        resp = run_rcon(cmd)
        print(f'=== COMMAND SENT: {repr(cmd)} ===')
        print(f'=== RCON RESPONSE: {repr(resp)} ===')

    return redirect(url_for('index'))


@app.post('/execute_command')
@login_required
def execute_command():
    command = request.form.get('command', '').strip()

    if command:
        response = run_rcon(command)
        flash(
            f"✅ Команда отправлена: '{command}'\n Ответ сервера: {response}",
            'success',
        )
    else:
        flash('Команда не может быть пустой!', 'error')

    return redirect(url_for('index'))


# --- ЗАПУСК ---
if __name__ == '__main__':
    with app.app_context():
        db.create_all()

    serve(app, host='0.0.0.0', port=55555)