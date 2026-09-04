import csv
import shutil
import sqlite3
import time
from datetime import datetime, timedelta
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog

DB = "focus.db"
POMODORO_SECONDS = 25 * 60


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Focus")
        self.root.geometry("1050x700")
        self.root.minsize(900, 600)

        self.conn = sqlite3.connect(DB)
        self.conn.row_factory = sqlite3.Row
        self.create_db()

        self.timer_job = None
        self.timer_running = False
        self.timer_paused = False
        self.remaining = POMODORO_SECONDS
        self.session_started = None
        self.current_session_task = None

        self.build_ui()
        self.refresh_all()
        self.update_timer_label()

    # ---------- Database ----------

    def create_db(self):
        self.conn.executescript("""
        PRAGMA foreign_keys = ON;

        CREATE TABLE IF NOT EXISTS projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            created_at TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            project_id INTEGER,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            status TEXT NOT NULL DEFAULT 'todo',
            created_at TEXT NOT NULL,
            completed_at TEXT,
            FOREIGN KEY(project_id) REFERENCES projects(id) ON DELETE SET NULL
        );

        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE
        );

        CREATE TABLE IF NOT EXISTS task_tags (
            task_id INTEGER NOT NULL,
            tag_id INTEGER NOT NULL,
            PRIMARY KEY(task_id, tag_id),
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE CASCADE,
            FOREIGN KEY(tag_id) REFERENCES tags(id) ON DELETE CASCADE
        );

        CREATE TABLE IF NOT EXISTS pomodoro_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_id INTEGER,
            started_at TEXT NOT NULL,
            ended_at TEXT NOT NULL,
            duration_seconds INTEGER NOT NULL,
            status TEXT NOT NULL,
            description TEXT DEFAULT '',
            FOREIGN KEY(task_id) REFERENCES tasks(id) ON DELETE SET NULL
        );
        """)
        self.conn.commit()

    def get_or_create_project(self, name):
        name = (name or "").strip()
        if not name:
            return None
        self.conn.execute(
            "INSERT OR IGNORE INTO projects(name, created_at) VALUES (?, ?)",
            (name, now())
        )
        self.conn.commit()
        return self.conn.execute(
            "SELECT id FROM projects WHERE name=?", (name,)
        ).fetchone()["id"]

    def get_or_create_tag(self, name):
        name = name.strip()
        if not name:
            return None
        self.conn.execute(
            "INSERT OR IGNORE INTO tags(name) VALUES (?)", (name,)
        )
        self.conn.commit()
        return self.conn.execute(
            "SELECT id FROM tags WHERE name=?", (name,)
        ).fetchone()["id"]

    # ---------- UI ----------

    def build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill="x")

        ttk.Button(top, text="New Task", command=self.new_task).pack(side="left")
        ttk.Button(top, text="Edit Task", command=self.edit_task).pack(side="left", padx=5)
        ttk.Button(top, text="Complete", command=self.complete_task).pack(side="left")
        ttk.Button(top, text="Delete", command=self.delete_task).pack(side="left", padx=5)

        ttk.Separator(top, orient="vertical").pack(side="left", fill="y", padx=10)

        ttk.Button(top, text="Import CSV", command=self.import_csv).pack(side="left")
        ttk.Button(top, text="Export Tasks", command=self.export_tasks).pack(side="left", padx=5)
        ttk.Button(top, text="Export Pomodoros", command=self.export_pomodoros).pack(side="left")
        ttk.Button(top, text="Backup", command=self.backup).pack(side="left", padx=5)
        ttk.Button(top, text="Analytics", command=self.analytics).pack(side="left")

        main = ttk.PanedWindow(self.root, orient="horizontal")
        main.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        left = ttk.Frame(main, padding=5)
        right = ttk.Frame(main, padding=5)
        main.add(left, weight=1)
        main.add(right, weight=3)

        ttk.Label(left, text="Projects", font=("", 12, "bold")).pack(anchor="w")

        project_bar = ttk.Frame(left)
        project_bar.pack(fill="x", pady=5)
        ttk.Button(project_bar, text="+", width=3, command=self.new_project).pack(side="left")
        ttk.Button(project_bar, text="All", command=lambda: self.select_project(None)).pack(side="left", padx=4)

        self.project_list = tk.Listbox(left, height=20)
        self.project_list.pack(fill="both", expand=True)
        self.project_list.bind("<<ListboxSelect>>", self.on_project_select)

        ttk.Label(right, text="Tasks", font=("", 12, "bold")).pack(anchor="w")

        task_frame = ttk.Frame(right)
        task_frame.pack(fill="both", expand=True, pady=5)

        columns = ("title", "project", "tags", "status")
        self.tasks_tree = ttk.Treeview(task_frame, columns=columns, show="headings", selectmode="browse")
        self.tasks_tree.heading("title", text="Task")
        self.tasks_tree.heading("project", text="Project")
        self.tasks_tree.heading("tags", text="Tags")
        self.tasks_tree.heading("status", text="Status")
        self.tasks_tree.column("title", width=300)
        self.tasks_tree.column("project", width=130)
        self.tasks_tree.column("tags", width=180)
        self.tasks_tree.column("status", width=90)
        self.tasks_tree.pack(side="left", fill="both", expand=True)

        scroll = ttk.Scrollbar(task_frame, orient="vertical", command=self.tasks_tree.yview)
        scroll.pack(side="right", fill="y")
        self.tasks_tree.configure(yscrollcommand=scroll.set)
        self.tasks_tree.bind("<<TreeviewSelect>>", self.on_task_select)

        bottom = ttk.LabelFrame(right, text="Pomodoro", padding=10)
        bottom.pack(fill="x", pady=8)

        self.selected_task_label = ttk.Label(bottom, text="Task: —")
        self.selected_task_label.grid(row=0, column=0, columnspan=4, sticky="w")

        self.timer_label = ttk.Label(bottom, text="25:00", font=("", 32, "bold"))
        self.timer_label.grid(row=1, column=0, rowspan=2, padx=(0, 25))

        self.start_btn = ttk.Button(bottom, text="Start", command=self.start_timer)
        self.start_btn.grid(row=1, column=1, padx=4)

        self.pause_btn = ttk.Button(bottom, text="Pause", command=self.pause_timer, state="disabled")
        self.pause_btn.grid(row=1, column=2, padx=4)

        self.stop_btn = ttk.Button(bottom, text="Stop", command=self.stop_timer, state="disabled")
        self.stop_btn.grid(row=1, column=3, padx=4)

        ttk.Label(bottom, text="Session description:").grid(row=2, column=1, sticky="w", pady=(8, 0))
        self.session_desc = ttk.Entry(bottom)
        self.session_desc.grid(row=2, column=2, columnspan=2, sticky="ew", pady=(8, 0))
        bottom.columnconfigure(2, weight=1)

        stats = ttk.Frame(right)
        stats.pack(fill="x")
        self.stats_label = ttk.Label(stats, text="")
        self.stats_label.pack(anchor="w")

    # ---------- Tasks ----------

    def refresh_all(self):
        self.refresh_projects()
        self.refresh_tasks()
        self.refresh_stats()

    def refresh_projects(self):
        self.project_list.delete(0, "end")
        self.project_list.insert("end", "All Projects")
        rows = self.conn.execute("SELECT * FROM projects ORDER BY name").fetchall()
        for row in rows:
            self.project_list.insert("end", row["name"])

    def refresh_tasks(self, project_id=None):
        for item in self.tasks_tree.get_children():
            self.tasks_tree.delete(item)

        if project_id is None:
            rows = self.conn.execute("""
                SELECT t.*, p.name AS project,
                       GROUP_CONCAT(g.name, ', ') AS tags
                FROM tasks t
                LEFT JOIN projects p ON p.id=t.project_id
                LEFT JOIN task_tags tt ON tt.task_id=t.id
                LEFT JOIN tags g ON g.id=tt.tag_id
                GROUP BY t.id
                ORDER BY CASE t.status WHEN 'todo' THEN 0 ELSE 1 END, t.created_at DESC
            """).fetchall()
        else:
            rows = self.conn.execute("""
                SELECT t.*, p.name AS project,
                       GROUP_CONCAT(g.name, ', ') AS tags
                FROM tasks t
                LEFT JOIN projects p ON p.id=t.project_id
                LEFT JOIN task_tags tt ON tt.task_id=t.id
                LEFT JOIN tags g ON g.id=tt.tag_id
                WHERE t.project_id=?
                GROUP BY t.id
                ORDER BY CASE t.status WHEN 'todo' THEN 0 ELSE 1 END, t.created_at DESC
            """, (project_id,)).fetchall()

        for row in rows:
            self.tasks_tree.insert(
                "", "end", iid=str(row["id"]),
                values=(
                    row["title"],
                    row["project"] or "",
                    row["tags"] or "",
                    row["status"]
                )
            )

    def get_selected_task_id(self):
        selected = self.tasks_tree.selection()
        return int(selected[0]) if selected else None

    def new_task(self):
        self.task_dialog()

    def task_dialog(self, task_id=None):
        old = None
        tags_old = ""
        if task_id:
            old = self.conn.execute(
                "SELECT * FROM tasks WHERE id=?", (task_id,)
            ).fetchone()
            if not old:
                return
            tags_old = ", ".join(
                r["name"] for r in self.conn.execute("""
                    SELECT g.name FROM tags g
                    JOIN task_tags tt ON tt.tag_id=g.id
                    WHERE tt.task_id=?
                    ORDER BY g.name
                """, (task_id,))
            )

        win = tk.Toplevel(self.root)
        win.title("Edit Task" if old else "New Task")
        win.transient(self.root)
        win.grab_set()

        ttk.Label(win, text="Title").grid(row=0, column=0, sticky="w", padx=10, pady=8)
        title = ttk.Entry(win, width=55)
        title.grid(row=0, column=1, padx=10, pady=8)
        if old:
            title.insert(0, old["title"])

        ttk.Label(win, text="Project").grid(row=1, column=0, sticky="w", padx=10, pady=8)
        project = ttk.Entry(win, width=55)
        project.grid(row=1, column=1, padx=10, pady=8)
        if old and old["project_id"]:
            p = self.conn.execute(
                "SELECT name FROM projects WHERE id=?", (old["project_id"],)
            ).fetchone()
            if p:
                project.insert(0, p["name"])

        ttk.Label(win, text="Tags").grid(row=2, column=0, sticky="w", padx=10, pady=8)
        tags = ttk.Entry(win, width=55)
        tags.grid(row=2, column=1, padx=10, pady=8)
        tags.insert(0, tags_old)

        ttk.Label(win, text="Description").grid(row=3, column=0, sticky="nw", padx=10, pady=8)
        desc = tk.Text(win, width=42, height=7)
        desc.grid(row=3, column=1, padx=10, pady=8)
        if old:
            desc.insert("1.0", old["description"] or "")

        def save():
            t = title.get().strip()
            if not t:
                messagebox.showerror("Error", "Title is required.", parent=win)
                return

            project_id = self.get_or_create_project(project.get())
            description = desc.get("1.0", "end").strip()

            if task_id:
                self.conn.execute("""
                    UPDATE tasks
                    SET title=?, project_id=?, description=?
                    WHERE id=?
                """, (t, project_id, description, task_id))
                self.conn.execute("DELETE FROM task_tags WHERE task_id=?", (task_id,))
            else:
                cur = self.conn.execute("""
                    INSERT INTO tasks(title, project_id, description, status, created_at)
                    VALUES (?, ?, ?, 'todo', ?)
                """, (t, project_id, description, now()))
                task_id = cur.lastrowid

            for tag in tags.get().split(","):
                tag_id = self.get_or_create_tag(tag)
                if tag_id:
                    self.conn.execute(
                        "INSERT OR IGNORE INTO task_tags(task_id, tag_id) VALUES (?, ?)",
                        (task_id, tag_id)
                    )

            self.conn.commit()
            win.destroy()
            self.refresh_all()

        ttk.Button(win, text="Save", command=save).grid(
            row=4, column=1, sticky="e", padx=10, pady=10
        )

    def edit_task(self):
        task_id = self.get_selected_task_id()
        if task_id:
            self.task_dialog(task_id)

    def complete_task(self):
        task_id = self.get_selected_task_id()
        if not task_id:
            return
        self.conn.execute("""
            UPDATE tasks SET status='done', completed_at=? WHERE id=?
        """, (now(), task_id))
        self.conn.commit()
        self.refresh_all()

    def delete_task(self):
        task_id = self.get_selected_task_id()
        if not task_id:
            return
        if not messagebox.askyesno("Delete", "Delete selected task?"):
            return
        self.conn.execute("DELETE FROM tasks WHERE id=?", (task_id,))
        self.conn.commit()
        self.refresh_all()
        self.selected_task_label.config(text="Task: —")

    # ---------- Projects ----------

    def new_project(self):
        name = simpledialog.askstring("New Project", "Project name:", parent=self.root)
        if name and name.strip():
            try:
                self.get_or_create_project(name)
                self.refresh_projects()
            except sqlite3.Error as e:
                messagebox.showerror("Error", str(e))

    def select_project(self, project_id):
        self.refresh_tasks(project_id)

    def on_project_select(self, _event=None):
        sel = self.project_list.curselection()
        if not sel or sel[0] == 0:
            self.refresh_tasks(None)
            return
        name = self.project_list.get(sel[0])
        row = self.conn.execute(
            "SELECT id FROM projects WHERE name=?", (name,)
        ).fetchone()
        self.refresh_tasks(row["id"] if row else None)

    def on_task_select(self, _event=None):
        task_id = self.get_selected_task_id()
        if not task_id:
            self.selected_task_label.config(text="Task: —")
            return
        row = self.conn.execute(
            "SELECT title FROM tasks WHERE id=?", (task_id,)
        ).fetchone()
        self.selected_task_label.config(text=f"Task: {row['title']}")

    # ---------- Pomodoro ----------

    def start_timer(self):
        task_id = self.get_selected_task_id()
        if not task_id:
            messagebox.showwarning("Pomodoro", "Select a task first.")
            return

        if not self.timer_running:
            self.current_session_task = task_id
            self.session_started = datetime.now()
            self.remaining = POMODORO_SECONDS
            self.timer_running = True
            self.timer_paused = False
        else:
            self.timer_paused = False

        self.start_btn.config(state="disabled")
        self.pause_btn.config(state="normal")
        self.stop_btn.config(state="normal")
        self.tick()

    def tick(self):
        self.update_timer_label()
        if not self.timer_running or self.timer_paused:
            return

        if self.remaining <= 0:
            self.finish_timer("completed")
            return

        self.remaining -= 1
        self.timer_job = self.root.after(1000, self.tick)

    def pause_timer(self):
        if not self.timer_running:
            return
        self.timer_paused = not self.timer_paused
        self.pause_btn.config(text="Resume" if self.timer_paused else "Pause")
        if not self.timer_paused:
            self.tick()

    def stop_timer(self):
        if not self.timer_running:
            return
        self.finish_timer("stopped")

    def finish_timer(self, status):
        if self.timer_job:
            self.root.after_cancel(self.timer_job)
            self.timer_job = None

        if self.session_started and self.current_session_task:
            elapsed = int((datetime.now() - self.session_started).total_seconds())
            elapsed = max(0, min(elapsed, POMODORO_SECONDS))
            if elapsed >= 1:
                self.conn.execute("""
                    INSERT INTO pomodoro_sessions
                    (task_id, started_at, ended_at, duration_seconds, status, description)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    self.current_session_task,
                    self.session_started.strftime("%Y-%m-%d %H:%M:%S"),
                    now(),
                    elapsed,
                    status,
                    self.session_desc.get().strip()
                ))
                self.conn.commit()

        self.timer_running = False
        self.timer_paused = False
        self.current_session_task = None
        self.session_started = None
        self.remaining = POMODORO_SECONDS

        self.start_btn.config(state="normal")
        self.pause_btn.config(state="disabled", text="Pause")
        self.stop_btn.config(state="disabled")
        self.session_desc.delete(0, "end")
        self.update_timer_label()
        self.refresh_stats()

        if status == "completed":
            messagebox.showinfo("Pomodoro", "Pomodoro completed.")

    def update_timer_label(self):
        mins, secs = divmod(max(0, self.remaining), 60)
        self.timer_label.config(text=f"{mins:02d}:{secs:02d}")

    # ---------- Analytics ----------

    def refresh_stats(self):
        today = datetime.now().strftime("%Y-%m-%d")
        week_start = (datetime.now() - timedelta(days=datetime.now().weekday())).strftime("%Y-%m-%d")

        t = self.conn.execute("""
            SELECT COALESCE(SUM(duration_seconds),0) AS seconds,
                   COUNT(*) AS count
            FROM pomodoro_sessions
            WHERE date(started_at)=?
        """, (today,)).fetchone()

        w = self.conn.execute("""
            SELECT COALESCE(SUM(duration_seconds),0) AS seconds,
                   COUNT(*) AS count
            FROM pomodoro_sessions
            WHERE date(started_at)>=?
        """, (week_start,)).fetchone()

        self.stats_label.config(
            text=f"Today: {self.format_seconds(t['seconds'])} / {t['count']} pomodoros    "
                 f"Week: {self.format_seconds(w['seconds'])} / {w['count']} pomodoros"
        )

    def analytics(self):
        today = datetime.now().strftime("%Y-%m-%d")
        week_start = datetime.now() - timedelta(days=datetime.now().weekday())

        rows = self.conn.execute("""
            SELECT date(started_at) AS day,
                   SUM(duration_seconds) AS seconds,
                   COUNT(*) AS sessions
            FROM pomodoro_sessions
            WHERE date(started_at)>=?
            GROUP BY date(started_at)
            ORDER BY day
        """, (week_start.strftime("%Y-%m-%d"),)).fetchall()

        lines = ["WEEKLY ANALYTICS", ""]
        for row in rows:
            lines.append(
                f"{row['day']}   {self.format_seconds(row['seconds'])}   "
                f"{row['sessions']} pomodoros"
            )

        lines += ["", f"Today: {today}"]
        win = tk.Toplevel(self.root)
        win.title("Analytics")
        win.geometry("450x350")
        text = tk.Text(win, font=("TkFixedFont", 11))
        text.pack(fill="both", expand=True, padx=10, pady=10)
        text.insert("1.0", "\n".join(lines))
        text.config(state="disabled")

    @staticmethod
    def format_seconds(seconds):
        seconds = int(seconds or 0)
        h, rem = divmod(seconds, 3600)
        m, _ = divmod(rem, 60)
        return f"{h}h {m:02d}m" if h else f"{m}m"

    # ---------- CSV ----------

    def import_csv(self):
        path = filedialog.askopenfilename(
            title="Import Tasks",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")]
        )
        if not path:
            return

        count = 0
        try:
            with open(path, "r", encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    title = (row.get("title") or "").strip()
                    if not title:
                        continue

                    project_id = self.get_or_create_project(row.get("project", ""))
                    status = (row.get("status") or "todo").strip().lower()
                    if status not in ("todo", "done"):
                        status = "todo"

                    cur = self.conn.execute("""
                        INSERT INTO tasks(title, project_id, description, status, created_at)
                        VALUES (?, ?, ?, ?, ?)
                    """, (
                        title,
                        project_id,
                        row.get("description", ""),
                        status,
                        now()
                    ))
                    task_id = cur.lastrowid

                    for tag in (row.get("tags") or "").split(","):
                        tag_id = self.get_or_create_tag(tag)
                        if tag_id:
                            self.conn.execute(
                                "INSERT OR IGNORE INTO task_tags(task_id, tag_id) VALUES (?, ?)",
                                (task_id, tag_id)
                            )
                    count += 1

            self.conn.commit()
            self.refresh_all()
            messagebox.showinfo("Import", f"Imported {count} tasks.")
        except Exception as e:
            messagebox.showerror("Import Error", str(e))

    def export_tasks(self):
        path = filedialog.asksaveasfilename(
            title="Export Tasks",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not path:
            return

        rows = self.conn.execute("""
            SELECT t.id, t.title, t.description, t.status, t.created_at,
                   t.completed_at, p.name AS project,
                   GROUP_CONCAT(g.name, ', ') AS tags
            FROM tasks t
            LEFT JOIN projects p ON p.id=t.project_id
            LEFT JOIN task_tags tt ON tt.task_id=t.id
            LEFT JOIN tags g ON g.id=tt.tag_id
            GROUP BY t.id
            ORDER BY t.id
        """).fetchall()

        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "title", "description", "project", "tags",
                "status", "created_at", "completed_at"
            ])
            for r in rows:
                writer.writerow([
                    r["id"], r["title"], r["description"], r["project"] or "",
                    r["tags"] or "", r["status"], r["created_at"], r["completed_at"] or ""
                ])

        messagebox.showinfo("Export", "Tasks exported.")

    def export_pomodoros(self):
        path = filedialog.asksaveasfilename(
            title="Export Pomodoros",
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if not path:
            return

        rows = self.conn.execute("""
            SELECT s.*, t.title AS task
            FROM pomodoro_sessions s
            LEFT JOIN tasks t ON t.id=s.task_id
            ORDER BY s.started_at
        """).fetchall()

        with open(path, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "id", "task", "started_at", "ended_at",
                "duration_seconds", "status", "description"
            ])
            for r in rows:
                writer.writerow([
                    r["id"], r["task"] or "", r["started_at"], r["ended_at"],
                    r["duration_seconds"], r["status"], r["description"] or ""
                ])

        messagebox.showinfo("Export", "Pomodoros exported.")

    # ---------- Backup ----------

    def backup(self):
        default = f"focus_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.db"
        path = filedialog.asksaveasfilename(
            title="Backup SQLite Database",
            initialfile=default,
            defaultextension=".db",
            filetypes=[("SQLite database", "*.db"), ("All files", "*.*")]
        )
        if not path:
            return

        self.conn.commit()
        shutil.copy2(DB, path)
        messagebox.showinfo("Backup", f"Backup created:\n{path}")

    # ---------- Close ----------

    def close(self):
        if self.timer_running:
            if not messagebox.askyesno(
                "Exit", "A Pomodoro is running. Exit without saving it?"
            ):
                return
        self.conn.close()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.protocol("WM_DELETE_WINDOW", app.close)
    root.mainloop()
