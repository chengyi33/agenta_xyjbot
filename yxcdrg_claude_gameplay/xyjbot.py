"""
xyjbot.py — Map-driven XYJ2000 kill bot.

Navigation: look → identify current room → BFS to goal → take next step → repeat.
No dead-reckoning. Every step re-confirms position from the look output.
"""
import socket, time, re, sys, os
from collections import deque
from xyjmap import XYJMap, LANDMARKS, REVERSE

sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)

HOST, PORT = "146.190.143.182", 6666
USER, PASS = "yxcdrg", "198633"
TARGET_KILLS = int(os.environ.get("XYJ_TARGET", "1"))  # kills THIS run
LOG = os.path.join(os.environ.get("TEMP", "."), "xyjbot.log")
MFILE = os.path.join(os.environ.get("TEMP", "."), "xyjbot_mission.txt")
# Persistent lifetime kill tally (running tab across sessions)
TALLY = os.path.join(os.path.dirname(__file__), "kill_tally.txt")

def tally_get():
    try: return int(open(TALLY).read().strip() or 0)
    except Exception: return 0

def tally_add(n=1):
    v = tally_get() + n
    try: open(TALLY, "w").write(str(v))
    except Exception: pass
    return v

# Region/area resolution now comes from Yuan's message parsed against find.map
# (see parse_mission / resolve_target below); no hard-coded keyword table needed.

# ── network ────────────────────────────────────────────────────────────
def drain(s, quiet=1.0, maxt=8.0):
    s.setblocking(False); buf = b""; start = last = time.time()
    while True:
        try:
            c = s.recv(4096)
            if c: buf += c; last = time.time()
            else: break
        except BlockingIOError:
            if buf and (time.time() - last) > quiet: break
            if (time.time() - start) > maxt: break
            time.sleep(0.03)
    return buf

def clean(b):
    for enc in ("utf-8", "gbk"):
        try:
            t = b.replace(b"\x00", b"").decode(enc)
            return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", t)
        except Exception:
            pass
    return b.replace(b"\x00", b"").decode("gbk", errors="replace")

def send(s, cmd, quiet=1.0):
    s.sendall((cmd + "\r\n").encode())
    return clean(drain(s, quiet=quiet))

def m(s, cmd, q=1.0):
    r = send(s, cmd, quiet=q)
    try:
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(f">> {cmd}\n{r}\n")
    except Exception:
        pass
    return r

# ── room parsing ───────────────────────────────────────────────────────
EXIT_TOKENS = {"northeast","northwest","southeast","southwest",
               "eastup","westdown","northup","southdown",
               "north","south","east","west","up","down","enter","out"}

def parse_short(desc):
    for line in desc.split("\n")[:6]:
        line = line.strip()
        if line and not line.startswith(">"):
            # room header: "南海之滨 - " or "南海之滨 -" or "南海之滨－"
            line = re.split(r"\s*[-－]\s*", line)[0].strip()
            return line
    return ""

def parse_exits(desc):
    """Parse exits from the game's explicit exit line only."""
    mk = re.search(r"出口[是有为]?\s*(.+)", desc)
    if not mk:
        return set()
    seg = re.split(r"[。\n]", mk.group(1))[0]
    return {tok for tok in re.findall(r"[a-zA-Z]+", seg.lower()) if tok in EXIT_TOKENS}

# ── room identification ────────────────────────────────────────────────
def _in_dirs(rid, area_dirs):
    if not area_dirs:
        return True
    return any(rid.startswith(d.rstrip("/") + "/") for d in area_dirs)

def identify(M, short, exits, hint_id=None, area_dirs=None):
    """Return best room id for short+exits. hint_id is expected location.
    area_dirs (list of dir prefixes) restricts candidates when known."""
    cands = M.by_short.get(short, [])
    if not cands:
        return None
    # Constrain to the mission area if that leaves any candidates.
    if area_dirs:
        scoped = [c for c in cands if _in_dirs(c, area_dirs)]
        if scoped:
            cands = scoped
    if len(cands) == 1:
        return cands[0]
    # hint: expected room matches short
    if hint_id and M.short_of(hint_id) == short and hint_id in cands:
        return hint_id
    # exits fingerprint: exact match
    if exits:
        es = set(exits)
        exact = [c for c in cands if set(M.exits_of(c)) == es]
        if len(exact) == 1:
            return exact[0]
        # subset match: map exits ⊆ actual (game may show extra exits). Require a
        # NON-EMPTY overlap so a room with no mapped exits (an incomplete map
        # entry, e.g. d/qujing/yinwu/shanmen) can't spuriously match everything.
        sub = [c for c in cands
               if M.exits_of(c) and set(M.exits_of(c)).issubset(es)]
        if len(sub) == 1:
            return sub[0]
        # reverse subset: actual seen exits ⊆ map exits (game may hide some)
        sup = [c for c in cands
               if M.exits_of(c) and es.issubset(set(M.exits_of(c)))]
        if len(sup) == 1:
            return sup[0]
    return None  # ambiguous

def look_and_id(s, M, hint_id=None, area_dirs=None):
    """Look at current room, return (room_id_or_None, desc, short, exits)."""
    drain(s, quiet=0.3, maxt=1.0)
    desc = m(s, "look", q=1.2)
    handle_madao(s, desc)
    short = parse_short(desc)
    exits = parse_exits(desc)
    rid = identify(M, short, exits, hint_id, area_dirs)
    return rid, desc, short, exits

# ── movement ───────────────────────────────────────────────────────────
MOVE_FAIL = ("方向没有", "不能往", "没有出口", "无法往", "那个方向",
             "没有路", "走不通", "这个方向", "不能到")

DEATH_SIGNS = ("你死了", "你已经死亡", "你在地狱", "你升天了")
COMBAT_SIGNS = ("想杀死你", "正盯着", "缓缓地移动脚步", "寻找进攻")

