import tkinter as tk
from tkinter import ttk
from datetime import datetime, timedelta

import database


def format_time(seconds):
    seconds = int(seconds or 0)

    hours = seconds // 3600
    minutes = (seconds % 3600) // 60

    if hours:
        return f"{hours}h {minutes:02d}m"

    return f"{minutes}m"


class AnalyticsUI:

    def __init__(self, parent, app):

        self.parent = parent
        self.app = app

        self.build()
        self.refresh()

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

        # -------------------------------------------------
        # Today
        # -------------------------------------------------

        today = ttk.LabelFrame(
            frame,
            text="Today"
        )

        today.pack(
            fill="x",
            pady=10
        )

        self.today_focus = ttk.Label(
            today,
            text="Focus: 0m",
            font=("TkDefaultFont", 14)
        )

        self.today_focus.pack(
            pady=10
        )

        self.today_count = ttk.Label(
            today,
            text="Pomodoros: 0"
        )

        self.today_count.pack(
            pady=(0, 10)
        )

        # -------------------------------------------------
        # Week
        # -------------------------------------------------

        week = ttk.LabelFrame(
            frame,
            text="This Week"
        )

        week.pack(
            fill="x",
            pady=10
        )

        self.week_focus = ttk.Label(
            week,
            text="Focus: 0m",
            font=("TkDefaultFont", 14)
        )

        self.week_focus.pack(
            pady=10
        )

        self.week_count = ttk.Label(
            week,
            text="Pomodoros: 0"
        )

        self.week_count.pack(
            pady=(0, 10)
        )

        # -------------------------------------------------
        # Refresh
        # -------------------------------------------------

        ttk.Button(
            frame,
            text="Refresh",
            command=self.refresh
        ).pack(
            pady=20
        )

    # =====================================================
    # Refresh
    # =====================================================

    def refresh(self):

        now = datetime.now()

        # Today
        today_start = datetime.combine(
            now.date(),
            datetime.min.time()
        )

        tomorrow = (
            today_start +
            timedelta(days=1)
        )

        # Week
        monday = (
            now.date() -
            timedelta(days=now.weekday())
        )

        week_start = datetime.combine(
            monday,
            datetime.min.time()
        )

        week_end = (
            week_start +
            timedelta(days=7)
        )

        today_start_str = today_start.isoformat(
            timespec="seconds"
        )

        tomorrow_str = tomorrow.isoformat(
            timespec="seconds"
        )

        week_start_str = week_start.isoformat(
            timespec="seconds"
        )

        week_end_str = week_end.isoformat(
            timespec="seconds"
        )

        # -------------------------------------------------
        # Today
        # -------------------------------------------------

        today_focus = (
            database.get_focus_seconds_between(
                today_start_str,
                tomorrow_str
            )
        )

        today_count = (
            database.get_pomodoro_count_between(
                today_start_str,
                tomorrow_str
            )
        )

        # -------------------------------------------------
        # Week
        # -------------------------------------------------

        week_focus = (
            database.get_focus_seconds_between(
                week_start_str,
                week_end_str
            )
        )

        week_count = (
            database.get_pomodoro_count_between(
                week_start_str,
                week_end_str
            )
        )

        # -------------------------------------------------
        # UI
        # -------------------------------------------------

        self.today_focus.config(
            text=(
                f"Focus: "
                f"{format_time(today_focus)}"
            )
        )

        self.today_count.config(
            text=(
                f"Pomodoros: "
                f"{today_count}"
            )
        )

        self.week_focus.config(
            text=(
                f"Focus: "
                f"{format_time(week_focus)}"
            )
        )

        self.week_count.config(
            text=(
                f"Pomodoros: "
                f"{week_count}"
            )
        )