"""
mission.py — Yuan interaction, mission parsing, target resolution.

Handles: ask yuan, parse mission message, resolve region→directory→landmark,
sweep vicinity for the monster.
"""
import re, time, sys, os
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (LANDMARKS, MISSION_TTL, STUCK_SECS, SPAWN_DIRS, ACCESSIBLE_DIRS,
                    LOG_PATH, MISSION_FILE, MAX_STEPS_PER_NAV, REGION_ALIASES)
from net import m, drain, clean, has_monster
from map_engine import _in_dirs


# ── Mission parsing ────────────────────────────────────────────────────
RE_MISSION = re.compile(
    r"近有(?P<name>.+?)\((?P<id>[\w ]+)\)在(?P<region>[^（(]+?)"
    r"(?:[（(](?P<landmark>[^）)]+?)一带[）)])?出没")


def parse_mission(text):
    """Return (name, ids, region, landmark) or (None, [], None, None)."""
    mm = RE_MISSION.search(text)
    if not mm:
        return None, [], None, None
    name = mm.group("name")
    ids = mm.group("id").lower().split()
    region = mm.group("region").strip()
    landmark = (mm.group("landmark") or "").strip() or None
    return name, ids, region, landmark


def resolve_target(M, region, landmark):
    """Resolve mission to (anchor_id, search_dirs).
    Returns (None, []) if unreachable."""
    # Apply region aliases (e.g. 灵台方寸 → 方寸山, 东海龙宫 → 龙宫)
    if region and region in REGION_ALIASES:
        region = REGION_ALIASES[region]
    dirs = M.area_dirs_for_region(region) if region else []
    anchor = None

    # Landmark-less rooms: region might be a room short name
    if not dirs and not landmark and region and region in M.by_short:
        landmark = region

    if landmark:
        cands = M.by_short.get(landmark, [])
        if dirs:
            scoped = [c for c in cands if _in_dirs(c, dirs)]
            if scoped:
                cands = scoped
        # Filter to spawn dirs
        spawn_cands = [c for c in cands if _is_spawn_dir(c)]
        if spawn_cands:
            cands = spawn_cands
        # Prefer accessible dirs
        acc_cands = [c for c in cands if _is_accessible(c)]
        if acc_cands:
            cands = acc_cands
        if len(cands) == 1:
            anchor = cands[0]
        elif len(cands) > 1:
            hub = LANDMARKS["hub"]
            reachable = [c for c in cands if M.path(hub, c) is not None]
            anchor = reachable[0] if reachable else cands[0]
        if anchor is not None:
            dirs = [anchor.rsplit("/", 1)[0]]

    if not dirs:
        return None, []

    if anchor is None:
        pool = [r for d in dirs for r in M.rooms_under(d) if M.exits_of(r)]
        # Prefer rooms reachable from hub; fall back to first in pool
        hub = LANDMARKS["hub"]
        reachable_pool = [r for r in pool if M.path(hub, r) is not None]
        anchor = reachable_pool[0] if reachable_pool else (pool[0] if pool else None)

    if anchor is not None and not _is_accessible(anchor):
        # Not in ACCESSIBLE_DIRS whitelist — fall back to path-from-hub check.
        # Some regions (e.g. 崎岖小路 in d/moon) are reachable via westway but
        # not listed in ACCESSIBLE_DIRS. Allow if hub→anchor path exists.
        if M.path(LANDMARKS["hub"], anchor) is None:
            return None, []

    return anchor, dirs


def _is_spawn_dir(rid):
    return any(rid.startswith(d.rstrip("/") + "/") for d in SPAWN_DIRS)


def _is_accessible(rid):
    return any(rid.startswith(d + "/") for d in ACCESSIBLE_DIRS)


# ── Mission persistence ────────────────────────────────────────────────
def save_mission(name, ids, region, landmark, t_start=None):
    if t_start is None:
        t_start = int(time.time())
    try:
        open(MISSION_FILE, "w", encoding="utf-8").write(
            f"{name}|{' '.join(ids or [])}|{region or ''}|{landmark or ''}|{t_start}")
    except Exception:
        pass


def load_mission():
    try:
        p = open(MISSION_FILE, encoding="utf-8").read().strip().split("|")
        p += [""] * (5 - len(p))
        name, ids, region, landmark = p[0], p[1].split(), p[2] or None, p[3] or None
        t_start = int(p[4]) if p[4] else 0
        return name, ids, region, landmark, t_start
    except Exception:
        return None, [], None, None, 0


def mission_age(t_start):
    return int(time.time()) - t_start if t_start else 0


def mission_expired(t_start):
    return t_start and mission_age(t_start) >= MISSION_TTL