def handle_madao(s, r):
    """If 马盗 is present or demanding money, pay immediately.
    Returns True if we handled it (caller should re-look before continuing)."""
    if "马盗" in r:
        if "要钱" in r or "买路钱" in r or "不给钱" in r or any(c in r for c in COMBAT_SIGNS):
            print("  [马盗] detected — paying 10 silver")
            m(s, "give ma dao 10 silver", q=2.0)
            time.sleep(1)
            return True
    return False

def is_dead(r):
    return any(w in r for w in DEATH_SIGNS)

def parse_hp(hr):
    """Parse `hp` output. Returns dict with (cur,max) for 气血/精神/食物/饮水.
    Format: '气血：  264/  264 (100%)    内力： ...' — match by name label."""
    out = {}
    for label in ("气血", "精神", "食物", "饮水"):
        mm = re.search(rf"{label}：\s*(\d+)\s*/\s*(\d+)", hr)
        if mm:
            out[label] = (int(mm.group(1)), int(mm.group(2)))
    return out

def step(s, d):
    r = m(s, d, q=0.7)  # long enough to receive full room desc on success
    handle_madao(s, r)
    return r, not any(w in r for w in MOVE_FAIL)

# ── BFS navigation ─────────────────────────────────────────────────────
def goto(s, M, goal_id, max_steps=150, area_dirs=None):
    """Navigate to goal_id. Look before every step to confirm position.
    Tracks (prev_id, last_dir) so ambiguous room names resolve via adjacency.
    area_dirs constrains room identification to the mission area.
    Returns True if arrived, False if stuck."""
    prev_id = None
    last_dir = None
    fail_streak = 0  # consecutive failed steps on the same direction
    last_fail_dir = None
    for attempt in range(max_steps):
        rid, desc, short, exits = look_and_id(s, M, hint_id=goal_id,
                                              area_dirs=area_dirs)

        # If identify() failed but we have prev_id+last_dir, resolve via map
        if rid is None and prev_id and last_dir:
            # The room we should be in after moving last_dir from prev_id
            expected = M.exits_of(prev_id).get(last_dir) or \
                next((nb for nb, dd in M.adj.get(prev_id, {}).items()
                      if dd == last_dir), None)
            if expected and M.short_of(expected) == short:
                rid = expected

        if rid == goal_id or short == M.short_of(goal_id):
            return True

        # If 马盗 is in the room, pay and re-look before doing anything else.
        if "马盗" in desc:
            handle_madao(s, desc)
            time.sleep(2)
            continue  # re-look next iteration

        # If we're in mid-combat (not a mission fight), wait for it to resolve.
        if any(c in desc for c in COMBAT_SIGNS) and "马盗" not in desc:
            print("  [nav] in unexpected combat — waiting 5s")
            time.sleep(5)
            continue

        if rid is None:
            if not exits:
                print(f"  [nav] stuck: no exits at '{short}'"); return False
            # Wander toward goal: pick exit that isn't a backtrack
            avoid = REVERSE.get(last_dir)
            d = next((e for e in exits if e != avoid), next(iter(exits)))
            _, moved = step(s, d)
            if moved: last_dir = d
            continue

        # BFS from confirmed position
        path = M.path(rid, goal_id)
        if path is None:
            print(f"  [nav] no path from {rid} to {goal_id}"); return False
        if not path:
            return True
        d, nxt = path[0]
        r, moved = step(s, d)
        if is_dead(r):
            print("  [nav] died during navigation"); return "dead"
        # Detect a "silent" non-move for VERB edges (dive/swim/climb) that fail
        # WITHOUT a MOVE_FAIL string. Only for non-compass verbs — compass moves
        # between same-named rooms (e.g. the 海底 chain) are legit moves.
        s_short = parse_short(r)
        if moved and d not in EXIT_TOKENS and s_short and s_short == short:
            moved = False
            print(f"  [nav] '{d}' did not change room ('{short}') — treating as blocked")
        if moved:
            prev_id = rid
            last_dir = d
            fail_streak = 0
            last_fail_dir = None
            # Try to identify the new room FROM the step response (skip explicit look)
            s_exits = parse_exits(r)
            s_rid = identify(M, s_short, s_exits, hint_id=nxt, area_dirs=area_dirs)
            if s_rid is not None:
                rid = s_rid
                if rid == goal_id or s_short == M.short_of(goal_id):
                    return True
                continue  # skip look_and_id next iteration
        else:
            if d == last_fail_dir:
                fail_streak += 1
            else:
                fail_streak = 1
                last_fail_dir = d
            if fail_streak >= 3:
                print(f"  [nav] direction '{d}' failed {fail_streak}x — blocked or phantom edge, giving up")
                return False
            print(f"  [nav] blocked going {d} from {short} (attempt {fail_streak})")
    print(f"  [nav] max steps reached"); return False

# ── monsters ───────────────────────────────────────────────────────────
def has_monster(desc, name):
    for line in desc.split("\n"):
        if "(" in line and ")" in line and name in line:
            return True
    return False

