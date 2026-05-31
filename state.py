"""State persistence for the Song Folder Player."""

import io
import json
import msvcrt
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


# State file location - same directory as the app
STATE_FILE = Path(__file__).parent / "state.json"
LOCK_FILE = Path(__file__).parent / "state.lock"
MAX_RECENT_FOLDERS = 20


@dataclass
class PlaylistState:
    """State for a single playlist/folder."""

    current_filename: str = ""
    shuffle_order: list[str] | None = None  # filenames in shuffle order; None = straight mode
    loop_enabled: bool = True
    playback_position_ms: int = 0  # Position within current track

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "current_filename": self.current_filename,
            "shuffle_order": self.shuffle_order,
            "loop_enabled": self.loop_enabled,
            "playback_position_ms": self.playback_position_ms,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "PlaylistState":
        """Create PlaylistState from dictionary."""
        shuffle_order = data.get("shuffle_order")
        # Back-compat: old format stored integer indices — discard them since we
        # cannot convert without knowing which files were present at save time.
        if shuffle_order and isinstance(shuffle_order[0], int):
            shuffle_order = None
        return cls(
            current_filename=data.get("current_filename", ""),
            shuffle_order=shuffle_order,
            loop_enabled=data.get("loop_enabled", True),
            playback_position_ms=data.get("playback_position_ms", 0),
        )


@dataclass
class AppState:
    """Application state containing recent folders and playlist states."""

    recent_folders: list[str] = field(default_factory=list)
    playlists: dict[str, PlaylistState] = field(default_factory=dict)
    volume: int = 100  # Global volume level (0-100)
    zoom_level: float = 1.2  # UI zoom level (1.0 = 100%)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "recent_folders": self.recent_folders,
            "playlists": {
                folder: state.to_dict() for folder, state in self.playlists.items()
            },
            "volume": self.volume,
            "zoom_level": self.zoom_level,
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
        volume = data.get("volume", 100)
        zoom_level = data.get("zoom_level", 1.2)
        return cls(
            recent_folders=recent_folders,
            playlists=playlists,
            volume=volume,
            zoom_level=zoom_level,
        )

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


def acquire_lock() -> io.TextIOWrapper | None:
    """Try to acquire an exclusive lock for state writing.

    Returns:
        File handle if lock acquired (must stay open), None if another
        instance already holds the lock.
    """
    try:
        fh = open(LOCK_FILE, "w", encoding="utf-8")
        msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        fh.write(str(os.getpid()))
        fh.flush()
        return fh
    except (OSError, PermissionError):
        try:
            fh.close()
        except Exception:
            pass
        return None


def release_lock(fh: io.TextIOWrapper) -> None:
    """Release the state lock and clean up the lock file.

    Args:
        fh: File handle returned by acquire_lock.
    """
    try:
        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        fh.close()
    except OSError:
        pass
    try:
        LOCK_FILE.unlink(missing_ok=True)
    except OSError:
        pass
