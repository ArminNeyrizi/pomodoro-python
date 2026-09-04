import sqlite3
from pathlib import Path
from datetime import datetime


# =========================================================
# Database
# =========================================================

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "focus.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


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

            -- Hierarchy
            parent_id INTEGER,
            sort_order INTEGER DEFAULT 0,

            estimated_seconds INTEGER DEFAULT 0,
            status TEXT DEFAULT 'todo',

            created_at TEXT NOT NULL,
            completed_at TEXT,

            FOREIGN KEY(project_id)
                REFERENCES projects(id)
                ON DELETE SET NULL,

            FOREIGN KEY(parent_id)
                REFERENCES tasks(id)
                ON DELETE CASCADE
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

    # -----------------------------------------------------
    # Migration for old databases
    # -----------------------------------------------------

    columns = {
        row["name"]
        for row in conn.execute(
            "PRAGMA table_info(tasks)"
        ).fetchall()
    }

    if "parent_id" not in columns:
        conn.execute("""
            ALTER TABLE tasks
            ADD COLUMN parent_id INTEGER
        """)

    if "sort_order" not in columns:
        conn.execute("""
            ALTER TABLE tasks
            ADD COLUMN sort_order INTEGER DEFAULT 0
        """)

    conn.commit()

    # -----------------------------------------------------
    # Give old tasks a sort order
    # -----------------------------------------------------

    rows = conn.execute("""
        SELECT id
        FROM tasks
        ORDER BY id
    """).fetchall()

    for index, row in enumerate(rows):
        conn.execute("""
            UPDATE tasks
            SET sort_order = ?
            WHERE id = ?
        """, (index, row["id"]))

    conn.commit()
    conn.close()

    rebuild_all_wbs()


# =========================================================
# Generic Queries
# =========================================================

def fetch_all(sql, params=()):
    conn = get_connection()

    try:
        cursor = conn.execute(sql, params)
        return cursor.fetchall()
    finally:
        conn.close()


def fetch_one(sql, params=()):
    conn = get_connection()

    try:
        cursor = conn.execute(sql, params)
        return cursor.fetchone()
    finally:
        conn.close()


def execute(sql, params=()):
    conn = get_connection()

    try:
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


# =========================================================
# Projects
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
# Tags
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
# Tasks - Create / Update / Read
# =========================================================

def create_task(
    title,
    wbs="",
    project_id=None,
    estimated_seconds=0,
    parent_id=None,
    sort_order=None
):
    """
    Creates a task.

    WBS is ignored when hierarchy is used.
    WBS is generated automatically.
    """

    if sort_order is None:
        sort_order = get_next_sort_order(parent_id)

    task_id = execute("""
        INSERT INTO tasks (
            title,
            wbs,
            project_id,
            parent_id,
            sort_order,
            estimated_seconds,
            status,
            created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, 'todo', ?)
    """, (
        title.strip(),
        "",
        project_id,
        parent_id,
        sort_order,
        int(estimated_seconds or 0),
        datetime.now().isoformat(timespec="seconds")
    ))

    rebuild_all_wbs()

    return task_id


def update_task(
    task_id,
    title,
    wbs="",
    project_id=None,
    estimated_seconds=0,
    parent_id=None
):
    """
    Updates task information.

    Parent can be changed.
    WBS is automatically regenerated.
    """

    if parent_id == task_id:
        raise ValueError(
            "A task cannot be its own parent."
        )

    if parent_id is not None:
        if is_descendant(
            parent_id,
            task_id
        ):
            raise ValueError(
                "A task cannot be moved inside its own child."
            )

    old = get_task(task_id)

    if not old:
        raise ValueError("Task not found.")

    old_parent = old["parent_id"]

    # If parent changes, put task at the end
    # of the new parent's children.
    if old_parent != parent_id:

        sort_order = get_next_sort_order(
            parent_id
        )

        execute("""
            UPDATE tasks
            SET
                title = ?,
                project_id = ?,
                estimated_seconds = ?,
                parent_id = ?,
                sort_order = ?
            WHERE id = ?
        """, (
            title.strip(),
            project_id,
            int(estimated_seconds or 0),
            parent_id,
            sort_order,
            task_id
        ))

    else:

        execute("""
            UPDATE tasks
            SET
                title = ?,
                project_id = ?,
                estimated_seconds = ?
            WHERE id = ?
        """, (
            title.strip(),
            project_id,
            int(estimated_seconds or 0),
            task_id
        ))

    normalize_sort_orders()
    rebuild_all_wbs()


