from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify, abort
from datetime import datetime, timedelta
import sqlite3
import os
import shutil
import logging
import traceback
import uuid
from functools import wraps
from dotenv import load_dotenv
from werkzeug.security import check_password_hash, generate_password_hash

load_dotenv()

app = Flask(__name__, static_folder='static')
app.secret_key = os.environ.get('SECRET_KEY', 'task_manager_secret_key_2024_change_in_production')
app.config['WTF_CSRF_ENABLED'] = True
app.config['WTF_CSRF_TIME_LIMIT'] = 3600
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['SESSION_COOKIE_SECURE'] = os.environ.get('SESSION_COOKIE_SECURE', 'false').lower() == 'true'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=12)

# Logging setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

try:
    from flask_wtf.csrf import CSRFProtect
    from forms import AnnouncementForm
    csrf = CSRFProtect(app)
except ImportError:
    AnnouncementForm = None
    csrf = None

@app.context_processor
def inject_csrf_token():
    if csrf:
        return {
            'can_manage_users': can_manage_users(session.get('role', '')),
            'can_see_activity': can_see_activity_log(session.get('role', '')),
            'can_manage_announcements': can_manage_announcements(session.get('role', '')),
            'can_manage_system': can_manage_system(session.get('role', '')),
            'can_see_all_tasks': can_see_all_tasks(session.get('role', '')),
        }
    return {
        'csrf_token': lambda: '',
        'can_manage_users': can_manage_users(session.get('role', '')),
        'can_see_activity': can_see_activity_log(session.get('role', '')),
        'can_manage_announcements': can_manage_announcements(session.get('role', '')),
        'can_manage_system': can_manage_system(session.get('role', '')),
        'can_see_all_tasks': can_see_all_tasks(session.get('role', '')),
    }

# Email (optional)
# Email config removed for cleanup - enable if needed
# app.config['MAIL_SERVER'] = os.environ.get('MAIL_SERVER', '')
# ...

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_NAME = os.environ.get('DB_NAME', 'task_manager.db')
DB_PATH = DB_NAME if os.path.isabs(DB_NAME) else os.path.join(BASE_DIR, DB_NAME)

def backup_database():
    # Safety net: keep automatic snapshots before schema maintenance.
    if not os.path.exists(DB_PATH):
        return
    backups_dir = os.path.join(BASE_DIR, 'backups')
    os.makedirs(backups_dir, exist_ok=True)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(backups_dir, f'task_manager_{stamp}.db')
    shutil.copy2(DB_PATH, backup_path)

# Roles with hierarchy: مسؤول_النظام > مدير > مشرف > موظف > متدرب
def can_manage_users(role):
    return role in ('مدير', 'مسؤول_النظام')

def can_see_all_tasks(role):
    return role in ('مدير', 'مشرف', 'مسؤول_النظام')

def can_manage_announcements(role):
    return role in ('مدير', 'مسؤول_النظام')

def can_see_activity_log(role):
    return role in ('مدير', 'مسؤول_النظام')

def can_manage_system(role):
    return role == 'مسؤول_النظام'

def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            if 'user_id' not in session:
                return redirect(url_for('login'))
            if session.get('role') not in allowed_roles:
                flash('غير مصرح لك بهذه الصفحة', 'error')
                return redirect(url_for('dashboard'))
            return f(*args, **kwargs)
        return decorated
    return decorator

# Simple in-memory rate limit for login (5 per minute per IP)
from collections import defaultdict
_login_attempts = defaultdict(list)
def check_login_rate_limit():
    ip = request.remote_addr
    now = datetime.now()
    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < timedelta(minutes=1)]
    if len(_login_attempts[ip]) >= 5:
        return False
    _login_attempts[ip].append(now)
    return True

STATUS_TO_PROGRESS = {
    'معلقة': 0,
    'قيد التنفيذ': 50,
    'مكتملة': 100
}

