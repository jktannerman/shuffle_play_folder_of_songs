"""State persistence for the Song Folder Player."""

import json
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# State file location - same directory as the app
STATE_FILE = Path(__file__).parent / "state.json"
MAX_RECENT_FOLDERS = 10


@dataclass
class PlaylistState:
    """State for a single playlist/folder."""

    current_index: int = 0
    shuffle_order: list[int] | None = None
    loop_enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "current_index": self.current_index,
            "shuffle_order": self.shuffle_order,
            "loop_enabled": self.loop_enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlaylistState":
        """Create PlaylistState from dictionary."""
        return cls(
            current_index=data.get("current_index", 0),
            shuffle_order=data.get("shuffle_order"),
            loop_enabled=data.get("loop_enabled", True),
        )


@dataclass
class AppState:
    """Application state containing recent folders and playlist states."""

    recent_folders: list[str] = field(default_factory=list)
    playlists: dict[str, PlaylistState] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "recent_folders": self.recent_folders,
            "playlists": {
                folder: state.to_dict() for folder, state in self.playlists.items()
            },
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AppState":
        """Create AppState from dictionary."""
        recent_folders = data.get("recent_folders", [])
        playlists_data = data.get("playlists", {})
        playlists = {
            folder: PlaylistState.from_dict(state)
            for folder, state in playlists_data.items()
        }
        return cls(recent_folders=recent_folders, playlists=playlists)

    def add_recent_folder(self, folder_path: str) -> None:
        """Add a folder to the recent folders list.

        Args:
            folder_path: Path to the folder to add.
        """
        # Normalize the path
        normalized = str(Path(folder_path).resolve())

        # Remove if already in list
        if normalized in self.recent_folders:
            self.recent_folders.remove(normalized)

        # Add to front
        self.recent_folders.insert(0, normalized)

        # Trim to max size
        self.recent_folders = self.recent_folders[:MAX_RECENT_FOLDERS]

    def get_playlist_state(self, folder_path: str) -> PlaylistState:
        """Get or create playlist state for a folder.

        Args:
            folder_path: Path to the folder.

        Returns:
            PlaylistState for the folder.
        """
        normalized = str(Path(folder_path).resolve())
        if normalized not in self.playlists:
            self.playlists[normalized] = PlaylistState()
        return self.playlists[normalized]

    def set_playlist_state(self, folder_path: str, state: PlaylistState) -> None:
        """Set playlist state for a folder.

        Args:
            folder_path: Path to the folder.
            state: PlaylistState to set.
        """
        normalized = str(Path(folder_path).resolve())
        self.playlists[normalized] = state


def load_state() -> AppState:
    """Load application state from disk.

    Returns:
        AppState loaded from file, or new state if file doesn't exist.
    """
    if not STATE_FILE.exists():
        return AppState()

    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        return AppState.from_dict(data)
    except (json.JSONDecodeError, OSError):
        return AppState()


def save_state(state: AppState) -> None:
    """Save application state to disk atomically.

    Uses write-to-temp-then-rename for atomic writes.

    Args:
        state: AppState to save.
    """
    # Create parent directory if needed
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)

    # Write to temporary file first
    fd, temp_path = tempfile.mkstemp(
        dir=STATE_FILE.parent,
        prefix="state_",
        suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state.to_dict(), f, indent=2)

        # Atomic rename (on Windows, need to remove target first)
        if STATE_FILE.exists():
            STATE_FILE.unlink()
        Path(temp_path).rename(STATE_FILE)
    except OSError:
        # Clean up temp file on failure
        try:
            os.unlink(temp_path)
        except OSError:
            pass
        raise
