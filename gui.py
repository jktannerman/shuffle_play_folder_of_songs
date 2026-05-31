"""Tkinter GUI for Song Folder Player."""

import ctypes
import sys
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from .media_utils import scan_folder
from .player import VLCPlayer
from .playlist import PlaylistController
from .state import AppState

# Dark theme colors (matching multi_file_search style)
DARK_BG = "#1e1e1e"        # Main background (darkest)
DARK_BG_ALT = "#2d2d2d"    # Frames, listbox
DARK_BG_WIDGET = "#3c3c3c" # Buttons, entry fields
DARK_FG = "#d4d4d4"        # Text color
DARK_ACCENT = "#264f78"    # Selection highlight


class _ToolTip:
    """Simple hover tooltip for a tkinter widget."""

    def __init__(self, widget: tk.Widget, text: str) -> None:
        self._widget = widget
        self._text = text
        self._tip_window: tk.Toplevel | None = None
        widget.bind("<Enter>", self._show)
        widget.bind("<Leave>", self._hide)

    def _show(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if self._tip_window:
            return
        x = self._widget.winfo_rootx() + self._widget.winfo_width()
        y = self._widget.winfo_rooty() + self._widget.winfo_height() + 2
        tw = tk.Toplevel(self._widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x - 280}+{y}")
        label = tk.Label(
            tw, text=self._text, justify="left",
            background="#ffffe0", foreground="#000000",
            relief="solid", borderwidth=1, padx=4, pady=2,
        )
        label.pack()
        self._tip_window = tw

    def _hide(self, event: tk.Event) -> None:  # type: ignore[type-arg]
        if self._tip_window:
            self._tip_window.destroy()
            self._tip_window = None


def add_readonly_indicator(root: tk.Tk) -> None:
    """Add a READ-ONLY badge to the top-right corner of the window.

    Args:
        root: The root tkinter window.
    """
    badge = tk.Label(
        root,
        text=" READ-ONLY ",
        font=("Segoe UI", 8, "bold"),
        bg="#8B0000",
        fg="white",
    )
    badge.place(relx=1.0, x=-6, y=6, anchor="ne")
    badge.lift()
    _ToolTip(
        badge,
        "Another instance is already running.\n"
        "This instance will not save state changes to disk.",
    )


def _enable_dark_title_bar(window: tk.Tk) -> None:
    """Enable dark title bar on Windows 10/11.

    Args:
        window: The tkinter root window.
    """
    if sys.platform != "win32":
        return

    try:
        window.update()  # Ensure window is created
        hwnd = ctypes.windll.user32.GetParent(window.winfo_id())

        # DWMWA_USE_IMMERSIVE_DARK_MODE = 20 (Windows 10 20H1+)
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        value = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value), ctypes.sizeof(value)
        )
    except (AttributeError, OSError):
        pass  # Silently fail on older Windows versions


