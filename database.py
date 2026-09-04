import sqlite3
from pathlib import Path
from datetime import datetime


# =========================================================
# DATABASE CONFIG
# =========================================================

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "focus.db"


# =========================================================
# CONNECTION
# =========================================================

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def init_db():
    conn = get_connection()

    conn.executescript("""
        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            wbs TEXT,
            title TEXT NOT NULL,
            project_id INTEGER,
            estimated_seconds INTEGER DEFAULT 0,
            status TEXT DEFAULT 'todo',
            created_at TEXT NOT NULL,
            completed_at TEXT,

            FOREIGN KEY(project_id)
                REFERENCES projects(id)
                ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS task_tags (
            task_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,

            PRIMARY KEY(task_id, tag_id),

            FOREIGN KEY(task_id)
                REFERENCES tasks(id)
                ON DELETE CASCADE,

            FOREIGN KEY(tag_id)
                REFERENCES tags(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS task_prerequisites (
            task_id INTEGER NOT NULL,
            prerequisite_task_id INTEGER NOT NULL,

            PRIMARY KEY(task_id, prerequisite_task_id),

            FOREIGN KEY(task_id)
                REFERENCES tasks(id)
                ON DELETE CASCADE,

            FOREIGN KEY(prerequisite_task_id)
                REFERENCES tasks(id)
                ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pomodoros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            task_id INTEGER NOT NULL,

            started_at TEXT NOT NULL,
            ended_at TEXT,

            duration_seconds INTEGER DEFAULT 0,

            description TEXT,

            status TEXT DEFAULT 'completed',

            FOREIGN KEY(task_id)
                REFERENCES tasks(id)
                ON DELETE CASCADE
        );
    """)

    conn.commit()
    conn.close()


# =========================================================
# GENERIC QUERY FUNCTIONS
# =========================================================

def fetch_all(sql, params=()):
    conn = get_connection()

    cursor = conn.execute(sql, params)

    rows = cursor.fetchall()

    conn.close()

    return rows


def fetch_one(sql, params=()):
    conn = get_connection()

    cursor = conn.execute(sql, params)

    row = cursor.fetchone()

    conn.close()

    return row


def execute(sql, params=()):
    conn = get_connection()

    cursor = conn.execute(sql, params)

    conn.commit()

    last_id = cursor.lastrowid

    conn.close()

    return last_id


# =========================================================
# PROJECTS
# =========================================================

def get_projects():
    return fetch_all("""
        SELECT *
        FROM projects
        ORDER BY name
    """)


def get_project(project_id):
    return fetch_one("""
        SELECT *
        FROM projects
        WHERE id = ?
    """, (project_id,))


def get_or_create_project(name):
    if not name:
        return None

    name = name.strip()

    if not name:
        return None

    existing = fetch_one("""
        SELECT id
        FROM projects
        WHERE name = ?
    """, (name,))

    if existing:
        return existing["id"]

    return execute("""
        INSERT INTO projects (
            name,
            created_at
        )
        VALUES (?, ?)
    """, (
        name,
        datetime.now().isoformat(timespec="seconds")
    ))


# =========================================================
# TAGS
# =========================================================

def get_tags():
    return fetch_all("""
        SELECT *
        FROM tags
        ORDER BY name
    """)


def get_or_create_tag(name):
    if not name:
        return None

    name = name.strip()

    if not name:
        return None

    existing = fetch_one("""
        SELECT id
        FROM tags
        WHERE name = ?
    """, (name,))

    if existing:
        return existing["id"]

    return execute("""
        INSERT INTO tags (
            name,
            created_at
        )
        VALUES (?, ?)
    """, (
        name,
        datetime.now().isoformat(timespec="seconds")
    ))


# =========================================================
# TASKS
# =========================================================

def create_task(
    title,
    wbs="",
    project_id=None,
    estimated_seconds=0
):
    return execute("""
        INSERT INTO tasks (
            title,
            wbs,
            project_id,
            estimated_seconds,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, 'todo', ?)
    """, (
        title.strip(),
        wbs.strip(),
        project_id,
        int(estimated_seconds or 0),
        datetime.now().isoformat(timespec="seconds")
    ))


def update_task(
    task_id,
    title,
    wbs="",
    project_id=None,
    estimated_seconds=0
):
    execute("""
        UPDATE tasks

        SET
            title = ?,
            wbs = ?,
            project_id = ?,
            estimated_seconds = ?

        WHERE id = ?
    """, (
        title.strip(),
        wbs.strip(),
        project_id,
        int(estimated_seconds or 0),
        task_id
    ))


def get_task(task_id):
    return fetch_one("""
        SELECT
            t.*,
            p.name AS project_name,

            COALESCE(
                (
                    SELECT SUM(duration_seconds)
                    FROM pomodoros
                    WHERE task_id = t.id
                ),
                0
            ) AS actual_seconds

        FROM tasks t

        LEFT JOIN projects p
            ON p.id = t.project_id

        WHERE t.id = ?
    """, (task_id,))


