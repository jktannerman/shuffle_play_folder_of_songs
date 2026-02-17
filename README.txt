================================================================================
                         SONG FOLDER PLAYER
                    Audio/Video Playlist Manager
================================================================================

OVERVIEW
--------
A Python GUI application for managing and playing audio/video files from
folders using VLC Media Player. Built with tkinter for the interface and
python-vlc for media playback.


REQUIREMENTS
------------
- Python 3.13+
- VLC Media Player (installed on system)
- python-vlc library (pip install python-vlc)


INSTALLATION
------------
1. Ensure VLC Media Player is installed on your system
2. Install dependencies:
   py -3.13 -m pip install -r requirements.txt
3. Run the application:
   py -3.13 -m song_folder_player.main
   (Run from the parent directory of song_folder_player/)


ARCHITECTURE
------------
song_folder_player/
    __init__.py      - Package marker
    main.py          - Entry point, initializes GUI and state
    gui.py           - Tkinter GUI components and event handling
    player.py        - VLC media player wrapper
    state.py         - JSON-based state persistence
    media_utils.py   - File filtering and natural sorting
    requirements.txt - Python dependencies
    state.json       - Auto-generated state file (created on first run)


FEATURES
--------

1. FOLDER-BASED PLAYLISTS
   - Open any folder containing media files
   - Scans top-level files only (no subdirectory recursion)
   - Filters to supported media formats automatically

2. SUPPORTED MEDIA FORMATS
   Audio: .mp3, .wav, .flac, .aac, .ogg, .wma, .m4a, .opus, .aiff
   Video: .mp4, .mkv, .avi, .mov, .wmv, .flv, .webm, .m4v, .mpeg, .mpg

3. NATURAL SORTING
   Files are sorted naturally, so numbered tracks appear in correct order:
   track1.mp3, track2.mp3, track10.mp3 (not track1, track10, track2)

4. PLAYBACK MODES
   - Straight mode: Plays files in sorted order
   - Shuffle mode: Randomized playback order (per-playlist)
   - Current song stays at top of list when shuffle enabled or reshuffled
   - Reshuffle button: Generate new random order for remaining tracks
   - Loop toggle: Loop playlist or stop at end

5. PER-PLAYLIST STATE
   Each folder remembers independently:
   - Current track position
   - Playback position within track (resumes where you left off)
   - Shuffle mode on/off
   - Shuffle order (preserved across sessions)
   - Loop setting

6. RECENT FOLDERS
   - Tracks up to 10 most recently opened folders
   - Dropdown for quick access to recent folders
   - Most recent folder auto-loads on startup

7. SESSION PERSISTENCE
   State is saved automatically:
   - Every 5 seconds (playback position, volume, zoom)
   - On folder opened
   - On track changed (manual or automatic)
   - On shuffle toggled or reshuffled
   - On loop toggled
   - On application close

   State file uses atomic writes (temp file + rename) for safety.

8. AUTO-RESUME ON STARTUP
   - Loads most recent folder automatically
   - Loads current track into VLC (paused)
   - Seeks to saved playback position
   - Restores saved volume level
   - Restores saved zoom level
   - Keyboard shortcuts work immediately without clicking

9. PROGRESS BAR
   - Shows current playback position
   - Displays time as M:SS or H:MM:SS for long files
   - Click to seek to position
   - Drag to scrub through track
   - Updates every 250ms

10. VOLUME CONTROL
    - Slider with numeric display (0-100)
    - Click slider to jump to position
    - Drag slider to adjust
    - Keyboard shortcuts for quick adjustment
    - Volume level persisted across sessions

11. UI ZOOM
    - Adjustable font size for all UI elements
    - Zoom range: 50% to 200%
    - Default zoom: 120%
    - Zoom level persisted across sessions

12. SEARCH FILTER
    - Real-time filtering as you type (VLC-style)
    - Case-insensitive substring matching against filenames
    - First matching result highlighted while typing
    - Enter in search bar focuses listbox with first result ready to play
    - Escape in listbox (during search) returns to search bar for more typing
    - Escape in search bar clears search and restores previous track position
    - Clear checkbox to quickly reset the search
    - Currently playing track hidden if it doesn't match filter
    - Keyboard shortcuts (Next/Previous) operate on full playlist, ignoring filter
    - Double-click filtered results to play without clearing search

13. KEYBOARD SHORTCUTS (Global)
    Space       - Pause/unpause current track
    End         - Skip to next track
    Home        - Restart current track from beginning
    Left Arrow  - Seek backward 5 seconds
    Right Arrow - Seek forward 5 seconds
    Enter       - Play selected track (listbox) / Focus listbox (search bar)
    /           - Decrease volume by 5%
    *           - Increase volume by 5%
    Ctrl++      - Zoom in (increase UI font size)
    Ctrl+=      - Zoom in (alternative)
    Ctrl+-      - Zoom out (decrease UI font size)
    Ctrl+0      - Reset zoom to 120% (default)
    Ctrl+F      - Focus search bar (selects existing text)
    Escape      - Return to search bar (listbox during search)
                  Clear search and restore position (search bar)

