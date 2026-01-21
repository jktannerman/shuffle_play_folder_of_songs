"""Tkinter GUI for Song Folder Player."""

import random
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk
from typing import Callable

from .media_utils import scan_folder
from .player import VLCPlayer
from .state import AppState, PlaylistState, save_state


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

        # Current folder and files
        self._current_folder: str | None = None
        self._media_files: list[Path] = []
        self._playlist_state: PlaylistState | None = None
        self._loading: bool = False  # Flag to prevent callbacks during load
        self._seeking: bool = False  # Flag to prevent progress updates while seeking

        # Search filter state
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", self._on_search_change)
        # Maps filtered listbox pos -> (original_display_pos, file_index)
        self._filtered_indices: list[tuple[int, int]] = []

        # Zoom level (1.0 = 100%)
        self._zoom_level: float = 1.0
        self._base_font_sizes: dict[str, int] = {
            "playlist": 10,
            "ui": 9,
        }

        # ttk style for theming
        self._style = ttk.Style()

        # VLC player with end callback
        self._player = VLCPlayer(on_end_callback=self._on_track_end)

        # Build GUI
        self._setup_window()
        self._create_widgets()
        self._bind_events()

        # Apply saved volume
        self._volume_var.set(self.state.volume)
        self._player.set_volume(self.state.volume)
        self._volume_level_label.config(text=str(self.state.volume))

        # Apply saved zoom level
        self._zoom_level = self.state.zoom_level
        self._apply_zoom()

        # Start progress bar update loop
        self._update_progress()

        # Start periodic save timer (every 5 seconds)
        self._start_periodic_save()

        # Load last folder if available
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
        # Use a Canvas to draw a perfectly centered X
        self._search_clear_btn = tk.Canvas(
            mode_frame,
            width=16,
            height=16,
            cursor="hand2",
            relief="raised",
            borderwidth=1,
            highlightthickness=0,
        )
        self._search_clear_btn.pack(side=tk.RIGHT, padx=(6, 0), pady=2)
        self._search_clear_btn.bind("<Button-1>", lambda e: self._clear_search())
        self._draw_clear_x()

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
        self.root.bind("<Control-0>", lambda e: self._zoom_reset())  # Reset to 100%

        # Search shortcuts
        self.root.bind("<Control-f>", self._on_ctrl_f)
        self.root.bind("<Escape>", self._on_escape)

    def _update_recent_combo(self) -> None:
        """Update the recent folders dropdown."""
        display_names = []
        for folder in self.state.recent_folders:
            # Show just the folder name with full path as tooltip-like display
            name = Path(folder).name
            display_names.append(f"{name} - {folder}")
        self._recent_combo["values"] = display_names

        if display_names:
            self._recent_combo.current(0)

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
        # Set loading flag to prevent toggle callbacks from firing
        self._loading = True

        # Scan for media files
        self._media_files = scan_folder(folder_path)
        self._current_folder = str(Path(folder_path).resolve())

        # Update state
        self.state.add_recent_folder(self._current_folder)
        self._playlist_state = self.state.get_playlist_state(self._current_folder)

        # Update UI
        self._folder_label.config(text=f"Folder: {self._current_folder}")
        self._update_recent_combo()

        # Load playlist state into UI (without triggering callbacks)
        self._shuffle_var.set(self._playlist_state.shuffle_order is not None)
        self._loop_var.set(self._playlist_state.loop_enabled)
        self._reshuffle_btn.config(
            state=tk.NORMAL if self._playlist_state.shuffle_order else tk.DISABLED
        )

        # Clear loading flag
        self._loading = False

        # Validate shuffle order
        if self._playlist_state.shuffle_order is not None:
            if len(self._playlist_state.shuffle_order) != len(self._media_files):
                # Regenerate shuffle order if file count changed
                self._generate_shuffle_order()

        # Validate current index
        max_index = len(self._media_files) - 1
        if self._playlist_state.current_index > max_index:
            self._playlist_state.current_index = 0

        # Update playlist display
        self._update_playlist_display()
        self._save_state()

        # Stop old playback and load new playlist's current track (paused)
        self._player.stop()
        self._load_current_track_paused()

    def _update_playlist_display(self) -> None:
        """Update the playlist listbox with optional search filtering."""
        self._playlist_listbox.delete(0, tk.END)
        self._filtered_indices.clear()

        if not self._media_files:
            return

        # Get search term (case-insensitive)
        search_term = self._search_var.get().lower().strip()

        # Determine display order
        if self._playlist_state and self._playlist_state.shuffle_order:
            display_order = self._playlist_state.shuffle_order
        else:
            display_order = list(range(len(self._media_files)))

        # Get current display index for marking
        current_display_idx = self._get_current_display_index()

        # Add files to listbox (filtered by search term)
        filtered_current_pos: int | None = None
        for pos, file_index in enumerate(display_order):
            if 0 <= file_index < len(self._media_files):
                file = self._media_files[file_index]

                # Apply search filter
                if search_term and search_term not in file.name.lower():
                    continue

                # Track position in filtered list: (original_display_pos, file_index)
                filtered_pos = len(self._filtered_indices)
                self._filtered_indices.append((pos, file_index))

                # Show marker only if this is current track and it passes filter
                prefix = ">> " if pos == current_display_idx else "   "
                self._playlist_listbox.insert(tk.END, f"{prefix}{file.name}")

                # Track filtered position of current track
                if pos == current_display_idx:
                    filtered_current_pos = filtered_pos

        # Highlight current track in filtered list (if visible)
        if filtered_current_pos is not None:
            self._playlist_listbox.selection_clear(0, tk.END)
            self._playlist_listbox.selection_set(filtered_current_pos)
            self._playlist_listbox.see(filtered_current_pos)
            # Always reset horizontal scroll to leftmost position
            self._playlist_listbox.xview_moveto(0)

    def _get_current_display_index(self) -> int | None:
        """Get the current track's index in the display order.

        Returns:
            Display index of current track, or None if no track.
        """
        if not self._playlist_state:
            return None

        if self._playlist_state.shuffle_order:
            # In shuffle mode, current_index is the position in shuffle_order
            return self._playlist_state.current_index
        else:
            # In straight mode, current_index is the actual file index
            return self._playlist_state.current_index

    def _get_file_index_for_display_position(self, display_pos: int) -> int:
        """Get the actual file index for a display position.

        Args:
            display_pos: Position in the displayed list.

        Returns:
            Index in self._media_files.
        """
        if self._playlist_state and self._playlist_state.shuffle_order:
            return self._playlist_state.shuffle_order[display_pos]
        return display_pos

    def _generate_shuffle_order(self) -> None:
        """Generate a new shuffle order with current song at top."""
        if not self._playlist_state or not self._media_files:
            return

        # Determine current file index
        if self._playlist_state.shuffle_order:
            # Already in shuffle mode - get file index from shuffle order
            current_idx = self._playlist_state.current_index
            if 0 <= current_idx < len(self._playlist_state.shuffle_order):
                current_file_index = self._playlist_state.shuffle_order[current_idx]
            else:
                current_file_index = 0
        else:
            # In straight mode - current_index is the file index
            current_file_index = self._playlist_state.current_index

        # Clamp to valid range
        if current_file_index < 0 or current_file_index >= len(self._media_files):
            current_file_index = 0

        # Shuffle all other indices
        other_indices = [i for i in range(len(self._media_files)) if i != current_file_index]
        random.shuffle(other_indices)

        # Put current song at top, others below
        self._playlist_state.shuffle_order = [current_file_index] + other_indices
        self._playlist_state.current_index = 0

    def _on_shuffle_toggle(self) -> None:
        """Handle shuffle checkbox toggle."""
        if self._loading or not self._playlist_state:
            return

        if self._shuffle_var.get():
            # Enable shuffle
            self._generate_shuffle_order()
            self._reshuffle_btn.config(state=tk.NORMAL)
        else:
            # Disable shuffle - find current track's real index
            if self._playlist_state.shuffle_order and self._media_files:
                current_display_idx = self._playlist_state.current_index
                if 0 <= current_display_idx < len(self._playlist_state.shuffle_order):
                    real_index = self._playlist_state.shuffle_order[current_display_idx]
                    self._playlist_state.current_index = real_index

            self._playlist_state.shuffle_order = None
            self._reshuffle_btn.config(state=tk.DISABLED)

        self._update_playlist_display()
        self._save_state()

    def _on_reshuffle(self) -> None:
        """Handle reshuffle button click."""
        if not self._playlist_state or not self._shuffle_var.get():
            return

        self._generate_shuffle_order()
        self._update_playlist_display()
        self._save_state()

    def _on_loop_toggle(self) -> None:
        """Handle loop checkbox toggle."""
        if self._loading:
            return
        if self._playlist_state:
            self._playlist_state.loop_enabled = self._loop_var.get()
            self._save_state()

    def _on_search_change(self, *args: object) -> None:
        """Handle search entry text change.

        Args:
            *args: Variable trace callback arguments (name, index, mode).
        """
        self._update_playlist_display()

    def _clear_search(self) -> None:
        """Clear the search filter."""
        self._search_var.set("")
        # Return focus to root so keyboard shortcuts work
        self.root.focus_set()

    def _draw_clear_x(self) -> None:
        """Draw the X on the clear button canvas."""
        canvas = self._search_clear_btn
        canvas.delete("all")
        # Get canvas dimensions (accounting for border)
        w = canvas.winfo_width()
        h = canvas.winfo_height()
        if w <= 1:  # Not yet rendered, use configured size
            w = int(canvas.cget("width"))
            h = int(canvas.cget("height"))
        # Draw X with padding from edges
        pad = max(3, int(min(w, h) * 0.25))
        canvas.create_line(pad, pad, w - pad, h - pad, width=1, fill="black")
        canvas.create_line(w - pad, pad, pad, h - pad, width=1, fill="black")

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

    def _on_escape(self, event: tk.Event) -> None:
        """Handle Escape to clear and defocus search.

        Args:
            event: The key event.
        """
        if self.root.focus_get() == self._search_entry:
            self._clear_search()

    def _on_volume_change(self, value: str) -> None:
        """Handle volume slider change.

        Args:
            value: New volume value as string (from Scale widget).
        """
        volume = int(float(value))
        self._player.set_volume(volume)
        self.state.volume = volume
        self._volume_level_label.config(text=str(volume))

    def _on_volume_click(self, event: tk.Event) -> None:
        """Handle click on volume slider to jump to position.

        Args:
            event: The mouse event.
        """
        widget_width = event.widget.winfo_width()
        if widget_width > 0:
            position = max(0.0, min(1.0, event.x / widget_width))
            volume = int(position * 100)
            self._volume_var.set(volume)
            self._player.set_volume(volume)
            self.state.volume = volume
            self._volume_level_label.config(text=str(volume))

    def _adjust_volume(self, delta: int) -> None:
        """Adjust volume by a relative amount.

        Args:
            delta: Amount to adjust volume by (positive or negative).
        """
        current = self._volume_var.get()
        new_volume = max(0, min(100, current + delta))
        self._volume_var.set(new_volume)
        self._player.set_volume(new_volume)
        self.state.volume = new_volume
        self._volume_level_label.config(text=str(new_volume))

    def _zoom_in(self) -> None:
        """Increase zoom level by 10%."""
        self._zoom_level = min(2.0, self._zoom_level + 0.1)
        self._apply_zoom()

    def _zoom_out(self) -> None:
        """Decrease zoom level by 10%."""
        self._zoom_level = max(0.5, self._zoom_level - 0.1)
        self._apply_zoom()

    def _zoom_reset(self) -> None:
        """Reset zoom level to 100%."""
        self._zoom_level = 1.0
        self._apply_zoom()

    def _apply_zoom(self) -> None:
        """Apply current zoom level to all fonts."""
        # Save to state
        self.state.zoom_level = self._zoom_level

        playlist_size = int(self._base_font_sizes["playlist"] * self._zoom_level)
        ui_size = int(self._base_font_sizes["ui"] * self._zoom_level)

        # Update playlist listbox font (tk widget)
        self._playlist_listbox.config(font=("Consolas", playlist_size))

        # Update ttk widget fonts via styles
        self._style.configure("TButton", font=("TkDefaultFont", ui_size))
        self._style.configure("TLabel", font=("TkDefaultFont", ui_size))
        self._style.configure("TCheckbutton", font=("TkDefaultFont", ui_size))
        self._style.configure("TCombobox", font=("TkDefaultFont", ui_size))
        self._style.configure("TEntry", font=("TkDefaultFont", ui_size))

        # Update search clear button (always square, matches search entry height)
        self.root.update_idletasks()  # Ensure entry has updated dimensions
        entry_height = self._search_entry.winfo_reqheight()
        clear_btn_size = max(14, entry_height - 4)  # Slightly smaller than entry
        self._search_clear_btn.config(width=clear_btn_size, height=clear_btn_size)
        self._draw_clear_x()

        # Update specific label fonts (these override the style)
        self._volume_level_label.config(font=("Consolas", ui_size))
        self._now_playing_label.config(font=("Arial", ui_size))
        self._time_label.config(font=("Consolas", ui_size))

        # Update combobox dropdown font
        self.root.option_add("*TCombobox*Listbox.font", ("TkDefaultFont", ui_size))

    def _play_selected(self) -> None:
        """Play the selected track in the listbox."""
        selection = self._playlist_listbox.curselection()
        if not selection or not self._media_files:
            return

        filtered_pos = selection[0]

        # Map filtered listbox position to original display position
        if filtered_pos < len(self._filtered_indices):
            original_display_pos, _ = self._filtered_indices[filtered_pos]
            self._play_at_display_position(original_display_pos)

    def _play_at_display_position(self, display_pos: int) -> None:
        """Play track at the given display position.

        Args:
            display_pos: Position in the displayed list.
        """
        if not self._media_files or not self._playlist_state:
            return

        if display_pos < 0 or display_pos >= len(self._media_files):
            return

        file_index = self._get_file_index_for_display_position(display_pos)
        file_path = self._media_files[file_index]

        # Update state (reset position since we're starting fresh)
        self._playlist_state.current_index = display_pos
        self._playlist_state.playback_position_ms = 0
        self._save_state()

        # Play the file
        self._player.play(file_path)
        self._update_playlist_display()
        self._now_playing_label.config(text=f"Now playing: {file_path.name}")

    def _stop(self) -> None:
        """Stop playback."""
        self._player.stop()
        self._now_playing_label.config(text="")

    def _load_current_track_paused(self) -> None:
        """Load the current track into VLC but start paused.

        This is used on startup so keyboard shortcuts work immediately.
        Restores the saved playback position if available.
        """
        if not self._media_files or not self._playlist_state:
            return

        current_pos = self._playlist_state.current_index
        if current_pos < 0 or current_pos >= len(self._media_files):
            return

        file_index = self._get_file_index_for_display_position(current_pos)
        file_path = self._media_files[file_index]

        # Play the file, then pause after a short delay
        self._player.play(file_path)
        self._now_playing_label.config(text=f"Now playing: {file_path.name}")

        # Schedule pause after VLC has started (needs small delay)
        self.root.after(100, self._player.pause)

        # Seek to saved position after VLC has loaded (needs more delay)
        saved_position = self._playlist_state.playback_position_ms
        if saved_position > 0:
            self.root.after(200, lambda: self._player.set_time(saved_position))

    def _play_next(self) -> None:
        """Play the next track."""
        if not self._playlist_state or not self._media_files:
            return

        current = self._playlist_state.current_index
        next_pos = current + 1

        if next_pos >= len(self._media_files):
            if self._playlist_state.loop_enabled:
                next_pos = 0
            else:
                self._stop()
                return

        self._play_at_display_position(next_pos)

    def _play_previous(self) -> None:
        """Play the previous track."""
        if not self._playlist_state or not self._media_files:
            return

        current = self._playlist_state.current_index
        prev_pos = current - 1

        if prev_pos < 0:
            if self._playlist_state.loop_enabled:
                prev_pos = len(self._media_files) - 1
            else:
                prev_pos = 0

        self._play_at_display_position(prev_pos)

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
        # Allow typing in search entry
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
        if self._player.get_current_file():
            self._player.pause()

    def _restart_current(self) -> None:
        """Restart the current track from the beginning."""
        if self._player.get_current_file():
            self._player.set_time(0)

    def _seek_relative(self, seconds: int) -> None:
        """Seek forward or backward by a number of seconds.

        Args:
            seconds: Number of seconds to seek (negative for backward).
        """
        if not self._player.get_current_file():
            return

        current_ms = self._player.get_time()
        length_ms = self._player.get_length()

        if current_ms < 0 or length_ms < 0:
            return

        new_ms = current_ms + (seconds * 1000)
        # Clamp to valid range
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
        if not self._player.get_current_file():
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
                # Update the variable to match
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
        if self._player.get_current_file():
            current_ms = self._player.get_time()
            length_ms = self._player.get_length()

            if current_ms >= 0 and length_ms > 0:
                # Update progress bar (skip if user is seeking)
                if not self._seeking:
                    position = current_ms / length_ms
                    self._progress_var.set(position)

                # Update time label
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

        # Schedule next update
        self.root.after(250, self._update_progress)

    def _save_state(self) -> None:
        """Save current state to disk."""
        if self._on_state_change:
            self._on_state_change()
        else:
            save_state(self.state)

    def _start_periodic_save(self) -> None:
        """Start the periodic save timer."""
        self._periodic_save()

    def _periodic_save(self) -> None:
        """Periodically save playback position and volume to state."""
        # Update playback position from player
        if self._playlist_state and self._player.get_current_file():
            current_ms = self._player.get_time()
            if current_ms >= 0:
                self._playlist_state.playback_position_ms = current_ms

        # Save state to disk
        self._save_state()

        # Schedule next save (every 5 seconds)
        self.root.after(5000, self._periodic_save)

    def _on_close(self) -> None:
        """Handle window close event."""
        self._player.release()
        self._save_state()
        self.root.destroy()

    def run(self) -> None:
        """Start the main event loop."""
        self.root.mainloop()