def fight(s, name, ids=None):
    """Engage the monster. ids = preferred target ids from Yuan (e.g. ['qingshe']),
    tried before the generic guai/jing fallbacks."""
    print(f"  >> ENGAGING {name}")
    tids = list(ids or []) + ["guai", "jing"]
    for tid in tids:
        m(s, f"follow {tid}", q=0.8)
    engaged = False
    for _ in range(3):
        for tid in tids:
            r = m(s, f"kill {tid}", q=1.5)
            if any(w in r for w in ("喝道","想杀","领教","奉陪")):
                print(f"  >> engaged"); engaged = True; break
        if engaged: break
        time.sleep(1)
    if not engaged:
        print("  !! could not engage"); return False
    # Victory strings — NOTE: 青烟 removed (matches the 厢房 incense-burner room
    # description and false-triggers a win). A real kill uses 死了/服了/etc.
    VICTORY = ("死了", "服了", "投降", "化做一道青光", "原形", "领罪", "走开", "大赦")
    for j in range(70):
        time.sleep(3)
        r = clean(drain(s, quiet=1.8, maxt=5.0))
        if not r: continue
        # Monster died? Require the monster to be the subject (name present) to
        # avoid matching unrelated room/other-mob text.
        if any(w in r for w in VICTORY) and (name in r or "领罪" in r or "大赦" in r):
            print("  *** VICTORY ***"); return True
        if is_dead(r): print("  !! WE DIED"); return "dead"
        if "承让" in r: print("  LOST"); return False
        if "清醒" in r:
            # KO'd (passed out) — guai likely disappears; signal mission reset needed
            print("  !! KO'd (passed out) — guai gone, need mission reset")
            return "mission_lost"
        # Flee: distinguish MONSTER fleeing (chase — it's almost dead) from OUR
        # wimpy flee (rest & retry). Monster-flee line contains the monster name.
        if any(w in r for w in ("落荒而逃", "仓皇逃走", "逃跑", "夺路而逃")):
            if name in r:
                d = _chase_dir(r)
                if d:
                    print(f"  [CHASE] {name} fled {d} — pursuing")
                    step(s, d)
                    for tid in tids:  # re-engage in the new room
                        rr = m(s, f"kill {tid}", q=1.2)
                        if any(w in rr for w in ("喝道","想杀","领教","奉陪")):
                            break
                    continue
                print(f"  [CHASE] {name} fled but no direction — will re-search")
                return "monster_fled"
            print("  [WIMPY] we fled — recover HP and retry")
            return "fled"
    return False

# Chinese exit words → English direction, for chasing a fleeing monster.
_CN_DIR = {
    "东北": "northeast", "西北": "northwest", "东南": "southeast", "西南": "southwest",
    "东": "east", "西": "west", "南": "south", "北": "north",
    "上": "up", "下": "down",
}

def _chase_dir(text):
    """Parse '<monster>往<dir>落荒而逃了' → English direction, or None."""
    mm = re.search(r"往([东西南北上下]+)", text)
    if not mm:
        return None
    return _CN_DIR.get(mm.group(1))

# ── sweep ──────────────────────────────────────────────────────────────
def _bfs_order(M, start_id, search_dirs, radius):
    """Room ids within search_dirs, ordered by hop distance from start (<=radius)."""
    seen = {start_id: 0}
    order = [start_id]
    q = deque([start_id])
    while q:
        u = q.popleft()
        if seen[u] >= radius:
            continue
        for nb in M.adj.get(u, {}):
            if nb in seen:
                continue
            seen[nb] = seen[u] + 1
            if _in_dirs(nb, search_dirs):
                order.append(nb)
                q.append(nb)
    return order

# Area small enough to fully sweep (the guai random_moves, so for a compact
# region like 高老庄 ~34 rooms we search all of it; only huge regions like
# 长安城 are vicinity-only to avoid the endless-circling problem).
MAX_FULL_SWEEP = 45

def sweep_vicinity(s, M, anchor_id, search_dirs, name, ids, radius=3):
    """Go to the landmark anchor, then search for the wandering monster.
    Small area → sweep the whole reachable region (guai drifts from landmark).
    Huge area → only the landmark's radius-hop vicinity. If still not found,
    return "not_found" so the caller waits rather than tight-looping.
    Gives up after STUCK_SECS total."""
    low = eat_drink_if_needed(s)   # top up food/water before heading out
    if low:                        # ran out of food/water — restock at kezhan
        restock_consumables(s, M)
    wait_full_hp(s)          # rest until 气血 and 精神 are full before engaging
    t_start = time.time()
    print(f"  -> landmark {M.short_of(anchor_id)} ({anchor_id})")
    r = goto(s, M, anchor_id, area_dirs=search_dirs, max_steps=200)
    if r == "dead": return "dead"
    if not r:
        print(f"  [sweep] could not reach anchor {M.short_of(anchor_id)} — aborting")
        return "not_found"
    # Full reachable area from the anchor (within search_dirs).
    full = _bfs_order(M, anchor_id, search_dirs, 999)
    if len(full) <= MAX_FULL_SWEEP:
        order = full
        print(f"  small area ({len(full)} rooms) — full sweep")
    else:
        order = _bfs_order(M, anchor_id, search_dirs, radius)
        print(f"  large area ({len(full)} rooms) — vicinity only: {len(order)} within {radius} hops")
    engaged = False   # did we ever actually fight it? (for Yuan 除尽 confirmation)
    for room_id in order:
        if time.time() - t_start > STUCK_SECS:
            print(f"  [TIMEOUT] sweep exceeded {STUCK_SECS}s")
            return "engaged_lost" if engaged else "not_found"
        r = goto(s, M, room_id, area_dirs=search_dirs, max_steps=200)
        if r == "dead": return "dead"
        if not r: continue
        desc = m(s, "look", q=1.2)
        if has_monster(desc, name):
            print(f"  ** {name} found in {M.short_of(room_id)} **")
            engaged = True
            for _retry in range(5):  # several attempts (wimpy recovery / chasing)
                result = fight(s, name, ids)
                if result is True: return True
                if result == "dead": return "dead"
                if result == "mission_lost": return "mission_lost"
                if result == "monster_fled":
                    # Monster ran but we're healthy — re-scan this room's
                    # neighborhood to re-engage (no rest needed).
                    found = False
                    for nb in [room_id] + list(M.adj.get(room_id, {})):
                        if goto(s, M, nb, area_dirs=search_dirs, max_steps=40) is True:
                            if has_monster(m(s, "look", q=1.0), name):
                                found = True; break
                    if found:
                        continue
                    break
                if result == "fled":
                    # WE fled (low HP) — eat/drink, rest to full, then retry
                    eat_drink_if_needed(s)
                    wait_full_hp(s)
                    r2 = goto(s, M, room_id, area_dirs=search_dirs, max_steps=200)
                    if r2 == "dead": return "dead"
                    desc = m(s, "look", q=1.2)
                    if not has_monster(desc, name):
                        print("  [RECOVER] monster left the room — searching again")
                        break
                    continue
                break  # False/None = lost clean, move on
    # If we fought it but never saw a clean kill, it may have died off-screen —
    # signal "engaged_lost" so main() can confirm via Yuan's 除尽. Otherwise the
    # guai was never here (mission expired / wandered off).
    if engaged:
        print(f"  fought {name} but lost track — Yuan will confirm if it died")
        return "engaged_lost"
    print(f"  {name} not near landmark — mission likely expired")
    return "not_found"

