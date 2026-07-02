"""
xyjmap.py — Navigation over the XYJ2000 room graph built by build_map.py.

Loads xyj2000_map.json and provides:
  - short-name -> room id lookup (with adjacency-based disambiguation)
  - BFS pathfinding between rooms, returning a list of (direction, dest_id)
  - BFS to the nearest room satisfying a predicate (e.g. "in area X")
  - direction resolution: to walk u->t, use u's own exit if present, else the
    reverse of t's exit back to u (91% of edges are bidirectional; runtime
    verification in the bot catches the rare one-way miss).

Landmarks (stable, source-verified unique short names) are exposed by id.
"""
import os, json
from collections import deque, defaultdict

MAP_PATH = os.path.join(os.path.dirname(__file__), "xyj2000_map.json")
FINDMAP_PATH = os.path.join(os.path.dirname(__file__), "..", "world",
                            "adm", "daemons", "find.map")

REVERSE = {
    "north": "south", "south": "north", "east": "west", "west": "east",
    "up": "down", "down": "up", "enter": "out", "out": "enter",
    "northeast": "southwest", "southwest": "northeast",
    "northwest": "southeast", "southeast": "northwest",
    "northup": "southdown", "southdown": "northup",
    "eastup": "westdown", "westdown": "eastup",
    "westup": "eastdown", "eastdown": "westup",
    "northdown": "southup", "southup": "northdown",
}

# Verb-based transitions (not normal exits). (from_room, to_room, command).
# `dive` at 东海之滨 → 海底 works for 龙宫 family members (yxcdrg qualifies).
SPECIAL_EDGES = [
    ("d/changan/eastseashore", "d/sea/under1", "dive"),
]

# Source-verified unique landmark rooms
LANDMARKS = {
    "hub":        "d/city/center",       # 十字街头
    "yuan":       "d/city/tianjiantai",  # 天监台
    "kezhan":     "d/city/kezhan",       # 南城客栈 (food/water)
    "shop":       "d/city/bingqipu",     # 兵器铺 (weapons)
    "bank":       "d/city/bank",         # 相记钱庄 (deposit/withdraw gold)
}


