import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
import csv
import shutil

import database
from pomodoro import PomodoroTimer


# =========================================================
# HELPERS
# =========================================================

def format_time(seconds):
    seconds = int(seconds or 0)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60
    secs = seconds % 60

    if hours > 0:
        return f"{hours:02d}:{minutes:02d}:{secs:02d}"

    return f"{minutes:02d}:{secs:02d}"


def parse_time(value):
    """
    Examples:
        25
        25m
        1h
        1h 30m
    """

    if not value:
        return 0

    value = value.strip().lower()

    try:
        if "h" in value:
            parts = value.replace("h", "").strip()

            hours = float(parts)

            return int(hours * 3600)

        if "m" in value:
            minutes = float(
                value.replace("m", "").strip()
            )

            return int(minutes * 60)

        return int(float(value)) * 60

    except ValueError:
        return 0


# =========================================================
# MAIN UI
# =========================================================

class FocusApp:

    def __init__(self, root):

        self.root = root

        self.root.title("Focus App")

        self.root.geometry("1200x750")

        self.root.minsize(900, 600)

        database.init_db()

        self.timer = PomodoroTimer(
            duration_minutes=25
        )

        self.timer_task_id = None

        self.create_ui()

        self.refresh_tasks()

        self.refresh_projects()

        self.update_analytics()

        self.update_timer()

    # =====================================================
    # MAIN UI
    # =====================================================

    def create_ui(self):

        notebook = ttk.Notebook(
            self.root
        )

        notebook.pack(
            fill="both",
            expand=True
        )

        self.tasks_tab = ttk.Frame(
            notebook
        )

        self.pomodoro_tab = ttk.Frame(
            notebook
        )

        self.analytics_tab = ttk.Frame(
            notebook
        )

        notebook.add(
            self.tasks_tab,
            text="Tasks"
        )

        notebook.add(
            self.pomodoro_tab,
            text="Pomodoro"
        )

        notebook.add(
            self.analytics_tab,
            text="Analytics"
        )

        self.create_tasks_tab()

        self.create_pomodoro_tab()

        self.create_analytics_tab()

    # =====================================================
    # TASKS TAB
    # =====================================================

    def create_tasks_tab(self):

        toolbar = ttk.Frame(
            self.tasks_tab
        )

        toolbar.pack(
            fill="x",
            padx=10,
            pady=10
        )

        ttk.Button(
            toolbar,
            text="New Task",
            command=self.new_task
        ).pack(
            side="left",
            padx=3
        )

        ttk.Button(
            toolbar,
            text="Edit",
            command=self.edit_task
        ).pack(
            side="left",
            padx=3
        )

        ttk.Button(
            toolbar,
            text="Complete",
            command=self.complete_task
        ).pack(
            side="left",
            padx=3
        )

        ttk.Button(
            toolbar,
            text="Reopen",
            command=self.reopen_task
        ).pack(
            side="left",
            padx=3
        )

        ttk.Button(
            toolbar,
            text="Delete",
            command=self.delete_task
        ).pack(
            side="left",
            padx=3
        )

        ttk.Button(
            toolbar,
            text="Start Pomodoro",
            command=self.start_selected_pomodoro
        ).pack(
            side="left",
            padx=15
        )

        ttk.Button(
            toolbar,
            text="Import CSV",
            command=self.import_csv
        ).pack(
            side="right",
            padx=3
        )

        ttk.Button(
            toolbar,
            text="Export CSV",
            command=self.export_tasks
        ).pack(
            side="right",
            padx=3
        )

        ttk.Button(
            toolbar,
            text="Backup",
            command=self.backup_database
        ).pack(
            side="right",
            padx=3
        )

        # -------------------------------------------------
        # SEARCH
        # -------------------------------------------------

        search_frame = ttk.Frame(
            self.tasks_tab
        )

        search_frame.pack(
            fill="x",
            padx=10,
            pady=(0, 10)
        )

        ttk.Label(
            search_frame,
            text="Search"
        ).pack(
            side="left"
        )

        self.search_var = tk.StringVar()

        search_entry = ttk.Entry(
            search_frame,
            textvariable=self.search_var
        )

        search_entry.pack(
            side="left",
            fill="x",
            expand=True,
            padx=5
        )

        search_entry.bind(
            "<KeyRelease>",
            lambda event: self.refresh_tasks()
        )

        # -------------------------------------------------
        # TASK TABLE
        # -------------------------------------------------

        columns = (
            "id",
            "wbs",
            "title",
            "project",
            "estimate",
            "actual",
            "status"
        )

        self.task_tree = ttk.Treeview(
            self.tasks_tab,
            columns=columns,
            show="headings"
        )

        headings = {
            "id": "ID",
            "wbs": "WBS",
            "title": "Task",
            "project": "Project",
            "estimate": "Estimated",
            "actual": "Actual",
            "status": "Status"
        }

        widths = {
            "id": 50,
            "wbs": 80,
            "title": 350,
            "project": 150,
            "estimate": 100,
            "actual": 100,
            "status": 100
        }

        for column in columns:

            self.task_tree.heading(
                column,
                text=headings[column]
            )

            self.task_tree.column(
                column,
                width=widths[column],
                anchor="center"
            )

        self.task_tree.column(
            "title",
            anchor="w"
        )

        scrollbar = ttk.Scrollbar(
            self.tasks_tab,
            orient="vertical",
            command=self.task_tree.yview
        )

        self.task_tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.task_tree.pack(
            side="left",
            fill="both",
            expand=True,
            padx=(10, 0),
            pady=(0, 10)
        )

        scrollbar.pack(
            side="right",
            fill="y",
            padx=(0, 10),
            pady=(0, 10)
        )

        self.task_tree.bind(
            "<Double-1>",
            lambda event: self.edit_task()
        )

    # =====================================================
    # REFRESH TASKS
    # =====================================================

    def refresh_tasks(self):

        if not hasattr(
            self,
            "task_tree"
        ):
            return

        for item in self.task_tree.get_children():

            self.task_tree.delete(item)

        search = self.search_var.get()

        tasks = database.get_tasks(
            search
        )

        for task in tasks:

            self.task_tree.insert(
                "",
                "end",
                values=(
                    task["id"],
                    task["wbs"] or "",
                    task["title"],
                    task["project_name"] or "",
                    format_time(
                        task["estimated_seconds"]
                    ),
                    format_time(
                        task["actual_seconds"]
                    ),
                    task["status"]
                )
            )

    # =====================================================
    # SELECTED TASK
    # =====================================================

    def get_selected_task_id(self):

        selection = self.task_tree.selection()

        if not selection:

            return None

        item = self.task_tree.item(
            selection[0]
        )

        values = item["values"]

        if not values:
            return None

        return int(values[0])

    # =====================================================
    # NEW TASK
    # =====================================================

    def new_task(self):

        self.open_task_dialog()

    # =====================================================
    # EDIT TASK
    # =====================================================

    def edit_task(self):

        task_id = self.get_selected_task_id()

        if not task_id:

            messagebox.showwarning(
                "Task",
                "Select a task first."
            )

            return

        self.open_task_dialog(
            task_id
        )

    # =====================================================
    # TASK DIALOG
    # =====================================================

    def open_task_dialog(
        self,
        task_id=None
    ):

        window = tk.Toplevel(
            self.root
        )

        window.title(
            "Edit Task"
            if task_id
            else
            "New Task"
        )

        window.geometry(
            "600x650"
        )

        window.transient(
            self.root
        )

        window.grab_set()

        task = None

        if task_id:

            task = database.get_task(
                task_id
            )

            if not task:

                window.destroy()

                return

        # -------------------------------------------------
        # WBS
        # -------------------------------------------------

        ttk.Label(
            window,
            text="WBS"
        ).pack(
            anchor="w",
            padx=20,
            pady=(20, 5)
        )

        wbs_var = tk.StringVar(
            value=(
                task["wbs"]
                if task
                else ""
            )
        )

        ttk.Entry(
            window,
            textvariable=wbs_var
        ).pack(
            fill="x",
            padx=20
        )

        # -------------------------------------------------
        # TITLE
        # -------------------------------------------------

        ttk.Label(
            window,
            text="Title"
        ).pack(
            anchor="w",
            padx=20,
            pady=(15, 5)
        )

        title_var = tk.StringVar(
            value=(
                task["title"]
                if task
                else ""
            )
        )

        ttk.Entry(
            window,
            textvariable=title_var
        ).pack(
            fill="x",
            padx=20
        )

        # -------------------------------------------------
        # PROJECT
        # -------------------------------------------------

        ttk.Label(
            window,
            text="Project"
        ).pack(
            anchor="w",
            padx=20,
            pady=(15, 5)
        )

        self.refresh_projects()

        project_var = tk.StringVar()

        if task:

            project_var.set(
                task["project_name"]
                or ""
            )

        project_combo = ttk.Combobox(
            window,
            textvariable=project_var,
            values=self.project_names
        )

        project_combo.pack(
            fill="x",
            padx=20
        )

        # -------------------------------------------------
        # ESTIMATED TIME
        # -------------------------------------------------

        ttk.Label(
            window,
            text="Estimated Time"
        ).pack(
            anchor="w",
            padx=20,
            pady=(15, 5)
        )

        estimated_var = tk.StringVar()

        if task:

            estimated_var.set(
                format_time(
                    task["estimated_seconds"]
                )
            )

        ttk.Entry(
            window,
            textvariable=estimated_var
        ).pack(
            fill="x",
            padx=20
        )

        ttk.Label(
            window,
            text="Example: 30m / 1h / 1h 30m"
        ).pack(
            anchor="w",
            padx=20
        )

        # -------------------------------------------------
        # TAGS
        # -------------------------------------------------

        ttk.Label(
            window,
            text="Tags"
        ).pack(
            anchor="w",
            padx=20,
            pady=(15, 5)
        )

        tags_var = tk.StringVar()

        if task_id:

            tags = database.get_task_tags(
                task_id
            )

            tags_var.set(
                ", ".join(
                    tag["name"]
                    for tag in tags
                )
            )

        ttk.Entry(
            window,
            textvariable=tags_var
        ).pack(
            fill="x",
            padx=20
        )

        ttk.Label(
            window,
            text="Example: work, python, important"
        ).pack(
            anchor="w",
            padx=20
        )

        # -------------------------------------------------
        # PREREQUISITES
        # -------------------------------------------------

        ttk.Label(
            window,
            text="Prerequisite Task IDs"
        ).pack(
            anchor="w",
            padx=20,
            pady=(15, 5)
        )

        prerequisite_var = tk.StringVar()

        if task_id:

            prerequisites = (
                database.get_prerequisites(
                    task_id
                )
            )

            prerequisite_var.set(
                ", ".join(
                    str(row["id"])
                    for row in prerequisites
                )
            )

        ttk.Entry(
            window,
            textvariable=prerequisite_var
        ).pack(
            fill="x",
            padx=20
        )

        ttk.Label(
            window,
            text="Example: 2, 5, 8"
        ).pack(
            anchor="w",
            padx=20
        )

        # -------------------------------------------------
        # SAVE
        # -------------------------------------------------

        ttk.Button(
            window,
            text="Save",
            command=lambda: self.save_task(
                window,
                task_id,
                wbs_var.get(),
                title_var.get(),
                project_var.get(),
                estimated_var.get(),
                tags_var.get(),
                prerequisite_var.get()
            )
        ).pack(
            pady=25
        )

    # =====================================================
    # SAVE TASK
    # =====================================================

    def save_task(
        self,
        window,
        task_id,
        wbs,
        title,
        project,
        estimated,
        tags,
        prerequisites
    ):

        title = title.strip()

        if not title:

            messagebox.showerror(
                "Error",
                "Task title is required."
            )

            return

        estimated_seconds = parse_time(
            estimated
        )

        project_id = (
            database.get_or_create_project(
                project
            )
            if project.strip()
            else None
        )

        if task_id:

            database.update_task(
                task_id=task_id,
                title=title,
                wbs=wbs,
                project_id=project_id,
                estimated_seconds=estimated_seconds
            )

        else:

            task_id = database.create_task(
                title=title,
                wbs=wbs,
                project_id=project_id,
                estimated_seconds=estimated_seconds
            )

        # -------------------------------------------------
        # TAGS
        # -------------------------------------------------

        tag_names = [
            tag.strip()
            for tag in tags.split(",")
            if tag.strip()
        ]

        database.set_task_tags(
            task_id,
            tag_names
        )

        # -------------------------------------------------
        # PREREQUISITES
        # -------------------------------------------------

        prerequisite_ids = []

        for value in prerequisites.split(","):

            value = value.strip()

            if not value:
                continue

            try:

                prerequisite_id = int(
                    value
                )

                prerequisite_ids.append(
                    prerequisite_id
                )

            except ValueError:
                pass

        database.set_prerequisites(
            task_id,
            prerequisite_ids
        )

        window.destroy()

        self.refresh_tasks()

        self.refresh_projects()

        self.update_analytics()

    # =====================================================
    # COMPLETE
    # =====================================================

    def complete_task(self):

        task_id = self.get_selected_task_id()

        if not task_id:

            messagebox.showwarning(
                "Task",
                "Select a task first."
            )

            return

        database.complete_task(
            task_id
        )

        self.refresh_tasks()

        self.update_analytics()

    # =====================================================
    # REOPEN
    # =====================================================

    def reopen_task(self):

        task_id = self.get_selected_task_id()

        if not task_id:

            messagebox.showwarning(
                "Task",
                "Select a task first."
            )

            return

        database.reopen_task(
            task_id
        )

        self.refresh_tasks()

        self.update_analytics()

    # =====================================================
    # DELETE
    # =====================================================

    def delete_task(self):

        task_id = self.get_selected_task_id()

        if not task_id:

            messagebox.showwarning(
                "Task",
                "Select a task first."
            )

            return

        task = database.get_task(
            task_id
        )

        if not task:
            return

        answer = messagebox.askyesno(
            "Delete Task",
            f"Delete '{task['title']}'?"
        )

        if not answer:
            return

        database.delete_task(
            task_id
        )

        self.refresh_tasks()

        self.update_analytics()

    # =====================================================
    # PROJECTS
    # =====================================================

    def refresh_projects(self):

        projects = database.get_projects()

        self.project_names = [
            project["name"]
            for project in projects
        ]

    # =====================================================
    # POMODORO TAB
    # =====================================================

    def create_pomodoro_tab(self):

        frame = ttk.Frame(
            self.pomodoro_tab
        )

        frame.pack(
            expand=True
        )

        self.pomodoro_task_label = ttk.Label(
            frame,
            text="No Task Selected",
            font=("Arial", 20)
        )

        self.pomodoro_task_label.pack(
            pady=(50, 20)
        )

        self.timer_label = ttk.Label(
            frame,
            text="25:00",
            font=("Arial", 70)
        )

        self.timer_label.pack(
            pady=20
        )

        self.timer_status_label = ttk.Label(
            frame,
            text="Ready"
        )

        self.timer_status_label.pack(
            pady=10
        )

        # -------------------------------------------------
        # DESCRIPTION
        # -------------------------------------------------

        ttk.Label(
            frame,
            text="Session Description"
        ).pack(
            pady=(30, 5)
        )

        self.description_var = tk.StringVar()

        self.description_entry = ttk.Entry(
            frame,
            textvariable=self.description_var,
            width=70
        )

        self.description_entry.pack(
            pady=5
        )

        # -------------------------------------------------
        # BUTTONS
        # -------------------------------------------------

        buttons = ttk.Frame(
            frame
        )

        buttons.pack(
            pady=30
        )

        ttk.Button(
            buttons,
            text="Start",
            command=self.start_selected_pomodoro
        ).pack(
            side="left",
            padx=5
        )

        ttk.Button(
            buttons,
            text="Pause",
            command=self.pause_pomodoro
        ).pack(
            side="left",
            padx=5
        )

        ttk.Button(
            buttons,
            text="Resume",
            command=self.resume_pomodoro
        ).pack(
            side="left",
            padx=5
        )

        ttk.Button(
            buttons,
            text="Stop",
            command=self.stop_pomodoro
        ).pack(
            side="left",
            padx=5
        )

        ttk.Button(
            buttons,
            text="Cancel",
            command=self.cancel_pomodoro
        ).pack(
            side="left",
            padx=5
        )

        ttk.Button(
            buttons,
            text="Export Sessions",
            command=self.export_pomodoros
        ).pack(
            side="left",
            padx=15
        )

    # =====================================================
    # START POMODORO
    # =====================================================

    def start_selected_pomodoro(self):

        if self.timer.is_running():

            messagebox.showwarning(
                "Pomodoro",
                "A Pomodoro is already running."
            )

            return

        task_id = self.get_selected_task_id()

        if not task_id:

            messagebox.showwarning(
                "Pomodoro",
                "Select a task first."
            )

            return

        task = database.get_task(
            task_id
        )

        if not task:
            return

        success, message = self.timer.start(
            task_id
        )

        if not success:

            messagebox.showwarning(
                "Prerequisites",
                message
            )

            return

        self.timer_task_id = task_id

        self.pomodoro_task_label.config(
            text=(
                f"{task['wbs'] + ' - ' if task['wbs'] else ''}"
                f"{task['title']}"
            )
        )

        self.timer_status_label.config(
            text="Running"
        )

        self.description_var.set("")

        self.update_timer()

    # =====================================================
    # PAUSE
    # =====================================================

    def pause_pomodoro(self):

        success, message = (
            self.timer.pause()
        )

        if success:

            self.timer_status_label.config(
                text="Paused"
            )

        else:

            messagebox.showwarning(
                "Pomodoro",
                message
            )

    # =====================================================
    # RESUME
    # =====================================================

    def resume_pomodoro(self):

        success, message = (
            self.timer.resume()
        )

        if success:

            self.timer_status_label.config(
                text="Running"
            )

        else:

            messagebox.showwarning(
                "Pomodoro",
                message
            )

    # =====================================================
    # STOP
    # =====================================================

    def stop_pomodoro(self):

        if not self.timer.is_running():

            messagebox.showwarning(
                "Pomodoro",
                "Timer is not running."
            )

            return

        description = (
            self.description_var.get()
        )

        success, result = (
            self.timer.stop(
                description
            )
        )

        if not success:

            messagebox.showwarning(
                "Pomodoro",
                result
            )

            return

        self.timer_task_id = None

        self.timer_status_label.config(
            text="Completed"
        )

        self.pomodoro_task_label.config(
            text="No Task Selected"
        )

        self.description_var.set("")

        self.refresh_tasks()

        self.update_analytics()

    # =====================================================
    # CANCEL
    # =====================================================

    def cancel_pomodoro(self):

        if not self.timer.is_running():

            return

        answer = messagebox.askyesno(
            "Cancel Pomodoro",
            "Cancel this Pomodoro?"
        )

        if not answer:
            return

        self.timer.cancel()

        self.timer_task_id = None

        self.timer_status_label.config(
            text="Cancelled"
        )

        self.pomodoro_task_label.config(
            text="No Task Selected"
        )

        self.description_var.set("")

        self.update_timer()

    # =====================================================
    # TIMER UPDATE
    # =====================================================

    def update_timer(self):

        remaining = (
            self.timer.tick()
        )

        self.timer_label.config(
            text=format_time(
                remaining
            )
        )

        # Pomodoro finished

        if self.timer.is_finished():

            self.finish_completed_pomodoro()

        self.root.after(
            500,
            self.update_timer
        )

    # =====================================================
    # AUTO COMPLETE POMODORO
    # =====================================================

    def finish_completed_pomodoro(self):

        if not self.timer.is_running():
            return

        description = (
            self.description_var.get()
        )

        self.timer.stop(
            description
        )

        self.timer_task_id = None

        self.timer_status_label.config(
            text="Pomodoro Completed"
        )

        self.pomodoro_task_label.config(
            text="No Task Selected"
        )

        self.description_var.set("")

        self.refresh_tasks()

        self.update_analytics()

        messagebox.showinfo(
            "Pomodoro",
            "Pomodoro completed."
        )

    # =====================================================
    # ANALYTICS TAB
    # =====================================================

    def create_analytics_tab(self):

        frame = ttk.Frame(
            self.analytics_tab
        )

        frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=30
        )

        ttk.Label(
            frame,
            text="Analytics",
            font=("Arial", 24)
        ).pack(
            anchor="w",
            pady=(0, 30)
        )

        self.today_focus_label = ttk.Label(
            frame,
            text="Today Focus: 00:00"
        )

        self.today_focus_label.pack(
            anchor="w",
            pady=10
        )

        self.today_pomodoro_label = ttk.Label(
            frame,
            text="Today Pomodoros: 0"
        )

        self.today_pomodoro_label.pack(
            anchor="w",
            pady=10
        )

        self.week_focus_label = ttk.Label(
            frame,
            text="This Week Focus: 00:00"
        )

        self.week_focus_label.pack(
            anchor="w",
            pady=10
        )

        self.week_pomodoro_label = ttk.Label(
            frame,
            text="This Week Pomodoros: 0"
        )

        self.week_pomodoro_label.pack(
            anchor="w",
            pady=10
        )

    # =====================================================
    # ANALYTICS
    # =====================================================

    def update_analytics(self):

        if not hasattr(
            self,
            "today_focus_label"
        ):
            return

        today = datetime.now().date()

        today_start = datetime.combine(
            today,
            datetime.min.time()
        )

        tomorrow = today + timedelta(
            days=1
        )

        tomorrow_start = datetime.combine(
            tomorrow,
            datetime.min.time()
        )

        # Monday

        week_start_date = (
            today
            - timedelta(
                days=today.weekday()
            )
        )

        week_start = datetime.combine(
            week_start_date,
            datetime.min.time()
        )

        week_end = tomorrow_start

        today_focus = (
            database.get_focus_seconds_between(
                today_start.isoformat(
                    timespec="seconds"
                ),
                tomorrow_start.isoformat(
                    timespec="seconds"
                )
            )
        )

        today_count = (
            database.get_pomodoro_count_between(
                today_start.isoformat(
                    timespec="seconds"
                ),
                tomorrow_start.isoformat(
                    timespec="seconds"
                )
            )
        )

        week_focus = (
            database.get_focus_seconds_between(
                week_start.isoformat(
                    timespec="seconds"
                ),
                week_end.isoformat(
                    timespec="seconds"
                )
            )
        )

        week_count = (
            database.get_pomodoro_count_between(
                week_start.isoformat(
                    timespec="seconds"
                ),
                week_end.isoformat(
                    timespec="seconds"
                )
            )
        )

        self.today_focus_label.config(
            text=(
                f"Today Focus: "
                f"{format_time(today_focus)}"
            )
        )

        self.today_pomodoro_label.config(
            text=(
                f"Today Pomodoros: "
                f"{today_count}"
            )
        )

        self.week_focus_label.config(
            text=(
                f"This Week Focus: "
                f"{format_time(week_focus)}"
            )
        )

        self.week_pomodoro_label.config(
            text=(
                f"This Week Pomodoros: "
                f"{week_count}"
            )
        )

    # =====================================================
    # CSV EXPORT TASKS
    # =====================================================

    def export_tasks(self):

        path = filedialog.asksaveasfilename(
            title="Export Tasks",
            defaultextension=".csv",
            filetypes=[
                (
                    "CSV Files",
                    "*.csv"
                )
            ]
        )

        if not path:
            return

        tasks = database.get_tasks()

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            writer = csv.writer(
                file
            )

            writer.writerow([
                "id",
                "wbs",
                "title",
                "project",
                "estimated_seconds",
                "actual_seconds",
                "status",
                "created_at",
                "completed_at"
            ])

            for task in tasks:

                writer.writerow([
                    task["id"],
                    task["wbs"] or "",
                    task["title"],
                    task["project_name"] or "",
                    task["estimated_seconds"],
                    task["actual_seconds"],
                    task["status"],
                    task["created_at"],
                    task["completed_at"] or ""
                ])

        messagebox.showinfo(
            "Export",
            "Tasks exported successfully."
        )

    # =====================================================
    # CSV IMPORT TASKS
    # =====================================================

    def import_csv(self):

        path = filedialog.askopenfilename(
            title="Import Tasks",
            filetypes=[
                (
                    "CSV Files",
                    "*.csv"
                )
            ]
        )

        if not path:
            return

        try:

            with open(
                path,
                "r",
                encoding="utf-8-sig",
                newline=""
            ) as file:

                reader = csv.DictReader(
                    file
                )

                count = 0

                for row in reader:

                    title = (
                        row.get("title")
                        or row.get("Task")
                        or row.get("task")
                    )

                    if not title:
                        continue

                    wbs = (
                        row.get("wbs")
                        or row.get("WBS")
                        or ""
                    )

                    project = (
                        row.get("project")
                        or row.get("Project")
                        or ""
                    )

                    estimated = (
                        row.get(
                            "estimated_seconds"
                        )
                        or row.get(
                            "estimated_time"
                        )
                        or row.get(
                            "estimate"
                        )
                        or "0"
                    )

                    try:

                        estimated_seconds = int(
                            estimated
                        )

                    except ValueError:

                        estimated_seconds = (
                            parse_time(
                                estimated
                            )
                        )

                    project_id = (
                        database.get_or_create_project(
                            project
                        )
                        if project.strip()
                        else None
                    )

                    task_id = database.create_task(
                        title=title,
                        wbs=wbs,
                        project_id=project_id,
                        estimated_seconds=estimated_seconds
                    )

                    tags = (
                        row.get("tags")
                        or ""
                    )

                    tag_names = [
                        tag.strip()
                        for tag in tags.split(",")
                        if tag.strip()
                    ]

                    database.set_task_tags(
                        task_id,
                        tag_names
                    )

                    count += 1

            self.refresh_tasks()

            self.refresh_projects()

            messagebox.showinfo(
                "Import",
                f"{count} tasks imported."
            )

        except Exception as error:

            messagebox.showerror(
                "Import Error",
                str(error)
            )

    # =====================================================
    # CSV EXPORT POMODOROS
    # =====================================================

    def export_pomodoros(self):

        path = filedialog.asksaveasfilename(
            title="Export Pomodoros",
            defaultextension=".csv",
            filetypes=[
                (
                    "CSV Files",
                    "*.csv"
                )
            ]
        )

        if not path:
            return

        pomodoros = (
            database.get_all_pomodoros()
        )

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            writer = csv.writer(
                file
            )

            writer.writerow([
                "id",
                "task_id",
                "task",
                "started_at",
                "ended_at",
                "duration_seconds",
                "description"
            ])

            for session in pomodoros:

                writer.writerow([
                    session["id"],
                    session["task_id"],
                    session["task_title"],
                    session["started_at"],
                    session["ended_at"],
                    session["duration_seconds"],
                    session["description"] or ""
                ])

        messagebox.showinfo(
            "Export",
            "Pomodoros exported successfully."
        )

    # =====================================================
    # BACKUP
    # =====================================================

    def backup_database(self):

        source = database.DB_PATH

        if not source.exists():

            messagebox.showerror(
                "Backup",
                "Database does not exist yet."
            )

            return

        path = filedialog.asksaveasfilename(
            title="Backup Database",
            defaultextension=".db",
            filetypes=[
                (
                    "SQLite Database",
                    "*.db"
                )
            ]
        )

        if not path:
            return

        try:

            shutil.copy2(
                source,
                path
            )

            messagebox.showinfo(
                "Backup",
                "Database backup created."
            )

        except Exception as error:

            messagebox.showerror(
                "Backup Error",
                str(error)
            )