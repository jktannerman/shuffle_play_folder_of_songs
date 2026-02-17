"""Main entry point for Song Folder Player."""

import atexit
import tkinter as tk

from .gui import SongFolderPlayerGUI
from .state import AppState, acquire_lock, load_state, release_lock, save_state


class _ToolTip:
    """Simple hover tooltip for a tkinter widget."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._widget = widget
        self._text = text
        self._tip_window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if self._tip_window:
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width()
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 2
        tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x - 280}+{y}")
        label = tk.Label(
            tw, text=self._text, justify="left",
            background="#ffffe0", foreground="#000000",
            relief="solid", borderwidth=1, padx=4, pady=2,
        )
        label.pack()
        self._tip_window = tw

    def _hide(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


def _add_readonly_indicator(root: tk.Tk) -> None:
    """Add a READ-ONLY badge to the top-right corner of the window.

    Args:
        root: The root tkinter window.
    """
    badge = tk.Label(
        root,
        text=" READ-ONLY ",
        font=("Segoe UI", 8, "bold"),
        bg="#8B0000",
        fg="white",
    )
    badge.place(relx=1.0, x=-6, y=6, anchor="ne")
    badge.lift()
    _ToolTip(
        badge,
        "Another instance is already running.\n"
        "This instance will not save state changes to disk.",
    )


def _print_banner() -> None:
    """Print a music-themed block banner in cyan."""
    cyan = "\033[36m"
    reset = "\033[0m"
    banner = (
        "\n"
        "  ██████  ███████ ██████\n"
        "  ██      ██      ██   ██\n"
        "  ██████  █████   ██████\n"
        "      ██  ██      ██\n"
        "  ██████  ██      ██\n"
        "\n"
        "  ♪  Song Folder Player  ♪\n"
    )
    print(f"{cyan}{banner}{reset}")


def main() -> None:
    """Initialize and run the Song Folder Player application."""
    _print_banner()

    # Load saved state
    state = load_state()

    # Create main window
    root = tk.Tk()

    # Try to acquire the instance lock
    lock_handle = acquire_lock()

    if lock_handle is not None:
        # Primary instance — save state normally
        atexit.register(release_lock, lock_handle)

        def on_state_change() -> None:
            save_state(state)
    else:
        # Read-only instance — no-op save
        def on_state_change() -> None:
            pass

    # Create and run GUI
    app = SongFolderPlayerGUI(root, state, on_state_change=on_state_change)

    if lock_handle is None:
        _add_readonly_indicator(root)

    app.run()


if __name__ == "__main__":
    main()
