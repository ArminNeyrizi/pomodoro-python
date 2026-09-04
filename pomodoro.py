import time
from datetime import datetime

import database


class PomodoroTimer:
    """
    مدیریت تایمر پومودورو.

    این کلاس مسئول UI نیست.
    فقط منطق تایمر و ثبت Session را مدیریت می‌کند.
    """

    def __init__(self, duration_minutes=25):

        self.duration_seconds = duration_minutes * 60

        self.remaining_seconds = self.duration_seconds

        self.running = False
        self.paused = False

        self.task_id = None
        self.pomodoro_id = None

        self.started_at = None

        self.elapsed_before_pause = 0
        self.last_tick = None

    # =====================================================
    # START
    # =====================================================

    def start(self, task_id):

        if self.running:
            return False, "Timer is already running."

        # بررسی prerequisiteها
        incomplete = database.prerequisites_completed(task_id)

        if incomplete:

            titles = [
                row["title"]
                for row in incomplete
            ]

            return (
                False,
                "Prerequisites are not completed:\n"
                + "\n".join(
                    f"- {title}"
                    for title in titles
                )
            )

        self.task_id = task_id

        self.started_at = datetime.now()

        self.last_tick = time.time()

        self.remaining_seconds = self.duration_seconds

        self.elapsed_before_pause = 0

        self.running = True
        self.paused = False

        self.pomodoro_id = database.create_pomodoro(
            task_id=task_id,
            started_at=self.started_at.isoformat(
                timespec="seconds"
            )
        )

        return True, "Timer started."

    # =====================================================
    # PAUSE
    # =====================================================

    def pause(self):

        if not self.running:
            return False, "Timer is not running."

        if self.paused:
            return False, "Timer is already paused."

        self._update_elapsed()

        self.paused = True

        return True, "Timer paused."

    # =====================================================
    # RESUME
    # =====================================================

    def resume(self):

        if not self.running:
            return False, "Timer is not running."

        if not self.paused:
            return False, "Timer is already running."

        self.last_tick = time.time()

        self.paused = False

        return True, "Timer resumed."

    # =====================================================
    # STOP
    # =====================================================

    def stop(self, description=""):

        if not self.running:
            return False, "Timer is not running."

        if not self.paused:
            self._update_elapsed()

        elapsed = (
            self.duration_seconds
            - self.remaining_seconds
        )

        if elapsed < 0:
            elapsed = 0

        ended_at = datetime.now()

        database.finish_pomodoro(
            pomodoro_id=self.pomodoro_id,
            ended_at=ended_at.isoformat(
                timespec="seconds"
            ),
            duration_seconds=elapsed,
            description=description
        )

        self.running = False
        self.paused = False

        self.task_id = None
        self.pomodoro_id = None
        self.started_at = None

        self.remaining_seconds = self.duration_seconds

        self.elapsed_before_pause = 0

        self.last_tick = None

        return True, elapsed

    # =====================================================
    # CANCEL
    # =====================================================

    def cancel(self):

        if not self.running:
            return False, "Timer is not running."

        if self.pomodoro_id:

            database.cancel_pomodoro(
                self.pomodoro_id
            )

        self.running = False
        self.paused = False

        self.task_id = None
        self.pomodoro_id = None
        self.started_at = None

        self.remaining_seconds = self.duration_seconds

        self.elapsed_before_pause = 0

        self.last_tick = None

        return True, "Timer cancelled."

    # =====================================================
    # TICK
    # =====================================================

    def tick(self):

        if not self.running:
            return self.remaining_seconds

        if self.paused:
            return self.remaining_seconds

        self._update_elapsed()

        # Pomodoro تمام شده
        if self.remaining_seconds <= 0:

            self.remaining_seconds = 0

            return 0

        return self.remaining_seconds

    # =====================================================
    # UPDATE ELAPSED
    # =====================================================

    def _update_elapsed(self):

        if not self.running:
            return

        if self.paused:
            return

        if self.last_tick is None:
            self.last_tick = time.time()
            return

        current_time = time.time()

        delta = current_time - self.last_tick

        self.last_tick = current_time

        self.remaining_seconds -= delta

        if self.remaining_seconds < 0:
            self.remaining_seconds = 0

    # =====================================================
    # STATUS
    # =====================================================

    def is_running(self):

        return self.running

    def is_paused(self):

        return self.paused

    def is_finished(self):

        return (
            self.running
            and self.remaining_seconds <= 0
        )

    # =====================================================
    # TIME
    # =====================================================

    def get_remaining_seconds(self):

        return max(
            0,
            int(self.remaining_seconds)
        )

    def get_elapsed_seconds(self):

        return max(
            0,
            int(
                self.duration_seconds
                - self.remaining_seconds
            )
        )

    # =====================================================
    # RESET
    # =====================================================

    def reset(self):

        self.running = False
        self.paused = False

        self.task_id = None
        self.pomodoro_id = None
        self.started_at = None

        self.remaining_seconds = self.duration_seconds

        self.elapsed_before_pause = 0

        self.last_tick = None