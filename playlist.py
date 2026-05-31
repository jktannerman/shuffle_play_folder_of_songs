"""Playlist navigation and state management."""

import random
from pathlib import Path

from .state import PlaylistState


class PlaylistController:
    """Manages playlist navigation, shuffle, and per-folder state persistence.

    Owns the runtime integer indices and the PlaylistState for the currently
    loaded folder. The GUI holds one instance and calls into it for all
    navigation decisions; this class never touches tkinter.

    Lifecycle::

        controller = PlaylistController()
        controller.load(files, playlist_state)  # on every folder open
        controller.sync_to_state()              # before each save
    """

    def __init__(self) -> None:
        self._files: list[Path] = []
        self._current_index: int = 0
        self._shuffle_order: list[int] | None = None
        self._playlist_state: PlaylistState | None = None

    # ------------------------------------------------------------------ #
    # Loading and persistence                                              #
    # ------------------------------------------------------------------ #

    def load(self, files: list[Path], playlist_state: PlaylistState) -> None:
        """Load a file list, taking ownership of playlist_state.

        Reconciles the saved filename-based state against the actual files on
        disk, handling renames, deletions, and additions gracefully.

        Args:
            files: Media files from disk, naturally sorted.
            playlist_state: Saved state for this folder (mutated in-place by
                sync_to_state).
        """
        self._files = files
        self._playlist_state = playlist_state
        self._reconcile()

    def sync_to_state(self) -> None:
        """Write runtime indices back to PlaylistState as filenames.

        Must be called before serialising AppState to disk.
        """
        if not self._playlist_state or not self._files:
            return

        if self._shuffle_order is not None:
            file_index = (
                self._shuffle_order[self._current_index]
                if 0 <= self._current_index < len(self._shuffle_order)
                else 0
            )
        else:
            file_index = self._current_index

        if 0 <= file_index < len(self._files):
            self._playlist_state.current_filename = self._files[file_index].name

        if self._shuffle_order is not None:
            self._playlist_state.shuffle_order = [
                self._files[i].name
                for i in self._shuffle_order
                if 0 <= i < len(self._files)
            ]
        else:
            self._playlist_state.shuffle_order = None

    def _reconcile(self) -> None:
        """Resolve saved filename-based state to runtime integer indices.

        Handles files added, removed, or renamed since state was saved:
        - Renamed/deleted current track: resets to first file in display order.
        - Deleted tracks in shuffle: removed silently from shuffle order.
        - Added tracks in shuffle mode: inserted at random positions.
        - Added tracks in straight mode: included automatically by sort order.
        """
        if not self._playlist_state or not self._files:
            self._current_index = 0
            self._shuffle_order = None
            return

        filename_to_index: dict[str, int] = {f.name: i for i, f in enumerate(self._files)}

        # Resolve current file by name; fall back to first file if gone.
        saved_name = self._playlist_state.current_filename
        if saved_name and saved_name in filename_to_index:
            current_file_index = filename_to_index[saved_name]
        else:
            current_file_index = 0

        saved_shuffle = self._playlist_state.shuffle_order
        if saved_shuffle is not None:
            # Retain files still present, preserving saved order.
            present_names: set[str] = {n for n in saved_shuffle if n in filename_to_index}
            resolved: list[int] = [filename_to_index[n] for n in saved_shuffle if n in present_names]

            # Insert newly added files at random positions.
            new_indices = [i for i, f in enumerate(self._files) if f.name not in present_names]
            if new_indices:
                random.shuffle(new_indices)
                for idx in new_indices:
                    insert_pos = random.randint(0, len(resolved))
                    resolved.insert(insert_pos, idx)

            self._shuffle_order = resolved or None
            if self._shuffle_order and current_file_index in self._shuffle_order:
                self._current_index = self._shuffle_order.index(current_file_index)
            else:
                self._current_index = 0
        else:
            self._shuffle_order = None
            self._current_index = current_file_index

    # ------------------------------------------------------------------ #
    # Properties                                                           #
    # ------------------------------------------------------------------ #

    @property
    def is_loaded(self) -> bool:
        """True if a folder has been loaded."""
        return self._playlist_state is not None

    @property
    def files(self) -> list[Path]:
        """Current media files in natural sort order."""
        return self._files

    @property
    def current_display_index(self) -> int:
        """Current position in the display order."""
        return self._current_index

    @property
    def display_order(self) -> list[int]:
        """File indices in display order (shuffle sequence or straight 0..n-1)."""
        if self._shuffle_order is not None:
            return self._shuffle_order
        return list(range(len(self._files)))

    @property
    def shuffle_enabled(self) -> bool:
        """True if shuffle mode is active."""
        return self._shuffle_order is not None

    @property
    def loop_enabled(self) -> bool:
        """True if the playlist loops at the end."""
        return self._playlist_state.loop_enabled if self._playlist_state else True

    @loop_enabled.setter
    def loop_enabled(self, value: bool) -> None:
        if self._playlist_state:
            self._playlist_state.loop_enabled = value

    @property
    def playback_position_ms(self) -> int:
        """Saved playback position within the current track, in milliseconds."""
        return self._playlist_state.playback_position_ms if self._playlist_state else 0

    @playback_position_ms.setter
    def playback_position_ms(self, value: int) -> None:
        if self._playlist_state:
            self._playlist_state.playback_position_ms = value

    # ------------------------------------------------------------------ #
    # File access                                                          #
    # ------------------------------------------------------------------ #

    def current_file(self) -> Path | None:
        """Path of the currently active track, or None if nothing is loaded."""
        return self.file_at(self._current_index)

    def file_at(self, display_pos: int) -> Path | None:
        """Path of the file at the given display position.

        Args:
            display_pos: Position in the display order.

        Returns:
            Path to the file, or None if out of range.
        """
        if not self._files:
            return None
        if self._shuffle_order is not None:
            if 0 <= display_pos < len(self._shuffle_order):
                file_index = self._shuffle_order[display_pos]
                return self._files[file_index] if 0 <= file_index < len(self._files) else None
            return None
        return self._files[display_pos] if 0 <= display_pos < len(self._files) else None

    # ------------------------------------------------------------------ #
    # Navigation                                                           #
    # ------------------------------------------------------------------ #

    def go_to(self, display_pos: int) -> None:
        """Set current position and reset the saved playback offset to zero.

        Args:
            display_pos: Position in the display order to jump to.
        """
        self._current_index = display_pos
        if self._playlist_state:
            self._playlist_state.playback_position_ms = 0

    def advance(self) -> int | None:
        """Move to the next track.

        Returns:
            New display index, or None if at the end and loop is disabled.
        """
        order_len = len(self._shuffle_order) if self._shuffle_order is not None else len(self._files)
        if order_len == 0:
            return None
        next_pos = self._current_index + 1
        if next_pos >= order_len:
            if self.loop_enabled:
                next_pos = 0
            else:
                return None
        self.go_to(next_pos)
        return next_pos

    def retreat(self) -> int:
        """Move to the previous track.

        Returns:
            New display index.
        """
        if not self._files:
            return 0
        order_len = len(self._shuffle_order) if self._shuffle_order is not None else len(self._files)
        prev_pos = self._current_index - 1
        if prev_pos < 0:
            prev_pos = order_len - 1 if self.loop_enabled else 0
        self.go_to(prev_pos)
        return prev_pos

    # ------------------------------------------------------------------ #
    # Shuffle                                                              #
    # ------------------------------------------------------------------ #

    def enable_shuffle(self) -> None:
        """Enable shuffle mode, placing the current track first."""
        current_file_index = self._current_file_index()
        other_indices = [i for i in range(len(self._files)) if i != current_file_index]
        random.shuffle(other_indices)
        self._shuffle_order = [current_file_index] + other_indices
        self._current_index = 0

    def disable_shuffle(self) -> None:
        """Disable shuffle mode, keeping the current file active."""
        self._current_index = self._current_file_index()
        self._shuffle_order = None

    def reshuffle(self) -> None:
        """Generate a new shuffle order (only effective in shuffle mode)."""
        if self._shuffle_order is not None:
            self.enable_shuffle()

    def _current_file_index(self) -> int:
        """Return the index into self._files for the current track."""
        if self._shuffle_order is not None:
            if 0 <= self._current_index < len(self._shuffle_order):
                return self._shuffle_order[self._current_index]
            return 0
        return self._current_index if 0 <= self._current_index < len(self._files) else 0
