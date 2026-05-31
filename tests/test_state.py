"""Tests for state: data classes, serialization, and persistence."""

import json
from pathlib import Path

import pytest

from song_folder_player.state import AppState, PlaylistState, load_state, save_state


class TestPlaylistState:
    def test_roundtrip(self) -> None:
        original = PlaylistState(
            current_filename="track3.mp3",
            shuffle_order=["track3.mp3", "track1.mp3", "track2.mp3"],
            loop_enabled=False,
            playback_position_ms=12345,
        )
        restored = PlaylistState.from_dict(original.to_dict())
        assert restored.current_filename == original.current_filename
        assert restored.shuffle_order == original.shuffle_order
        assert restored.loop_enabled == original.loop_enabled
        assert restored.playback_position_ms == original.playback_position_ms

    def test_straight_mode_roundtrip(self) -> None:
        original = PlaylistState(current_filename="a.mp3", shuffle_order=None)
        assert PlaylistState.from_dict(original.to_dict()).shuffle_order is None

    def test_back_compat_integer_shuffle_discarded(self) -> None:
        """Old format stored integer indices — they must be silently discarded."""
        data = {
            "current_filename": "track1.mp3",
            "shuffle_order": [2, 0, 1],
            "loop_enabled": True,
            "playback_position_ms": 0,
        }
        state = PlaylistState.from_dict(data)
        assert state.shuffle_order is None

    def test_defaults_on_missing_keys(self) -> None:
        state = PlaylistState.from_dict({})
        assert state.current_filename == ""
        assert state.shuffle_order is None
        assert state.loop_enabled is True
        assert state.playback_position_ms == 0


class TestAppState:
    def test_roundtrip(self) -> None:
        state = AppState(
            recent_folders=["C:\\Music\\A", "C:\\Music\\B"],
            playlists={
                "C:\\Music\\A": PlaylistState(
                    current_filename="song.mp3",
                    shuffle_order=None,
                    loop_enabled=True,
                    playback_position_ms=500,
                )
            },
            volume=80,
            zoom_level=1.5,
        )
        restored = AppState.from_dict(state.to_dict())
        assert restored.recent_folders == state.recent_folders
        assert restored.volume == 80
        assert restored.zoom_level == 1.5
        assert restored.playlists["C:\\Music\\A"].current_filename == "song.mp3"

    def test_add_recent_folder_prepends(self) -> None:
        state = AppState(recent_folders=["C:\\B"])
        state.add_recent_folder("C:\\A")
        assert state.recent_folders[0] == str(Path("C:\\A").resolve())

    def test_add_recent_folder_deduplicates(self) -> None:
        folder = str(Path("C:\\Music").resolve())
        state = AppState(recent_folders=[folder, "C:\\Other"])
        state.add_recent_folder(folder)
        assert state.recent_folders.count(folder) == 1
        assert state.recent_folders[0] == folder

    def test_add_recent_folder_trims_to_max(self) -> None:
        state = AppState(recent_folders=[f"C:\\folder{i}" for i in range(20)])
        state.add_recent_folder("C:\\new_folder")
        assert len(state.recent_folders) == 20

    def test_get_playlist_state_creates_new(self) -> None:
        state = AppState()
        ps = state.get_playlist_state("C:\\Music")
        assert isinstance(ps, PlaylistState)

    def test_get_playlist_state_returns_existing(self) -> None:
        state = AppState()
        ps1 = state.get_playlist_state("C:\\Music")
        ps1.current_filename = "track.mp3"
        ps2 = state.get_playlist_state("C:\\Music")
        assert ps2.current_filename == "track.mp3"


class TestLoadSaveState:
    def test_save_and_load_roundtrip(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import song_folder_player.state as state_module
        monkeypatch.setattr(state_module, "STATE_FILE", tmp_path / "state.json")

        original = AppState(volume=42, zoom_level=1.1)
        original.add_recent_folder("C:\\Music")
        save_state(original)

        restored = load_state()
        assert restored.volume == 42
        assert restored.zoom_level == 1.1

    def test_load_missing_file_returns_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import song_folder_player.state as state_module
        monkeypatch.setattr(state_module, "STATE_FILE", tmp_path / "nonexistent.json")

        state = load_state()
        assert isinstance(state, AppState)
        assert state.volume == 100

    def test_load_corrupt_file_returns_defaults(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import song_folder_player.state as state_module
        corrupt = tmp_path / "state.json"
        corrupt.write_text("not valid json", encoding="utf-8")
        monkeypatch.setattr(state_module, "STATE_FILE", corrupt)

        state = load_state()
        assert isinstance(state, AppState)