# ── mission persistence ────────────────────────────────────────────────
# Guai lifetime (from yaoguai.c:528 stay_time=+1800, yuantiangang.c:134 reminder
# window <t+1800). The guai lives 30 min from assignment; after that yuan rolls
# a new one. It random_moves, so it drifts from its landmark over those 30 min.
MISSION_TTL = 1800  # seconds a guai/mission stays alive

def save_mission(name, ids, region, landmark, t_start=None):
    if t_start is None:
        t_start = int(time.time())
    try:
        open(MFILE,"w",encoding="utf-8").write(
            f"{name}|{' '.join(ids or [])}|{region or ''}|{landmark or ''}|{t_start}")
    except Exception: pass

def load_mission():
    try:
        p = (open(MFILE,encoding="utf-8").read().strip().split("|"))
        p += [""] * (5 - len(p))
        name, ids, region, landmark = p[0], p[1].split(), p[2] or None, p[3] or None
        t_start = int(p[4]) if p[4] else 0
        return name, ids, region, landmark, t_start
    except Exception:
        return None, [], None, None, 0

def mission_age(t_start):
    """Seconds since the mission was assigned (0 if unknown)."""
    return int(time.time()) - t_start if t_start else 0

def mission_expired(t_start):
    """True if the 30-min guai lifetime has elapsed."""
    return t_start and mission_age(t_start) >= MISSION_TTL

# ── mission parsing ────────────────────────────────────────────────────
# 近有青蛇怪(Qingshe guai)在开封城（春醇茶栈一带）出没
RE_MISSION = re.compile(
    r"近有(?P<name>.+?)\((?P<id>[\w ]+)\)在(?P<region>[^（(]+?)"
    r"(?:[（(](?P<landmark>[^）)]+?)一带[）)])?出没")

def parse_mission(text):
    """Return (name, ids, region, landmark) or (None, [], None, None)."""
    mm = RE_MISSION.search(text)
    if not mm:
        return None, [], None, None
    name = mm.group("name")
    ids = mm.group("id").lower().split()          # e.g. ['qingshe', 'guai']
    region = mm.group("region").strip()
    landmark = (mm.group("landmark") or "").strip() or None
    return name, ids, region, landmark

# Directories a mission guai can actually spawn in (from yaoguai.c dirs1/2/3).
# A landmark short-name may exist in several dirs; only these are valid spawns,
# so we must resolve to one of them (e.g. 御花园 → d/sea, NOT d/huanggong).
SPAWN_DIRS = (
    "d/city", "d/westway", "d/kaifeng", "d/lingtai", "d/moon", "d/gao",
    "d/sea", "d/nanhai", "d/eastway", "d/ourhome/honglou",
    "d/xueshan", "d/qujing", "d/penglai", "d/death", "d/meishan",
)

def _is_spawn_dir(rid):
    return any(rid.startswith(d.rstrip("/") + "/") for d in SPAWN_DIRS)

# Dirs we can ACTUALLY reach (graph-reachable ≠ walkable: d/qujing/d/death are
# graph-connected but gated by NPCs/quests in-game). Foot-reachable spawn dirs
# plus d/sea (龙宫, via `dive` — yxcdrg is a 东海龙宫 disciple).
ACCESSIBLE_DIRS = (
    "d/city", "d/westway", "d/kaifeng", "d/lingtai", "d/gao", "d/eastway",
    "d/sea",
)

def _is_accessible(rid):
    return any(rid.startswith(d + "/") for d in ACCESSIBLE_DIRS)

def resolve_target(M, region, landmark):
    """Resolve mission to (anchor_id, search_dirs).
    search_dirs bounds the search + identify(); anchor is where to start.
    Returns (None, []) if the region is unknown/unreachable."""
    dirs = M.area_dirs_for_region(region) if region else []
    anchor = None
    # Landmark-less palace/special rooms: Yuan says "在<room>出没" with no
    # （…一带）clause, so the parser puts the ROOM short-name in `region`. If
    # that word isn't a find.map region but IS a room short-name, use it as
    # the landmark (e.g. 御花园 → the 御花园 room).
    if not dirs and not landmark and region and region in M.by_short:
        landmark = region
    if landmark:
        cands = M.by_short.get(landmark, [])
        if dirs:
            scoped = [c for c in cands if _in_dirs(c, dirs)]
            if scoped:
                cands = scoped
        # Only rooms in real spawn dirs can hold the guai. This picks 龙宫's
        # 御花园 (d/sea) over the palace copy (d/huanggong, never a spawn).
        spawn_cands = [c for c in cands if _is_spawn_dir(c)]
        if spawn_cands:
            cands = spawn_cands
        # Prefer candidates we can actually reach (d/sea via dive over d/qujing
        # dungeons that are graph-connected but gated in-game).
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
            # Landmark's own directory is authoritative for the search scope.
            dirs = [anchor.rsplit("/", 1)[0]]
    if not dirs:
        return None, []
    if anchor is None:
        # No usable landmark: start from any room in the region's dirs.
        pool = [r for d in dirs for r in M.rooms_under(d) if M.exits_of(r)]
        anchor = pool[0] if pool else None
    # Reject anchors in dirs we can't actually walk to (d/qujing/d/death/etc are
    # graph-connected but gated in-game) → main() treats as unreachable & waits.
    if anchor is not None and not _is_accessible(anchor):
        return None, []
    return anchor, dirs