def get_task(task_id):
    return fetch_one("""
        SELECT
            t.*,

            p.name AS project_name,

            COALESCE(
                (
                    SELECT SUM(duration_seconds)
                    FROM pomodoros
                    WHERE
                        task_id = t.id
                        AND status = 'completed'
                ),
                0
            ) AS actual_seconds

        FROM tasks t

        LEFT JOIN projects p
            ON p.id = t.project_id

        WHERE t.id = ?
    """, (task_id,))


def get_tasks(search=""):
    search = (search or "").strip()

    if search:

        return fetch_all("""
            SELECT
                t.*,

                p.name AS project_name,

                COALESCE(
                    (
                        SELECT SUM(duration_seconds)
                        FROM pomodoros
                        WHERE
                            task_id = t.id
                            AND status = 'completed'
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

            ORDER BY
                t.wbs,
                t.sort_order
        """, (
            f"%{search}%",
            f"%{search}%",
            f"%{search}%"
        ))

    return get_all_tasks_tree_order()


def get_all_tasks_tree_order():
    """
    Returns every task in WBS order.
    """

    tasks = fetch_all("""
        SELECT
            t.*,

            p.name AS project_name,

            COALESCE(
                (
                    SELECT SUM(duration_seconds)
                    FROM pomodoros
                    WHERE
                        task_id = t.id
                        AND status = 'completed'
                ),
                0
            ) AS actual_seconds

        FROM tasks t

        LEFT JOIN projects p
            ON p.id = t.project_id

        ORDER BY
            t.wbs,
            t.sort_order,
            t.id
    """)

    return tasks


# =========================================================
# Task Hierarchy
# =========================================================

def get_children(parent_id=None):
    """
    Get direct children of a task.
    """

    if parent_id is None:

        return fetch_all("""
            SELECT *
            FROM tasks
            WHERE parent_id IS NULL
            ORDER BY sort_order, id
        """)

    return fetch_all("""
        SELECT *
        FROM tasks
        WHERE parent_id = ?
        ORDER BY sort_order, id
    """, (parent_id,))


def get_parent(task_id):
    task = get_task(task_id)

    if not task:
        return None

    parent_id = task["parent_id"]

    if parent_id is None:
        return None

    return get_task(parent_id)


def get_next_sort_order(parent_id=None):

    if parent_id is None:

        row = fetch_one("""
            SELECT
                COALESCE(
                    MAX(sort_order),
                    -1
                ) + 1 AS next_order
            FROM tasks
            WHERE parent_id IS NULL
        """)

    else:

        row = fetch_one("""
            SELECT
                COALESCE(
                    MAX(sort_order),
                    -1
                ) + 1 AS next_order
            FROM tasks
            WHERE parent_id = ?
        """, (parent_id,))

    return row["next_order"]


def set_parent(task_id, parent_id):
    """
    Move a task under another task.
    """

    if task_id == parent_id:
        raise ValueError(
            "A task cannot be its own parent."
        )

    if parent_id is not None:

        if is_descendant(
            parent_id,
            task_id
        ):
            raise ValueError(
                "Cannot move a task inside its own child."
            )

    new_order = get_next_sort_order(
        parent_id
    )

    execute("""
        UPDATE tasks
        SET
            parent_id = ?,
            sort_order = ?
        WHERE id = ?
    """, (
        parent_id,
        new_order,
        task_id
    ))

    normalize_sort_orders()
    rebuild_all_wbs()


def set_sort_order(task_id, sort_order):
    execute("""
        UPDATE tasks
        SET sort_order = ?
        WHERE id = ?
    """, (
        sort_order,
        task_id
    ))

    normalize_sort_orders()
    rebuild_all_wbs()


def is_descendant(task_id, possible_parent_id):
    """
    Returns True if task_id is inside
    possible_parent_id's descendants.

    Used to prevent circular trees.
    """

    current = get_task(task_id)

    visited = set()

    while current:

        parent_id = current["parent_id"]

        if parent_id is None:
            return False

        if parent_id in visited:
            return False

        visited.add(parent_id)

        if parent_id == possible_parent_id:
            return True

        current = get_task(parent_id)

    return False


def normalize_sort_orders():
    """
    Makes sibling sort_order values:
    0, 1, 2, 3...
    """

    conn = get_connection()

    try:

        roots = conn.execute("""
            SELECT id
            FROM tasks
            WHERE parent_id IS NULL
            ORDER BY sort_order, id
        """).fetchall()

        for index, row in enumerate(roots):

            conn.execute("""
                UPDATE tasks
                SET sort_order = ?
                WHERE id = ?
            """, (
                index,
                row["id"]
            ))

        parents = conn.execute("""
            SELECT DISTINCT parent_id
            FROM tasks
            WHERE parent_id IS NOT NULL
        """).fetchall()

        for parent in parents:

            parent_id = parent["parent_id"]

            children = conn.execute("""
                SELECT id
                FROM tasks
                WHERE parent_id = ?
                ORDER BY sort_order, id
            """, (parent_id,)).fetchall()

            for index, child in enumerate(children):

                conn.execute("""
                    UPDATE tasks
                    SET sort_order = ?
                    WHERE id = ?
                """, (
                    index,
                    child["id"]
                ))

        conn.commit()

    finally:
        conn.close()


