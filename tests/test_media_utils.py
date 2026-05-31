"""Tests for media_utils: file filtering and natural sort."""

from pathlib import Path

import pytest

from song_folder_player.media_utils import (
    MEDIA_EXTENSIONS,
    is_media_file,
    natural_sort_key,
    scan_folder,
)


class TestIsMediaFile:
    def test_audio_extensions(self) -> None:
        for ext in (".mp3", ".flac", ".wav", ".ogg", ".m4a", ".opus"):
            assert is_media_file(Path(f"file{ext}")), ext

    def test_video_extensions(self) -> None:
        for ext in (".mp4", ".mkv", ".avi", ".mov", ".webm"):
            assert is_media_file(Path(f"file{ext}")), ext

    def test_unsupported_extensions(self) -> None:
        for ext in (".txt", ".jpg", ".pdf", ".py", ""):
            assert not is_media_file(Path(f"file{ext}")), ext

    def test_case_insensitive(self) -> None:
        assert is_media_file(Path("file.MP3"))
        assert is_media_file(Path("file.FLAC"))
        assert is_media_file(Path("file.MkV"))


class TestNaturalSortKey:
    def test_numeric_ordering(self) -> None:
        files = [Path("track10.mp3"), Path("track2.mp3"), Path("track1.mp3")]
        files.sort(key=natural_sort_key)
        assert [f.name for f in files] == ["track1.mp3", "track2.mp3", "track10.mp3"]

    def test_purely_alphabetic(self) -> None:
        files = [Path("charlie.mp3"), Path("alpha.mp3"), Path("bravo.mp3")]
        files.sort(key=natural_sort_key)
        assert [f.name for f in files] == ["alpha.mp3", "bravo.mp3", "charlie.mp3"]

    def test_mixed_numeric_and_text(self) -> None:
        files = [Path("b1.mp3"), Path("a2.mp3"), Path("a10.mp3"), Path("a1.mp3")]
        files.sort(key=natural_sort_key)
        assert [f.name for f in files] == ["a1.mp3", "a2.mp3", "a10.mp3", "b1.mp3"]

    def test_case_insensitive_sort(self) -> None:
        files = [Path("B.mp3"), Path("a.mp3")]
        files.sort(key=natural_sort_key)
        assert files[0].name == "a.mp3"


class TestScanFolder:
    def test_returns_media_files_sorted(self, tmp_path: Path) -> None:
        for name in ("track10.mp3", "track2.mp3", "track1.mp3"):
            (tmp_path / name).touch()
        result = scan_folder(tmp_path)
        assert [f.name for f in result] == ["track1.mp3", "track2.mp3", "track10.mp3"]

    def test_ignores_non_media_files(self, tmp_path: Path) -> None:
        (tmp_path / "song.mp3").touch()
        (tmp_path / "cover.jpg").touch()
        (tmp_path / "notes.txt").touch()
        result = scan_folder(tmp_path)
        assert [f.name for f in result] == ["song.mp3"]

    def test_ignores_subdirectories(self, tmp_path: Path) -> None:
        (tmp_path / "song.mp3").touch()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        (subdir / "hidden.mp3").touch()
        result = scan_folder(tmp_path)
        assert [f.name for f in result] == ["song.mp3"]

    def test_empty_folder(self, tmp_path: Path) -> None:
        assert scan_folder(tmp_path) == []

    def test_nonexistent_folder(self, tmp_path: Path) -> None:
        assert scan_folder(tmp_path / "does_not_exist") == []