# ── yuan ───────────────────────────────────────────────────────────────
def ask_yuan(s, M):
    """Return (name, ids, region, landmark, t_start, cleared).
    cleared=True when Yuan says "妖魔已经除尽了" (除尽) — authoritative proof the
    PREVIOUS mission guai was killed (yaoguai.c die() sets done1 → yuan says
    除尽). This catches kills we didn't visually see (e.g. we wimpy-ran and the
    guai died from our last hit). t_start = when the guai was assigned."""
    goto(s, M, LANDMARKS["yuan"])
    r = m(s, "ask yuan about kill", q=3.0)
    print("  --- YUAN ---")
    for ln in r.split("\n"):
        if "袁天罡" in ln or "近有" in ln or "收服" in ln: print("   ", ln.strip())
    cleared = "除尽" in r
    name, ids, region, landmark = parse_mission(r)
    if not name and cleared:
        r = m(s, "ask yuan about kill", q=3.0)
        name, ids, region, landmark = parse_mission(r)
    if name:
        # NEW mission ("近有...出没") — the guai just spawned, clock starts now.
        t_start = int(time.time())
        save_mission(name, ids, region, landmark, t_start)
        return name, ids, region, landmark, t_start, cleared
    # Reminder form "在下不是请您去收服X吗?" — same guai as before, keep its clock.
    mm = re.search(r"收服(.+?)吗", r)
    if mm:
        want = mm.group(1)
        sn, sids, sreg, slm, st = load_mission()
        if sn == want:
            return sn, sids, sreg, slm, st, cleared
        return want, [], None, None, 0, cleared
    return None, [], None, None, 0, cleared

# ── connect / recovery ─────────────────────────────────────────────────
# IMPORTANT position model:
#   * Plain socket reconnect  -> char stays at its LAST position (no anchor).
#   * The `quit` command      -> char respawns at kezhan BUT loses ALL items.
# So the only reliable way to reach a known start is quit+relog, then re-gear.

def raw_login(M):
    """Open socket + log in. Char lands at its last position (NOT kezhan)."""
    s = socket.create_connection((HOST, PORT), timeout=15)
    drain(s, quiet=3.0, maxt=12.0)
    m(s,"gb"); m(s,"no"); m(s, USER)
    r = send(s, PASS, quiet=4.0)
    if "y/n" in r: m(s,"y",q=4.0)
    m(s, "set wimpy 15")   # flee early — death wipes all money/xp
    return s

def quit_relog(s, M):
    """Issue the `quit` command (drops all items, anchors at kezhan), then
    reconnect. Returns a NEW socket freshly logged in AT KEZHAN."""
    try: m(s, "quit", q=3.0)
    except Exception: pass
    try: s.close()
    except Exception: pass
    time.sleep(3)
    return raw_login(M)

def _money_from_score(sc):
    """Parse total wealth in 两 from score text.
    Includes silver (两) + gold coins converted (1 gold = 100两)."""
    mm = re.search(r"(\d+)\s*两", sc)
    liang = int(mm.group(1)) if mm else 0
    mm2 = re.search(r"(\d+)\s*钱", sc)
    qian = int(mm2.group(1)) if mm2 else 0
    # Gold coins show as e.g. "黄金 X 些" or "X some gold" in inventory/score
    mm3 = re.search(r"黄金[^0-9]*(\d+)", sc)
    gold = int(mm3.group(1)) if mm3 else 0
    return liang + qian / 10.0 + gold * 100

KEEP_ON_HAND = 50  # keep 50两 on hand (food/water/马盗 tolls); deposit the rest

def bank_account(s, M):
    """Go to 相记钱庄, check account balance. Returns balance string."""
    goto(s, M, LANDMARKS["bank"])
    r = m(s, "account", q=2.0)
    print(f"  [BANK] account: {r.strip()[:120]}")
    return r

def bank_deposit_excess(s, M):
    """Deposit everything above KEEP_ON_HAND两 into 相记钱庄.
    Deposits gold coins directly, then deposits excess silver.
    Call after each kill loot pickup to protect money from death."""
    goto(s, M, LANDMARKS["bank"])
    # Deposit any gold coins in inventory directly
    m(s, "deposit gold", q=2.0)
    sc = m(s, "score", q=2.0)
    on_hand = _money_from_score(sc)
    if on_hand <= KEEP_ON_HAND:
        print(f"  [BANK] on hand {on_hand:.1f}两 ≤ {KEEP_ON_HAND} — nothing to deposit")
        return
    to_deposit = int(on_hand - KEEP_ON_HAND)
    if to_deposit <= 0:
        return
    r = m(s, f"deposit {to_deposit} silver", q=2.0)
    print(f"  [BANK] deposited {to_deposit}两: {r.strip()[:80]}")

def bank_withdraw_for_gear(s, M, need=20):
    """Withdraw enough from bank to buy gear (blade+shield = ~15両).
    Deposits any gold coins in inventory first, then withdraws silver if needed."""
    sc = m(s, "score", q=2.0)
    on_hand = _money_from_score(sc)
    if on_hand >= need:
        return on_hand
    goto(s, M, LANDMARKS["bank"])
    # Deposit gold coins first so they're in the bank as gold balance
    m(s, "deposit gold", q=2.0)
    sc = m(s, "score", q=2.0)
    on_hand = _money_from_score(sc)
    if on_hand >= need:
        return on_hand
    to_withdraw = need - int(on_hand)
    r = m(s, f"withdraw {to_withdraw} silver", q=2.0)
    print(f"  [BANK] withdrew {to_withdraw}两: {r.strip()[:80]}")
    sc = m(s, "score", q=2.0)
    after = _money_from_score(sc)
    print(f"  [BANK] on hand now: {after:.1f}两")
    return after

def get_gold(s, M, times=3):
    """At kezhan, 大爷 (da ye) gives gold. Only one-time — verify via score."""
    goto(s, M, LANDMARKS["kezhan"])
    before_sc = m(s, "score", q=2.0)
    before = _money_from_score(before_sc)
    for _ in range(times):
        r = m(s, "ask da ye about gold", q=1.5)
        if not any(w in r for w in ("给", "gold", "两", "钱")): break
    after_sc = m(s, "score", q=2.0)
    after = _money_from_score(after_sc)
    got = after - before
    print(f"  [GOLD] asked 大爷: before={before:.1f}两 after={after:.1f}两 got={got:.1f}两")
    return after  # returns current money

