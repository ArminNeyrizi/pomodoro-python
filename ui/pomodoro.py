import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime

from pomodoro import PomodoroTimer
import database


def format_time(seconds):
    seconds = int(seconds or 0)

    minutes = seconds // 60
    seconds = seconds % 60

    return f"{minutes:02d}:{seconds:02d}"


class PomodoroUI:

    def __init__(self, parent, app):

        self.parent = parent
        self.app = app

        self.timer = PomodoroTimer(25)

        self.build()
        self.update_timer()

    # =====================================================
    # Build
    # =====================================================

    def build(self):

        frame = ttk.Frame(
            self.parent
        )

        frame.pack(
            fill="both",
            expand=True,
            padx=30,
            pady=30
        )

        ttk.Label(
            frame,
            text="Current Task"
        ).pack()

        self.task_label = ttk.Label(
            frame,
            text="No task",
            font=("TkDefaultFont", 15)
        )

        self.task_label.pack(
            pady=(5, 20)
        )

        self.timer_label = ttk.Label(
            frame,
            text="25:00",
            font=("TkDefaultFont", 52)
        )

        self.timer_label.pack(
            pady=15
        )

        self.status_label = ttk.Label(
            frame,
            text="Ready"
        )

        self.status_label.pack()

        # Description
        ttk.Label(
            frame,
            text="What did you work on?"
        ).pack(
            pady=(30, 5)
        )

        self.description = tk.Text(
            frame,
            height=5,
            width=70
        )

        self.description.pack()

        # Buttons
        buttons = ttk.Frame(
            frame
        )

        buttons.pack(
            pady=20
        )

        self.add_button(
            buttons,
            "Start",
            self.start
        )

        self.add_button(
            buttons,
            "Pause",
            self.pause
        )

        self.add_button(
            buttons,
            "Resume",
            self.resume
        )

        self.add_button(
            buttons,
            "Stop",
            self.stop
        )

        self.add_button(
            buttons,
            "Cancel",
            self.cancel
        )

        ttk.Button(
            frame,
            text="Export Sessions",
            command=self.export
        ).pack(
            pady=10
        )

    def add_button(
        self,
        parent,
        text,
        command
    ):

        ttk.Button(
            parent,
            text=text,
            command=command
        ).pack(
            side="left",
            padx=4
        )

    # =====================================================
    # Start
    # =====================================================

    def start(self, task_id=None):

        if task_id is None:

            task_id = (
                self.app.tasks.selected_id(
                    warning=False
                )
            )

        if task_id is None:

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
                "Pomodoro",
                message
            )

            return

        self.task_label.config(
            text=(
                f"{task['wbs'] or ''} "
                f"{task['title']}"
            )
        )

        self.description.delete(
            "1.0",
            "end"
        )

    # =====================================================
    # Pause
    # =====================================================

    def pause(self):

        success, message = self.timer.pause()

        if not success:

            messagebox.showwarning(
                "Pomodoro",
                message
            )

    # =====================================================
    # Resume
    # =====================================================

    def resume(self):

        success, message = self.timer.resume()

        if not success:

            messagebox.showwarning(
                "Pomodoro",
                message
            )

    # =====================================================
    # Stop
    # =====================================================

    def stop(self):

        if not self.timer.is_running():
            return

        description = (
            self.description
            .get("1.0", "end")
            .strip()
        )

        self.timer.stop(
            description
        )

        self.reset_ui()

        self.app.tasks.refresh()

        self.app.analytics.refresh()

    # =====================================================
    # Cancel
    # =====================================================

    def cancel(self):

        if not self.timer.is_running():
            return

        if not messagebox.askyesno(
            "Cancel Pomodoro",
            "Cancel this Pomodoro?"
        ):
            return

        self.timer.cancel()

        self.reset_ui()

    # =====================================================
    # Timer Update
    # =====================================================

    def update_timer(self):

        remaining = self.timer.tick()

        self.timer_label.config(
            text=format_time(
                remaining
            )
        )

        if self.timer.is_running():

            if self.timer.is_paused():

                self.status_label.config(
                    text="Paused"
                )

            else:

                self.status_label.config(
                    text="Running"
                )

        else:

            self.status_label.config(
                text="Ready"
            )

        if self.timer.is_finished():

            description = (
                self.description
                .get("1.0", "end")
                .strip()
            )

            self.timer.stop(
                description
            )

            self.reset_ui()

            self.app.tasks.refresh()
            self.app.analytics.refresh()

            messagebox.showinfo(
                "Pomodoro",
                "Pomodoro completed."
            )

        self.parent.after(
            500,
            self.update_timer
        )

    # =====================================================
    # Reset
    # =====================================================

    def reset_ui(self):

        self.task_label.config(
            text="No task"
        )

        self.description.delete(
            "1.0",
            "end"
        )

        self.timer_label.config(
            text="25:00"
        )

    # =====================================================
    # Export
    # =====================================================

    def export(self):

        sessions = database.get_all_pomodoros()

        if not sessions:

            messagebox.showinfo(
                "Export",
                "No Pomodoro sessions."
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

        import csv

        with open(
            path,
            "w",
            newline="",
            encoding="utf-8-sig"
        ) as file:

            writer = csv.writer(file)

            writer.writerow([
                "id",
                "task_id",
                "task",
                "started_at",
                "ended_at",
                "duration_seconds",
                "description"
            ])

            for session in sessions:

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
            "Pomodoro sessions exported."
        )