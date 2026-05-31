"""Main entry point for Song Folder Player."""

import atexit
import json
import logging
import tkinter as tk

from .gui import SongFolderPlayerGUI, add_readonly_indicator
from .state import APP_DIR, LOG_FILE, acquire_lock, load_state, release_lock, save_state


class _JSONFormatter(logging.Formatter):
    """One JSON object per line log formatter."""

    def format(self, record: logging.LogRecord) -> str:
        obj: dict[str, object] = {
            "time": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
            "module": record.module,
            "msg": record.getMessage(),
        }
        if record.exc_info:
            obj["exc"] = self.formatException(record.exc_info)
        return json.dumps(obj)


def _configure_logging() -> None:
    handler = logging.FileHandler(LOG_FILE, encoding="utf-8")
    handler.setFormatter(_JSONFormatter())
    logging.root.setLevel(logging.DEBUG)
    logging.root.addHandler(handler)


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
    APP_DIR.mkdir(parents=True, exist_ok=True)
    _configure_logging()
    logging.getLogger(__name__).info("starting")
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
        add_readonly_indicator(root)

    app.run()


if __name__ == "__main__":
    main()