# Messages that mean "stop — full or rate-limited (can't consume more now)"
_FULL_MSGS = ("饱了", "不想喝", "喝不下", "吃不下", "喝太多", "灌不下", "吃太多")
# Messages that mean "the item is gone/empty — can't refill from inventory"
_EMPTY_MSGS = ("一滴也不剩", "一点也不剩", "没有", "什么", "不懂", "干干净净")

def eat_drink_if_needed(s):
    """Eat/drink until food and water are full (read from `hp`).
    Returns a set of labels ({'食物','饮水'}) still low because we ran OUT of
    the item (empty containers) — caller can restock."""
    hr = m(s, "hp", q=1.5)
    hp = parse_hp(hr)
    still_low = set()
    for label, cmd in [("食物", "eat gou rou"), ("饮水", "drink jiudai")]:
        if label not in hp:
            continue
        cur, mx = hp[label]
        if cur < mx:
            print(f"  [{label}] {cur}/{mx} — refilling")
            ran_out = False
            for _ in range(15):  # spam until full or out of items
                r = m(s, cmd, q=0.5)
                if any(w in r for w in _FULL_MSGS):
                    break
                if any(w in r for w in _EMPTY_MSGS):
                    print(f"  [{label}] out of items — need restock")
                    ran_out = True
                    break
            if ran_out:
                still_low.add(label)
    return still_low

def restock_consumables(s, M):
    """Go to 南城客栈 (kezhan): refill empty 桂花酒袋 with `fill jiudai` (cheap),
    buy more 红烧狗肉 for food, then eat/drink to full."""
    print("  [RESTOCK] heading to kezhan for food/water")
    goto(s, M, LANDMARKS["kezhan"])
    # Refill the wine bags we already carry (cheaper than buying new ones)
    m(s, "fill jiudai", q=1.0)
    # Top up food; buy a few more gou rou in case we're out
    for _ in range(8):
        r = m(s, "buy gou rou from xiao er", q=0.6)
        if any(w in r for w in ("钱不够", "没有卖", "什么")):
            break
    eat_drink_if_needed(s)

def wait_full_hp(s, tries=40):
    """Rest until 气血 AND 精神 are full (both regen over time). The user's
    rule: never engage without full HP and 精神."""
    for _ in range(tries):
        hr = m(s, "hp", q=1.0)
        hp = parse_hp(hr)
        qixue = hp.get("气血", (1, 1))
        jingshen = hp.get("精神", (1, 1))
        print(f"  [HP] 气血 {qixue[0]}/{qixue[1]}  精神 {jingshen[0]}/{jingshen[1]}")
        if qixue[0] >= qixue[1] and jingshen[0] >= jingshen[1]:
            return True
        time.sleep(6)  # regen tick
    print("  [HP] timed out waiting for full HP/精神 — proceeding anyway")
    return False

def gear_up(s, M):
    """Gear up: first pick up any dropped gear at yuan (天监台), then buy from shop."""
    # Step 1: check yuan's location for dropped armor/weapons the user may have left
    goto(s, M, LANDMARKS["yuan"])
    r = m(s, "look", q=1.5)
    if any(w in r for w in ("甲", "盔", "盾", "刀", "剑", "枪", "叉", "袍", "衣", "护", "马", "肉", "酒")):
        print("  [GEAR] items at yuan — picking up")
        m(s, "get all", q=1.5)
        # Remove/drop default linen before equipping better gear
        m(s, "unwield all", q=1.0)
        m(s, "remove all", q=1.0)
        m(s, "drop coarse", q=1.0)   # 粗布衣(Coarse) — inferior to 战袍
        m(s, "wield all", q=1.0)
        m(s, "wear all", q=1.0)
    # Eat and drink to full — food/water is critical for HP regen
    eat_drink_if_needed(s)
    # Mount the horse if we have one (faster travel)
    rm = m(s, "mount ma", q=1.5)
    if "骑上" in rm or "骑着" in rm:
        print("  [HORSE] mounted 黑马 for faster travel")
    sc = m(s, "score", q=2.5)
    def stat(pat):
        mm = re.search(pat, sc); return int(mm.group(1)) if mm else 0
    dmg = stat(r"兵器伤害力：\[\s*(\d+)"); arm = stat(r"盔甲保护力：\[\s*(\d+)")
    print(f"  gear dmg={dmg} armor={arm}")
    # base armor from clothing is ~1; treat < 10 as "needs a shield".
    need_wpn, need_arm = dmg == 0, arm < 10
    if need_wpn or need_arm:
        # Deposit any gold coins so they're available to withdraw as silver
        goto(s, M, LANDMARKS["bank"])
        m(s, "deposit gold", q=2.0)
        money = get_gold(s, M)  # one-time gold from 大爷 (may already be claimed)
        if money < 15:
            # Try bank withdrawal — main protection against death money-wipe
            money = bank_withdraw_for_gear(s, M, need=15)
        print(f"  money available: {money:.1f}两")
        if money < 0.05:
            print("  !! no money — skipping shop, will fight with bare hands")
        else:
            goto(s, M, LANDMARKS["shop"])
            print("  --- 兵器铺 stock ---")
            for ln in m(s, "list", q=1.5).split("\n"):
                if ln.strip(): print("   ", ln.strip())
            bought = False
            if need_wpn:  # prioritize damage: 钢刀(25) first, then cheaper options
                for wpn in ("blade", "spear", "sword", "fork", "dagger"):
                    r = m(s, f"buy {wpn} from xiao xiao", q=1.3)
                    if "钱不够" in r or "什么" in r:  # broke or bad id — try next
                        continue
                    bought = True; break
            if need_arm:
                r = m(s,"buy shield from xiao xiao",q=1.3)
                if "钱不够" not in r and "什么" not in r: bought = True
            if bought:
                # wield AND wear everything we now hold
                m(s, "wield all", q=1.0)
                m(s, "wear all", q=1.0)
            else:
                print("  !! could not buy gear despite having money")
        sc = m(s, "score", q=2.5)
        dmg = stat(r"兵器伤害力：\[\s*(\d+)"); arm = stat(r"盔甲保护力：\[\s*(\d+)")
        print(f"  gear after buy: dmg={dmg} armor={arm}")

