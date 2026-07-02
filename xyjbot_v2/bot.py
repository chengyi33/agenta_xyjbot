"""
bot.py — Main loop + state machine for XYJ2000 autonomous kill bot.

Architecture: Dead reckoning navigation + incremental position tracking.
States: INIT → GEARING → MISSION → TRAVELING → SEARCHING → FIGHTING → LOOTING → BANKING → MISSION
Recovery: any → LOST → quit+relog → GEARING
"""
import time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import *
from map_engine import XYJMap
from nav import Navigator
from net import connect, disconnect, m, drain, clean, parse_short, parse_exits, is_dead, send
from economy import gear_up, eat_drink, restock, wait_full_hp, bank_deposit, already_geared
from mission import ask_yuan, resolve_target, sweep_vicinity, load_mission, save_mission
from mission import mission_age, mission_expired, MISSION_TTL
from combat import fight

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


def tally_get():
    try:
        return int(open(TALLY_PATH).read().strip() or 0)
    except Exception:
        return 0


def tally_add(n=1):
    v = tally_get() + n
    try:
        open(TALLY_PATH, "w").write(str(v))
    except Exception:
        pass
    return v


# ── Recovery ──────────────────────────────────────────────────────────
def escape_ourhome(s, nav):
    """Escape from d/ourhome after death respawn."""
    print("  [ourhome] attempting escape")
    for cmd in ("recall", "go longmen", "go east", "go north", "go west", "go out"):
        m(s, cmd, q=2.0)
        rid, _, _, _ = nav.look_and_identify()
        if rid and not rid.startswith(OURHOME_PREFIX):
            print(f"  [ourhome] escaped to {rid}")
            return True
    # Quit again — startroom should be kezhan now
    print("  [ourhome] quit+relog")
    try:
        m(s, "quit", q=3.0)
    except Exception:
        pass
    disconnect(s)
    time.sleep(3)
    s2 = connect()
    nav.s = s2
    nav.current_rid = None
    rid, _, _, _ = nav.look_and_identify()
    if rid and rid.startswith(OURHOME_PREFIX):
        for cmd in ("recall", "go longmen", "go east", "go north"):
            m(nav.s, cmd, q=2.0)
            rid, _, _, _ = nav.look_and_identify()
            if rid and not rid.startswith(OURHOME_PREFIX):
                break
    return True


def recover_to_kezhan(s, nav):
    """Full recovery: quit+relog (lose items), re-gear."""
    print("  [RECOVER] quit+relog to kezhan")
    try:
        m(s, "quit", q=3.0)
    except Exception:
        pass
    disconnect(s)
    time.sleep(3)
    s2 = connect()
    nav.s = s2
    nav.current_rid = None

    # Check if we're in ourhome
    rid, _, _, _ = nav.look_and_identify()
    if rid and rid.startswith(OURHOME_PREFIX):
        escape_ourhome(s2, nav)

    # Re-gear
    if not already_geared(s2):
        print("  [RECOVER] re-gearing")
        gear_up(s2, nav)
    return s2