def get_tasks(search=""):
    search = search.strip()

    if search:

        return fetch_all("""
            SELECT
                t.*,
                p.name AS project_name,

                COALESCE(
                    (
                        SELECT SUM(duration_seconds)
                        FROM pomodoros
                        WHERE task_id = t.id
                    ),
                    0
                ) AS actual_seconds

            FROM tasks t

            LEFT JOIN projects p
                ON p.id = t.project_id

            WHERE
                t.title LIKE ?
                OR t.wbs LIKE ?
                OR p.name LIKE ?

            ORDER BY t.id DESC
        """, (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ))

    return fetch_all("""
        SELECT
            t.*,
            p.name AS project_name,

            COALESCE(
                (
                    SELECT SUM(duration_seconds)
                    FROM pomodoros
                    WHERE task_id = t.id
                ),
                0
            ) AS actual_seconds

        FROM tasks t

        LEFT JOIN projects p
            ON p.id = t.project_id

        ORDER BY t.id DESC
    """)


def complete_task(task_id):
    execute("""
        UPDATE tasks

        SET
            status = 'completed',
            completed_at = ?

        WHERE id = ?
    """, (
        datetime.now().isoformat(timespec="seconds"),
        task_id
    ))


def reopen_task(task_id):
    execute("""
        UPDATE tasks

        SET
            status = 'todo',
            completed_at = NULL

        WHERE id = ?
    """, (task_id,))


def delete_task(task_id):
    execute("""
        DELETE FROM tasks
        WHERE id = ?
    """, (task_id,))


# =========================================================
# TAG RELATIONSHIPS
# =========================================================

def set_task_tags(task_id, tag_names):

    execute("""
        DELETE FROM task_tags
        WHERE task_id = ?
    """, (task_id,))

    for name in tag_names:

        tag_id = get_or_create_tag(name)

        if tag_id:

            execute("""
                INSERT OR IGNORE INTO task_tags (
                    task_id,
                    tag_id
                )
                VALUES (?, ?)
            """, (
                task_id,
                tag_id
            ))


def get_task_tags(task_id):

    return fetch_all("""
        SELECT
            tags.*

        FROM tags

        JOIN task_tags
            ON task_tags.tag_id = tags.id

        WHERE task_tags.task_id = ?

        ORDER BY tags.name
    """, (task_id,))


# =========================================================
# PREREQUISITES
# =========================================================

def set_prerequisites(
    task_id,
    prerequisite_ids
):

    execute("""
        DELETE FROM task_prerequisites
        WHERE task_id = ?
    """, (task_id,))

    for prerequisite_id in prerequisite_ids:

        if prerequisite_id == task_id:
            continue

        execute("""
            INSERT OR IGNORE INTO task_prerequisites (
                task_id,
                prerequisite_task_id
            )
            VALUES (?, ?)
        """, (
            task_id,
            prerequisite_id
        ))


def get_prerequisites(task_id):

    return fetch_all("""
        SELECT
            t.*

        FROM tasks t

        JOIN task_prerequisites tp
            ON tp.prerequisite_task_id = t.id

        WHERE tp.task_id = ?

        ORDER BY t.id
    """, (task_id,))


def prerequisites_completed(task_id):

    rows = fetch_all("""
        SELECT
            t.id,
            t.title,
            t.status

        FROM tasks t

        JOIN task_prerequisites tp
            ON tp.prerequisite_task_id = t.id

        WHERE
            tp.task_id = ?
            AND t.status != 'completed'
    """, (task_id,))

    return rows


# =========================================================
# POMODOROS
# =========================================================

def create_pomodoro(
    task_id,
    started_at
):

    return execute("""
        INSERT INTO pomodoros (
            task_id,
            started_at,
            status
        )
        VALUES (?, ?, 'running')
    """, (
        task_id,
        started_at
    ))


def finish_pomodoro(
    pomodoro_id,
    ended_at,
    duration_seconds,
    description=""
):

    execute("""
        UPDATE pomodoros

        SET
            ended_at = ?,
            duration_seconds = ?,
            description = ?,
            status = 'completed'

        WHERE id = ?
    """, (
        ended_at,
        int(duration_seconds),
        description.strip(),
        pomodoro_id
    ))


def cancel_pomodoro(pomodoro_id):

    execute("""
        UPDATE pomodoros

        SET
            status = 'cancelled'

        WHERE id = ?
    """, (pomodoro_id,))


def get_pomodoros_for_task(task_id):

    return fetch_all("""
        SELECT *
        FROM pomodoros

        WHERE
            task_id = ?
            AND status = 'completed'

        ORDER BY started_at DESC
    """, (task_id,))


def get_all_pomodoros():

    return fetch_all("""
        SELECT
            p.*,
            t.title AS task_title

        FROM pomodoros p

        JOIN tasks t
            ON t.id = p.task_id

        WHERE p.status = 'completed'

        ORDER BY p.started_at DESC
    """)


# =========================================================
# ANALYTICS
# =========================================================

def get_focus_seconds_between(
    start_datetime,
    end_datetime
):

    row = fetch_one("""
        SELECT
            COALESCE(
                SUM(duration_seconds),
                0
            ) AS total

        FROM pomodoros

        WHERE
            status = 'completed'
            AND started_at >= ?
            AND started_at < ?
    """, (
        start_datetime,
        end_datetime
    ))

    return row["total"] if row else 0


def get_pomodoro_count_between(
    start_datetime,
    end_datetime
):

    row = fetch_one("""
        SELECT
            COUNT(*) AS total

        FROM pomodoros

        WHERE
            status = 'completed'
            AND started_at >= ?
            AND started_at < ?
    """, (
        start_datetime,
        end_datetime
    ))

    return row["total"] if row else 0