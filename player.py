"""VLC media player wrapper."""

from pathlib import Path
from typing import Callable

import vlc


class VLCPlayer:
    """Wrapper for VLC media player with event callbacks."""

    def __init__(self, on_end_callback: Callable[[], None] | None = None) -> None:
        """Initialize VLC player.

        Args:
            on_end_callback: Function to call when track ends.
        """
        # Use --quiet to suppress verbose VLC logging (stale cache warnings, etc.)
        self._instance = vlc.Instance("--quiet")
        self._player = self._instance.media_player_new()
        self._on_end_callback = on_end_callback
        self._current_file: Path | None = None

        # Set up end-of-media event
        event_manager = self._player.event_manager()
        event_manager.event_attach(
            vlc.EventType.MediaPlayerEndReached,
            self._handle_end_reached
        )

    def _handle_end_reached(self, event: vlc.Event) -> None:
        """Handle media end reached event.

        Args:
            event: VLC event (unused but required by callback signature).
        """
        if self._on_end_callback:
            self._on_end_callback()

    def play(self, file_path: str | Path) -> bool:
        """Play a media file.

        Args:
            file_path: Path to the media file to play.

        Returns:
            True if playback started successfully.
        """
        path = Path(file_path)
        if not path.exists():
            return False

        # Create new media and set it
        media = self._instance.media_new(str(path))
        self._player.set_media(media)
        self._current_file = path

        # Start playback
        result = self._player.play()
        return result == 0

    def stop(self) -> None:
        """Stop playback."""
        self._player.stop()
        self._current_file = None

    def pause(self) -> None:
        """Toggle pause state."""
        self._player.pause()

    def is_playing(self) -> bool:
        """Check if media is currently playing.

        Returns:
            True if media is playing.
        """
        return self._player.is_playing() == 1

    def get_current_file(self) -> Path | None:
        """Get the currently playing file.

        Returns:
            Path to current file, or None if nothing is playing.
        """
        return self._current_file

    def set_on_end_callback(self, callback: Callable[[], None] | None) -> None:
        """Set the callback for when track ends.

        Args:
            callback: Function to call when track ends.
        """
        self._on_end_callback = callback

    def get_time(self) -> int:
        """Get current playback time in milliseconds.

        Returns:
            Current time in milliseconds, or -1 if not available.
        """
        return self._player.get_time()

    def set_time(self, ms: int) -> None:
        """Set playback time in milliseconds.

        Args:
            ms: Time in milliseconds to seek to.
        """
        self._player.set_time(ms)

    def get_length(self) -> int:
        """Get total media length in milliseconds.

        Returns:
            Total length in milliseconds, or -1 if not available.
        """
        return self._player.get_length()

    def get_position(self) -> float:
        """Get playback position as a fraction.

        Returns:
            Position from 0.0 to 1.0, or -1 if not available.
        """
        return self._player.get_position()

    def get_volume(self) -> int:
        """Get current volume level.

        Returns:
            Volume level from 0 to 100.
        """
        return self._player.audio_get_volume()

    def set_volume(self, volume: int) -> None:
        """Set volume level.

        Args:
            volume: Volume level from 0 to 100.
        """
        self._player.audio_set_volume(max(0, min(100, volume)))

    def release(self) -> None:
        """Release VLC resources."""
        self._player.stop()
        self._player.release()
        self._instance.release()