# ── Yuan interaction ──────────────────────────────────────────────────
def ask_yuan(s, nav):
    """Return (name, ids, region, landmark, t_start, cleared).
    cleared=True when Yuan says 除尽 (previous mission completed)."""
    result = nav.goto(LANDMARKS["yuan"])
    if result == "inaccessible":
        print("  [YUAN] in inaccessible region — can't reach Yuan")
        return None, [], None, None, 0, False
    r = m(s, "ask yuan about kill", q=3.0, log_path=LOG_PATH)
    print("  --- YUAN ---")
    for ln in r.split("\n"):
        if "袁天罡" in ln or "近有" in ln or "收服" in ln:
            print(f"    {ln.strip()}")

    cleared = "除尽" in r
    name, ids, region, landmark = parse_mission(r)

    if not name and cleared:
        r = m(s, "ask yuan about kill", q=3.0)
        name, ids, region, landmark = parse_mission(r)

    if name:
        t_start = int(time.time())
        save_mission(name, ids, region, landmark, t_start)
        return name, ids, region, landmark, t_start, cleared

    # Reminder form: "在下不是请您去收服X吗?"
    mm = re.search(r"收服(.+?)吗", r)
    if mm:
        want = mm.group(1)
        sn, sids, sreg, slm, st = load_mission()
        if sn == want and sreg:
            # Saved mission found with region info — continue it
            return sn, sids, sreg, slm, st, cleared
        # No saved mission or missing region — try asking Yuan about the specific monster
        r2 = m(s, f"ask yuan about {want}", q=3.0, log_path=LOG_PATH)
        name2, ids2, region2, landmark2 = parse_mission(r2)
        if name2 and region2:
            # Preserve the OLDER t_start if Yuan is re-describing the same monster
            # in a new location — don't reset the clock (prevents indefinite waits
            # for unreachable missions whose clock keeps resetting to "now").
            if sn == name2 and st:
                t_start = st  # keep original issue time
                print(f"  [YUAN] reminder re-parsed with region; keeping original t_start (age {int(time.time())-st}s)")
            else:
                t_start = int(time.time())
            save_mission(name2, ids2, region2, landmark2, t_start)
            return name2, ids2, region2, landmark2, t_start, cleared
        # Still no region — try asking about kill one more time
        r3 = m(s, "ask yuan about kill", q=3.0, log_path=LOG_PATH)
        name3, ids3, region3, landmark3 = parse_mission(r3)
        if name3 and region3:
            # Same clock-preservation logic
            if sn == name3 and st:
                t_start = st
                print(f"  [YUAN] kill re-parsed same monster; keeping original t_start (age {int(time.time())-st}s)")
            else:
                t_start = int(time.time())
            save_mission(name3, ids3, region3, landmark3, t_start)
            return name3, ids3, region3, landmark3, t_start, cleared
        # Give up — return with what we have, bot will wait for timer
        print(f"  [YUAN] can't get region for {want} — waiting for mission to expire")
        return want, [], None, None, int(time.time()), cleared

    return None, [], None, None, 0, cleared


# ── Sweep ─────────────────────────────────────────────────────────────
MAX_FULL_SWEEP = 45  # rooms — small areas get full sweep
MAX_GLOBAL_SWEEP_ROOMS = 600  # cap on global sweep (fallback when no region)