14. VLC INTEGRATION
    - Media plays in separate VLC window
    - Automatic advancement to next track on completion
    - Respects loop/stop setting at playlist end
    - Quiet mode suppresses VLC plugin cache warnings

15. MULTI-INSTANCE SUPPORT
    - Multiple instances can run simultaneously without state corruption
    - First instance acquires a file lock and saves state normally
    - Subsequent instances run fully functional but in read-only mode
    - Read-only instances show a "READ-ONLY" badge in the top-right corner
    - Lock auto-releases on crash (no stale lock cleanup needed)

16. DARK MODE THEME
    - Full dark theme applied to all UI elements
    - Dark title bar on Windows 10/11 (native integration)
    - Color scheme: #1e1e1e (darkest), #2d2d2d (frames), #3c3c3c (widgets)
    - Light text (#d4d4d4) for readability
    - Styled scrollbars and sliders to match theme


GUI LAYOUT
----------
+------------------------------------------------------------------+
| [Open Folder]  Recent: [dropdown menu______v]                    |
+------------------------------------------------------------------+
| Folder: C:\path\to\current\folder                                |
+------------------------------------------------------------------+
| [x] Shuffle  [Reshuffle]  [x] Loop       [__________________] [x] |
+------------------------------------------------------------------+
|                                                                  |
|    >> track1.mp3                                                 |
|       track2.mp3                                                 |
|       track3.mp3                                                 |
|       ...                                                        |
|                                                                  |
+------------------------------------------------------------------+
| [Play] [Stop] [Previous] [Next]              Vol: [==] 75        |
+------------------------------------------------------------------+
| Now playing: track1.mp3                                          |
+------------------------------------------------------------------+
| [==========|----------------]  2:34 / 5:12                       |
+------------------------------------------------------------------+

- ">>" marker indicates currently playing track
- Selected track highlighted in listbox
- Double-click or Enter to play selected track
- Volume slider shows numeric value (0-100)


STATE FILE FORMAT (state.json)
------------------------------
{
  "recent_folders": [
    "C:\\Music\\Album1",
    "C:\\Music\\Album2"
  ],
  "playlists": {
    "C:\\Music\\Album1": {
      "current_index": 3,
      "shuffle_order": [2, 0, 4, 1, 3],
      "loop_enabled": true,
      "playback_position_ms": 45230
    },
    "C:\\Music\\Album2": {
      "current_index": 0,
      "shuffle_order": null,
      "loop_enabled": false,
      "playback_position_ms": 0
    }
  },
  "volume": 75,
  "zoom_level": 1.2
}

- shuffle_order: null = straight mode, array = shuffle mode
- current_index: position in display order (shuffle or straight)
- playback_position_ms: position within current track (milliseconds)
- volume: global volume level (0-100)
- zoom_level: UI zoom multiplier (0.5-2.0, default 1.2)


NOTES
-----
- Buttons do not take keyboard focus (Space won't accidentally press them)
- Arrow keys are global (override listbox navigation for seeking)
- VLC must be installed separately; python-vlc is just the bindings
- If VLC shows "stale plugins cache" warnings, run as Administrator:
  "C:\Program Files\VideoLAN\VLC\vlc-cache-gen.exe" "C:\Program Files\VideoLAN\VLC\plugins"


VERSION HISTORY
---------------
v1.5 - February 2026
- Multi-instance support with lockfile-based coordination
- First instance saves state normally; subsequent instances run in read-only mode
- "READ-ONLY" badge in top-right corner with hover tooltip on secondary instances
- Uses msvcrt file locking — auto-released on crash, no stale lock issues

v1.4 - January 2026
- Keyboard-only search navigation flow
- Enter in search bar focuses listbox with first result underlined
- Escape in listbox (during search) returns to search bar with text selected
- Escape in search bar clears search and restores previous track position
- Pre-search position remembered and restored on search cancel

v1.3 - January 2026
- Dark mode theme throughout the application
- Dark title bar on Windows 10/11 (uses native Windows API)
- Color scheme matches multi_file_search style (#1e1e1e backgrounds)
- Dark scrollbar and slider styling
- Search now highlights first matching result while typing
- Escape restores highlight to currently playing track
- Clear button replaced with checkbox (matches theme aesthetics)

v1.2 - January 2026
- Search filter bar (VLC-style real-time filtering)
- Case-insensitive substring matching
- Clear button to reset search
- Keyboard navigation unaffected by search filter
- Ctrl+F to focus search bar
- Escape to clear and defocus search bar

v1.1 - January 2026
- Playback position persistence (resumes where you left off per-playlist)
- Volume persistence across sessions
- Volume keyboard shortcuts (/ and * for -5%/+5%)
- Volume level numeric display next to slider
- UI zoom functionality (Ctrl++, Ctrl+-, Ctrl+0)
- Zoom level persistence across sessions
- Default zoom set to 120%
- Periodic auto-save every 5 seconds
- Shuffle keeps current song at top of list

v1.0 - January 2026 (Initial implementation)
- Core playback functionality
- Shuffle/loop modes with per-playlist state
- Persistent state across sessions
- Keyboard shortcuts
- Interactive progress bar with seeking
- Auto-resume on startup