# ── Main ──────────────────────────────────────────────────────────────
def main():
    open(LOG_PATH, "w", encoding="utf-8").write("=== XYJBOT v2 ===\n")
    M = XYJMap()
    print(f"[MAP] {len(M.g)} rooms loaded, {len(M.adj)} adjacency entries")

    s = connect()
    nav = Navigator(s, M)
    print("[CONNECTED]")

    # ── INIT: localize ─────────────────────────────────────────────────
    rid, desc, short, exits = nav.look_and_identify()
    if rid:
        print(f"[LOC] at {short} ({rid})")
        if rid.startswith(OURHOME_PREFIX):
            escape_ourhome(s, nav)
    else:
        print("[LOC] couldn't identify — continuing anyway")
        # Try to localize by walking
        nav.force_localize(M)

    # ── GEARING ────────────────────────────────────────────────────────
    if not already_geared(s):
        print("[GEARING] no weapon — gearing up")
        gear_up(s, nav)
    else:
        print("[GEARING] already equipped")
        if eat_drink(s):
            restock(s, nav)

    # ── MAIN LOOP ─────────────────────────────────────────────────────
    kills = 0
    nf_name, nf_count = None, 0
    _lm_name, _, _, _, _ = load_mission()
    pending_guai = _lm_name

    for attempt in range(120):
        if kills >= TARGET_KILLS:
            break

        print(f"\n[ATTEMPT {attempt+1}] kills={kills}/{TARGET_KILLS}")

        # ── MISSION: ask Yuan ─────────────────────────────────────────
        name, ids, region, landmark, t_start, cleared = ask_yuan(s, nav)

        # Check if previous mission was completed (除尽)
        if cleared and pending_guai:
            kills += 1
            total = tally_add(1)
            print(f"\n  *** KILL confirmed (除尽): {pending_guai} | run {kills}/{TARGET_KILLS} | LIFETIME {total} ***")
            pending_guai = None
            if kills >= TARGET_KILLS:
                break

        if not name:
            print("  no mission; wait 20s")
            time.sleep(20)
            continue

        age = mission_age(t_start)
        print(f"  Mission: {name} ids={ids} region={region} landmark={landmark} (age {age}s/{MISSION_TTL}s)")

        # Check expiry
        if mission_expired(t_start):
            print(f"  mission expired — re-asking")
            time.sleep(2)
            continue

        # ── Resolve target ─────────────────────────────────────────────
        anchor, search_dirs = resolve_target(M, region, landmark)
        if anchor is None or not search_dirs:
            remain = MISSION_TTL - mission_age(t_start)
            nap = max(30, min(remain + 5, 600))
            print(f"  unreachable region; waiting {nap}s")
            time.sleep(nap)
            continue

        # Check reachability from hub
        test_path = M.path(LANDMARKS["hub"], anchor)
        if test_path is None:
            remain = MISSION_TTL - mission_age(t_start)
            nap = max(30, min(remain + 5, 600))
            print(f"  {search_dirs} unreachable from hub; waiting {nap}s")
            time.sleep(nap)
            continue

        # Check gear/money for dangerous areas
        sc = m(s, "score", q=2.0)
        import re
        _dm = re.search(r"兵器伤害力：\[\s*(\d+)", sc)
        cur_dmg = int(_dm.group(1)) if _dm else 0
        from economy import _money_from_score
        cur_money = _money_from_score(sc)

        DANGEROUS_DIRS = ["d/westway"]
        if any(sd in DANGEROUS_DIRS for sd in search_dirs) and (cur_dmg == 0 or cur_money < 10):
            print(f"  [SKIP] dangerous area, not prepared — waiting")
            time.sleep(30)
            continue

        if cur_dmg == 0 and cur_money < 1:
            print("  [GEAR UP] unarmed + broke — trying bank")
            gear_up(s, nav)
            sc2 = m(s, "score", q=2.0)
            _dm2 = re.search(r"兵器伤害力：\[\s*(\d+)", sc2)
            if not (_dm2 and int(_dm2.group(1)) > 0):
                print("  still unarmed — waiting 60s")
                time.sleep(60)
                continue

        # ── SEARCHING + FIGHTING ──────────────────────────────────────
        t0 = time.time()
        result = sweep_vicinity(s, nav, M, anchor, search_dirs, name, ids)
        elapsed = time.time() - t0

        # ── Handle result ──────────────────────────────────────────────
        if result == "mission_lost":
            print("  !! KO'd — guai gone. Recovering, waiting for reset")
            eat_drink(s)
            wait_full_hp(s)
            continue

        if result is True:
            kills += 1
            total = tally_add(1)
            pending_guai = None
            print(f"\n  *** KILL #{kills} this run: {name} | LIFETIME TOTAL: {total} ***")
            time.sleep(2)
            drain(s, quiet=1.0, maxt=3.0)
            m(s, "get all", q=1.5)
            bank_deposit(s, nav)

        elif result == "engaged_lost":
            print(f"  engaged {name} but unconfirmed — checking Yuan")
            pending_guai = name
            continue

        elif result == "dead":
            print("  !! WE DIED — recovering")
            s = recover_to_kezhan(s, nav)
            nav.s = s

        elif result == "not_found":
            nf_count = nf_count + 1 if name == nf_name else 1
            nf_name = name
            if nf_count >= 2:
                print(f"  {name} unfindable {nf_count}x — waiting 5min")
                time.sleep(300)
                nf_count = 0
            else:
                print(f"  {name} not found — re-asking yuan")
                time.sleep(3)
        else:
            print(f"  !! unknown result: {result} (took {elapsed:.0f}s)")

    print(f"\n=== DONE: {kills} kills this run | LIFETIME {tally_get()} ===")
    m(s, "hp", q=2.0)
    print("*** session end: closing socket (no casual quit) ***")
    time.sleep(1)
    disconnect(s)


if __name__ == "__main__":
    main()
