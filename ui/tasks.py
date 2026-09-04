import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import csv
import shutil
import re

import database

from .task_dialog import TaskDialog


def format_time(seconds):
    seconds = int(seconds or 0)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours:
        return f"{hours}h {minutes:02d}m"

    return f"{minutes:02d}m"


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
            "Invalid time. Example: 90, 90m, 1h, 1h 30m"
        )

    return int(total)


class TasksUI:

    def __init__(self, parent, app):

        self.parent = parent
        self.app = app

        self.tree_to_task = {}
        self.task_to_tree = {}

        self.build()
        self.refresh()

    # =====================================================
    # Build
    # =====================================================

    def build(self):

        toolbar = ttk.Frame(self.parent)
        toolbar.pack(
            fill="x",
            padx=10,
            pady=10
        )

        self.button(
            toolbar,
            "New",
            self.new_task
        )

        self.button(
            toolbar,
            "Add Child",
            self.new_child
        )

        self.button(
            toolbar,
            "Edit",
            self.edit_task
        )

        self.button(
            toolbar,
            "Complete",
            self.complete_task
        )

        self.button(
            toolbar,
            "Reopen",
            self.reopen_task
        )

        self.button(
            toolbar,
            "Delete",
            self.delete_task
        )

        ttk.Separator(
            toolbar,
            orient="vertical"
        ).pack(
            side="left",
            fill="y",
            padx=8
        )

        self.button(
            toolbar,
            "Indent",
            self.indent
        )

        self.button(
            toolbar,
            "Outdent",
            self.outdent
        )

        self.button(
            toolbar,
            "Move Up",
            self.move_up
        )

        self.button(
            toolbar,
            "Move Down",
            self.move_down
        )

        ttk.Separator(
            toolbar,
            orient="vertical"
        ).pack(
            side="left",
            fill="y",
            padx=8
        )

        self.button(
            toolbar,
            "Pomodoro",
            self.start_pomodoro
        )

        self.button(
            toolbar,
            "Import CSV",
            self.import_csv
        )

        self.button(
            toolbar,
            "Export CSV",
            self.export_csv
        )

        self.button(
            toolbar,
            "Backup",
            self.backup
        )

        # Search
        search_frame = ttk.Frame(
            self.parent
        )

        search_frame.pack(
            fill="x",
            padx=10,
            pady=(0, 8)
        )

        ttk.Label(
            search_frame,
            text="Search:"
        ).pack(side="left")

        self.search_var = tk.StringVar()

        search = ttk.Entry(
            search_frame,
            textvariable=self.search_var
        )

        search.pack(
            side="left",
            fill="x",
            expand=True,
            padx=8
        )

        search.bind(
            "<KeyRelease>",
            lambda e: self.refresh()
        )

        # Tree
        tree_frame = ttk.Frame(
            self.parent
        )

        tree_frame.pack(
            fill="both",
            expand=True,
            padx=10,
            pady=(0, 10)
        )

        self.tree = ttk.Treeview(
            tree_frame,
            columns=(
                "project",
                "estimated",
                "actual",
                "status"
            ),
            show="tree headings",
            selectmode="browse"
        )

        self.tree.heading(
            "#0",
            text="WBS / Task"
        )

        self.tree.heading(
            "project",
            text="Project"
        )

        self.tree.heading(
            "estimated",
            text="Estimated"
        )

        self.tree.heading(
            "actual",
            text="Actual"
        )

        self.tree.heading(
            "status",
            text="Status"
        )

        self.tree.column(
            "#0",
            width=520
        )

        self.tree.column(
            "project",
            width=180
        )

        self.tree.column(
            "estimated",
            width=100,
            anchor="center"
        )

        self.tree.column(
            "actual",
            width=100,
            anchor="center"
        )

        self.tree.column(
            "status",
            width=100,
            anchor="center"
        )

        scrollbar = ttk.Scrollbar(
            tree_frame,
            orient="vertical",
            command=self.tree.yview
        )

        self.tree.configure(
            yscrollcommand=scrollbar.set
        )

        self.tree.grid(
            row=0,
            column=0,
            sticky="nsew"
        )

        scrollbar.grid(
            row=0,
            column=1,
            sticky="ns"
        )

        tree_frame.rowconfigure(
            0,
            weight=1
        )

        tree_frame.columnconfigure(
            0,
            weight=1
        )

        # Mouse
        self.tree.bind(
            "<Double-1>",
            lambda e: self.edit_task()
        )

        # Mac keyboard
        self.tree.bind(
            "<Return>",
            self.new_task_keyboard
        )

        self.tree.bind(
            "<Command-Return>",
            self.new_child_keyboard
        )

        self.tree.bind(
            "<Tab>",
            self.indent_keyboard
        )

        self.tree.bind(
            "<Shift-Tab>",
            self.outdent_keyboard
        )

        self.tree.bind(
            "<Command-Up>",
            self.move_up_keyboard
        )

        self.tree.bind(
            "<Command-Down>",
            self.move_down_keyboard
        )

        self.tree.bind(
            "<Delete>",
            self.delete_keyboard
        )

        self.tree.bind(
            "<Command-e>",
            lambda e: self.edit_task()
        )

        # Expand / collapse
        self.tree.bind(
            "<Left>",
            self.collapse
        )

        self.tree.bind(
            "<Right>",
            self.expand
        )

    def button(self, parent, text, command):

        ttk.Button(
            parent,
            text=text,
            command=command
        ).pack(
            side="left",
            padx=3
        )

    # =====================================================
    # Refresh
    # =====================================================

    def refresh(self):

        selected = self.selected_id(
            warning=False
        )

        expanded = {
            self.tree_to_task[item]
            for item in self.tree.get_children("")
            if self.tree.item(item, "open")
        }

        for item in self.tree.get_children():
            self.tree.delete(item)

        self.tree_to_task.clear()
        self.task_to_tree.clear()

        search = self.search_var.get().strip()

        if search:

            tasks = database.get_tasks(
                search
            )

            for task in tasks:
                self.insert_task(
                    "",
                    task
                )

        else:

            tasks = database.get_all_tasks_tree_order()

            self.build_tree(
                None,
                "",
                tasks,
                expanded
            )

        if selected:
            self.select(selected)

    # =====================================================
    # Tree
    # =====================================================

    def build_tree(
        self,
        parent_id,
        tree_parent,
        tasks,
        expanded
    ):

        children = [
            task
            for task in tasks
            if task["parent_id"] == parent_id
        ]

        children.sort(
            key=lambda x: (
                x["sort_order"],
                x["id"]
            )
        )

        for task in children:

            item = self.insert_task(
                tree_parent,
                task
            )

            self.build_tree(
                task["id"],
                item,
                tasks,
                expanded
            )

            if task["id"] in expanded:
                self.tree.item(
                    item,
                    open=True
                )

    def insert_task(
        self,
        parent,
        task
    ):

        text = (
            f"{task['wbs']}  {task['title']}"
            if task["wbs"]
            else task["title"]
        )

        status = (
            "Completed"
            if task["status"] == "completed"
            else "Todo"
        )

        item = self.tree.insert(
            parent,
            "end",
            iid=str(task["id"]),
            text=text,
            values=(
                task["project_name"] or "",
                format_time(
                    task["estimated_seconds"]
                ),
                format_time(
                    task["actual_seconds"]
                ),
                status
            )
        )

        self.tree_to_task[item] = task["id"]
        self.task_to_tree[task["id"]] = item

        return item

    # =====================================================
    # Selection
    # =====================================================

    def selected_id(self, warning=True):

        selection = self.tree.selection()

        if not selection:

            if warning:
                messagebox.showwarning(
                    "Task",
                    "Select a task first."
                )

            return None

        return self.tree_to_task.get(
            selection[0]
        )

    def select(self, task_id):

        item = self.task_to_tree.get(
            task_id
        )

        if not item:
            return

        self.tree.selection_set(item)
        self.tree.focus(item)
        self.tree.see(item)

    # =====================================================
    # New / Edit
    # =====================================================

    def new_task(self):

        selected = self.selected_id(
            warning=False
        )

        parent_id = None

        if selected:

            task = database.get_task(
                selected
            )

            if task:
                parent_id = task["parent_id"]

        self.open_dialog(
            parent_id=parent_id
        )

    def new_child(self):

        selected = self.selected_id()

        if selected is None:
            return

        self.open_dialog(
            parent_id=selected
        )

    def open_dialog(
        self,
        task=None,
        parent_id=None
    ):

        TaskDialog(
            self.parent.winfo_toplevel(),
            task=task,
            parent_id=parent_id,
            on_saved=self.after_save
        )

    def after_save(self, task_id):

        self.refresh()
        self.select(task_id)

    def edit_task(self):

        task_id = self.selected_id()

        if task_id is None:
            return

        task = database.get_task(
            task_id
        )

        if task:

            self.open_dialog(
                task=task,
                parent_id=task["parent_id"]
            )

    # =====================================================
    # Status
    # =====================================================

    def complete_task(self):

        task_id = self.selected_id()

        if task_id is None:
            return

        database.complete_task(
            task_id
        )

        self.refresh()

    def reopen_task(self):

        task_id = self.selected_id()

        if task_id is None:
            return

        database.reopen_task(
            task_id
        )

        self.refresh()

    # =====================================================
    # Delete
    # =====================================================

    def delete_keyboard(self, event=None):

        self.delete_task()

        return "break"

    def delete_task(self):

        task_id = self.selected_id()

        if task_id is None:
            return

        task = database.get_task(
            task_id
        )

        if not task:
            return

        children = database.get_children(
            task_id
        )

        if children:

            text = (
                f"'{task['title']}' has "
                f"{len(children)} child task(s).\n\n"
                "All child tasks will also be deleted.\n\n"
                "Continue?"
            )

        else:

            text = (
                f"Delete '{task['title']}'?"
            )

        if not messagebox.askyesno(
            "Delete Task",
            text
        ):
            return

        database.delete_task(
            task_id
        )

        self.refresh()

    # =====================================================
    # Indent / Outdent
    # =====================================================

    def indent_keyboard(self, event=None):

        self.indent()

        return "break"

    def indent(self):

        task_id = self.selected_id()

        if task_id is None:
            return

        if database.indent_task(
            task_id
        ):

            self.refresh()
            self.select(task_id)

    def outdent_keyboard(self, event=None):

        self.outdent()

        return "break"

    def outdent(self):

        task_id = self.selected_id()

        if task_id is None:
            return

        if database.outdent_task(
            task_id
        ):

            self.refresh()
            self.select(task_id)

    # =====================================================
    # Move
    # =====================================================

    def move_up_keyboard(self, event=None):

        self.move_up()

        return "break"

    def move_up(self):

        task_id = self.selected_id()

        if task_id is None:
            return

        if database.move_task_up(
            task_id
        ):

            self.refresh()
            self.select(task_id)

    def move_down_keyboard(self, event=None):

        self.move_down()

        return "break"

    def move_down(self):

        task_id = self.selected_id()

        if task_id is None:
            return

        if database.move_task_down(
            task_id
        ):

            self.refresh()
            self.select(task_id)

    # =====================================================
    # Expand / Collapse
    # =====================================================

    def expand(self, event=None):

        selection = self.tree.selection()

        if not selection:
            return "break"

        item = selection[0]

        children = self.tree.get_children(
            item
        )

        if children:

            self.tree.item(
                item,
                open=True
            )

        return "break"

    def collapse(self, event=None):

        selection = self.tree.selection()

        if not selection:
            return "break"

        item = selection[0]

        if self.tree.item(
            item,
            "open"
        ):

            self.tree.item(
                item,
                open=False
            )

        else:

            parent = self.tree.parent(
                item
            )

            if parent:
                self.tree.selection_set(
                    parent
                )
                self.tree.focus(parent)

        return "break"

    # =====================================================
    # Pomodoro
    # =====================================================

    def start_pomodoro(self):

        task_id = self.selected_id()

        if task_id is None:
            return

        self.app.notebook.select(
            self.app.pomodoro_tab
        )

        self.app.pomodoro.start(
            task_id
        )

    # =====================================================
    # CSV Export
    # =====================================================

    def export_csv(self):

        tasks = database.get_all_tasks_tree_order()

        if not tasks:

            messagebox.showinfo(
                "Export",
                "No tasks."
            )

            return

        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                ("CSV", "*.csv")
            ]
        )

        if not path:
            return

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "id",
                "wbs",
                "title",
                "parent_id",
                "project",
                "estimated_seconds",
                "actual_seconds",
                "status",
                "tags"
            ])

            for task in tasks:

                tags = database.get_task_tags(
                    task["id"]
                )

                writer.writerow([
                    task["id"],
                    task["wbs"] or "",
                    task["title"],
                    task["parent_id"] or "",
                    task["project_name"] or "",
                    task["estimated_seconds"] or 0,
                    task["actual_seconds"] or 0,
                    task["status"],
                    ",".join(
                        tag["name"]
                        for tag in tags
                    )
                ])

        messagebox.showinfo(
            "Export",
            "Tasks exported."
        )

    # =====================================================
    # CSV Import
    # =====================================================

    def import_csv(self):

        path = filedialog.askopenfilename(
            filetypes=[
                ("CSV", "*.csv")
            ]
        )

        if not path:
            return

        try:

            with open(
                path,
                "r",
                newline="",
                encoding="utf-8-sig"
            ) as file:

                rows = list(
                    csv.DictReader(file)
                )

            wbs_map = {}
            imported = 0

            rows.sort(
                key=lambda row: (
                    len(
                        (
                            row.get("wbs")
                            or row.get("WBS")
                            or ""
                        ).split(".")
                    ),
                    (
                        row.get("wbs")
                        or row.get("WBS")
                        or ""
                    )
                )
            )

            for row in rows:

                title = (
                    row.get("title")
                    or row.get("Task")
                    or ""
                ).strip()

                if not title:
                    continue

                wbs = (
                    row.get("wbs")
                    or row.get("WBS")
                    or ""
                ).strip()

                project = (
                    row.get("project")
                    or row.get("Project")
                    or ""
                ).strip()

                estimate = (
                    row.get("estimated_seconds")
                    or row.get("estimated_time")
                    or ""
                )

                try:
                    estimated = parse_time(
                        estimate
                    )
                except ValueError:
                    estimated = 0

                project_id = (
                    database.get_or_create_project(
                        project
                    )
                )

                parent_id = None

                if "." in wbs:

                    parent_wbs = ".".join(
                        wbs.split(".")[:-1]
                    )

                    parent_id = wbs_map.get(
                        parent_wbs
                    )

                task_id = database.create_task(
                    title=title,
                    project_id=project_id,
                    estimated_seconds=estimated,
                    parent_id=parent_id
                )

                wbs_map[wbs] = task_id

                tags = (
                    row.get("tags")
                    or row.get("Tags")
                    or ""
                )

                database.set_task_tags(
                    task_id,
                    [
                        x.strip()
                        for x in tags.split(",")
                        if x.strip()
                    ]
                )

                imported += 1

        except Exception as error:

            messagebox.showerror(
                "Import Error",
                str(error)
            )

            return

        self.refresh()

        messagebox.showinfo(
            "Import",
            f"{imported} tasks imported."
        )

    # =====================================================
    # Backup
    # =====================================================

    def backup(self):

        path = filedialog.asksaveasfilename(
            defaultextension=".db",
            initialfile="focus_backup.db",
            filetypes=[
                ("SQLite Database", "*.db")
            ]
        )

        if not path:
            return

        try:

            shutil.copy2(
                database.DB_PATH,
                path
            )

        except Exception as error:

            messagebox.showerror(
                "Backup Error",
                str(error)
            )

            return

        messagebox.showinfo(
            "Backup",
            "Backup created."
        )

    # =====================================================
    # Keyboard New Task
    # =====================================================

    def new_task_keyboard(self, event=None):

        self.new_task()

        return "break"

    def new_child_keyboard(self, event=None):

        self.new_child()

        return "break"