# When lost in a stack of same-named rooms (e.g. 大雁塔内 dyt1-7), head toward
# the ground/exit — an end room is uniquely identifiable ({out,up} or {down}).
_LOCALIZE_PREF = ["out", "down", "west", "south", "east", "north", "enter", "up"]

def localize(s, M, tries=16):
    """Find our current room WITHOUT quitting (protects money/gear).
    Walk until we land in a uniquely-identifiable room. Returns rid or None."""
    for _ in range(tries):
        rid, desc, short, exits = look_and_id(s, M)
        if rid is not None:
            print(f"  [LOC] at {short} ({rid})")
            return rid
        # ambiguous/unknown — step toward the exit/ground (prefer out/down) so
        # stacked same-named rooms resolve at an identifiable end room.
        if not exits:
            break
        d = next((p for p in _LOCALIZE_PREF if p in exits), next(iter(exits)))
        step(s, d)
    print("  [LOC] could not localize in place")
    return None

def already_geared(s):
    """True if char already has a weapon (dmg>0) — gear persists across short
    disconnects, so we can skip the walk-to-yuan/shop gear_up entirely."""
    sc = m(s, "score", q=2.0)
    mm = re.search(r"兵器伤害力：\[\s*(\d+)", sc)
    return bool(mm and int(mm.group(1)) > 0)

def prepare(s, M, allow_quit_reset=True):
    """Ready the char: localize in place. Only gear up if actually unarmed
    (gear persists across short disconnects, so usually we resume in place).
    Only quit-resets to kezhan (losing items) if truly lost AND allowed."""
    rid = localize(s, M)
    if rid and rid.startswith(OURHOME_PREFIX):
        # Landed in disconnected ourhome after death respawn — escape first.
        s = escape_ourhome(s, M)
        rid = localize(s, M)
    if rid is None and allow_quit_reset:
        print("  [LOC] lost -> quit+relog to kezhan (loses money/items!)")
        s = quit_relog(s, M)
        localize(s, M)
    # Only gear up if we're actually unarmed — otherwise resume where we are.
    if not already_geared(s):
        print("  [PREPARE] unarmed — running gear_up")
        gear_up(s, M)
    else:
        print("  [PREPARE] already geared — resuming in place (no walk-back)")
        if eat_drink_if_needed(s):   # out of food/water → restock at kezhan
            restock_consumables(s, M)
    return s

def connect_login(M):
    s = raw_login(M)
    print("[SETUP]")
    # Don't quit-reset at startup — we may be carrying gifted money/gear.
    return prepare(s, M, allow_quit_reset=False)

OURHOME_PREFIX = "d/ourhome/"

def escape_ourhome(s, M):
    """Called when stuck in d/ourhome after death respawn.
    xiaoer's init() already resets startroom→kezhan, so we just need to
    die (or find a way out) to get back. Try recall and common teleport
    commands; if still stuck, quit again and reconnect — startroom is now
    kezhan so respawn will land there."""
    print("  [ourhome] attempting escape (recall/go commands)")
    for cmd in ("recall", "go longmen", "go east", "go north", "go west", "go out"):
        r = m(s, cmd, q=2.0)
        if is_dead(r):
            break  # died — respawn at kezhan now that xiaoer fixed startroom
        # Re-localize to see if we escaped
        rid, _, _, _ = look_and_id(s, M)
        if rid and not rid.startswith(OURHOME_PREFIX):
            print(f"  [ourhome] escaped to {rid}")
            return s
    # Still in ourhome — quit again; startroom is now kezhan so respawn there.
    print("  [ourhome] quit+relog (startroom now kezhan)")
    s = quit_relog(s, M)
    rid, _, _, _ = look_and_id(s, M)
    if rid and rid.startswith(OURHOME_PREFIX):
        print("  [ourhome] still in ourhome after 2nd quit — trying escape again")
        for cmd in ("recall", "go longmen", "go east", "go north"):
            m(s, cmd, q=2.0)
            rid, _, _, _ = look_and_id(s, M)
            if rid and not rid.startswith(OURHOME_PREFIX):
                break
    return s

def recover_to_kezhan(s, M):
    """Deliberate unstick when dead/lost: quit (lose items, respawn at startroom),
    relog, re-gear. Returns the NEW ready socket."""
    print("  [RECOVER] lost/stuck -> quit + relog to kezhan (re-gearing)")
    s = quit_relog(s, M)
    # If we landed in ourhome (disconnected area), escape first.
    rid = localize(s, M)
    if rid and rid.startswith(OURHOME_PREFIX):
        s = escape_ourhome(s, M)
    return prepare(s, M)

STUCK_SECS = 600  # 10 min per mission sweep before giving up
MAX_ATTEMPTS = 120  # outer loop cap (enough for several 30-min timers)