class SongFolderPlayerGUI:
    """Main GUI for the Song Folder Player application."""

    def __init__(
        self,
        root: tk.Tk,
        state: AppState,
        on_state_change: Callable[[], None] | None = None,
    ) -> None:
        """Initialize the GUI.

        Args:
            root: Tkinter root window.
            state: Application state.
            on_state_change: Callback when state changes (for saving).
        """
        self.root = root
        self.state = state
        self._on_state_change = on_state_change

        # Playlist controller — owns navigation logic and per-folder state.
        self._playlist = PlaylistController()

        # Current folder path (used for state lookups and label display).
        self._current_folder: str | None = None

        self._loading: bool = False  # Suppresses toggle callbacks during folder load
        self._seeking: bool = False  # Suppresses progress updates while scrubbing

        # Search filter state
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        # Maps filtered listbox pos -> original display pos
        self._filtered_indices: list[int] = []
        # When True, search results highlight first match; when False, highlight current track
        self._search_select_first: bool = False
        # Stores active item position before search began (for restore on Esc)
        self._pre_search_active_pos: int | None = None

        # Zoom level (1.0 = 100%, default 1.2 = 120%)
        self._zoom_level: float = 1.2
        self._base_font_sizes: dict[str, int] = {
            "playlist": 10,
            "ui": 9,
        }

        # ttk style for theming
        self._style = ttk.Style()
        self._apply_dark_theme()

        # VLC player - deferred until after window is drawn
        self._player: VLCPlayer | None = None

        # Build GUI
        self._setup_window()
        self._create_widgets()
        self._bind_events()

        # Apply saved volume (UI only; player initialized after window is drawn)
        self._volume_var.set(self.state.volume)
        self._volume_level_label.config(text=str(self.state.volume))

        # Apply saved zoom level
        self._zoom_level = self.state.zoom_level
        self._apply_zoom()

        # Start progress bar update loop
        self._update_progress()

        # Start periodic save timer (every 5 seconds)
        self._periodic_save()

        # Defer player creation and folder load until after window is drawn
        self.root.after(0, self._init_player)

    def _init_player(self) -> None:
        """Spawn a background thread to initialize VLC.

        VLC plugin scanning can block for several seconds on first launch.
        Running it off the main thread keeps the window responsive.
        """
        self._playlist_listbox.insert(tk.END, "  Loading player...")
        self._playlist_listbox.itemconfig(0, foreground="#666666")

        def _create() -> None:
            player = VLCPlayer(on_end_callback=self._on_track_end)
            self.root.after(0, lambda: self._finish_player_init(player))

        threading.Thread(target=_create, daemon=True).start()

    def _finish_player_init(self, player: VLCPlayer) -> None:
        """Complete player setup on the main thread once VLC is ready.

        Args:
            player: The fully initialized VLCPlayer instance.
        """
        self._player = player
        self._player.set_volume(self.state.volume)

        if self.state.recent_folders:
            self._load_folder(self.state.recent_folders[0])

    def _setup_window(self) -> None:
        """Configure the main window."""
        self.root.title("Song Folder Player")
        self.root.geometry("500x600")
        self.root.minsize(400, 400)

    def _create_widgets(self) -> None:
        """Create all GUI widgets."""
        # Main container with padding
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Top section: Open folder and recent folders
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 10))

        self._open_btn = ttk.Button(
            top_frame, text="Open Folder", command=self._open_folder_dialog,
            takefocus=False
        )
        self._open_btn.pack(side=tk.LEFT, padx=(0, 10))

        # Recent folders dropdown
        ttk.Label(top_frame, text="Recent:").pack(side=tk.LEFT, padx=(0, 5))
        self._recent_var = tk.StringVar()
        self._recent_combo = ttk.Combobox(
            top_frame,
            textvariable=self._recent_var,
            state="readonly",
            width=40,
            height=20,
        )
        self._recent_combo.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._update_recent_combo()

        # Current folder label
        self._folder_label = ttk.Label(
            main_frame, text="No folder selected", wraplength=450
        )
        self._folder_label.pack(fill=tk.X, pady=(0, 10))

        # Mode toggles frame
        mode_frame = ttk.Frame(main_frame)
        mode_frame.pack(fill=tk.X, pady=(0, 10))

        # Shuffle checkbox
        self._shuffle_var = tk.BooleanVar(value=False)
        self._shuffle_check = ttk.Checkbutton(
            mode_frame,
            text="Shuffle",
            variable=self._shuffle_var,
            command=self._on_shuffle_toggle,
            takefocus=False,
        )
        self._shuffle_check.pack(side=tk.LEFT, padx=(0, 10))

        # Reshuffle button
        self._reshuffle_btn = ttk.Button(
            mode_frame, text="Reshuffle", command=self._on_reshuffle, state=tk.DISABLED,
            takefocus=False
        )
        self._reshuffle_btn.pack(side=tk.LEFT, padx=(0, 20))

        # Loop checkbox
        self._loop_var = tk.BooleanVar(value=True)
        self._loop_check = ttk.Checkbutton(
            mode_frame,
            text="Loop Playlist",
            variable=self._loop_var,
            command=self._on_loop_toggle,
            takefocus=False,
        )
        self._loop_check.pack(side=tk.LEFT)

        # Search bar (right side of mode_frame)
        # Clear checkbox - clicking clears search and re-checks itself
        self._search_clear_var = tk.BooleanVar(value=True)
        self._search_clear_btn = ttk.Checkbutton(
            mode_frame,
            variable=self._search_clear_var,
            command=self._on_clear_checkbox,
            takefocus=False,
        )
        self._search_clear_btn.pack(side=tk.RIGHT, padx=(6, 0), pady=2)

        self._search_entry = ttk.Entry(
            mode_frame,
            textvariable=self._search_var,
            width=33,
        )
        self._search_entry.pack(side=tk.RIGHT, padx=(10, 0))

        # Playlist listbox with scrollbar
        list_frame = ttk.Frame(main_frame)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self._scrollbar = ttk.Scrollbar(list_frame)
        self._scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        self._playlist_listbox = tk.Listbox(
            list_frame,
            yscrollcommand=self._scrollbar.set,
            selectmode=tk.SINGLE,
            font=("Consolas", 10),
            bg=DARK_BG,
            fg=DARK_FG,
            selectbackground=DARK_ACCENT,
            selectforeground="white",
        )
        self._playlist_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scrollbar.config(command=self._playlist_listbox.yview)

        # Playback controls
        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X)

        self._play_btn = ttk.Button(
            control_frame, text="Play", command=self._play_selected,
            takefocus=False
        )
        self._play_btn.pack(side=tk.LEFT, padx=(0, 5))

        self._stop_btn = ttk.Button(
            control_frame, text="Stop", command=self._stop, takefocus=False
        )
        self._stop_btn.pack(side=tk.LEFT, padx=(0, 5))

        self._prev_btn = ttk.Button(
            control_frame, text="Previous", command=self._play_previous,
            takefocus=False
        )
        self._prev_btn.pack(side=tk.LEFT, padx=(0, 5))

        self._next_btn = ttk.Button(
            control_frame, text="Next", command=self._play_next, takefocus=False
        )
        self._next_btn.pack(side=tk.LEFT)

        # Volume slider (on the right)
        self._volume_var = tk.IntVar(value=100)

        # Volume level label (shows numeric value)
        self._volume_level_label = ttk.Label(
            control_frame, text="100", font=("Consolas", 9), width=3
        )
        self._volume_level_label.pack(side=tk.RIGHT)

        self._volume_slider = ttk.Scale(
            control_frame,
            variable=self._volume_var,
            from_=0,
            to=100,
            orient=tk.HORIZONTAL,
            length=100,
            command=self._on_volume_change,
            takefocus=False,
        )
        self._volume_slider.pack(side=tk.RIGHT, padx=(0, 5))
        self._volume_slider.bind("<ButtonPress-1>", self._on_volume_click)

        ttk.Label(control_frame, text="Vol:").pack(side=tk.RIGHT, padx=(10, 5))

        # Now playing label
        self._now_playing_label = ttk.Label(main_frame, text="", font=("Arial", 9))
        self._now_playing_label.pack(fill=tk.X, pady=(10, 0))

        # Progress bar frame
        progress_frame = ttk.Frame(main_frame)
        progress_frame.pack(fill=tk.X, pady=(5, 0))

        # Time label (current / total)
        self._time_label = ttk.Label(
            progress_frame, text="0:00 / 0:00", font=("Consolas", 9)
        )
        self._time_label.pack(side=tk.RIGHT, padx=(10, 0))

        # Progress bar (using Scale for click/drag seeking)
        self._progress_var = tk.DoubleVar(value=0.0)
        self._progress_bar = ttk.Scale(
            progress_frame,
            variable=self._progress_var,
            from_=0.0,
            to=1.0,
            orient=tk.HORIZONTAL,
            takefocus=False,
        )
        self._progress_bar.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # Bind mouse events for seeking
        self._progress_bar.bind("<ButtonPress-1>", self._on_seek_start)
        self._progress_bar.bind("<ButtonRelease-1>", self._on_seek_end)

    def _bind_events(self) -> None:
        """Bind event handlers."""
        self._playlist_listbox.bind("<Double-1>", lambda e: self._play_selected())
        self._playlist_listbox.bind("<Return>", lambda e: self._play_selected())
        self._recent_combo.bind("<<ComboboxSelected>>", self._on_recent_selected)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Global keyboard shortcuts
        # All handlers return "break" to prevent event propagation to listbox
        self.root.bind("<space>", self._on_space_press)
        self.root.bind("<End>", self._on_end_press)
        self.root.bind("<Home>", self._on_home_press)
        self.root.bind("<Left>", self._on_left_press)
        self.root.bind("<Right>", self._on_right_press)
        self.root.bind("/", lambda e: self._adjust_volume(-5))
        self.root.bind("*", lambda e: self._adjust_volume(5))

        # Zoom shortcuts (Ctrl++ and Ctrl+-)
        self.root.bind("<Control-plus>", lambda e: self._zoom_in())
        self.root.bind("<Control-equal>", lambda e: self._zoom_in())  # Ctrl+= (no shift)
        self.root.bind("<Control-minus>", lambda e: self._zoom_out())
        self.root.bind("<Control-0>", lambda e: self._zoom_reset())  # Reset to 120%

        # Search shortcuts
        self.root.bind("<Control-f>", self._on_ctrl_f)
        self.root.bind("<Escape>", self._on_escape)
        self._search_entry.bind("<Return>", self._on_search_enter)

    def _update_recent_combo(self) -> None:
        """Update the recent folders dropdown."""
        display_names = []
        for folder in self.state.recent_folders:
            name = Path(folder).name
            display_names.append(f"{name} - {folder}")
        self._recent_combo["values"] = display_names

        if display_names:
            self._recent_combo.current(0)
            self._recent_var.set(display_names[0])

    def _on_recent_selected(self, event: tk.Event) -> None:
        """Handle selection from recent folders dropdown."""
        selection = self._recent_combo.current()
        if 0 <= selection < len(self.state.recent_folders):
            folder = self.state.recent_folders[selection]
            self._load_folder(folder)

    def _open_folder_dialog(self) -> None:
        """Open folder selection dialog."""
        initial_dir = None
        if self._current_folder:
            initial_dir = self._current_folder
        elif self.state.recent_folders:
            initial_dir = self.state.recent_folders[0]

        folder = filedialog.askdirectory(
            title="Select Music Folder", initialdir=initial_dir
        )
        if folder:
            self._load_folder(folder)

    def _load_folder(self, folder_path: str) -> None:
        """Load a folder and its media files.

        Args:
            folder_path: Path to the folder to load.
        """
        self._loading = True
        try:
            self._current_folder = str(Path(folder_path).resolve())
            files = scan_folder(self._current_folder)

            self.state.add_recent_folder(self._current_folder)
            playlist_state = self.state.get_playlist_state(self._current_folder)
            self._playlist.load(files, playlist_state)

            self._folder_label.config(text=f"Folder: {self._current_folder}")
            self._update_recent_combo()

            # Sync UI toggles to restored state (without triggering callbacks)
            self._shuffle_var.set(self._playlist.shuffle_enabled)
            self._loop_var.set(self._playlist.loop_enabled)
            self._reshuffle_btn.config(
                state=tk.NORMAL if self._playlist.shuffle_enabled else tk.DISABLED
            )
        finally:
            self._loading = False

        self._update_playlist_display()
        self._save_state()

        if self._player is not None:
            self._player.stop()
            self._load_current_track_paused()

        self._playlist_listbox.focus_set()

    def _update_playlist_display(self) -> None:
        """Update the playlist listbox with optional search filtering."""
        self._playlist_listbox.delete(0, tk.END)
        self._filtered_indices.clear()

        files = self._playlist.files
        if not files:
            return

        search_term = self._search_var.get().lower().strip()
        display_order = self._playlist.display_order
        current_display_idx = self._playlist.current_display_index

        items: list[str] = []
        filtered_current_pos: int | None = None
        for pos, file_index in enumerate(display_order):
            if 0 <= file_index < len(files):
                file = files[file_index]

                if search_term and search_term not in file.name.lower():
                    continue

                filtered_pos = len(self._filtered_indices)
                self._filtered_indices.append(pos)

                prefix = ">> " if pos == current_display_idx else "   "
                items.append(f"{prefix}{file.name}")

                if pos == current_display_idx:
                    filtered_current_pos = filtered_pos

        if items:
            self._playlist_listbox.insert(tk.END, *items)

        # Determine active (underline) and selection (highlight) positions
        # Selection = currently playing track, Active = navigation cursor
        self._playlist_listbox.selection_clear(0, tk.END)

        if search_term and self._search_select_first and self._filtered_indices:
            active_pos = 0
            selection_pos = filtered_current_pos
        elif filtered_current_pos is not None:
            active_pos = filtered_current_pos
            selection_pos = filtered_current_pos
        elif self._filtered_indices:
            active_pos = 0
            selection_pos = 0
        else:
            active_pos = None
            selection_pos = None

        if selection_pos is not None:
            self._playlist_listbox.selection_set(selection_pos)
        if active_pos is not None:
            self._playlist_listbox.activate(active_pos)
            self._playlist_listbox.see(active_pos)
            self._playlist_listbox.xview_moveto(0)

    def _on_shuffle_toggle(self) -> None:
        """Handle shuffle checkbox toggle."""
        if self._loading or not self._playlist.is_loaded:
            return

        if self._shuffle_var.get():
            self._playlist.enable_shuffle()
            self._reshuffle_btn.config(state=tk.NORMAL)
        else:
            self._playlist.disable_shuffle()
            self._reshuffle_btn.config(state=tk.DISABLED)

        self._update_playlist_display()
        self._save_state()

    def _on_reshuffle(self) -> None:
        """Handle reshuffle button click."""
        if not self._playlist.is_loaded or not self._shuffle_var.get():
            return

        self._playlist.reshuffle()
        self._update_playlist_display()
        self._save_state()

    def _on_loop_toggle(self) -> None:
        """Handle loop checkbox toggle."""
        if self._loading:
            return
        if self._playlist.is_loaded:
            self._playlist.loop_enabled = self._loop_var.get()
            self._save_state()

    def _on_search_change(self, *args: object) -> None:
        """Handle search entry text change.

        Args:
            *args: Variable trace callback arguments (name, index, mode).
        """
        search_term = self._search_var.get().strip()

        if search_term and self._pre_search_active_pos is None:
            try:
                self._pre_search_active_pos = self._playlist_listbox.index(tk.ACTIVE)
            except tk.TclError:
                self._pre_search_active_pos = 0
        elif not search_term:
            self._pre_search_active_pos = None

        self._search_select_first = bool(search_term)
        self._update_playlist_display()

    def _clear_search(self) -> None:
        """Clear the search filter and restore current track highlight."""
        self._search_select_first = False
        self._pre_search_active_pos = None
        self._search_var.set("")

    def _on_clear_checkbox(self) -> None:
        """Handle clear checkbox click - clear search and re-check."""
        self._clear_search()
        self._search_clear_var.set(True)

    def _on_ctrl_f(self, event: tk.Event) -> str:
        """Handle Ctrl+F to focus search entry.

        Args:
            event: The key event.

        Returns:
            "break" to prevent default handling.
        """
        self._search_entry.focus_set()
        self._search_entry.select_range(0, tk.END)
        return "break"

    def _on_search_enter(self, event: tk.Event) -> str:
        """Handle Enter in search entry - focus listbox and activate first item.

        Args:
            event: The key event.

        Returns:
            "break" to prevent default handling.
        """
        if self._filtered_indices:
            self._playlist_listbox.focus_set()
            self._playlist_listbox.activate(0)
            self._playlist_listbox.see(0)
        return "break"

    def _on_escape(self, event: tk.Event) -> None:
        """Handle Escape for search navigation.

        - Search entry focused: Clear search, restore previous active position
        - Listbox focused during search: Return to search entry

        Args:
            event: The key event.
        """
        focused = self.root.focus_get()
        search_active = bool(self._search_var.get().strip())

        if focused == self._search_entry:
            saved_pos = self._pre_search_active_pos
            self._clear_search()
            if saved_pos is not None and self._filtered_indices:
                self._playlist_listbox.activate(saved_pos)
                self._playlist_listbox.see(saved_pos)
            self._playlist_listbox.focus_set()
        elif focused == self._playlist_listbox and search_active:
            self._search_entry.focus_set()
            self._search_entry.select_range(0, tk.END)

    def _set_volume(self, volume: int) -> None:
        """Apply a volume level to the player, state, and UI.

        Args:
            volume: Volume level from 0 to 100.
        """
        self._volume_var.set(volume)
        if self._player is not None:
            self._player.set_volume(volume)
        self.state.volume = volume
        self._volume_level_label.config(text=str(volume))

    def _on_volume_change(self, value: str) -> None:
        """Handle volume slider change.

        Args:
            value: New volume value as string (from Scale widget).
        """
        self._set_volume(int(float(value)))

    def _on_volume_click(self, event: tk.Event) -> None:
        """Handle click on volume slider to jump to position.

        Args:
            event: The mouse event.
        """
        widget_width = event.widget.winfo_width()
        if widget_width > 0:
            position = max(0.0, min(1.0, event.x / widget_width))
            self._set_volume(int(position * 100))

    def _adjust_volume(self, delta: int) -> None:
        """Adjust volume by a relative amount.

        Args:
            delta: Amount to adjust volume by (positive or negative).
        """
        self._set_volume(max(0, min(100, self._volume_var.get() + delta)))

    def _zoom_in(self) -> None:
        """Increase zoom level by 10%."""
        self._zoom_level = min(2.0, self._zoom_level + 0.1)
        self._apply_zoom()

    def _zoom_out(self) -> None:
        """Decrease zoom level by 10%."""
        self._zoom_level = max(0.5, self._zoom_level - 0.1)
        self._apply_zoom()

    def _zoom_reset(self) -> None:
        """Reset zoom level to 120% (default)."""
        self._zoom_level = 1.2
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        """Apply current zoom level to all fonts."""
        self.state.zoom_level = self._zoom_level

        playlist_size = int(self._base_font_sizes["playlist"] * self._zoom_level)
        ui_size = int(self._base_font_sizes["ui"] * self._zoom_level)

        self._playlist_listbox.config(font=("Consolas", playlist_size))

        self._style.configure("TButton", font=("TkDefaultFont", ui_size))
        self._style.configure("TLabel", font=("TkDefaultFont", ui_size))
        self._style.configure("TCheckbutton", font=("TkDefaultFont", ui_size))
        self._style.configure("TCombobox", font=("TkDefaultFont", ui_size))
        self._style.configure("TEntry", font=("TkDefaultFont", ui_size))

        self._volume_level_label.config(font=("Consolas", ui_size))
        self._now_playing_label.config(font=("Arial", ui_size))
        self._time_label.config(font=("Consolas", ui_size))

        self.root.option_add("*TCombobox*Listbox.font", ("TkDefaultFont", ui_size))

    def _apply_dark_theme(self) -> None:
        """Apply dark theme to all widgets."""
        self._style.theme_use("clam")

        self._style.configure(".", background=DARK_BG_ALT, foreground=DARK_FG)
        self._style.configure("TFrame", background=DARK_BG_ALT)
        self._style.configure("TLabel", background=DARK_BG_ALT, foreground=DARK_FG)
        self._style.configure(
            "TButton", background=DARK_BG_WIDGET, foreground=DARK_FG, borderwidth=1
        )
        self._style.map(
            "TButton",
            background=[("active", "#4a4a4a"), ("pressed", "#5a5a5a")],
            foreground=[("active", DARK_FG), ("pressed", DARK_FG)],
        )
        self._style.configure("TCheckbutton", background=DARK_BG_ALT, foreground=DARK_FG)
        self._style.configure(
            "TCombobox", fieldbackground=DARK_BG_WIDGET, foreground=DARK_FG,
            selectbackground=DARK_ACCENT, selectforeground="white"
        )
        self._style.map(
            "TCombobox",
            fieldbackground=[("readonly", DARK_BG_WIDGET)],
            foreground=[("readonly", DARK_FG)],
            selectbackground=[("readonly", DARK_ACCENT)],
            selectforeground=[("readonly", "white")],
        )
        self._style.configure("TEntry", fieldbackground=DARK_BG_WIDGET, foreground=DARK_FG)

        self._style.configure(
            "TScrollbar",
            background="#5a5a5a",
            troughcolor=DARK_BG_ALT,
            borderwidth=0,
            arrowcolor=DARK_FG,
        )
        self._style.map(
            "TScrollbar",
            background=[("active", "#6a6a6a"), ("pressed", "#7a7a7a")],
        )

        self._style.configure(
            "Horizontal.TScale",
            background=DARK_BG_ALT,
            troughcolor=DARK_BG,
            borderwidth=0,
            sliderthickness=14,
        )
        self._style.map(
            "Horizontal.TScale",
            background=[("active", "#6a6a6a")],
        )

        self.root.configure(bg=DARK_BG_ALT)
        _enable_dark_title_bar(self.root)

    def _play_selected(self) -> None:
        """Play the active (underlined) track in the listbox."""
        if not self._playlist.files:
            return

        try:
            filtered_pos = self._playlist_listbox.index(tk.ACTIVE)
        except tk.TclError:
            return

        if filtered_pos < len(self._filtered_indices):
            self._play_at_display_position(self._filtered_indices[filtered_pos])

    def _play_at_display_position(self, display_pos: int) -> None:
        """Play track at the given display position.

        Args:
            display_pos: Position in the displayed list.
        """
        if self._player is None or not self._playlist.is_loaded:
            return

        file_path = self._playlist.file_at(display_pos)
        if file_path is None:
            return

        self._playlist.go_to(display_pos)
        self._save_state()

        self._player.play(file_path)
        self._update_playlist_display()
        self._now_playing_label.config(text=f"Now playing: {file_path.name}")

    def _stop(self) -> None:
        """Stop playback."""
        if self._player is None:
            return
        self._player.stop()
        self._now_playing_label.config(text="")

    def _load_current_track_paused(self) -> None:
        """Load the current track into VLC but start paused.

        Used on folder load so keyboard shortcuts work immediately.
        Restores the saved playback position if available.
        """
        if self._player is None or not self._playlist.is_loaded:
            return

        file_path = self._playlist.file_at(self._playlist.current_display_index)
        if file_path is None:
            return

        # Pause fires in the MediaPlayerPlaying callback before VLC's audio
        # buffer drains to the audio device — no audible blip.
        self._player.play_paused(file_path)
        self._now_playing_label.config(text=f"Now playing: {file_path.name}")

        saved_position = self._playlist.playback_position_ms
        if saved_position > 0:
            self.root.after(200, lambda: self._player.set_time(saved_position))

    def _play_next(self) -> None:
        """Play the next track."""
        if not self._playlist.is_loaded:
            return

        next_pos = self._playlist.advance()
        if next_pos is None:
            self._stop()
        else:
            self._play_at_display_position(next_pos)

    def _play_previous(self) -> None:
        """Play the previous track."""
        if not self._playlist.is_loaded:
            return

        self._play_at_display_position(self._playlist.retreat())

    def _on_track_end(self) -> None:
        """Handle track end event from VLC.

        Note: This is called from a VLC thread, so we schedule on main thread.
        """
        self.root.after(0, self._play_next)

    def _on_space_press(self, event: tk.Event) -> str | None:
        """Handle space key press globally.

        Args:
            event: The key event.

        Returns:
            "break" to prevent event propagation, or None to allow normal handling.
        """
        if self.root.focus_get() == self._search_entry:
            return None
        self._toggle_pause()
        return "break"

    def _on_end_press(self, event: tk.Event) -> str:
        """Handle End key press to skip to next track.

        Args:
            event: The key event.

        Returns:
            "break" to prevent event propagation to listbox.
        """
        self._play_next()
        return "break"

    def _on_home_press(self, event: tk.Event) -> str:
        """Handle Home key press to restart current track.

        Args:
            event: The key event.

        Returns:
            "break" to prevent event propagation to listbox.
        """
        self._restart_current()
        return "break"

    def _on_left_press(self, event: tk.Event) -> str:
        """Handle Left arrow key press to seek backward.

        Args:
            event: The key event.

        Returns:
            "break" to prevent event propagation to listbox.
        """
        self._seek_relative(-5)
        return "break"

    def _on_right_press(self, event: tk.Event) -> str:
        """Handle Right arrow key press to seek forward.

        Args:
            event: The key event.

        Returns:
            "break" to prevent event propagation to listbox.
        """
        self._seek_relative(5)
        return "break"

    def _toggle_pause(self) -> None:
        """Toggle pause/play state."""
        if self._player is None:
            return
        if self._player.get_current_file():
            self._player.pause()

    def _restart_current(self) -> None:
        """Restart the current track from the beginning."""
        if self._player is None:
            return
        if self._player.get_current_file():
            self._player.set_time(0)

    def _seek_relative(self, seconds: int) -> None:
        """Seek forward or backward by a number of seconds.

        Args:
            seconds: Number of seconds to seek (negative for backward).
        """
        if self._player is None or not self._player.get_current_file():
            return

        current_ms = self._player.get_time()
        length_ms = self._player.get_length()

        if current_ms < 0 or length_ms < 0:
            return

        new_ms = current_ms + (seconds * 1000)
        new_ms = max(0, min(new_ms, length_ms))
        self._player.set_time(new_ms)

    def _on_seek_start(self, event: tk.Event) -> None:
        """Handle mouse press on progress bar to start seeking.

        Args:
            event: The mouse event.
        """
        self._seeking = True

    def _on_seek_end(self, event: tk.Event) -> None:
        """Handle mouse release on progress bar to complete seeking.

        Args:
            event: The mouse event.
        """
        if self._player is None or not self._player.get_current_file():
            self._seeking = False
            return

        length_ms = self._player.get_length()
        if length_ms > 0:
            # Calculate position directly from click coordinates
            # (the Scale variable may not be updated yet for clicks)
            widget_width = event.widget.winfo_width()
            if widget_width > 0:
                position = max(0.0, min(1.0, event.x / widget_width))
                # Clamp to slightly below 1.0 to avoid triggering end-of-track
                position = min(position, 0.999)
                new_ms = int(position * length_ms)
                self._player.set_time(new_ms)
                self._progress_var.set(position)

        self._seeking = False

    def _format_time(self, ms: int) -> str:
        """Format milliseconds as a time string.

        Args:
            ms: Time in milliseconds.

        Returns:
            Formatted string like "M:SS", "MM:SS", or "H:MM:SS" for long files.
        """
        if ms < 0:
            return "0:00"

        total_seconds = ms // 1000
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60

        if hours > 0:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        else:
            return f"{minutes}:{seconds:02d}"

    def _update_progress(self) -> None:
        """Update the progress bar and time label."""
        if self._player and self._player.get_current_file():
            current_ms = self._player.get_time()
            length_ms = self._player.get_length()

            if current_ms >= 0 and length_ms > 0:
                if not self._seeking:
                    position = current_ms / length_ms
                    self._progress_var.set(position)
                current_str = self._format_time(current_ms)
                total_str = self._format_time(length_ms)
                self._time_label.config(text=f"{current_str} / {total_str}")
            else:
                if not self._seeking:
                    self._progress_var.set(0.0)
                self._time_label.config(text="0:00 / 0:00")
        else:
            if not self._seeking:
                self._progress_var.set(0.0)
            self._time_label.config(text="0:00 / 0:00")

        self.root.after(250, self._update_progress)

    def _save_state(self) -> None:
        """Save current state to disk."""
        self._playlist.sync_to_state()
        if self._on_state_change:
            self._on_state_change()

    def _periodic_save(self) -> None:
        """Periodically save playback position and volume to state."""
        if self._player and self._playlist.is_loaded and self._player.get_current_file():
            current_ms = self._player.get_time()
            if current_ms >= 0:
                self._playlist.playback_position_ms = current_ms

        self._save_state()
        self.root.after(5000, self._periodic_save)

    def _on_close(self) -> None:
        """Handle window close event."""
        if self._player:
            if self._playlist.is_loaded and self._player.get_current_file():
                current_ms = self._player.get_time()
                if current_ms >= 0:
                    self._playlist.playback_position_ms = current_ms
            self._player.release()
        self._save_state()
        self.root.destroy()

    def run(self) -> None:
        """Start the main event loop."""
        self.root.mainloop()