# =========================================================
# WBS Generation
# =========================================================

def rebuild_all_wbs():
    """
    Generates WBS from the hierarchy.

    Example:

        1
        1.1
        1.2
        1.2.1
        2
        2.1
    """

    conn = get_connection()

    try:

        def update_children(
            parent_id,
            prefix=""
        ):

            children = conn.execute("""
                SELECT
                    id
                FROM tasks
                WHERE parent_id IS ?
                ORDER BY sort_order, id
            """, (parent_id,)).fetchall()

            for index, child in enumerate(
                children,
                start=1
            ):

                if prefix:
                    wbs = f"{prefix}.{index}"
                else:
                    wbs = str(index)

                conn.execute("""
                    UPDATE tasks
                    SET wbs = ?
                    WHERE id = ?
                """, (
                    wbs,
                    child["id"]
                ))

                update_children(
                    child["id"],
                    wbs
                )

        update_children(None)

        conn.commit()

    finally:
        conn.close()


# =========================================================
# Indent / Outdent
# =========================================================

def indent_task(task_id):
    """
    Makes the task a child of the previous sibling.
    """

    task = get_task(task_id)

    if not task:
        return False

    parent_id = task["parent_id"]

    siblings = get_children(parent_id)

    previous = None

    for sibling in siblings:

        if sibling["id"] == task_id:
            break

        previous = sibling

    if previous is None:
        return False

    new_parent_id = previous["id"]

    set_parent(
        task_id,
        new_parent_id
    )

    return True


def outdent_task(task_id):
    """
    Moves task one level up.
    """

    task = get_task(task_id)

    if not task:
        return False

    parent_id = task["parent_id"]

    if parent_id is None:
        return False

    parent = get_task(parent_id)

    if not parent:
        return False

    grandparent_id = parent["parent_id"]

    set_parent(
        task_id,
        grandparent_id
    )

    return True


# =========================================================
# Move Up / Down
# =========================================================

def move_task_up(task_id):
    task = get_task(task_id)

    if not task:
        return False

    parent_id = task["parent_id"]

    siblings = list(
        get_children(parent_id)
    )

    index = next(
        (
            i
            for i, item in enumerate(siblings)
            if item["id"] == task_id
        ),
        None
    )

    if index is None or index == 0:
        return False

    previous = siblings[index - 1]

    conn = get_connection()

    try:

        current_order = task["sort_order"]
        previous_order = previous["sort_order"]

        conn.execute("""
            UPDATE tasks
            SET sort_order = ?
            WHERE id = ?
        """, (
            previous_order,
            task_id
        ))

        conn.execute("""
            UPDATE tasks
            SET sort_order = ?
            WHERE id = ?
        """, (
            current_order,
            previous["id"]
        ))

        conn.commit()

    finally:
        conn.close()

    normalize_sort_orders()
    rebuild_all_wbs()

    return True


def move_task_down(task_id):
    task = get_task(task_id)

    if not task:
        return False

    parent_id = task["parent_id"]

    siblings = list(
        get_children(parent_id)
    )

    index = next(
        (
            i
            for i, item in enumerate(siblings)
            if item["id"] == task_id
        ),
        None
    )

    if index is None:
        return False

    if index >= len(siblings) - 1:
        return False

    next_task = siblings[index + 1]

    conn = get_connection()

    try:

        current_order = task["sort_order"]
        next_order = next_task["sort_order"]

        conn.execute("""
            UPDATE tasks
            SET sort_order = ?
            WHERE id = ?
        """, (
            next_order,
            task_id
        ))

        conn.execute("""
            UPDATE tasks
            SET sort_order = ?
            WHERE id = ?
        """, (
            current_order,
            next_task["id"]
        ))

        conn.commit()

    finally:
        conn.close()

    normalize_sort_orders()
    rebuild_all_wbs()

    return True


# =========================================================
# Task Status
# =========================================================

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

    normalize_sort_orders()
    rebuild_all_wbs()


# =========================================================
# Tags Relationship
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
# Prerequisites
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

        ORDER BY t.wbs
    """, (task_id,))


def prerequisites_completed(task_id):

    return fetch_all("""
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


# =========================================================
# Pomodoro
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

        WHERE
            p.status = 'completed'

        ORDER BY p.started_at DESC
    """)


# =========================================================
# Analytics
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