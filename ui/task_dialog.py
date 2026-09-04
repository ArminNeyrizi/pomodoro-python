import tkinter as tk
from tkinter import ttk, messagebox
import re

import database


def parse_time(value):
    value = str(value or "").strip().lower()

    if not value:
        return 0

    if re.fullmatch(r"\d+(\.\d+)?", value):
        return int(float(value) * 60)

    total = 0

    hour = re.search(r"([\d.]+)\s*h", value)
    minute = re.search(r"([\d.]+)\s*m", value)
    second = re.search(r"([\d.]+)\s*s", value)

    if hour:
        total += float(hour.group(1)) * 3600

    if minute:
        total += float(minute.group(1)) * 60

    if second:
        total += float(second.group(1))

    if total == 0:
        raise ValueError(
            "Invalid time. Examples: 90, 90m, 1h, 1h 30m"
        )

    return int(total)


def format_time(seconds):
    seconds = int(seconds or 0)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours:
        return f"{hours}h {minutes:02d}m"

    return f"{minutes}m"


class TaskDialog:

    def __init__(
        self,
        parent,
        task=None,
        parent_id=None,
        on_saved=None
    ):

        self.parent = parent
        self.task = task
        self.parent_id = parent_id
        self.on_saved = on_saved

        self.window = tk.Toplevel(parent)

        self.window.title(
            "Edit Task"
            if task
            else "New Task"
        )

        self.window.geometry(
            "520x470"
        )

        self.window.resizable(
            False,
            False
        )

        self.window.transient(parent)
        self.window.grab_set()

        self.build()

        self.window.bind(
            "<Return>",
            self.save
        )

        self.window.bind(
            "<Escape>",
            self.cancel
        )

        self.window.protocol(
            "WM_DELETE_WINDOW",
            self.cancel
        )

        self.title_entry.focus_set()

    # =====================================================
    # Build
    # =====================================================

    def build(self):

        frame = ttk.Frame(
            self.window
        )

        frame.pack(
            fill="both",
            expand=True,
            padx=25,
            pady=20
        )

        # -------------------------------------------------
        # Parent
        # -------------------------------------------------

        ttk.Label(
            frame,
            text="Parent Task"
        ).pack(
            anchor="w"
        )

        parent_name = "Root"

        if self.parent_id:

            parent = database.get_task(
                self.parent_id
            )

            if parent:

                parent_name = (
                    f"{parent['wbs']}  "
                    f"{parent['title']}"
                )

        ttk.Label(
            frame,
            text=parent_name
        ).pack(
            anchor="w",
            pady=(3, 15)
        )

        # -------------------------------------------------
        # Title
        # -------------------------------------------------

        ttk.Label(
            frame,
            text="Title"
        ).pack(
            anchor="w"
        )

        self.title_var = tk.StringVar(
            value=(
                self.task["title"]
                if self.task
                else ""
            )
        )

        self.title_entry = ttk.Entry(
            frame,
            textvariable=self.title_var
        )

        self.title_entry.pack(
            fill="x",
            pady=(3, 12)
        )

        # -------------------------------------------------
        # Project
        # -------------------------------------------------

        ttk.Label(
            frame,
            text="Project"
        ).pack(
            anchor="w"
        )

        projects = database.get_projects()

        project_names = [
            project["name"]
            for project in projects
        ]

        self.project_var = tk.StringVar(
            value=(
                self.task["project_name"]
                if self.task
                and self.task["project_name"]
                else ""
            )
        )

        self.project_combo = ttk.Combobox(
            frame,
            textvariable=self.project_var,
            values=project_names
        )

        self.project_combo.pack(
            fill="x",
            pady=(3, 12)
        )

        # -------------------------------------------------
        # Estimated Time
        # -------------------------------------------------

        ttk.Label(
            frame,
            text="Estimated Time"
        ).pack(
            anchor="w"
        )

        self.estimated_var = tk.StringVar(
            value=(
                format_time(
                    self.task[
                        "estimated_seconds"
                    ]
                )
                if self.task
                else ""
            )
        )

        ttk.Entry(
            frame,
            textvariable=self.estimated_var
        ).pack(
            fill="x",
            pady=(3, 12)
        )

        # -------------------------------------------------
        # Tags
        # -------------------------------------------------

        ttk.Label(
            frame,
            text="Tags"
        ).pack(
            anchor="w"
        )

        tags = ""

        if self.task:

            task_tags = database.get_task_tags(
                self.task["id"]
            )

            tags = ", ".join(
                tag["name"]
                for tag in task_tags
            )

        self.tags_var = tk.StringVar(
            value=tags
        )

        ttk.Entry(
            frame,
            textvariable=self.tags_var
        ).pack(
            fill="x",
            pady=(3, 12)
        )

        # -------------------------------------------------
        # Prerequisites
        # -------------------------------------------------

        ttk.Label(
            frame,
            text="Prerequisites"
        ).pack(
            anchor="w"
        )

        prerequisites = ""

        if self.task:

            items = database.get_prerequisites(
                self.task["id"]
            )

            prerequisites = ", ".join(
                str(item["id"])
                for item in items
            )

        self.prerequisites_var = tk.StringVar(
            value=prerequisites
        )

        ttk.Entry(
            frame,
            textvariable=self.prerequisites_var
        ).pack(
            fill="x",
            pady=(3, 15)
        )

        # -------------------------------------------------
        # Buttons
        # -------------------------------------------------

        button_frame = ttk.Frame(
            frame
        )

        button_frame.pack(
            fill="x",
            pady=(10, 0)
        )

        ttk.Button(
            button_frame,
            text="Cancel",
            command=self.cancel
        ).pack(
            side="right",
            padx=(8, 0)
        )

        ttk.Button(
            button_frame,
            text="OK",
            command=self.save
        ).pack(
            side="right"
        )

    # =====================================================
    # Save
    # =====================================================

    def save(self, event=None):

        title = self.title_var.get().strip()

        if not title:

            messagebox.showerror(
                "Error",
                "Task title is required.",
                parent=self.window
            )

            self.title_entry.focus_set()

            return "break"

        try:

            estimated_seconds = parse_time(
                self.estimated_var.get()
            )

        except ValueError as error:

            messagebox.showerror(
                "Invalid Time",
                str(error),
                parent=self.window
            )

            return "break"

        project_id = (
            database.get_or_create_project(
                self.project_var.get()
            )
        )

        try:

            if self.task:

                task_id = self.task["id"]

                database.update_task(
                    task_id=task_id,
                    title=title,
                    project_id=project_id,
                    estimated_seconds=estimated_seconds,
                    parent_id=self.parent_id
                )

            else:

                task_id = database.create_task(
                    title=title,
                    project_id=project_id,
                    estimated_seconds=estimated_seconds,
                    parent_id=self.parent_id
                )

            # Tags
            tags = [
                tag.strip()
                for tag in self.tags_var.get().split(",")
                if tag.strip()
            ]

            database.set_task_tags(
                task_id,
                tags
            )

            # Prerequisites
            prerequisite_ids = []

            raw = (
                self.prerequisites_var
                .get()
                .strip()
            )

            if raw:

                for value in raw.split(","):

                    value = value.strip()

                    if not value:
                        continue

                    try:

                        prerequisite_ids.append(
                            int(value)
                        )

                    except ValueError:

                        raise ValueError(
                            f"Invalid prerequisite ID: "
                            f"{value}"
                        )

            database.set_prerequisites(
                task_id,
                prerequisite_ids
            )

        except Exception as error:

            messagebox.showerror(
                "Error",
                str(error),
                parent=self.window
            )

            return "break"

        self.window.grab_release()
        self.window.destroy()

        if self.on_saved:
            self.on_saved(task_id)

        return "break"

    # =====================================================
    # Cancel
    # =====================================================

    def cancel(self, event=None):

        self.window.grab_release()
        self.window.destroy()

        return "break"