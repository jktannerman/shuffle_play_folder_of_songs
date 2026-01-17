"""Media file utilities for scanning and filtering files."""

import re
from pathlib import Path


# Supported audio extensions
AUDIO_EXTENSIONS: set[str] = {
    ".mp3", ".wav", ".flac", ".aac", ".ogg", ".wma", ".m4a", ".opus", ".aiff"
}

# Supported video extensions
VIDEO_EXTENSIONS: set[str] = {
    ".mp4", ".mkv", ".avi", ".mov", ".wmv", ".flv", ".webm", ".m4v", ".mpeg", ".mpg"
}

# All supported media extensions
MEDIA_EXTENSIONS: set[str] = AUDIO_EXTENSIONS | VIDEO_EXTENSIONS


def is_media_file(path: Path) -> bool:
    """Check if a file is a supported media file.

    Args:
        path: Path to the file to check.

    Returns:
        True if the file has a supported media extension.
    """
    return path.suffix.lower() in MEDIA_EXTENSIONS


def natural_sort_key(path: Path) -> list[int | str]:
    """Generate a sort key for natural sorting of filenames.

    This handles numbered files correctly, e.g., "track2.mp3" comes before "track10.mp3".

    Args:
        path: Path to generate sort key for.

    Returns:
        List of alternating strings and integers for proper sorting.
    """
    text = path.name.lower()
    parts: list[int | str] = []
    for segment in re.split(r'(\d+)', text):
        if segment.isdigit():
            parts.append(int(segment))
        else:
            parts.append(segment)
    return parts


def scan_folder(folder_path: str | Path) -> list[Path]:
    """Scan a folder for media files (top-level only).

    Args:
        folder_path: Path to the folder to scan.

    Returns:
        List of Path objects for media files, sorted naturally.
    """
    folder = Path(folder_path)
    if not folder.is_dir():
        return []

    media_files: list[Path] = []
    for item in folder.iterdir():
        if item.is_file() and is_media_file(item):
            media_files.append(item)

    # Sort files using natural sort
    media_files.sort(key=natural_sort_key)
    return media_files
