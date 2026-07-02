"""
nav.py — Navigation with dead reckoning.

The key innovation: track position incrementally. After moving `north` from
room X, you're at X's north neighbor — no need to `look` every step.

Only `look` on: startup, mismatch, or stuck. This cuts navigation time by ~60%.
"""
import time, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (LANDMARKS, REVERSE, EXIT_TOKENS, MOVE_FAIL, STEP_TIMEOUT,
                    LOOK_TIMEOUT, LOG_PATH, COMBAT_SIGNS, OURHOME_PREFIX)
from net import drain, clean, send, m, parse_short, parse_exits, is_dead
from map_engine import _in_dirs


class Navigator:
    """Tracks position and navigates using dead reckoning."""

    def __init__(self, socket, map_engine):
        self.s = socket
        self.M = map_engine
        self.current_rid = None    # tracked position
        self.last_dir = None       # direction we just moved
        self.stuck_count = 0       # consecutive failed identifications

    def look_and_identify(self, hint_id=None, area_dirs=None):
        """Look at current room and identify it. Returns (rid, desc, short, exits)."""
        drain(self.s, quiet=0.3, maxt=1.0)
        desc = m(self.s, "look", q=LOOK_TIMEOUT, log_path=LOG_PATH)
        short = parse_short(desc)
        exits = parse_exits(desc)
        rid = self.M.identify(short, exits_seen=exits, prev_id=self.current_rid,
                               came_dir=self.last_dir, area_dirs=area_dirs)
        if rid:
            self.current_rid = rid
            self.M.record_identification(short, exits, rid)
            self.stuck_count = 0
        return rid, desc, short, exits

    def step(self, direction):
        """Move one step. Returns (response, moved_bool)."""
        r = m(self.s, direction, q=STEP_TIMEOUT, log_path=LOG_PATH)
        moved = not any(w in r for w in MOVE_FAIL)
        # Handle 马盗 (road bandit)
        if "马盗" in r:
            self._handle_madao(r)
        return r, moved

    def _handle_madao(self, desc):
        """Pay 马盗 (road bandit) immediately if demanding money."""
        if "马盗" in desc and ("要钱" in desc or "买路钱" in desc or
                                 "不给钱" in desc or any(c in desc for c in COMBAT_SIGNS)):
            print("  [马盗] paying 10 silver")
            m(self.s, "give ma dao 10 silver", q=2.0)
            time.sleep(1)

    def goto(self, goal_id, area_dirs=None, max_steps=200):
        """Navigate to goal_id using dead reckoning.

        Returns: True if arrived, False if stuck, "dead" if died.
        Includes stuck detection: if >60s elapsed and <50% path done, returns "stuck".
        Caller decides whether to quit+relog based on gear value.
        """
        # If we don't know where we are, identify first
        if self.current_rid is None:
            rid, desc, short, exits = self.look_and_identify(area_dirs=area_dirs)
            if rid is None:
                print("  [nav] can't identify starting position")
                return self._localize_and_retry(goal_id, area_dirs)

        start_rid = self.current_rid
        start_time = time.time()
        total_path_len = None
        fail_count = 0  # consecutive stuck detections

        for attempt in range(max_steps):
            if self.current_rid == goal_id:
                return True

            # BFS from current position
            path = self.M.path(self.current_rid, goal_id)
            if path is None:
                print(f"  [nav] no path from {self.current_rid} to {goal_id}")
                return False
            if not path:
                return True

            # Track total path length for progress estimation
            if total_path_len is None:
                total_path_len = len(path)

            # ── Stuck detection ─────────────────────────────────────
            elapsed = time.time() - start_time
            remaining = len(path)
            progress = 1 - (remaining / max(total_path_len, 1))
            if elapsed > 60 and progress < 0.5:
                print(f"  [nav] STUCK: {elapsed:.0f}s elapsed, {progress*100:.0f}% done")
                # Try 1: re-look, re-identify, re-BFS
                rid, desc, short, exits = self.look_and_identify(area_dirs=area_dirs)
                if rid is not None:
                    self.current_rid = rid
                    new_path = self.M.path(rid, goal_id)
                    if new_path is not None and len(new_path) < remaining:
                        print(f"  [nav] re-identified, new path: {len(new_path)} steps")
                        continue
                fail_count += 1
                if fail_count >= 2:
                    return "stuck"
                # Try wandering in a new direction
                if exits:
                    avoid = REVERSE.get(self.last_dir)
                    d = next((e for e in exits if e != avoid), next(iter(exits)))
                    self.step(d)
                continue

            # ── Dead reckoning: move without looking ──────────────────
            d, expected_next = path[0]
            r, moved = self.step(d)

            if is_dead(r):
                print("  [nav] died during navigation")
                return "dead"

            # Check if the move succeeded by matching the room short name
            if moved:
                actual_short = parse_short(r)
                actual_exits = parse_exits(r)
                expected_short = self.M.short_of(expected_next)

                if actual_short == expected_short:
                    # Success! Update position without looking
                    self.current_rid = expected_next
                    self.last_dir = d
                    self.M.record_identification(actual_short, actual_exits, expected_next)
                    self.stuck_count = 0
                    continue
                else:
                    # Mismatch — try to identify from the response
                    rid = self.M.identify(actual_short, exits_seen=actual_exits,
                                          prev_id=self.current_rid, came_dir=d,
                                          area_dirs=area_dirs)
                    if rid:
                        self.current_rid = rid
                        self.last_dir = d
                        continue
                    # Can't identify — fall through to look
                    print(f"  [nav] mismatch: expected '{expected_short}', got '{actual_short}'")

            # Move failed or can't identify — look and re-identify
            rid, desc, short, exits = self.look_and_identify(
                hint_id=expected_next, area_dirs=area_dirs)
            if rid is None:
                self.stuck_count += 1
                if self.stuck_count >= 3:
                    print(f"  [nav] stuck 3x — giving up")
                    return False
                # Try wandering toward goal
                if exits:
                    avoid = REVERSE.get(self.last_dir)
                    d = next((e for e in exits if e != avoid), next(iter(exits)))
                    r, moved = self.step(d)
                    if moved:
                        self.last_dir = d
                continue
            else:
                self.last_dir = d if moved else None

        print(f"  [nav] max steps ({max_steps}) reached")
        return False

    def _localize_and_retry(self, goal_id, area_dirs=None, tries=16):
        """Find current position by walking to a uniquely identifiable room."""
        print("  [nav] localizing — walking to unique room")
        localize_pref = ["out", "down", "west", "south", "east", "north", "enter", "up"]
        for _ in range(tries):
            rid, desc, short, exits = self.look_and_identify(area_dirs=area_dirs)
            if rid is not None:
                print(f"  [nav] localized at {short} ({rid})")
                return self.goto(goal_id, area_dirs, max_steps=200)
            if not exits:
                break
            d = next((p for p in localize_pref if p in exits), next(iter(exits)))
            self.step(d)
        print("  [nav] could not localize")
        return False

    def force_localize(self, M_obj):
        """Public localize for external callers."""
        return self._localize_and_retry(None)
