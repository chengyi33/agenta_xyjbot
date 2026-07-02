"""
map_engine.py — Room graph, BFS pathfinding, and room identification.

Key improvements over original:
1. Dead reckoning: track position incrementally, don't look every step
2. Exits fingerprint: use exit directions as primary disambiguator
3. Long description matching: fallback for empty short names
4. Special edges: dive, swim, climb, jump all in the graph
5. Confidence tracking: learn from correct identifications
"""
import os, json, re
from collections import deque, defaultdict

# Use config from same directory
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (MAP_PATH, FINDMAP_PATH, LANDMARKS, REVERSE, SPECIAL_EDGES,
                    EXIT_TOKENS, REGIONS, region_of, region_name_of)


class XYJMap:
    """Room graph with BFS pathfinding and multi-strategy room identification."""

    def __init__(self, path=MAP_PATH):
        raw = json.load(open(path, encoding="utf-8"))

        # Handle both old format (flat dict) and new format (rooms + special_edges)
        if "rooms" in raw:
            self.g = raw["rooms"]
            file_edges = raw.get("special_edges", [])
        else:
            self.g = raw
            file_edges = []

        # ── Fix exit targets ───────────────────────────────────────────
        for rid, v in self.g.items():
            ex = v.get("exits", {})
            for d, t in list(ex.items()):
                # Strip trailing .c
                tt = t[:-2] if t.endswith(".c") else t
                if tt in self.g:
                    if tt != t:
                        ex[d] = tt
                    continue
                # Fix doubled-prefix bug
                parts = tt.split("/")
                for k in range(1, len(parts)):
                    sub = "/".join(parts[k:])
                    if sub in self.g:
                        ex[d] = sub
                        break

        # ── Build short name index ─────────────────────────────────────
        self.by_short = defaultdict(list)
        # Region-scoped index: by_short_in_region[region_prefix][short] = [rid, ...]
        self.by_short_in_region = defaultdict(lambda: defaultdict(list))
        for rid, v in self.g.items():
            s = v.get("short", "")
            if s:
                self.by_short[s].append(rid)
                rprefix = region_of(rid)
                self.by_short_in_region[rprefix][s].append(rid)

        # ── Build adjacency graph ───────────────────────────────────────
        # adj[u] = { neighbor_id: direction_to_walk_from_u }
        self.adj = defaultdict(dict)

        # Real exits first (authoritative)
        for u, v in self.g.items():
            for d, t in v.get("exits", {}).items():
                if t in self.g:
                    self.adj[u][t] = d

        # Track used directions per node
        used_dir = {u: set(self.adj[u].values()) for u in self.adj}

        # Inferred reverse edges (for bidirectional connections)
        for u, v in self.g.items():
            for d, t in v.get("exits", {}).items():
                if t not in self.g or u in self.adj.get(t, {}):
                    continue
                rev = REVERSE.get(d, d)
                td = used_dir.setdefault(t, set(self.adj.get(t, {}).values()))
                if rev in td:
                    continue
                self.adj[t][u] = rev
                td.add(rev)

        # ── Add special verb edges ─────────────────────────────────────
        # From config (manually verified) + from build_map.py (auto-parsed)
        all_special = list(SPECIAL_EDGES) + [(u, t, v) for u, t, v in file_edges]
        for u, t, verb in all_special:
            if u in self.g and t in self.g:
                self.adj[u][t] = verb

        # Also add reverse for swim (bidirectional) and climb (bidirectional)
        for u, t, verb in all_special:
            if verb in ("swim", "climb") and t in self.g and u in self.g:
                if u not in self.adj.get(t, {}):
                    self.adj[t][u] = verb  # same verb works both ways

        # Manually add swim for southseashore ↔ nanhai/island (not in auto-parse
        # because the LPC uses me->move() with a path string, which our parser
        # might miss if the function name doesn't match our pattern)
        manual_swim = [
            ("d/changan/southseashore", "d/nanhai/island", "swim"),
            ("d/nanhai/island", "d/changan/southseashore", "swim"),
        ]
        for u, t, verb in manual_swim:
            if u in self.g and t in self.g:
                self.adj[u][t] = verb

        # ── Load find.map (region → directory) ─────────────────────────
        self.dir_to_region = {}
        self.region_to_dirs = defaultdict(list)
        self._load_findmap()

        # ── Confidence cache: rooms we've correctly identified before ──
        # {short_name: {frozenset(exits): rid}}
        self._id_cache = defaultdict(dict)

        # ── Live map overrides: discovered/fixed during gameplay ────────
        # All overrides use confidence scoring:
        #   - New discoveries start "pending" (don't affect navigation)
        #   - After confirmation (2nd visit / round-trip) → promoted to "confirmed"
        #   - Broken edges are temporary (retry after 24h), permanent after 3 failures
        self._overrides_path = os.path.join(os.path.dirname(MAP_PATH), "map_overrides.json")
        self._bak_path = self._overrides_path + ".bak"

        # Confirmed overrides (applied to live map)
        self._broken_edges = {}         # {(from, to): {direction, failures, first_failed, permanent}}
        self._discovered_rooms = {}     # {rid: {short, exits, confidence, first_seen, last_confirmed}}
        self._discovered_edges = {}     # {(from, to): {direction, confidence, confirmed, first_seen}}

        # Pending (NOT applied to live map until confirmed)
        self._pending_rooms = {}        # {rid: {short, exits, first_seen, confirmations}}
        self._pending_edges = {}        # {(from, to): {direction, first_seen}}

        self._load_overrides()

        # Apply CONFIRMED overrides only to the graph
        for rid, info in self._discovered_rooms.items():
            if info.get("confidence", 0) >= 2 and rid not in self.g:
                self.g[rid] = {"short": info.get("short", ""), "exits": info.get("exits", {})}
                s = info.get("short", "")
                if s:
                    self.by_short[s].append(rid)
                    rprefix = region_of(rid)
                    self.by_short_in_region[rprefix][s].append(rid)

        for key, info in self._discovered_edges.items():
            if info.get("confidence", 0) >= 2:
                u, t = key
                self.adj[u][t] = info["direction"]

        # Remove broken edges from adjacency (only non-expired or permanent)
        import datetime as _dt
        now = _dt.datetime.now().timestamp()
        for key, info in self._broken_edges.items():
            u, t = key
            failures = info.get("failures", 1)
            permanent = info.get("permanent", False)
            first_failed = info.get("first_failed", now)
            age = now - first_failed
            # Temporary breaks expire after 24h, unless permanent or 3+ failures
            if permanent or failures >= 3 or age < 86400:
                self.adj.get(u, {}).pop(t, None)
            else:
                # Expired — remove from broken, allow retry
                del self._broken_edges[key]

    def _load_overrides(self):
        """Load map overrides from JSON file."""
        if not os.path.exists(self._overrides_path):
            return
        try:
            data = json.load(open(self._overrides_path, encoding="utf-8"))
            self._broken_edges = {tuple(k.split("|")): v
                                  for k, v in data.get("broken_edges", {}).items()}
            self._discovered_rooms = data.get("discovered_rooms", {})
            self._discovered_edges = {tuple(k.split("|")): v
                                      for k, v in data.get("discovered_edges", {}).items()}
            self._pending_rooms = data.get("pending_rooms", {})
            self._pending_edges = {tuple(k.split("|")): v
                                   for k, v in data.get("pending_edges", {}).items()}
            print(f"  [MAP] overrides: {len(self._broken_edges)} broken, "
                  f"{len(self._discovered_rooms)} confirmed rooms, "
                  f"{len(self._pending_rooms)} pending, "
                  f"{len(self._discovered_edges)} confirmed edges")
        except Exception as e:
            print(f"  [MAP] failed to load overrides: {e}")

    def _save_overrides(self):
        """Persist map overrides to JSON file, with .bak rollback safety."""
        import shutil, datetime as _dt
        data = {
            "broken_edges":    {f"{u}|{t}": v for (u, t), v in self._broken_edges.items()},
            "discovered_rooms": self._discovered_rooms,
            "discovered_edges": {f"{u}|{t}": v for (u, t), v in self._discovered_edges.items()},
            "pending_rooms":    self._pending_rooms,
            "pending_edges":    {f"{u}|{t}": v for (u, t), v in self._pending_edges.items()},
            "saved_at": _dt.datetime.now().isoformat(),
        }
        try:
            # Backup before write
            if os.path.exists(self._overrides_path):
                shutil.copy2(self._overrides_path, self._bak_path)
            json.dump(data, open(self._overrides_path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"  [MAP] failed to save overrides: {e}")

    def rollback_overrides(self):
        """Revert to last known-good overrides backup."""
        if not os.path.exists(self._bak_path):
            print("  [MAP] no backup to rollback to")
            return False
        import shutil
        shutil.copy2(self._bak_path, self._overrides_path)
        print("  [MAP] rolled back to backup overrides")
        # Reload
        self._broken_edges.clear()
        self._discovered_rooms.clear()
        self._discovered_edges.clear()
        self._pending_rooms.clear()
        self._pending_edges.clear()
        self._load_overrides()
        return True

    def mark_edge_broken(self, from_rid, to_rid, direction=None):
        """Mark an edge as broken/conditional.
        Temporary (24h) on first failure, permanent after 3 failures.
        """
        import datetime as _dt
        key = (from_rid, to_rid)
        existing = self._broken_edges.get(key, {})
        failures = existing.get("failures", 0) + 1
        self._broken_edges[key] = {
            "direction": direction,
            "failures": failures,
            "first_failed": existing.get("first_failed", _dt.datetime.now().timestamp()),
            "last_failed": _dt.datetime.now().timestamp(),
            "permanent": failures >= 3,
        }
        # Remove from adjacency immediately
        self.adj.get(from_rid, {}).pop(to_rid, None)
        status = "PERMANENT" if failures >= 3 else f"temp (failure #{failures})"
        print(f"  [MAP] edge broken [{status}]: {from_rid} → {to_rid} ({direction})")
        self._save_overrides()

    def add_discovered_room(self, rid, short, exits, from_rid=None, direction=None):
        """Add a discovered room. Requires 2 confirmations before affecting navigation.

        First sighting → pending (no map effect)
        Second sighting (same short+exits) → confirmed → added to live map
        """
        import datetime as _dt
        now = _dt.datetime.now().isoformat()

        # Check if already confirmed
        if rid in self._discovered_rooms:
            info = self._discovered_rooms[rid]
            info["confidence"] = info.get("confidence", 1) + 1
            info["last_confirmed"] = now
            print(f"  [MAP] room re-confirmed: {rid} ({short}) conf={info['confidence']}")
            self._save_overrides()
            return

        # Check if in pending
        if rid in self._pending_rooms:
            pending = self._pending_rooms[rid]
            # Same short name and similar exits → confirm!
            if pending.get("short") == short:
                pending["confirmations"] = pending.get("confirmations", 1) + 1
                if pending["confirmations"] >= 2:
                    print(f"  [MAP] room CONFIRMED after {pending['confirmations']} visits: {rid} ({short})")
                    self._discovered_rooms[rid] = {
                        "short": short, "exits": exits,
                        "confidence": 2,
                        "first_seen": pending.get("first_seen", now),
                        "last_confirmed": now,
                    }
                    del self._pending_rooms[rid]
                    # Now apply to live map
                    if rid not in self.g:
                        self.g[rid] = {"short": short, "exits": dict(exits)}
                        if short:
                            self.by_short[short].append(rid)
                            rprefix = region_of(rid)
                            self.by_short_in_region[rprefix][short].append(rid)
                    if from_rid and direction:
                        self.add_discovered_edge(from_rid, rid, direction)
                else:
                    print(f"  [MAP] room pending ({pending['confirmations']}/2): {rid} ({short})")
                self._save_overrides()
            return

        # First sighting — add to pending only
        print(f"  [MAP] room first sighting (pending): {rid} ({short}) exits={list(exits.keys())}")
        self._pending_rooms[rid] = {
            "short": short, "exits": exits,
            "from_rid": from_rid, "direction": direction,
            "first_seen": now, "confirmations": 1,
        }
        self._save_overrides()

    def add_discovered_edge(self, from_rid, to_rid, direction):
        """Add a new edge. Requires round-trip confirmation before affecting navigation.

        First direction (A→B) → pending
        Reverse confirmed (B→A exists) OR second traversal → confirmed → applied
        """
        import datetime as _dt
        now = _dt.datetime.now().isoformat()
        key = (from_rid, to_rid)
        rev_key = (to_rid, from_rid)

        # Already confirmed
        if key in self._discovered_edges:
            info = self._discovered_edges[key]
            info["confidence"] = info.get("confidence", 1) + 1
            print(f"  [MAP] edge re-confirmed: {from_rid} --{direction}--> {to_rid} conf={info['confidence']}")
            self._save_overrides()
            return

        # Check if reverse direction already confirmed (round-trip!)
        rev_confirmed = (rev_key in self._discovered_edges and
                         self._discovered_edges[rev_key].get("confidence", 0) >= 2)
        # Or second traversal of same edge
        pending = self._pending_edges.get(key)
        second_traversal = pending is not None and pending.get("direction") == direction

        if rev_confirmed or second_traversal:
            print(f"  [MAP] edge CONFIRMED: {from_rid} --{direction}--> {to_rid}")
            self._discovered_edges[key] = {
                "direction": direction, "confidence": 2,
                "first_seen": pending.get("first_seen", now) if pending else now,
                "last_confirmed": now,
            }
            self._pending_edges.pop(key, None)
            # Apply to live map
            self.adj[from_rid][to_rid] = direction
            self._save_overrides()
        else:
            # First time — add to pending
            print(f"  [MAP] edge first sighting (pending): {from_rid} --{direction}--> {to_rid}")
            self._pending_edges[key] = {"direction": direction, "first_seen": now}
            self._save_overrides()

    def _load_findmap(self, path=FINDMAP_PATH):
        data = None
        for enc in ("gbk", "gb18030", "gb2312", "utf-8"):
            try:
                data = open(path, encoding=enc, errors="replace").read()
                break
            except Exception:
                continue
        if not data:
            return
        for line in data.splitlines():
            parts = line.split()
            if len(parts) >= 2 and len(parts[0]) > 2 and len(parts[1]) > 1:
                d, name = parts[0], parts[1].replace(" ", "")
                self.dir_to_region[d] = name
                if d not in self.region_to_dirs[name]:
                    self.region_to_dirs[name].append(d)

    # ── Lookup ────────────────────────────────────────────────────────
    def short_of(self, rid):
        return self.g.get(rid, {}).get("short", "")

    def long_of(self, rid):
        return self.g.get(rid, {}).get("long", "")

    def exits_of(self, rid):
        return self.g.get(rid, {}).get("exits", {})

    def area_of(self, rid):
        return self.g.get(rid, {}).get("area", "")

    def is_outdoors(self, rid):
        return self.g.get(rid, {}).get("outdoors", False)

    def ids_with_short(self, short):
        return list(self.by_short.get(short, []))

    def area_dirs_for_region(self, name):
        return list(self.region_to_dirs.get(name, []))

    def rooms_under(self, dir_prefix):
        p = dir_prefix.rstrip("/") + "/"
        return [rid for rid in self.g if rid.startswith(p)]

    # ── Room Identification ────────────────────────────────────────────
    def identify(self, short, exits_seen=None, prev_id=None, came_dir=None,
                area_dirs=None, current_region=None):
        """Identify current room using multiple strategies.

        Priority:
          0. Region-scoped lookup: if current_region given, search only within it
          1. If prev_id + came_dir: follow the edge from prev_id
          2. Check confidence cache (previously verified matches)
          3. Exits fingerprint match (short + exits = unique)
          4. Subset/superset exits match
          5. Area_dirs constrained match
          6. First candidate (last resort)

        Returns room_id or None.
        """
        # ── Strategy 0: region-scoped lookup ──────────────────────────
        # If we know our current region, search only within it first.
        # This is the "I'm in 长安, so '街道' means one of 3 rooms" optimization.
        if current_region:
            regional_cands = self.by_short_in_region.get(current_region, {}).get(short, [])
            if regional_cands:
                cands = regional_cands
                # Region found — narrow down within region
                if len(cands) == 1:
                    return cands[0]
                # Continue with exits fingerprint, but scoped to region
                if exits_seen:
                    es = set(exits_seen)
                    exact = [c for c in cands if set(self.exits_of(c)) == es]
                    if len(exact) == 1:
                        self._id_cache[short][frozenset(es)] = exact[0]
                        return exact[0]
                    sub = [c for c in cands
                           if self.exits_of(c) and set(self.exits_of(c)).issubset(es)]
                    if len(sub) == 1:
                        self._id_cache[short][frozenset(es)] = sub[0]
                        return sub[0]
                    sup = [c for c in cands
                           if self.exits_of(c) and es.issubset(set(self.exits_of(c)))]
                    if len(sup) == 1:
                        self._id_cache[short][frozenset(es)] = sup[0]
                        return sup[0]
                    # Best Jaccard within region
                    best, best_score = None, -1
                    for c in cands:
                        cd = set(self.exits_of(c))
                        score = len(cd & es) / max(len(cd | es), 1)
                        if score > best_score:
                            best, best_score = c, score
                    return best
                # No exits info, but region-scoped — use prev_id if available
                if prev_id and came_dir:
                    target = self.exits_of(prev_id).get(came_dir)
                    if target and self.short_of(target) == short:
                        return target
                    for nb, dd in self.adj.get(prev_id, {}).items():
                        if dd == came_dir and self.short_of(nb) == short:
                            return nb
                return cands[0]  # best guess within region
            # Short name not found in current region — fall through to global search
            # This might mean we crossed a region boundary without noticing

        # ── Global fallback (original logic) ───────────────────────────
        cands = self.by_short.get(short, [])
        if not cands:
            return None

        if len(cands) == 1:
            return cands[0]

        # Strategy 1: adjacency from previous room + direction
        if prev_id and came_dir:
            # Direct exit from prev_id
            target = self.exits_of(prev_id).get(came_dir)
            if target and self.short_of(target) == short:
                return target
            # Inferred neighbor
            for nb, dd in self.adj.get(prev_id, {}).items():
                if dd == came_dir and self.short_of(nb) == short:
                    return nb

        # Strategy 2: confidence cache
        if exits_seen:
            key = frozenset(exits_seen)
            cached = self._id_cache.get(short, {}).get(key)
            if cached:
                return cached

        # Constrain to area if possible
        scoped = cands
        if area_dirs:
            scoped = [c for c in cands if _in_dirs(c, area_dirs)]
            if not scoped:
                scoped = cands  # don't over-constrain

        if len(scoped) == 1:
            return scoped[0]

        # Strategy 3: exits fingerprint exact match
        if exits_seen:
            es = set(exits_seen)
            exact = [c for c in scoped if set(self.exits_of(c)) == es]
            if len(exact) == 1:
                # Cache this match
                self._id_cache[short][frozenset(es)] = exact[0]
                return exact[0]

            # Strategy 4: subset match (map exits ⊆ seen exits)
            sub = [c for c in scoped
                   if self.exits_of(c) and set(self.exits_of(c)).issubset(es)]
            if len(sub) == 1:
                self._id_cache[short][frozenset(es)] = sub[0]
                return sub[0]

            # Strategy 5: superset match (seen exits ⊆ map exits)
            sup = [c for c in scoped
                   if self.exits_of(c) and es.issubset(set(self.exits_of(c)))]
            if len(sup) == 1:
                self._id_cache[short][frozenset(es)] = sup[0]
                return sup[0]

            # Strategy 6: best Jaccard similarity on exits
            best, best_score = None, -1
            for c in scoped:
                cd = set(self.exits_of(c))
                score = len(cd & es) / max(len(cd | es), 1)
                if score > best_score:
                    best, best_score = c, score
            return best

        return scoped[0] if scoped else cands[0]

    def record_identification(self, short, exits_seen, rid):
        """Manually record a verified identification for future use."""
        if exits_seen:
            self._id_cache[short][frozenset(exits_seen)] = rid

    # ── Pathfinding ───────────────────────────────────────────────────
    def path(self, start_id, goal_id):
        """BFS start→goal. Returns list of (direction, dest_id) or None."""
        if start_id == goal_id:
            return []
        prev = {start_id: None}
        q = deque([start_id])
        while q:
            u = q.popleft()
            if u == goal_id:
                break
            for nb, d in self.adj.get(u, {}).items():
                if nb not in prev:
                    prev[nb] = (u, d)
                    q.append(nb)
        if goal_id not in prev:
            return None
        steps = []
        cur = goal_id
        while prev[cur] is not None:
            u, d = prev[cur]
            steps.append((d, cur))
            cur = u
        return steps[::-1]

    def path_to_pred(self, start_id, pred):
        """BFS to nearest room where pred(room_id) is True.
        Returns (goal_id, [(dir,dest)...]) or (None, None)."""
        if pred(start_id):
            return start_id, []
        prev = {start_id: None}
        q = deque([start_id])
        while q:
            u = q.popleft()
            for nb, d in self.adj.get(u, {}).items():
                if nb not in prev:
                    prev[nb] = (u, d)
                    if pred(nb):
                        steps = []
                        cur = nb
                        while prev[cur] is not None:
                            pu, pd = prev[cur]
                            steps.append((pd, cur))
                            cur = pu
                        return nb, steps[::-1]
                    q.append(nb)
        return None, None

    def directions(self, start_id, goal_id):
        p = self.path(start_id, goal_id)
        return None if p is None else [d for d, _ in p]

    # ── Area helpers ──────────────────────────────────────────────────
    def rooms_in_area(self, area):
        return [rid for rid, v in self.g.items() if v.get("area") == area]

    def reachable_from(self, start_id, max_hops=999):
        """All room ids reachable from start_id within max_hops."""
        seen = {start_id: 0}
        q = deque([start_id])
        while q:
            u = q.popleft()
            if seen[u] >= max_hops:
                continue
            for nb in self.adj.get(u, {}):
                if nb not in seen:
                    seen[nb] = seen[u] + 1
                    q.append(nb)
        return seen

    def bfs_order(self, start_id, search_dirs=None, radius=999):
        """Room ids ordered by hop distance from start, optionally filtered
        to search_dirs only."""
        seen = {start_id: 0}
        order = [start_id]
        q = deque([start_id])
        while q:
            u = q.popleft()
            if seen[u] >= radius:
                continue
            for nb in self.adj.get(u, {}):
                if nb in seen:
                    continue
                seen[nb] = seen[u] + 1
                if search_dirs is None or _in_dirs(nb, search_dirs):
                    order.append(nb)
                q.append(nb)
        return order


def _in_dirs(rid, area_dirs):
    if not area_dirs:
        return True
    return any(rid.startswith(d.rstrip("/") + "/") for d in area_dirs)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    M = XYJMap()
    print(f"Rooms: {len(M.g)}")
    print(f"Rooms with short: {sum(1 for v in M.g.values() if v.get('short'))}")
    print(f"Rooms with exits: {sum(1 for v in M.g.values() if v.get('exits'))}")
    print(f"Adjacency entries: {len(M.adj)}")
    print(f"Unique short names: {len(M.by_short)}")
    print(f"Regions mapped: {len(M.region_to_dirs)}")

    # Test pathfinding
    hub = LANDMARKS["hub"]
    tests = [
        ("d/city/tianjiantai", "天监台 (Yuan)"),
        ("d/city/kezhan", "南城客栈 (kezhan)"),
        ("d/city/bingqipu", "兵器铺 (shop)"),
        ("d/gao/house", "高老庄 农舍"),
        ("d/changan/eastseashore", "东海之滨"),
        ("d/nanhai/island", "普陀山 小岛"),
    ]
    for goal, label in tests:
        p = M.path(hub, goal)
        if p is None:
            print(f"\n{label}: UNREACHABLE")
        else:
            print(f"\n{label}: {len(p)} steps")
            print(f"  dirs: {' '.join(d for d, _ in p)}")

    # Show top ambiguous names
    from collections import Counter
    c = Counter(v.get("short", "") for v in M.g.values())
    print("\nTop 5 ambiguous names:")
    for name, cnt in c.most_common(6):
        if name and cnt > 1:
            print(f"  {name}: {cnt} rooms")