def init_db():
    backup_database()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT NOT NULL,
            name TEXT NOT NULL,
            email TEXT,
            target_tasks INTEGER DEFAULT 5,
            overdue_notification_sent INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            assigned_to INTEGER,
            due_date TEXT,
            due_time TEXT,
            status TEXT DEFAULT 'معلقة',
            priority TEXT DEFAULT 'عادية',
            progress INTEGER DEFAULT 0,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            overdue_escalated INTEGER DEFAULT 0,
            FOREIGN KEY (assigned_to) REFERENCES users(id),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    # Announcements + seen tracking
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            content TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS announcement_seen (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            announcement_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(announcement_id, user_id),
            FOREIGN KEY (announcement_id) REFERENCES announcements(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            user_name TEXT,
            action TEXT NOT NULL,
            entity_type TEXT,
            entity_id INTEGER,
            details TEXT,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT,
            is_read INTEGER DEFAULT 0,
            email_sent INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Add performance indexes
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_assigned_to ON tasks(assigned_to)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_announcements_active ON announcements(is_active)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_announcement_seen_user ON announcement_seen(user_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_announcement_seen_ann ON announcement_seen(announcement_id)')
    
    for col in ['email', 'created_at']:
        try:
            cursor.execute(f'ALTER TABLE users ADD COLUMN {col} TEXT')
        except sqlite3.OperationalError:
            pass
    try:
        cursor.execute('ALTER TABLE tasks ADD COLUMN progress INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE tasks ADD COLUMN overdue_escalated INTEGER DEFAULT 0')
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute('ALTER TABLE tasks ADD COLUMN completed_at TEXT')
    except sqlite3.OperationalError:
        pass
    # Management org-wide targets
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS management_targets (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            period TEXT NOT NULL,
            period_type TEXT NOT NULL DEFAULT 'monthly',
            target_completions INTEGER DEFAULT 0,
            notes TEXT,
            created_by INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(period, period_type),
            FOREIGN KEY (created_by) REFERENCES users(id)
        )
    ''')
    cursor.execute("SELECT * FROM users WHERE username = 'admin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)",
            ('admin', generate_password_hash('admin123'), 'مدير', 'المدير العام')
        )
    
    # Add default system admin if not exists
    cursor.execute("SELECT * FROM users WHERE username = 'sysadmin'")
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, role, name) VALUES (?, ?, ?, ?)",
            ('sysadmin', generate_password_hash('sysadmin123'), 'مسؤول_النظام', 'مسؤول النظام')
        )
    
    conn.commit()
    conn.close()

init_db()

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('PRAGMA busy_timeout = 30000')
    conn.execute('PRAGMA foreign_keys = ON')
    conn.row_factory = sqlite3.Row
    return conn

def can_access_task(task, user_id, role):
    return can_see_all_tasks(role) or task['assigned_to'] == user_id or task['created_by'] == user_id

def parse_progress(value, default=0):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default
    return max(0, min(100, parsed))

def get_user_by_id(user_id):
    conn = get_db_connection()
    user = conn.execute('SELECT * FROM users WHERE id = ?', (user_id,)).fetchone()
    conn.close()
    return dict(user) if user else None

def log_activity(user_id, user_name, action, entity_type=None, entity_id=None, details=None):
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO activity_log (user_id, user_name, action, entity_type, entity_id, details)
        VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, user_name or '', action, entity_type, entity_id, details))
    conn.commit()
    conn.close()

def create_notification(user_id, title, message, send_email=False):
    import time
    max_retries = 3
    for attempt in range(max_retries):
        try:
            conn = get_db_connection()
            cur = conn.execute(
                'INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)',
                (user_id, title, message)
            )
            nid = cur.lastrowid
            conn.commit()
            conn.close()
            break
        except sqlite3.OperationalError as e:
            if 'database is locked' in str(e) and attempt < max_retries - 1:
                time.sleep(0.1 * (attempt + 1))  # Progressive backoff
                continue
            raise
    else:
        logger.error(f"Failed to create notification after {max_retries} retries: {title}")
    
    if send_email:
        try:
            from flask_mail import Mail, Message
            mail = Mail(app)
            user = get_user_by_id(user_id)
            if user and user.get('email') and app.config.get('MAIL_USERNAME'):
                msg = Message(title, sender=app.config['MAIL_DEFAULT_SENDER'], recipients=[user['email']], body=message)
                mail.send(msg)
                # Note: email_sent update omitted from retry-wrapped INSERT
                logger.info(f"Notification sent to {user.get('email') if user else 'unknown'}")
        except ImportError:
            logger.warning("Flask-Mail not installed - email notifications disabled")
        except Exception as e:
            logger.error(f"Failed to send notification email: {str(e)}")
            logger.error(traceback.format_exc())

def get_all_employees(role_filter=None):
    conn = get_db_connection()
    if role_filter:
        employees = conn.execute('''
            SELECT u.*,
                   (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id) as task_count,
                   (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'مكتملة') as completed_count,
                   (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'معلقة') as pending_count,
                   (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'قيد التنفيذ') as in_progress_count
            FROM users u WHERE role = ?
        ''', (role_filter,)).fetchall()
    else:
        employees = conn.execute('''
            SELECT u.*,
                   (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id) as task_count,
                   (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'مكتملة') as completed_count,
                   (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'معلقة') as pending_count,
                   (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'قيد التنفيذ') as in_progress_count
            FROM users u WHERE role IN ('موظف', 'مشرف', 'متدرب')
        ''').fetchall()
    conn.close()
    return employees

def get_all_supervisors():
    return get_all_employees('مشرف')

def get_managers():
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT u.*, (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id) as task_count,
               (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'مكتملة') as completed_count,
               (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'معلقة') as pending_count,
               (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'قيد التنفيذ') as in_progress_count
        FROM users u WHERE role IN ('مدير', 'مسؤول_النظام')
    ''').fetchall()
    conn.close()
    return rows

def get_all_users(include_trainees=True):
    conn = get_db_connection()
    roles = ('موظف', 'مشرف') if not include_trainees else ('موظف', 'مشرف', 'متدرب')
    placeholders = ','.join('?' * len(roles))
    users = conn.execute(f'''
        SELECT u.*, (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id) as task_count
        FROM users u WHERE role IN ({placeholders})
    ''', roles).fetchall()
    conn.close()
    return users

def get_tasks_for_user(user_id, role, priority=None, status=None):
    conn = get_db_connection()
    if can_see_all_tasks(role):
        query = '''
            SELECT t.*, u.name as assigned_to_name, creator.name as created_by_name
            FROM tasks t
            LEFT JOIN users u ON t.assigned_to = u.id
            LEFT JOIN users creator ON t.created_by = creator.id
        '''
        conditions, params = [], []
        if priority:
            conditions.append('t.priority = ?')
            params.append(priority)
        if status:
            conditions.append('t.status = ?')
            params.append(status)
        if conditions:
            query += ' WHERE ' + ' AND '.join(conditions)
        query += ' ORDER BY t.due_date ASC'
        tasks = conn.execute(query, params).fetchall()
    else:
        query = '''
            SELECT t.*, u.name as assigned_to_name, creator.name as created_by_name
            FROM tasks t
            LEFT JOIN users u ON t.assigned_to = u.id
            LEFT JOIN users creator ON t.created_by = creator.id
            WHERE t.assigned_to = ?
        '''
        params = [user_id]
        if priority:
            query += ' AND t.priority = ?'
            params.append(priority)
        if status:
            query += ' AND t.status = ?'
            params.append(status)
        query += ' ORDER BY t.due_date ASC'
        tasks = conn.execute(query, params).fetchall()
    conn.close()
    return tasks

def check_expiring_tasks():
    conn = get_db_connection()
    now = datetime.now()
    tomorrow = (now + timedelta(days=1)).strftime('%Y-%m-%d')
    today = now.strftime('%Y-%m-%d')
    expiring = conn.execute('''
        SELECT t.*, u.name as assigned_to_name
        FROM tasks t LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.status != 'مكتملة' AND t.due_date IN (?, ?)
    ''', (today, tomorrow)).fetchall()
    overdue = conn.execute('''
        SELECT t.*, u.name as assigned_to_name
        FROM tasks t LEFT JOIN users u ON t.assigned_to = u.id
        WHERE t.status != 'مكتملة' AND t.due_date IS NOT NULL AND t.due_date < ?
    ''', (today,)).fetchall()
    conn.close()
    return {'expiring': expiring, 'overdue': overdue}

def check_overdue_tasks_for_escalation():
    conn = get_db_connection()
    try:
        today = datetime.now().strftime('%Y-%m-%d')
        manager_ids = [r['id'] for r in conn.execute(
            "SELECT id FROM users WHERE role IN ('مدير', 'مسؤول_النظام')"
        ).fetchall()]
        overdue_tasks = conn.execute('''
            SELECT t.*, u.name as assigned_to_name, u.username as assigned_to_username
            FROM tasks t LEFT JOIN users u ON t.assigned_to = u.id
            WHERE t.status != 'مكتملة' AND t.due_date IS NOT NULL AND t.due_date < ?
            AND (t.overdue_escalated IS NULL OR t.overdue_escalated = 0)
        ''', (today,)).fetchall()
        
        if overdue_tasks:
            # Batch update overdue_escalated
            task_ids = [task['id'] for task in overdue_tasks]
            conn.executemany('UPDATE tasks SET overdue_escalated = 1 WHERE id = ?', [(tid,) for tid in task_ids])
            
            # Batch notifications
            notifications = []
            for task in overdue_tasks:
                for manager_id in manager_ids:
                    notifications.append((
                        manager_id,
                        'تنبيه تأخر مهمة',
                        f"المهمة '{task['title']}' متأخرة للموظف {task['assigned_to_name'] or 'غير محدد'}.",
                        task['id'], task['title'], task['assigned_to_name'], task['assigned_to_username'],
                        task['due_date'], task['due_time']
                    ))
            
            if notifications:
                conn.executemany(
                    'INSERT INTO notifications (user_id, title, message) VALUES (?, ?, ?)',
                    [(n[0], n[1], n[2]) for n in notifications]
                )
            
            escalation_messages = [{
                'task_id': task['id'], 'task_title': task['title'],
                'employee_name': task['assigned_to_name'], 'employee_username': task['assigned_to_username'],
                'due_date': task['due_date'], 'due_time': task['due_time']
            } for task in overdue_tasks]
            
            conn.commit()
            return escalation_messages
        return []
    finally:
        conn.close()

def get_chart_data(role, user_id):
    conn = get_db_connection()
    if can_see_all_tasks(role):
        status_counts = conn.execute('''
            SELECT status, COUNT(*) as cnt FROM tasks GROUP BY status
        ''').fetchall()
        total_tasks = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    else:
        status_counts = conn.execute('''
            SELECT status, COUNT(*) as cnt FROM tasks WHERE assigned_to = ? GROUP BY status
        ''', (user_id,)).fetchall()
        total_tasks = conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ?', (user_id,)).fetchone()[0]
    # Monthly completed for bar (last 6 months)
    six_months_ago = (datetime.now() - timedelta(days=180)).strftime('%Y-%m')
    monthly = conn.execute('''
        SELECT strftime('%Y-%m', created_at) as month, COUNT(*) as cnt
        FROM tasks WHERE status = 'مكتملة'
        ''' + (' AND assigned_to = ?' if not can_see_all_tasks(role) else '') + '''
        AND date(created_at) >= date('now', '-6 months')
        GROUP BY strftime('%Y-%m', created_at) ORDER BY month
    ''', (user_id,) if not can_see_all_tasks(role) else ()).fetchall()
    conn.close()
    return {
        'status_counts': [dict(r) for r in status_counts],
        'total_tasks': total_tasks,
        'monthly_completed': [dict(r) for r in monthly]
    }

def get_top_performer_month():
    conn = get_db_connection()
    this_month = datetime.now().strftime('%Y-%m')
    row = conn.execute('''
        SELECT u.id, u.name, COUNT(t.id) as completed_count
        FROM tasks t
        JOIN users u ON t.assigned_to = u.id
        WHERE t.status = 'مكتملة' AND strftime('%Y-%m', t.created_at) = ?
        AND u.role IN ('موظف', 'مشرف', 'متدرب')
        GROUP BY t.assigned_to ORDER BY completed_count DESC LIMIT 1
    ''', (this_month,)).fetchone()
    conn.close()
    return dict(row) if row else None

def get_monthly_achievement(month=None):
    """Monthly achievement per employee + org total."""
    if not month:
        month = datetime.now().strftime('%Y-%m')
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT u.id, u.name, u.role, u.username,
               COALESCE(u.target_tasks, 5) as target,
               COUNT(CASE WHEN t.status = 'مكتملة'
                     AND strftime('%Y-%m', COALESCE(t.completed_at, t.created_at)) = ?
                     THEN 1 END) as completed
        FROM users u
        LEFT JOIN tasks t ON t.assigned_to = u.id
        WHERE u.role IN ('موظف', 'مشرف', 'متدرب')
        GROUP BY u.id
        ORDER BY completed DESC
    ''', (month,)).fetchall()
    conn.close()
    result = []
    for r in rows:
        d = dict(r)
        d['pct'] = min(100, int(d['completed'] / d['target'] * 100)) if d['target'] > 0 else 0
        result.append(d)
    return result

def get_quarterly_achievement(year=None, quarter=None):
    """Quarterly achievement per employee for given year/quarter."""
    now = datetime.now()
    if not year:
        year = now.year
    if not quarter:
        quarter = (now.month - 1) // 3 + 1
    q_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
    start_m, end_m = q_months[quarter]
    start_date = f'{year}-{start_m:02d}-01'
    end_date = f'{year}-{end_m:02d}-31'
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT u.id, u.name, u.role, u.username,
               COALESCE(u.target_tasks, 5) as monthly_target,
               COUNT(CASE WHEN t.status = 'مكتملة'
                     AND date(COALESCE(t.completed_at, t.created_at)) BETWEEN date(?) AND date(?)
                     THEN 1 END) as completed
        FROM users u
        LEFT JOIN tasks t ON t.assigned_to = u.id
        WHERE u.role IN ('موظف', 'مشرف', 'متدرب')
        GROUP BY u.id
        ORDER BY completed DESC
    ''', (start_date, end_date)).fetchall()
    # Org total completed this quarter
    org_total = conn.execute('''
        SELECT COUNT(*) FROM tasks
        WHERE status = 'مكتملة'
        AND date(COALESCE(completed_at, created_at)) BETWEEN date(?) AND date(?)
    ''', (start_date, end_date)).fetchone()[0]
    # Management target for this quarter
    q_key = f'{year}-Q{quarter}'
    mgmt = conn.execute(
        'SELECT target_completions FROM management_targets WHERE period = ? AND period_type = ?',
        (q_key, 'quarterly')
    ).fetchone()
    conn.close()
    q_names = {1: 'الأول', 2: 'الثاني', 3: 'الثالث', 4: 'الرابع'}
    result = []
    for r in rows:
        d = dict(r)
        q_target = d['monthly_target'] * 3
        d['q_target'] = q_target
        d['pct'] = min(100, int(d['completed'] / q_target * 100)) if q_target > 0 else 0
        result.append(d)
    return {
        'quarter': quarter,
        'quarter_name': q_names[quarter],
        'year': year,
        'employees': result,
        'org_total': org_total,
        'mgmt_target': mgmt['target_completions'] if mgmt else 0
    }

def get_all_quarters_summary(year=None):
    """Summary of all 4 quarters for the year."""
    if not year:
        year = datetime.now().year
    conn = get_db_connection()
    quarters = []
    q_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
    q_names = {1: 'الأول', 2: 'الثاني', 3: 'الثالث', 4: 'الرابع'}
    for q, (sm, em) in q_months.items():
        start_date = f'{year}-{sm:02d}-01'
        end_date = f'{year}-{em:02d}-31'
        total = conn.execute('''
            SELECT COUNT(*) FROM tasks
            WHERE status = 'مكتملة'
            AND date(COALESCE(completed_at, created_at)) BETWEEN date(?) AND date(?)
        ''', (start_date, end_date)).fetchone()[0]
        q_key = f'{year}-Q{q}'
        mgmt = conn.execute(
            'SELECT target_completions FROM management_targets WHERE period = ? AND period_type = ?',
            (q_key, 'quarterly')
        ).fetchone()
        quarters.append({
            'quarter': q,
            'name': q_names[q],
            'total': total,
            'target': mgmt['target_completions'] if mgmt else 0,
            'pct': min(100, int(total / mgmt['target_completions'] * 100)) if mgmt and mgmt['target_completions'] > 0 else 0
        })
    conn.close()
    return quarters

def get_management_target(period, period_type):
    conn = get_db_connection()
    row = conn.execute(
        'SELECT * FROM management_targets WHERE period = ? AND period_type = ?',
        (period, period_type)
    ).fetchone()
    conn.close()
    return dict(row) if row else None

def get_recent_activity(limit=20):
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT * FROM activity_log ORDER BY created_at DESC LIMIT ?
    ''', (limit,)).fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_active_announcements(user_id):
    conn = get_db_connection()
    rows = conn.execute('''
        SELECT a.*, creator.name as created_by_name
        FROM announcements a
        LEFT JOIN users creator ON a.created_by = creator.id
        WHERE a.is_active = 1 ORDER BY a.created_at DESC
    ''').fetchall()
    result = []
    for r in rows:
        seen = conn.execute(
            'SELECT 1 FROM announcement_seen WHERE announcement_id = ? AND user_id = ?',
            (r['id'], user_id)
        ).fetchone()
        result.append({**dict(r), 'seen': seen is not None})
    conn.close()
    return result

@app.route('/')
def index():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return redirect(url_for('dashboard'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        if not check_login_rate_limit():
            flash('محاولات دخول كثيرة. انتظر دقيقة وحاول مجدداً.', 'error')
            return render_template('login.html')
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ?', (username,)).fetchone()
        conn.close()
        if user:
            if user['password'].startswith(('pbkdf2:', 'scrypt:', 'argon2:')):
                ok = check_password_hash(user['password'], password)
            else:
                ok = (user['password'] == password)
                if ok:
                    hashed = generate_password_hash(password)
                    conn = get_db_connection()
                    conn.execute('UPDATE users SET password = ? WHERE id = ?', (hashed, user['id']))
                    conn.commit()
                    conn.close()
            if ok:
                session.permanent = True
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']
                session['name'] = user['name']
                log_activity(user['id'], user['name'], 'تسجيل دخول', details=username)
                return redirect(url_for('dashboard'))
        flash('اسم المستخدم أو كلمة المرور خطأ', 'error')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    user = get_user_by_id(session['user_id'])
    tasks = get_tasks_for_user(session['user_id'], session['role'])
    alerts = check_expiring_tasks()
    escalations = []
    if can_see_activity_log(session['role']):
        escalations = check_overdue_tasks_for_escalation()
    conn = get_db_connection()
    role = session['role']
    if can_see_all_tasks(role):
        stats = {
            'total_employees': conn.execute("SELECT COUNT(*) FROM users WHERE role = 'موظف'").fetchone()[0],
            'total_supervisors': conn.execute("SELECT COUNT(*) FROM users WHERE role = 'مشرف'").fetchone()[0],
            'total_trainees': conn.execute("SELECT COUNT(*) FROM users WHERE role = 'متدرب'").fetchone()[0],
            'total_tasks': conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],
        }
    else:
        stats = {
            'total_employees': 0, 'total_supervisors': 0, 'total_trainees': 0,
            'total_tasks': conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ?', (session['user_id'],)).fetchone()[0],
        }
    stats['pending_tasks'] = conn.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('معلقة',)).fetchone()[0] if can_see_all_tasks(role) else conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status = ?', (session['user_id'], 'معلقة')).fetchone()[0]
    stats['in_progress_tasks'] = conn.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('قيد التنفيذ',)).fetchone()[0] if can_see_all_tasks(role) else conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status = ?', (session['user_id'], 'قيد التنفيذ')).fetchone()[0]
    stats['completed_tasks'] = conn.execute('SELECT COUNT(*) FROM tasks WHERE status = ?', ('مكتملة',)).fetchone()[0] if can_see_all_tasks(role) else conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status = ?', (session['user_id'], 'مكتملة')).fetchone()[0]
    today = datetime.now().strftime('%Y-%m-%d')
    stats['overdue_tasks'] = conn.execute('SELECT COUNT(*) FROM tasks WHERE status != ? AND due_date IS NOT NULL AND due_date < ?', ('مكتملة', today)).fetchone()[0] if can_see_all_tasks(role) else conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status != ? AND due_date IS NOT NULL AND due_date < ?', (session['user_id'], 'مكتملة', today)).fetchone()[0]
    conn.close()
    chart_data = get_chart_data(session['role'], session['user_id'])
    top_performer = get_top_performer_month() if can_see_activity_log(session['role']) else None
    recent_activity = get_recent_activity(10) if can_see_activity_log(session['role']) else []
    announcements = get_active_announcements(session['user_id'])

    # Team achievement for manager/supervisor
    team_monthly = []
    team_quarterly = None
    if can_see_all_tasks(role):
        team_monthly = get_monthly_achievement()
        now_dt = datetime.now()
        team_quarterly = get_quarterly_achievement(now_dt.year, (now_dt.month - 1) // 3 + 1)

    return render_template('dashboard.html', user=user, tasks=tasks, stats=stats, alerts=alerts, escalations=escalations,
                         chart_data=chart_data, top_performer=top_performer, recent_activity=recent_activity,
                         announcements=announcements, can_manage_users=can_manage_users(role),
                         can_see_activity=can_see_activity_log(role), can_manage_announcements=can_manage_announcements(role),
                         team_monthly=team_monthly, team_quarterly=team_quarterly)

@app.route('/my_dashboard')
@login_required
def my_dashboard():
    user = get_user_by_id(session['user_id'])
    conn = get_db_connection()
    uid = session['user_id']
    target = user.get('target_tasks') or 5
    this_month = datetime.now().strftime('%Y-%m')
    completed_this_month = conn.execute('''
        SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status = 'مكتملة'
        AND strftime('%Y-%m', created_at) = ?
    ''', (uid, this_month)).fetchone()[0]
    today = datetime.now().strftime('%Y-%m-%d')
    completed = conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status = ?', (uid, 'مكتملة')).fetchone()[0]
    overdue = conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status != ? AND due_date IS NOT NULL AND due_date < ?', (uid, 'مكتملة', today)).fetchone()[0]
    pending = conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status = ?', (uid, 'معلقة')).fetchone()[0]
    in_progress = conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status = ?', (uid, 'قيد التنفيذ')).fetchone()[0]
    tasks = get_tasks_for_user(uid, session['role'])
    conn.close()
    return render_template('my_dashboard.html', user=user, target=target, completed_this_month=completed_this_month,
                         completed=completed, overdue=overdue, pending=pending, in_progress=in_progress, tasks=tasks)

@app.route('/api/my_dashboard_search')
@login_required
def my_dashboard_search():
    q = request.args.get('q', '').strip()
    tasks = get_tasks_for_user(session['user_id'], session['role'])
    if not q:
        return jsonify({'tasks': [{'id': t['id'], 'title': t['title'], 'status': t['status'], 'due_date': t['due_date']} for t in tasks]})
    q_lower = q.lower()
    filtered = [t for t in tasks if q_lower in (t['title'] or '').lower() or q_lower in (t['description'] or '').lower()]
    return jsonify({'tasks': [{'id': t['id'], 'title': t['title'], 'status': t['status'], 'due_date': t['due_date']} for t in filtered]})

@app.route('/announcement/seen/<int:aid>', methods=['POST'])
@login_required
def mark_announcement_seen(aid):
    conn = get_db_connection()
    conn.execute('INSERT OR IGNORE INTO announcement_seen (announcement_id, user_id) VALUES (?, ?)', (aid, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/announcements', methods=['GET', 'POST'])
@login_required
def announcements_page():
    can_manage = can_manage_announcements(session['role'])
    form = AnnouncementForm() if AnnouncementForm else None
    if request.method == 'POST' and not can_manage:
        flash('غير مصرح بإدارة الإعلانات', 'error')
        return redirect(url_for('announcements_page'))
    if can_manage and request.method == 'POST':
        if form:
            is_valid = form.validate_on_submit()
            title = (form.title.data or '').strip()
            content = (form.content.data or '').strip()
        else:
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            is_valid = bool(title and content and len(title) >= 3 and len(content) >= 10)
        if is_valid:
            conn = get_db_connection()
            conn.execute('INSERT INTO announcements (title, content, created_by) VALUES (?, ?, ?)', 
                        (title, content, session['user_id']))
            conn.commit()
            conn.close()
            log_activity(session['user_id'], session.get('name'), 'إعلان جديد', 'announcement', None, title)
            flash('تم إضافة الإعلان بنجاح', 'success')
            return redirect(url_for('announcements_page'))
        flash('تأكد من العنوان (3+ أحرف) والمحتوى (10+ أحرف).', 'error')
    
    conn = get_db_connection()
    list_all = conn.execute('SELECT a.*, u.name as created_by_name FROM announcements a LEFT JOIN users u ON a.created_by = u.id ORDER BY a.created_at DESC').fetchall()
    conn.close()
    return render_template('announcements.html', user=get_user_by_id(session['user_id']), 
                         announcements=[dict(r) for r in list_all], form=form, can_manage_announcements=can_manage)

@app.route('/announcement/edit/<int:aid>', methods=['GET', 'POST'])
@login_required
def announcement_edit(aid):
    if not can_manage_announcements(session['role']):
        flash('غير مصرح', 'error')
        return redirect(url_for('dashboard'))
    form = AnnouncementForm() if AnnouncementForm else None
    announcement = None
    
    conn = get_db_connection()
    ann = conn.execute('SELECT * FROM announcements WHERE id = ?', (aid,)).fetchone()
    if ann:
        announcement = dict(ann)
        if form:
            form.title.data = announcement['title']
            form.content.data = announcement['content']
    
    if request.method == 'POST':
        if form:
            is_valid = form.validate_on_submit()
            title = (form.title.data or '').strip()
            content = (form.content.data or '').strip()
        else:
            title = request.form.get('title', '').strip()
            content = request.form.get('content', '').strip()
            is_valid = bool(title and content and len(title) >= 3 and len(content) >= 10)
        if is_valid:
            conn.execute('UPDATE announcements SET title = ?, content = ? WHERE id = ?', 
                        (title, content, aid))
            conn.commit()
            log_activity(session['user_id'], session.get('name'), 'تعديل إعلان', 'announcement', aid, title)
            conn.close()
            flash('تم تعديل الإعلان بنجاح', 'success')
            return redirect(url_for('announcements_page'))
        flash('تأكد من العنوان (3+ أحرف) والمحتوى (10+ أحرف).', 'error')
    conn.close()
    
    return render_template('announcement_edit.html', user=get_user_by_id(session['user_id']), 
                         announcement=announcement, form=form)

@app.route('/announcement/delete/<int:aid>', methods=['POST'])
@login_required
def announcement_delete(aid):
    if not can_manage_announcements(session['role']):
        flash('غير مصرح', 'error')
        return redirect(url_for('dashboard'))

    conn = get_db_connection()
    ann = conn.execute('SELECT title FROM announcements WHERE id = ?', (aid,)).fetchone()
    if ann:
        conn.execute('DELETE FROM announcements WHERE id = ?', (aid,))
        conn.execute('DELETE FROM announcement_seen WHERE announcement_id = ?', (aid,))
        conn.commit()
        log_activity(session['user_id'], session.get('name'), 'حذف إعلان', 'announcement', aid, ann['title'])
    conn.close()
    flash('تم حذف الإعلان', 'success')
    return redirect(url_for('announcements_page'))

@app.route('/announcement/toggle/<int:aid>', methods=['POST'])
@login_required
def announcement_toggle(aid):
    if not can_manage_announcements(session['role']):
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    row = conn.execute('SELECT is_active FROM announcements WHERE id = ?', (aid,)).fetchone()
    if row:
        new = 0 if row[0] else 1
        conn.execute('UPDATE announcements SET is_active = ? WHERE id = ?', (new, aid))
        conn.commit()
    conn.close()
    return redirect(url_for('announcements_page'))

@app.route('/activity')
@login_required
def activity_page():
    if not can_see_activity_log(session['role']):
        flash('غير مصرح', 'error')
        return redirect(url_for('dashboard'))
    recent = get_recent_activity(50)
    return render_template('activity.html', user=get_user_by_id(session['user_id']), activities=recent)

@app.route('/people')
@login_required
def people_page():
    if not can_manage_users(session['role']):
        flash('غير مصرح', 'error')
        return redirect(url_for('dashboard'))
    user = get_user_by_id(session['user_id'])
    managers = [dict(r) for r in (get_managers() if can_manage_system(session['role']) else [])]
    supervisors = [dict(r) for r in get_all_supervisors()]
    employees = [dict(r) for r in get_all_employees('موظف')]
    trainees = [dict(r) for r in get_all_employees('متدرب')]
    return render_template('people.html', user=user, managers=managers, supervisors=supervisors, employees=employees, trainees=trainees,
                         can_manage_system=can_manage_system(session['role']))

@app.route('/employees', methods=['GET', 'POST'])
@login_required
def employees():
    if not can_manage_users(session['role']):
        flash('غير مصرح لك بهذه الصفحة', 'error')
        return redirect(url_for('dashboard'))
    if request.method == 'POST':
        user_type = request.form.get('user_type', 'موظف')
        if user_type == 'مدير' and not can_manage_system(session['role']):
            flash('غير مصرح بإضافة مديرين', 'error')
            return redirect(url_for('employees'))
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '')
        name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip() or None
        if not username or not name or not password:
            flash('الاسم واسم المستخدم وكلمة المرور مطلوبة', 'error')
            return redirect(url_for('employees'))
        hashed_password = generate_password_hash(password)
        try:
            conn = get_db_connection()
            conn.execute('INSERT INTO users (username, password, role, name, email) VALUES (?, ?, ?, ?, ?)',
                        (username, hashed_password, user_type, name, email))
            conn.commit()
            uid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
            conn.close()
            log_activity(session['user_id'], session.get('name'), 'إضافة مستخدم', 'user', uid, name)
            role_name = {'مدير': 'مدير', 'مشرف': 'المشرف', 'موظف': 'الموظف', 'متدرب': 'المتدرب'}.get(user_type, user_type)
            flash(f'تم إضافة {role_name} بنجاح', 'success')
        except sqlite3.IntegrityError:
            flash('اسم المستخدم موجود بالفعل', 'error')
        return redirect(url_for('employees'))
    user = get_user_by_id(session['user_id'])
    employees_list = get_all_employees('موظف')
    supervisors_list = get_all_supervisors()
    trainees_list = get_all_employees('متدرب')
    return render_template('employees.html', employees=employees_list, supervisors=supervisors_list, trainees=trainees_list, user=user)

@app.route('/delete_employee/<int:employee_id>', methods=['POST'])
@login_required
def delete_employee(employee_id):
    if not can_manage_users(session['role']):
        flash('غير مصرح لك بهذه الصفحة', 'error')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    u = conn.execute('SELECT role, name FROM users WHERE id = ?', (employee_id,)).fetchone()
    if u and employee_id != session['user_id']:
        # Prevent deleting self or managers unless system admin
        if u['role'] == 'مدير' and not can_manage_system(session['role']):
            conn.close()
            flash('غير مصرح بحذف المديرين', 'error')
            return redirect(url_for('employees'))
        conn.execute('UPDATE tasks SET created_by = NULL WHERE created_by = ?', (employee_id,))
        conn.execute('DELETE FROM tasks WHERE assigned_to = ?', (employee_id,))
        conn.execute('DELETE FROM users WHERE id = ?', (employee_id,))
        conn.commit()
        log_activity(session['user_id'], session.get('name'), 'حذف مستخدم', 'user', employee_id, u['name'])
    conn.close()
    flash('تم الحذف بنجاح', 'success')
    return redirect(url_for('employees'))

@app.route('/edit_employee', methods=['POST'])
@login_required
def edit_employee():
    if not can_manage_users(session['role']):
        flash('غير مصرح', 'error')
        return redirect(url_for('dashboard'))
    employee_id = request.form.get('employee_id')
    name = request.form.get('name', '').strip()
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '')
    email = request.form.get('email', '').strip() or None
    user_type = request.form.get('user_type', 'موظف')
    conn = get_db_connection()
    if user_type == 'مدير' and not can_manage_system(session['role']):
        flash('غير مصرح بتعديل المديرين', 'error')
        return redirect(url_for('employees'))
    try:
        if password:
            conn.execute('UPDATE users SET name = ?, username = ?, password = ?, role = ?, email = ? WHERE id = ?',
                        (name, username, generate_password_hash(password), user_type, email, employee_id))
        else:
            conn.execute('UPDATE users SET name = ?, username = ?, role = ?, email = ? WHERE id = ?',
                        (name, username, user_type, email, employee_id))
        conn.commit()
        log_activity(session['user_id'], session.get('name'), 'تعديل مستخدم', 'user', int(employee_id), name)
        flash('تم تحديث البيانات بنجاح', 'success')
    except sqlite3.IntegrityError:
        flash('اسم المستخدم موجود بالفعل', 'error')
    conn.close()
    return redirect(url_for('employees'))

@app.route('/employee/<int:employee_id>/tasks')
@login_required
def employee_tasks(employee_id):
    if not can_see_all_tasks(session['role']) and session['user_id'] != employee_id:
        flash('غير مصرح', 'error')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    employee = conn.execute('SELECT * FROM users WHERE id = ?', (employee_id,)).fetchone()
    if not employee:
        conn.close()
        abort(404)
    tasks = conn.execute('''
        SELECT t.*, creator.name as created_by_name
        FROM tasks t LEFT JOIN users creator ON t.created_by = creator.id
        WHERE t.assigned_to = ? ORDER BY t.due_date ASC
    ''', (employee_id,)).fetchall()
    conn.close()
    return render_template('employee_tasks.html', employee=dict(employee) if employee else None, tasks=tasks, user=get_user_by_id(session['user_id']))

@app.route('/employee/<int:employee_id>/dashboard')
@login_required
def employee_dashboard(employee_id):
    if not can_see_all_tasks(session['role']) and session['user_id'] != employee_id:
        flash('غير مصرح', 'error')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    employee = conn.execute('SELECT * FROM users WHERE id = ?', (employee_id,)).fetchone()
    if not employee:
        conn.close()
        abort(404)
    now = datetime.now()
    today = now.strftime('%Y-%m-%d')
    this_month = now.strftime('%Y-%m')
    this_year = now.year
    current_quarter = (now.month - 1) // 3 + 1
    q_months = {1: (1, 3), 2: (4, 6), 3: (7, 9), 4: (10, 12)}
    q_names = {1: 'الأول', 2: 'الثاني', 3: 'الثالث', 4: 'الرابع'}
    start_m, end_m = q_months[current_quarter]
    q_start = f'{this_year}-{start_m:02d}-01'
    q_end   = f'{this_year}-{end_m:02d}-31'

    stats = {
        'total_tasks': conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ?', (employee_id,)).fetchone()[0],
        'completed_tasks': conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status = ?', (employee_id, 'مكتملة')).fetchone()[0],
        'in_progress_tasks': conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status = ?', (employee_id, 'قيد التنفيذ')).fetchone()[0],
        'pending_tasks': conn.execute('SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status = ?', (employee_id, 'معلقة')).fetchone()[0],
        'overdue_tasks': conn.execute(
            'SELECT COUNT(*) FROM tasks WHERE assigned_to = ? AND status != ? AND due_date IS NOT NULL AND due_date < ?',
            (employee_id, 'مكتملة', today)
        ).fetchone()[0],
    }
    monthly_completed = conn.execute('''
        SELECT COUNT(*) FROM tasks
        WHERE assigned_to = ? AND status = 'مكتملة'
        AND strftime('%Y-%m', COALESCE(completed_at, created_at)) = ?
    ''', (employee_id, this_month)).fetchone()[0]

    quarterly_completed = conn.execute('''
        SELECT COUNT(*) FROM tasks
        WHERE assigned_to = ? AND status = 'مكتملة'
        AND date(COALESCE(completed_at, created_at)) BETWEEN date(?) AND date(?)
    ''', (employee_id, q_start, q_end)).fetchone()[0]

    recent_tasks = conn.execute('''
        SELECT t.*, creator.name as created_by_name
        FROM tasks t
        LEFT JOIN users creator ON t.created_by = creator.id
        WHERE t.assigned_to = ?
        ORDER BY t.created_at DESC
        LIMIT 12
    ''', (employee_id,)).fetchall()
    conn.close()

    employee_dict = dict(employee)
    target = employee_dict.get('target_tasks') or 5
    q_target = target * 3
    completion_rate = int((stats['completed_tasks'] / stats['total_tasks']) * 100) if stats['total_tasks'] > 0 else 0
    monthly_pct  = min(100, int(monthly_completed  / target   * 100)) if target   > 0 else 0
    quarterly_pct = min(100, int(quarterly_completed / q_target * 100)) if q_target > 0 else 0

    return render_template(
        'employee_dashboard.html',
        user=get_user_by_id(session['user_id']),
        employee=employee_dict,
        stats=stats,
        recent_tasks=recent_tasks,
        monthly_completed=monthly_completed,
        target=target,
        completion_rate=completion_rate,
        monthly_target_rate=monthly_pct,
        monthly_pct=monthly_pct,
        quarterly_completed=quarterly_completed,
        q_target=q_target,
        quarterly_pct=quarterly_pct,
        current_quarter=current_quarter,
        quarter_name=q_names[current_quarter],
        this_year=this_year,
        this_month=this_month,
    )

@app.route('/add_task', methods=['POST'])
@login_required
def add_task():
    title = request.form.get('title', '').strip()
    description = request.form.get('description', '').strip()
    progress = parse_progress(request.form.get('progress', 0))
    if not title:
        flash('عنوان المهمة مطلوب', 'error')
        return redirect(url_for('tasks'))
    if can_manage_users(session['role']) or can_see_all_tasks(session['role']):
        assigned_to = request.form.get('assigned_to')
    else:
        assigned_to = session['user_id']
    due_date = request.form.get('due_date') or None
    due_time = request.form.get('due_time') or None
    priority = request.form.get('priority', 'عادية')
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO tasks (title, description, assigned_to, due_date, due_time, priority, progress, created_by)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (title, description, int(assigned_to) if assigned_to else None, due_date, due_time, priority, int(progress), session['user_id']))
    conn.commit()
    tid = conn.execute('SELECT last_insert_rowid()').fetchone()[0]
    conn.close()
    log_activity(session['user_id'], session.get('name'), 'إضافة مهمة', 'task', tid, title)
    assignee = get_user_by_id(int(assigned_to)) if assigned_to else None
    if assignee and assignee.get('id') != session['user_id']:
        create_notification(int(assigned_to), 'مهمة جديدة', f'تم تعيينك في مهمة: {title}', send_email=True)
    flash('تم اضافة المهمة بنجاح', 'success')
    return redirect(url_for('tasks'))

@app.route('/tasks', methods=['GET', 'POST'])
@login_required
def tasks():
    priority = request.args.get('priority')
    status = request.args.get('status')
    employees = get_all_users()
    user = get_user_by_id(session['user_id'])
    tasks_list = get_tasks_for_user(session['user_id'], session['role'], priority, status)
    return render_template('tasks.html', tasks=tasks_list, employees=employees, user=user, priority=priority, status=status)

@app.route('/update_task/<int:task_id>', methods=['POST'])
@login_required
def update_task(task_id):
    status = request.form.get('status')
    valid_statuses = {'معلقة', 'قيد التنفيذ', 'مكتملة'}
    if status not in valid_statuses:
        flash('حالة مهمة غير صالحة', 'error')
        return redirect(url_for('tasks'))
    conn = get_db_connection()
    task = conn.execute('SELECT * FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if not task:
        conn.close()
        return redirect(url_for('tasks'))
    if not can_access_task(task, session['user_id'], session['role']):
        conn.close()
        abort(403)
    # Assignee OR manager/sysadmin can update status
    if task['assigned_to'] != session['user_id'] and not can_manage_users(session['role']):
        conn.close()
        abort(403)
    progress = STATUS_TO_PROGRESS.get(status, task['progress'])
    now_str = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    completed_at = now_str if status == 'مكتملة' else None
    if status == 'مكتملة':
        conn.execute('UPDATE tasks SET status = ?, progress = ?, completed_at = ? WHERE id = ?',
                     (status, progress, completed_at, task_id))
    else:
        conn.execute('UPDATE tasks SET status = ?, progress = ?, completed_at = NULL WHERE id = ?',
                     (status, progress, task_id))
    conn.commit()
    conn.close()
    log_activity(session['user_id'], session.get('name'), 'تحديث حالة المهمة', 'task', task_id, f"{task['title']} → {status} ({progress}%)")
    if task['assigned_to'] and task['assigned_to'] != session['user_id'] and status == 'مكتملة':
        create_notification(task['assigned_to'], 'مهمة مكتملة', f'تم إكمال المهمة: {task["title"]}', send_email=True)
    flash('تم تحديث حالة المهمة ونسبة الإنجاز تلقائياً', 'success')
    return redirect(url_for('tasks'))

@app.route('/delete_task/<int:task_id>', methods=['POST'])
@login_required
def delete_task(task_id):
    if not can_manage_users(session['role']):
        flash('غير مصرح', 'error')
        return redirect(url_for('dashboard'))
    conn = get_db_connection()
    task = conn.execute('SELECT title FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if task:
        conn.execute('DELETE FROM tasks WHERE id = ?', (task_id,))
        conn.commit()
        log_activity(session['user_id'], session.get('name'), 'حذف مهمة', 'task', task_id, task['title'])
    conn.close()
    flash('تم حذف المهمة', 'success')
    return redirect(url_for('tasks'))

@app.route('/api/alerts')
@login_required
def api_alerts():
    alerts = check_expiring_tasks()
    return jsonify({
        'expiring': [dict(row) for row in alerts['expiring']],
        'overdue': [dict(row) for row in alerts['overdue']]
    })

@app.route('/api/notifications')
@login_required
def api_notifications():
    conn = get_db_connection()
    rows = conn.execute('SELECT id, title, message, is_read, created_at FROM notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 30', (session['user_id'],)).fetchall()
    conn.close()
    return jsonify({'notifications': [dict(r) for r in rows]})

@app.route('/api/notifications/read/<int:nid>', methods=['POST'])
@login_required
def api_notification_read(nid):
    conn = get_db_connection()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE id = ? AND user_id = ?', (nid, session['user_id']))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.route('/api/notifications/read_all', methods=['POST'])
@login_required
def api_notifications_read_all():
    conn = get_db_connection()
    conn.execute('UPDATE notifications SET is_read = 1 WHERE user_id = ?', (session['user_id'],))
    conn.commit()
    conn.close()
    return jsonify({'ok': True})

@app.errorhandler(500)
def internal_error(error):
    error_id = str(uuid.uuid4())[:8]
    logger.error(f"500 Internal Error [{error_id}]: {request.url}")
    logger.error(traceback.format_exc())
    
    user = None
    if 'user_id' in session:
        user = get_user_by_id(session['user_id'])
    
    return render_template('500.html', error_id=error_id, user=user), 500

@app.route('/toggle_theme')
def toggle_theme():
    if 'theme' in session:
        session.pop('theme')
    else:
        session['theme'] = 'dark'
    return redirect(request.referrer or url_for('dashboard'))

@app.route('/update_employee_target/<int:employee_id>', methods=['POST'])
@login_required
def update_employee_target(employee_id):
    if not can_manage_users(session['role']):
        return redirect(url_for('dashboard'))
    target = request.form.get('target_tasks', 5)
    conn = get_db_connection()
    conn.execute('UPDATE users SET target_tasks = ? WHERE id = ?', (target, employee_id))
    conn.commit()
    conn.close()
    flash('تم تحديث المستهدف بنجاح', 'success')
    return redirect(request.referrer or url_for('employees'))

@app.route('/update_task_progress/<int:task_id>', methods=['POST'])
@login_required
def update_task_progress(task_id):
    progress = parse_progress(request.form.get('progress', 0))
    conn = get_db_connection()
    task = conn.execute('SELECT id, title, assigned_to, created_by FROM tasks WHERE id = ?', (task_id,)).fetchone()
    if task:
        if not can_access_task(task, session['user_id'], session['role']):
            conn.close()
            abort(403)
        conn.execute('UPDATE tasks SET progress = ? WHERE id = ?', (progress, task_id))
        conn.commit()
        log_activity(session['user_id'], session.get('name'), 'تحديث نسبة إنجاز المهمة', 'task', task_id, f"{task['title']} → {progress}%")
    conn.close()
    return jsonify({'success': True, 'progress': progress})

@app.route('/set_management_target', methods=['POST'])
@login_required
@role_required('مسؤول_النظام')
def set_management_target():
    period_type = request.form.get('period_type', 'monthly')
    period = request.form.get('period', '').strip()
    target_completions = request.form.get('target_completions', 0)
    notes = request.form.get('notes', '').strip() or None
    try:
        target_completions = max(0, int(target_completions))
    except (ValueError, TypeError):
        target_completions = 0
    if not period:
        flash('الفترة مطلوبة', 'error')
        return redirect(url_for('system_admin'))
    conn = get_db_connection()
    conn.execute('''
        INSERT INTO management_targets (period, period_type, target_completions, notes, created_by)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(period, period_type) DO UPDATE SET
            target_completions = excluded.target_completions,
            notes = excluded.notes
    ''', (period, period_type, target_completions, notes, session['user_id']))
    conn.commit()
    conn.close()
    log_activity(session['user_id'], session.get('name'), 'تحديث هدف إداري', details=f'{period_type}: {period} → {target_completions}')
    flash('تم تحديث الهدف بنجاح', 'success')
    return redirect(url_for('system_admin'))

@app.route('/system_admin')
@login_required
@role_required('مسؤول_النظام')
def system_admin():
    user = get_user_by_id(session['user_id'])
    conn = get_db_connection()
    now = datetime.now()
    this_month = now.strftime('%Y-%m')
    this_year = now.year
    current_quarter = (now.month - 1) // 3 + 1

    # All users with task counts
    all_users = conn.execute('''
        SELECT u.*,
               (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id) as task_count,
               (SELECT COUNT(*) FROM tasks WHERE assigned_to = u.id AND status = 'مكتملة') as completed_count
        FROM users u ORDER BY u.role, u.created_at DESC
    ''').fetchall()

    # System stats
    today = now.strftime('%Y-%m-%d')
    stats = {
        'total_users':          conn.execute('SELECT COUNT(*) FROM users').fetchone()[0],
        'total_tasks':          conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0],
        'active_announcements': conn.execute('SELECT COUNT(*) FROM announcements WHERE is_active=1').fetchone()[0],
        'total_notifications':  conn.execute('SELECT COUNT(*) FROM notifications').fetchone()[0],
        'managers_count':       conn.execute("SELECT COUNT(*) FROM users WHERE role='مدير'").fetchone()[0],
        'completed_tasks':      conn.execute("SELECT COUNT(*) FROM tasks WHERE status='مكتملة'").fetchone()[0],
        'overdue_tasks':        conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE status!='مكتملة' AND due_date IS NOT NULL AND due_date<?",
            (today,)).fetchone()[0],
        'employees_count':      conn.execute("SELECT COUNT(*) FROM users WHERE role IN ('موظف','مشرف','متدرب')").fetchone()[0],
    }

    # Monthly achievement
    monthly_data = get_monthly_achievement(this_month)
    monthly_org_completed = sum(e['completed'] for e in monthly_data)
    monthly_mgmt = get_management_target(this_month, 'monthly')
    monthly_org_target = monthly_mgmt['target_completions'] if monthly_mgmt else 0
    monthly_org_pct = min(100, int(monthly_org_completed / monthly_org_target * 100)) if monthly_org_target > 0 else 0

    # Quarterly achievement
    quarterly_data = get_quarterly_achievement(this_year, current_quarter)
    all_quarters = get_all_quarters_summary(this_year)

    # Employee of month (top performer)
    top_performer = get_top_performer_month()
    if monthly_data:
        emp_of_month = monthly_data[0] if monthly_data[0]['completed'] > 0 else None
    else:
        emp_of_month = None

    # Activity
    activity = get_recent_activity(50)

    # Current month management target for form pre-fill
    q_key = f'{this_year}-Q{current_quarter}'
    quarterly_mgmt_target = get_management_target(q_key, 'quarterly')

    # All employees for target editing
    all_employees = conn.execute(
        "SELECT id, name, role, username, target_tasks FROM users WHERE role IN ('موظف','مشرف','متدرب') ORDER BY role, name"
    ).fetchall()

    conn.close()

    return render_template('system_admin.html',
        user=user,
        all_users=[dict(u) for u in all_users],
        stats=stats,
        activity=activity,
        monthly_data=monthly_data,
        monthly_org_completed=monthly_org_completed,
        monthly_org_target=monthly_org_target,
        monthly_org_pct=monthly_org_pct,
        this_month=this_month,
        quarterly_data=quarterly_data,
        all_quarters=all_quarters,
        current_quarter=current_quarter,
        this_year=this_year,
        q_key=q_key,
        quarterly_mgmt_target=quarterly_mgmt_target,
        emp_of_month=emp_of_month,
        top_performer=top_performer,
        all_employees=[dict(e) for e in all_employees],
    )


@app.route('/management')
@login_required
def management_dashboard():
    if not can_see_all_tasks(session['role']):
        flash('غير مصرح', 'error')
        return redirect(url_for('dashboard'))
    user = get_user_by_id(session['user_id'])
    now = datetime.now()
    this_month = now.strftime('%Y-%m')
    this_year = now.year
    current_quarter = (now.month - 1) // 3 + 1
    q_key = f'{this_year}-Q{current_quarter}'
    q_names = {1: 'الأول', 2: 'الثاني', 3: 'الثالث', 4: 'الرابع'}

    monthly_data = get_monthly_achievement(this_month)
    monthly_org_completed = sum(e['completed'] for e in monthly_data)
    monthly_mgmt = get_management_target(this_month, 'monthly')
    monthly_org_target = monthly_mgmt['target_completions'] if monthly_mgmt else 0
    monthly_org_pct = min(100, int(monthly_org_completed / monthly_org_target * 100)) if monthly_org_target > 0 else 0

    quarterly_data = get_quarterly_achievement(this_year, current_quarter)
    all_quarters = get_all_quarters_summary(this_year)
    quarterly_mgmt_target = get_management_target(q_key, 'quarterly')

    top_performer = get_top_performer_month()
    emp_of_month = monthly_data[0] if monthly_data and monthly_data[0]['completed'] > 0 else None

    conn = get_db_connection()
    all_employees = conn.execute(
        "SELECT id, name, role, username, target_tasks FROM users WHERE role IN ('موظف','مشرف','متدرب') ORDER BY role, name"
    ).fetchall()
    conn.close()

    return render_template('management_dashboard.html',
        user=user,
        monthly_data=monthly_data,
        monthly_org_completed=monthly_org_completed,
        monthly_org_target=monthly_org_target,
        monthly_org_pct=monthly_org_pct,
        this_month=this_month,
        quarterly_data=quarterly_data,
        all_quarters=all_quarters,
        current_quarter=current_quarter,
        this_year=this_year,
        q_key=q_key,
        quarter_name=q_names[current_quarter],
        quarterly_mgmt_target=quarterly_mgmt_target,
        emp_of_month=emp_of_month,
        top_performer=top_performer,
        all_employees=[dict(e) for e in all_employees],
        can_set_targets=can_manage_users(session['role']),
    )


if __name__ == '__main__':
    app.run(
        debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true',
        host=os.environ.get('FLASK_HOST', '0.0.0.0'),
        port=int(os.environ.get('PORT', 5000))
    )