class XYJMap:
    def __init__(self, path=MAP_PATH):
        self.g = json.load(open(path, encoding="utf-8"))
        # Fix a systematic map-build bug: 314 exit targets carry a trailing
        # ".c" (e.g. "d/sea/inside4.c") that doesn't match the room id
        # ("d/sea/inside4"), breaking BFS across the whole game. Strip it when
        # the stripped id is a real room.
        for rid, v in self.g.items():
            ex = v.get("exits", {})
            for d, t in list(ex.items()):
                tt = t[:-2] if t.endswith(".c") else t
                if tt in self.g:
                    if tt != t:
                        ex[d] = tt
                    continue
                # Doubled-prefix bug (e.g. "d/sea/d/changan/eastseashore" — an
                # absolute target got the room's own dir prepended). Strip
                # leading path segments until a real room id remains. This fixes
                # the 龙宫 surface route (under1 up → d/changan/eastseashore).
                parts = tt.split("/")
                for k in range(1, len(parts)):
                    sub = "/".join(parts[k:])
                    if sub in self.g:
                        ex[d] = sub
                        break
        # short -> list of ids
        self.by_short = defaultdict(list)
        for rid, v in self.g.items():
            if v["short"]:
                self.by_short[v["short"]].append(rid)
        # undirected adjacency with resolved walking direction:
        # adj[u] = { neighbor_id: direction_to_walk_from_u }
        self.adj = defaultdict(dict)
        # Real exits first — these are authoritative walking directions.
        for u, v in self.g.items():
            for d, t in v["exits"].items():
                if t in self.g:
                    self.adj[u][t] = d
        # Track directions already used by each node's REAL exits, so inferred
        # reverse edges never collide with a real one (a real 'south' means
        # walking 'south' goes there — not to some other reverse-inferred room).
        used_dir = {u: set(self.adj[u].values()) for u in self.adj}
        # Add inferred reverse edges only when (a) the forward isn't known and
        # (b) that direction is still free at the target — avoids two neighbors
        # sharing a direction, which caused BFS to plot un-walkable paths.
        for u, v in self.g.items():
            for d, t in v["exits"].items():
                if t not in self.g or u in self.adj[t]:
                    continue
                rev = REVERSE.get(d, d)
                td = used_dir.setdefault(t, set(self.adj[t].values()))
                if rev in td:
                    continue  # target already walks `rev` to a real room
                self.adj[t][u] = rev
                td.add(rev)
        # Special verb-based transitions not encoded as normal exits. Only add
        # ones usable by THIS character (yxcdrg is a 东海龙宫 disciple, so `dive`
        # at 东海之滨 works without a 避水咒 — see eastseashore.c do_dive()).
        for u, t, verb in SPECIAL_EDGES:
            if u in self.g and t in self.g:
                self.adj[u][t] = verb
        # find.map: directory <-> region (Chinese) name, from the MUD daemon.
        # A region name may map to several dirs (e.g. 长安城 -> d/city, d/eastway).
        self.dir_to_region = {}
        self.region_to_dirs = defaultdict(list)
        self._load_findmap()

    def _load_findmap(self, path=FINDMAP_PATH):
        try:
            data = open(path, encoding="gbk", errors="replace").read()
        except Exception:
            return
        for line in data.splitlines():
            parts = line.split()
            if len(parts) >= 2 and len(parts[0]) > 2 and len(parts[1]) > 1:
                d, name = parts[0], parts[1].replace(" ", "")
                self.dir_to_region[d] = name
                if d not in self.region_to_dirs[name]:
                    self.region_to_dirs[name].append(d)

    def area_dirs_for_region(self, name):
        """Chinese region name -> list of directory prefixes (e.g. 'd/kaifeng')."""
        return list(self.region_to_dirs.get(name, []))

    def rooms_under(self, dir_prefix):
        """All room ids under a directory prefix (id starts with prefix + '/')."""
        p = dir_prefix.rstrip("/") + "/"
        return [rid for rid in self.g if rid.startswith(p)]

    # ---- lookup -------------------------------------------------------
    def short_of(self, rid):
        return self.g.get(rid, {}).get("short", "")

    def area_of(self, rid):
        return self.g.get(rid, {}).get("area", "")

    def exits_of(self, rid):
        return self.g.get(rid, {}).get("exits", {})

    def ids_with_short(self, short):
        return list(self.by_short.get(short, []))

    def locate(self, short, exits_seen=None, prev_id=None, came_dir=None):
        """Resolve a room's short name to the best room id.

        Disambiguation priority:
          1. If prev_id + came_dir known: the id reached by walking came_dir
             from prev_id must have this short.
          2. If exits_seen (set of directions) given: match the candidate
             whose exit-direction set matches best.
          3. Unique short -> that id.
        Returns id or None.
        """
        cands = self.by_short.get(short, [])
        if not cands:
            return None
        if len(cands) == 1:
            return cands[0]
        # 1. adjacency from previous room
        if prev_id and came_dir:
            t = self.exits_of(prev_id).get(came_dir)
            if t and self.short_of(t) == short:
                return t
            # inferred neighbor
            for nb, dd in self.adj.get(prev_id, {}).items():
                if dd == came_dir and self.short_of(nb) == short:
                    return nb
        # 2. exits match
        if exits_seen:
            es = set(exits_seen)
            best, bestscore = None, -1
            for c in cands:
                cd = set(self.exits_of(c))
                score = len(cd & es) - abs(len(cd) - len(es))
                if score > bestscore:
                    best, bestscore = c, score
            return best
        # 3. fallback: first
        return cands[0]

    # ---- pathfinding --------------------------------------------------
    def path(self, start_id, goal_id):
        """BFS start->goal. Returns list of (direction, dest_id) or None."""
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
        """Just the list of direction strings, or None."""
        p = self.path(start_id, goal_id)
        return None if p is None else [d for d, _ in p]

    # ---- area helpers -------------------------------------------------
    def rooms_in_area(self, area):
        return [rid for rid, v in self.g.items() if v["area"] == area]

    def reachable_rooms_in_area(self, start_id, area, limit=400):
        """BFS from start, collecting room ids in `area` (order = walk order)."""
        out = []
        seen = {start_id}
        q = deque([start_id])
        while q and len(out) < limit:
            u = q.popleft()
            if self.area_of(u) == area:
                out.append(u)
            for nb in self.adj.get(u, {}):
                if nb not in seen:
                    seen.add(nb)
                    q.append(nb)
        return out


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")
    M = XYJMap()
    print(f"loaded {len(M.g)} rooms")
    hub = LANDMARKS["hub"]
    tests = [
        ("d/lingtai/gate", "方寸山山门"),
        ("d/kaifeng/east1", "开封大官道"),
        ("d/gao/gate", "高老庄门"),
    ]
    for goal, label in tests:
        dirs = M.directions(hub, goal)
        if dirs is None:
            print(f"\n{label}: UNREACHABLE")
        else:
            print(f"\n{label} ({goal}): {len(dirs)} steps")
            # show the route as short names
            cur = hub
            line = [M.short_of(cur)]
            for d in dirs:
                nb = None
                for n, dd in M.adj[cur].items():
                    if dd == d:
                        nb = n
                        break
                cur = nb
                line.append(f"-{d}->{M.short_of(cur)}")
            print("  " + " ".join(line[:1] + line[1:14]) + (" ..." if len(dirs) > 13 else ""))
            print("  dirs:", " ".join(dirs))
