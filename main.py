"""Main entry point for Song Folder Player."""

import tkinter as tk

from .gui import SongFolderPlayerGUI
from .state import AppState, load_state, save_state


def main() -> None:
    """Initialize and run the Song Folder Player application."""
    # Load saved state
    state = load_state()

    # Create main window
    root = tk.Tk()

    # Create save callback
    def on_state_change() -> None:
        save_state(state)

    # Create and run GUI
    app = SongFolderPlayerGUI(root, state, on_state_change=on_state_change)
    app.run()


if __name__ == "__main__":
    main()