def sweep_vicinity(s, nav, M, anchor_id, search_dirs, name, ids, radius=3, t_start=None):
    """Go to anchor, search for monster, fight if found.

    radius is the base hop radius for large-area sweeps.
    t_start (mission issue time) scales the radius: monsters wander ~1 room/min,
    so we expand the search window proportionally to mission age.
    """
    from economy import smart_eat_drink, wait_full_hp
    from combat import fight

    smart_eat_drink(s, nav)
    wait_full_hp(s)

    # Scale radius with mission age: monster walks ~1 room/min.
    # Base radius 3, add 1 hop per 45s elapsed, cap at 20.
    if t_start is not None:
        age_s = max(0, int(time.time()) - t_start)
        radius = min(3 + age_s // 45, 20)
        print(f"  [sweep] mission age {age_s}s → search radius {radius}")

    sweep_start = time.time()
    print(f"  -> landmark {M.short_of(anchor_id)} ({anchor_id})")
    r = nav.goto(anchor_id, area_dirs=search_dirs, max_steps=MAX_STEPS_PER_NAV)
    if r == "dead":
        return "dead"
    if r == "stuck":
        print(f"  [sweep] got stuck navigating to anchor")
        return "stuck"
    if not r:
        print(f"  [sweep] couldn't reach anchor")
        return "not_found"

    # Determine sweep scope
    full = M.bfs_order(anchor_id, search_dirs=search_dirs, radius=999)
    if len(full) <= MAX_FULL_SWEEP:
        order = full
        print(f"  small area ({len(full)} rooms) — full sweep")
    else:
        order = M.bfs_order(anchor_id, search_dirs=search_dirs, radius=radius)
        print(f"  large area ({len(full)} rooms) — vicinity: {len(order)} within {radius}h")

    # Pre-filter: skip rooms that are dead-ends (no path back to anchor).
    # This prevents the bot from entering locked sub-areas (e.g. monastery corridors)
    # that have one-way or locked doors and will trap the bot.
    safe_order = []
    for room_id in order:
        if room_id == anchor_id:
            safe_order.append(room_id)
            continue
        # Room must have a path back to anchor to be safe to visit
        if M.path(room_id, anchor_id) is not None:
            safe_order.append(room_id)
    if len(safe_order) < len(order):
        print(f"  [sweep] skipped {len(order)-len(safe_order)} dead-end rooms")
    order = safe_order

    engaged = False
    for room_id in order:
        if time.time() - sweep_start > STUCK_SECS:
            print(f"  [TIMEOUT] sweep exceeded {STUCK_SECS}s")
            return "engaged_lost" if engaged else "not_found"

        r = nav.goto(room_id, area_dirs=search_dirs, max_steps=MAX_STEPS_PER_NAV)
        if r == "dead":
            return "dead"
        if not r:
            continue

        desc = m(s, "look", q=1.2, log_path=LOG_PATH)
        if has_monster(desc, name):
            print(f"  ** {name} found in {M.short_of(room_id)} **")
            engaged = True
            for _retry in range(5):
                result = fight(s, name, ids)
                if result is True:
                    return True
                if result == "dead":
                    return "dead"
                if result == "mission_lost":
                    return "mission_lost"
                if result == "monster_fled":
                    # Re-scan neighborhood
                    found = False
                    for nb in [room_id] + list(M.adj.get(room_id, {})):
                        if nav.goto(nb, area_dirs=search_dirs, max_steps=40) is True:
                            if has_monster(m(s, "look", q=1.0), name):
                                found = True
                                break
                    if found:
                        continue
                    break
                if result == "fled":
                    smart_eat_drink(s, nav)
                    wait_full_hp(s)
                    r2 = nav.goto(room_id, area_dirs=search_dirs, max_steps=MAX_STEPS_PER_NAV)
                    if r2 == "dead":
                        return "dead"
                    desc = m(s, "look", q=1.2)
                    if not has_monster(desc, name):
                        print("  [RECOVER] monster left — searching again")
                        break
                    continue
                break

    if engaged:
        print(f"  fought {name} but lost track — Yuan will confirm")
        return "engaged_lost"
    print(f"  {name} not found — mission likely expired")
    return "not_found"


def global_sweep(s, nav, M, name, ids):
    """Fallback when Yuan gives no region: sweep all accessible dirs for monster.
    Used when reminder form has no region and we can't wait 30 min."""
    from economy import smart_eat_drink, wait_full_hp
    from combat import fight

    print(f"  [GLOBAL SWEEP] searching all accessible dirs for {name}")
    smart_eat_drink(s, nav)
    wait_full_hp(s)

    hub = LANDMARKS["hub"]
    order = M.bfs_order(hub, search_dirs=list(ACCESSIBLE_DIRS), radius=999)
    # Hard-filter: bfs_order may return rooms reachable via live-learned edges
    # that cross into unreachable regions (e.g. d/moon via a ghost edge).
    # Strictly keep only rooms whose prefix matches an ACCESSIBLE dir.
    order = [r for r in order if any(r.startswith(d + "/") or r == d for d in ACCESSIBLE_DIRS)]
    order = order[:MAX_GLOBAL_SWEEP_ROOMS]
    print(f"  [GLOBAL SWEEP] {len(order)} rooms to check (strict accessible filter)")

    engaged = False
    for room_id in order:
        r = nav.goto(room_id, area_dirs=list(ACCESSIBLE_DIRS), max_steps=MAX_STEPS_PER_NAV)
        if r == "dead":
            return "dead"
        if r in ("stuck", "inaccessible"):
            return "stuck"
        if not r:
            continue
        desc = m(s, "look", q=1.2, log_path=LOG_PATH)
        if has_monster(desc, name):
            print(f"  ** {name} FOUND in {M.short_of(room_id)} (global sweep) **")
            engaged = True
            result = fight(s, name, ids)
            if result is True:
                return True
            if result == "dead":
                return "dead"
            if result == "mission_lost":
                return "mission_lost"
            break

    if engaged:
        return "engaged_lost"
    print(f"  [GLOBAL SWEEP] {name} not found in accessible dirs")
    return "not_found"
