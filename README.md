
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
```
## 🧩 Core Modules Breakdown
    1. Backend & Logic
        ⚬ main.py: Initializes the application loop and window container.
        ⚬ database.py: Manages SQLite connections, handles schema migrations, and provides data access methods for tasks (with hierarchical parent_id and auto-calculated WBS numbers), projects, tags, prerequisites, and pomodoro sessions.
        ⚬ pomodoro.py: Implements the timer state machine (ready, running, paused, finished), tracking active seconds, and logging completed sessions.
    
    2. User Interface (ui/)
        ⚬ ui/app.py: Main application view holding the tab layout (Tasks, Pomodoro, Analytics).
        ⚬ ui/tasks.py: Handles the hierarchical WBS treeview. Implements task status management, search filtering, and import/export capabilities.
        ⚬ ui/task_dialog.py: A dedicated modal form (Toplevel) supporting time parsing (e.g., 90m, 1h 30m), tag management, and prerequisite links. Uses standard [Cancel] / [OK] buttons with keyboard bindings (Enter to save, Esc to cancel).
        ⚬ ui/pomodoro.py: Displays the active task, countdown clock (MM:SS), reflection text area, and session history export to CSV.
        ⚬ ui/analytics.py: Aggregates and displays focus time and Pomodoro counts for Today and This Week.

## ⌨️ Keyboard Shortcuts & Mac-Friendly WBS Navigation
    The task treeview is optimized for rapid keyboard-driven hierarchical planning:
    Shortcut	Action
    Enter	Create New Sibling Task
    Cmd + Enter	Create New Child Task (Sub-task)
    Tab	Indent Task (Make child of previous)
    Shift + Tab	Outdent Task
    Cmd + Up/Down	Move Task Up / Down in hierarchy
    Delete	Delete Task
    Double Click / Cmd + E	Edit Task

## 💾 Database Schema Overview (SQLite)
    ⚬ tasks: Stores id, parent_id (for WBS hierarchy), wbs (auto-generated string like 1.1.2), title, project_id, estimated_seconds, completed, and timestamps.
    ⚬ projects: Categorizes tasks by project name.
    ⚬ tags: Many-to-many relationship with tasks via task-tag mapping.
    ⚬ prerequisites: Tracks task dependencies.
    ⚬ pomodoro_sessions: Logs task_id, started_at, ended_at, duration_seconds, and user descriptions for analytics.

## 🚀 Getting Started
    1. Prerequisites: Python 3.8+ (Tkinter is included with standard Python installations on macOS/Linux/Windows).
    2. Run the Application: python3 main.py