# ── main ───────────────────────────────────────────────────────────────
def main():
    open(LOG,"w",encoding="utf-8").write("=== XYJBOT ===\n")
    M = XYJMap()
    print(f"[MAP] {len(M.g)} rooms loaded")
    s = connect_login(M)

    kills = 0
    nf_name, nf_count = None, 0   # track repeated not_found on the same target
    # Seed pending_guai from the last saved mission so a kill we made just before
    # a restart is still confirmed by Yuan's 除尽 on the first ask.
    _lm_name, _, _, _, _ = load_mission()
    pending_guai = _lm_name      # target we were fighting but didn't see die
    for attempt in range(MAX_ATTEMPTS):
        if kills >= TARGET_KILLS: break
        print(f"\n[ATTEMPT {attempt+1}] kills={kills}/{TARGET_KILLS}")
        name, ids, region, landmark, t_start, cleared = ask_yuan(s, M)
        # Yuan says 除尽 → the previous guai IS dead. Count it if we were on it
        # (covers kills we didn't visually see because wimpy ran us out).
        if cleared and pending_guai:
            kills += 1
            total = tally_add(1)
            print(f"\n  *** KILL confirmed by Yuan (除尽): {pending_guai}"
                  f"  |  run {kills}/{TARGET_KILLS}, LIFETIME {total} ***")
            pending_guai = None
            if kills >= TARGET_KILLS: break
        if not name:
            print("  no mission; wait 20s"); time.sleep(20); continue
        age = mission_age(t_start)
        print(f"  Mission: {name} ids={ids} region={region} landmark={landmark} "
              f"(age {age}s / {MISSION_TTL}s)")
        # If the 30-min guai lifetime is up, the target is despawning — re-ask
        # (yuan will roll a fresh mission) instead of chasing a dead one.
        if mission_expired(t_start):
            print(f"  mission expired ({age}s ≥ {MISSION_TTL}s) — re-asking for a new guai")
            time.sleep(2); continue
        # Unreachable-mission wait: sleep most of the remaining lifetime in one
        # go (nothing we can do until yuan rolls a fresh guai at expiry).
        def wait_out_expiry(reason):
            remain = MISSION_TTL - mission_age(t_start)
            nap = max(30, min(remain + 5, 600))  # cap a single nap at 10 min
            print(f"  {reason}; waiting {nap}s (mission {mission_age(t_start)}s/{MISSION_TTL}s)")
            time.sleep(nap)

        anchor, search_dirs = resolve_target(M, region, landmark)
        if anchor is None or not search_dirs:
            wait_out_expiry("unknown/unreachable region"); continue
        # Reachability from hub into the search dirs.
        from xyjmap import LANDMARKS as LM
        test_path, _ = M.path_to_pred(LM["hub"], lambda r: _in_dirs(r, search_dirs))
        if test_path is None:
            wait_out_expiry(f"{search_dirs} unreachable"); continue

        # Check gear/money before attempting any mission.
        cur_sc = m(s, "score", q=2.0)
        _dm = re.search(r"兵器伤害力：\[\s*(\d+)", cur_sc)
        cur_dmg = int(_dm.group(1)) if _dm else 0
        cur_money = _money_from_score(cur_sc)
        # Skip dangerous areas when ungeared (马盗 patrols 长安城西 and kills without toll money)
        DANGEROUS_DIRS = ["d/westway"]
        if any(sd in DANGEROUS_DIRS for sd in search_dirs) and (cur_dmg == 0 or cur_money < 10):
            print(f"  [SKIP] {search_dirs} dangerous (dmg={cur_dmg} money={cur_money:.1f}两) — wait for safer mission")
            time.sleep(30); continue
        # If completely ungeared, try to gear up (convert gold + withdraw from bank) before skipping
        if cur_dmg == 0 and cur_money < 1:
            print(f"  [GEAR UP NEEDED] dmg=0 money={cur_money:.1f}两 — trying bank/convert")
            gear_up(s, M)
            # Re-check after gear attempt
            cur_sc2 = m(s, "score", q=2.0)
            _dm2 = re.search(r"兵器伤害力：\[\s*(\d+)", cur_sc2)
            cur_dmg = int(_dm2.group(1)) if _dm2 else 0
            if cur_dmg == 0:
                print("  still unarmed after gear attempt — waiting 60s")
                time.sleep(60); continue

        t0 = time.time()
        killed = sweep_vicinity(s, M, anchor, search_dirs, name, ids)
        elapsed = time.time() - t0
        if killed == "mission_lost":
            # KO'd during fight — guai is gone; recover HP then wait for yuan to reset
            print("  !! KO'd — guai gone. Recovering then waiting for mission reset (~30min)")
            eat_drink_if_needed(s)
            wait_full_hp(s)
            continue
        if killed is True:
            kills += 1
            total = tally_add(1)
            pending_guai = None    # counted; don't double-count via 除尽
            print(f"\n  *** KILL #{kills} this run: {name}  |  LIFETIME TOTAL: {total} ***")
            time.sleep(2); drain(s, quiet=1.0, maxt=3.0)
            m(s,"get all",q=1.5)
            # Deposit excess gold immediately — death wipes everything on hand
            bank_deposit_excess(s, M)
        elif killed == "engaged_lost":
            # We fought it but didn't see it die. Remember it; next ask_yuan's
            # 除尽 will confirm the kill (or not). Go back to Yuan now to check.
            print(f"  engaged {name} but unconfirmed — checking Yuan for 除尽")
            pending_guai = name
            continue
        elif killed == "dead":
            print("  !! WE DIED — quit+relog to kezhan, re-gear")
            s = recover_to_kezhan(s, M)
        elif killed == "not_found":
            # Swept the area (or vicinity) and the guai isn't reachable.
            nf_count = nf_count + 1 if name == nf_name else 1
            nf_name = name
            if nf_count >= 2:
                # Same target keeps coming back unfindable → the server guai is
                # stuck somewhere we can't reach. Wait out its 30-min lifetime so
                # yuan rolls a fresh one, instead of tight-looping.
                print(f"  {name} unfindable {nf_count}x — waiting 5min for it to expire")
                time.sleep(300)
                nf_count = 0
            else:
                print(f"  {name} not found — re-asking yuan")
                time.sleep(3)
        else:
            print(f"  !! did not find/kill {name} (took {elapsed:.0f}s)")

    print(f"\n=== DONE: {kills} kills this run | LIFETIME {tally_get()} ===")
    m(s,"hp",q=2.0)
    print("*** session end: closing socket (no casual quit) ***")
    time.sleep(1); s.close()

if __name__ == "__main__":
    main()
