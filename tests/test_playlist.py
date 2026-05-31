"""Tests for PlaylistController: navigation, shuffle, and reconciliation."""

from pathlib import Path

import pytest

from song_folder_player.playlist import PlaylistController
from song_folder_player.state import PlaylistState


def files(*names: str) -> list[Path]:
    """Build a list of Path objects from bare filenames."""
    return [Path(n) for n in names]


def straight_state(current: str = "", loop: bool = True) -> PlaylistState:
    return PlaylistState(current_filename=current, shuffle_order=None, loop_enabled=loop)


def shuffle_state(current: str, order: list[str], loop: bool = True) -> PlaylistState:
    return PlaylistState(current_filename=current, shuffle_order=order, loop_enabled=loop)


# ------------------------------------------------------------------ #
# Loading                                                              #
# ------------------------------------------------------------------ #

class TestLoad:
    def test_empty_folder(self) -> None:
        # is_loaded returns True after any load() call (means "folder attempted", not "has files")
        ctrl = PlaylistController()
        ctrl.load([], straight_state())
        assert ctrl.is_loaded
        assert ctrl.files == []

    def test_is_loaded_after_nonempty_load(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3"), straight_state("a.mp3"))
        assert ctrl.is_loaded

    def test_straight_mode_current_index(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), straight_state("b.mp3"))
        assert ctrl.current_display_index == 1

    def test_missing_current_file_resets_to_first(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3"), straight_state("deleted.mp3"))
        assert ctrl.current_display_index == 0


# ------------------------------------------------------------------ #
# Navigation — straight mode                                           #
# ------------------------------------------------------------------ #

class TestAdvanceStraight:
    def test_advance_moves_forward(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), straight_state("a.mp3"))
        assert ctrl.advance() == 1

    def test_advance_wraps_with_loop(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3"), straight_state("b.mp3", loop=True))
        assert ctrl.advance() == 0

    def test_advance_returns_none_at_end_without_loop(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3"), straight_state("b.mp3", loop=False))
        assert ctrl.advance() is None

    def test_advance_empty_playlist(self) -> None:
        ctrl = PlaylistController()
        ctrl.load([], straight_state())
        assert ctrl.advance() is None


class TestRetreatStraight:
    def test_retreat_moves_backward(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), straight_state("c.mp3"))
        assert ctrl.retreat() == 1

    def test_retreat_wraps_with_loop(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), straight_state("a.mp3", loop=True))
        assert ctrl.retreat() == 2

    def test_retreat_stays_at_start_without_loop(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3"), straight_state("a.mp3", loop=False))
        assert ctrl.retreat() == 0


# ------------------------------------------------------------------ #
# Navigation — shuffle mode                                            #
# ------------------------------------------------------------------ #

class TestAdvanceShuffle:
    def test_advance_returns_none_at_end_without_loop(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(
            files("a.mp3", "b.mp3", "c.mp3"),
            shuffle_state("a.mp3", ["a.mp3", "b.mp3", "c.mp3"], loop=False),
        )
        ctrl.advance()  # -> 1
        ctrl.advance()  # -> 2
        assert ctrl.advance() is None

    def test_advance_wraps_at_end_with_loop(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(
            files("a.mp3", "b.mp3", "c.mp3"),
            shuffle_state("a.mp3", ["a.mp3", "b.mp3", "c.mp3"], loop=True),
        )
        ctrl.advance()  # -> 1
        ctrl.advance()  # -> 2
        assert ctrl.advance() == 0


class TestRetreatShuffle:
    def test_retreat_wraps_in_shuffle_mode(self) -> None:
        # Reconciliation guarantees len(shuffle_order) == len(files), so the
        # retreat() fix (using order_len instead of len(files)) can't be observed
        # as a behaviour difference through the public API — but the correct logic
        # is still tested here: retreat from position 0 wraps to the last position
        # in the display order, not to some other index.
        ctrl = PlaylistController()
        ctrl.load(
            files("a.mp3", "b.mp3", "c.mp3"),
            shuffle_state("a.mp3", ["a.mp3", "c.mp3", "b.mp3"]),
        )
        assert ctrl.current_display_index == 0
        result = ctrl.retreat()
        assert result == 2  # last position in shuffle order
        assert ctrl.file_at(result) is not None

    def test_retreat_stays_at_start_without_loop(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(
            files("a.mp3", "b.mp3", "c.mp3"),
            shuffle_state("a.mp3", ["a.mp3", "b.mp3", "c.mp3"], loop=False),
        )
        assert ctrl.current_display_index == 0
        assert ctrl.retreat() == 0

    def test_advance_and_retreat_cycle_in_shuffle(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(
            files("a.mp3", "b.mp3", "c.mp3"),
            shuffle_state("a.mp3", ["a.mp3", "c.mp3", "b.mp3"]),
        )
        ctrl.advance()   # -> 1
        ctrl.advance()   # -> 2
        pos = ctrl.advance()  # wraps -> 0
        assert pos == 0
        assert ctrl.retreat() == 2  # wraps back


# ------------------------------------------------------------------ #
# Shuffle enable/disable/reshuffle                                     #
# ------------------------------------------------------------------ #

class TestShuffle:
    def test_enable_shuffle_places_current_first(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), straight_state("b.mp3"))
        ctrl.enable_shuffle()
        assert ctrl.shuffle_enabled
        assert ctrl.current_display_index == 0
        assert ctrl.file_at(0) == Path("b.mp3")

    def test_disable_shuffle_preserves_current_file(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(
            files("a.mp3", "b.mp3", "c.mp3"),
            shuffle_state("b.mp3", ["b.mp3", "c.mp3", "a.mp3"]),
        )
        ctrl.disable_shuffle()
        assert not ctrl.shuffle_enabled
        assert ctrl.file_at(ctrl.current_display_index) == Path("b.mp3")

    def test_reshuffle_keeps_current_first(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), straight_state("b.mp3"))
        ctrl.enable_shuffle()
        ctrl.reshuffle()
        assert ctrl.file_at(0) == Path("b.mp3")

    def test_display_order_length_equals_file_count_in_shuffle(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), straight_state("a.mp3"))
        ctrl.enable_shuffle()
        assert len(ctrl.display_order) == 3


# ------------------------------------------------------------------ #
# Reconciliation                                                       #
# ------------------------------------------------------------------ #

class TestReconcile:
    def test_deleted_track_removed_from_shuffle(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(
            files("a.mp3", "b.mp3"),  # c.mp3 deleted
            shuffle_state("a.mp3", ["a.mp3", "c.mp3", "b.mp3"]),
        )
        names = [ctrl.file_at(i).name for i in range(len(ctrl.display_order))]
        assert "c.mp3" not in names
        assert len(ctrl.display_order) == 2

    def test_new_file_inserted_into_shuffle(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(
            files("a.mp3", "b.mp3", "c.mp3"),  # c.mp3 is new
            shuffle_state("a.mp3", ["a.mp3", "b.mp3"]),
        )
        names = {ctrl.file_at(i).name for i in range(len(ctrl.display_order))}
        assert "c.mp3" in names
        assert len(ctrl.display_order) == 3

    def test_integer_shuffle_order_discarded(self) -> None:
        """Back-compat: integer shuffle_order from old format is dropped in PlaylistState."""
        ps = PlaylistState.from_dict({
            "current_filename": "a.mp3",
            "shuffle_order": [1, 0, 2],
            "loop_enabled": True,
            "playback_position_ms": 0,
        })
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), ps)
        assert not ctrl.shuffle_enabled

    def test_empty_shuffle_order_after_all_deleted_falls_back(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(
            files("a.mp3"),
            shuffle_state("deleted.mp3", ["deleted.mp3"]),
        )
        assert ctrl.current_display_index == 0


# ------------------------------------------------------------------ #
# go_to and sync_to_state                                              #
# ------------------------------------------------------------------ #

class TestGoToAndSync:
    def test_go_to_resets_playback_position(self) -> None:
        ps = straight_state("a.mp3")
        ps.playback_position_ms = 5000
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3"), ps)
        ctrl.go_to(1)
        assert ctrl.playback_position_ms == 0

    def test_sync_to_state_writes_filename(self) -> None:
        ps = straight_state("a.mp3")
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), ps)
        ctrl.go_to(2)
        ctrl.sync_to_state()
        assert ps.current_filename == "c.mp3"

    def test_sync_to_state_writes_shuffle_order(self) -> None:
        ps = straight_state("a.mp3")
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), ps)
        ctrl.enable_shuffle()
        ctrl.sync_to_state()
        assert ps.shuffle_order is not None
        assert set(ps.shuffle_order) == {"a.mp3", "b.mp3", "c.mp3"}

    def test_sync_to_state_clears_shuffle_order_when_disabled(self) -> None:
        ps = shuffle_state("a.mp3", ["a.mp3", "b.mp3"])
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3"), ps)
        ctrl.disable_shuffle()
        ctrl.sync_to_state()
        assert ps.shuffle_order is None


# ------------------------------------------------------------------ #
# file_at                                                              #
# ------------------------------------------------------------------ #

class TestFileAt:
    def test_straight_mode(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(files("a.mp3", "b.mp3", "c.mp3"), straight_state("a.mp3"))
        assert ctrl.file_at(0) == Path("a.mp3")
        assert ctrl.file_at(2) == Path("c.mp3")
        assert ctrl.file_at(3) is None

    def test_shuffle_mode(self) -> None:
        ctrl = PlaylistController()
        ctrl.load(
            files("a.mp3", "b.mp3", "c.mp3"),
            shuffle_state("c.mp3", ["c.mp3", "a.mp3", "b.mp3"]),
        )
        assert ctrl.file_at(0) == Path("c.mp3")
        assert ctrl.file_at(1) == Path("a.mp3")
        assert ctrl.file_at(3) is None
