import tkinter as tk
from tkinter import ttk

import database

from .tasks import TasksUI
from .pomodoro import PomodoroUI
from .analytics import AnalyticsUI


class FocusApp:

    def __init__(self, root):

        self.root = root

        self.root.title("Focus")
        self.root.geometry("1250x750")
        self.root.minsize(950, 600)

        database.init_db()

        self.notebook = ttk.Notebook(root)
        self.notebook.pack(
            fill="both",
            expand=True
        )

        self.tasks_tab = ttk.Frame(
            self.notebook
        )

        self.pomodoro_tab = ttk.Frame(
            self.notebook
        )

        self.analytics_tab = ttk.Frame(
            self.notebook
        )

        self.notebook.add(
            self.tasks_tab,
            text="Tasks"
        )

        self.notebook.add(
            self.pomodoro_tab,
            text="Pomodoro"
        )

        self.notebook.add(
            self.analytics_tab,
            text="Analytics"
        )

        self.tasks = TasksUI(
            self.tasks_tab,
            self
        )

        self.pomodoro = PomodoroUI(
            self.pomodoro_tab,
            self
        )

        self.analytics = AnalyticsUI(
            self.analytics_tab,
            self
        )

    def refresh_all(self):

        self.tasks.refresh()
        self.analytics.refresh()