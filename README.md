# Pomodoro-Python (WBS & Focus Tracker Desktop App)

A minimalist, highly efficient desktop application built with Python and Tkinter that combines **Work Breakdown Structure (WBS)** task management (Microsoft Project style) with a **Pomodoro productivity timer** and **analytics tracking**.

---

## 🏗️ Project Architecture & Philosophy

The project follows a clean, modular structure designed to avoid overengineering while separating responsibilities clearly. It uses SQLite for local persistence and Tkinter for a native desktop UI tailored for macOS workflows.

```text
pomodoro-python/
│
├── main.py              # Application entry point
├── database.py          # SQLite database operations & schema management
├── pomodoro.py          # Core Pomodoro timer logic & state machine
│
└── ui/
    ├── __init__.py
    ├── app.py           # Core window & Notebook (Tabs) coordinator
    ├── tasks.py         # WBS Treeview, keyboard shortcuts, task operations
    ├── task_dialog.py   # Modal dialog for creating/editing tasks
    ├── pomodoro.py      # Pomodoro timer interface, session tracking & CSV export
    └── analytics.py     # Daily & weekly focus metrics and statistics
