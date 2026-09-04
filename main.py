import tkinter as tk
from ui import FocusApp


def main():
    root = tk.Tk()
    app = FocusApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()