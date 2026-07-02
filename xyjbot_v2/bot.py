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
from economy import gear_up, eat_drink, smart_eat_drink, wait_full_hp, bank_deposit, already_geared
from net import connect, disconnect, m, drain, clean, parse_short, parse_exits, is_dead, send, parse_hp
from mission import ask_yuan, resolve_target, sweep_vicinity, global_sweep, load_mission, save_mission
from mission import mission_age, mission_expired, MISSION_TTL
from combat import fight

os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)


def self_check(s, nav):
    """Full self-awareness check at startup. Assesses:
    - Position (where am I?)
    - HP/Sen (am I hurt?)
    - Food/Water (can I regen?)
    - Inventory (what am I carrying?)
    - Gear (weapon equipped? armor?)
    - Money (how much silver/gold?)
    Then takes corrective action before entering the main loop.
    """
    print("\n[SELF-CHECK] === Assessing condition ===")

    # 1. Position
    from config import ACCESSIBLE_DIRS as _ACCESSIBLE_DIRS
    rid, desc, short, exits = nav.look_and_identify()
    if rid:
        print(f"  [POS] {short} ({rid})")
        if rid.startswith(OURHOME_PREFIX):
            print("  [POS] stuck in ourhome — escaping")
            escape_ourhome(s, nav)
            rid, _, short, _ = nav.look_and_identify()
            print(f"  [POS] now at {short} ({rid})")
        elif not any(rid.startswith(d + '/') or rid.startswith(d) for d in _ACCESSIBLE_DIRS):
            # Wrong region (e.g. 取经路, 月宫) — try recall first, then quit
            print(f"  [POS] inaccessible region {rid} — trying recall")
            escaped = False
            for escape_cmd in ("recall", "go out", "go south", "go east", "go west", "go north"):
                m(s, escape_cmd, q=2.0)
                rid2, _, short2, _ = nav.look_and_identify()
                if rid2 and any(rid2.startswith(d) for d in _ACCESSIBLE_DIRS):
                    print(f"  [POS] escaped to {short2} ({rid2}) via {escape_cmd}")
                    rid = rid2
                    escaped = True
                    break
            if not escaped:
                print(f"  [POS] couldn't escape — quit+relog to return home")
                try:
                    m(s, "quit", q=3.0)
                except Exception:
                    pass
                from net import disconnect, connect
                disconnect(s)
                import time; time.sleep(3)
                s2 = connect()
                nav.s = s2
                nav.current_rid = None
                rid, _, short, _ = nav.look_and_identify()
                print(f"  [POS] after relog: {short} ({rid})")
                return self_check(s2, nav)  # re-run check with fresh connection
    else:
        print("  [POS] can't identify — will localize by walking")
        nav.force_localize(M_obj=None)

    # 2. HP / Sen / Food / Water
    hr = m(s, "hp", q=1.5, log_path=LOG_PATH)
    hp = parse_hp(hr)
    qixue = hp.get("气血", (0, 0))
    jingshen = hp.get("精神", (0, 0))
    food = hp.get("食物", (0, 0))
    water = hp.get("饮水", (0, 0))
    print(f"  [HP] 气血 {qixue[0]}/{qixue[1]}  精神 {jingshen[0]}/{jingshen[1]}")
    print(f"  [HP] 食物 {food[0]}/{food[1]}  饮水 {water[0]}/{water[1]}")

    # 3. Inventory
    inv = m(s, "i", q=1.5, log_path=LOG_PATH)
    has_weapon = any(w in inv for w in ("刀", "剑", "枪", "叉", "棍", "棒", "斧", "锤", "杖"))
    has_armor = any(w in inv for w in ("甲", "盾", "袍", "衣", "护"))
    print(f"  [INV] weapon in inventory: {has_weapon}, armor in inventory: {has_armor}")

    # 4. Gear (equipped stats)
    sc = m(s, "score", q=2.5, log_path=LOG_PATH)
    import re
    dmg = int((re.search(r"兵器伤害力：\[\s*(\d+)", sc) or [0,0])[1]) if re.search(r"兵器伤害力：\[\s*(\d+)", sc) else 0
    arm = int((re.search(r"盔甲保护力：\[\s*(\d+)", sc) or [0,0])[1]) if re.search(r"盔甲保护力：\[\s*(\d+)", sc) else 0
    print(f"  [GEAR] dmg={dmg} armor={arm}")

    # 5. Money
    from economy import _money_from_score
    money = _money_from_score(sc)
    print(f"  [GOLD] {money:.1f}两 on hand")

    # ── Corrective actions ───────────────────────────────────────────

    # Wield weapon if in inventory but not equipped
    if dmg == 0 and has_weapon:
        print("  [FIX] weapon in inventory but not wielded — wielding")
        m(s, "wield all", q=1.0)
        sc = m(s, "score", q=2.0)
        dmg = int((re.search(r"兵器伤害力：\[\s*(\d+)", sc) or [0,0])[1]) if re.search(r"兵器伤害力：\[\s*(\d+)", sc) else 0
        print(f"  [FIX] dmg after wield: {dmg}")

    # Wear armor if in inventory but not equipped
    if arm < 10 and has_armor:
        print("  [FIX] armor in inventory but not worn — wearing")
        m(s, "wear all", q=1.0)
        sc = m(s, "score", q=2.0)
        arm = int((re.search(r"盔甲保护力：\[\s*(\d+)", sc) or [0,0])[1]) if re.search(r"盔甲保护力：\[\s*(\d+)", sc) else 0
        print(f"  [FIX] armor after wear: {arm}")

    # Food/water low? Restock before anything else
    if food[0] < 150 or water[0] < 150:
        print("  [FIX] food/water low — smart restock")
        smart_eat_drink(s, nav)
        hr = m(s, "hp", q=1.5)
        hp = parse_hp(hr)
        food = hp.get("食物", (0, 0))
        water = hp.get("饮水", (0, 0))
        print(f"  [FIX] food {food[0]}/{food[1]}  water {water[0]}/{water[1]}")

    # HP/Sen low? Rest until full
    if qixue[0] < qixue[1] * 0.8 or jingshen[0] < jingshen[1] * 0.8:
        print("  [FIX] HP/Sen below 80% — resting to full")
        wait_full_hp(s)

    # No weapon at all? Gear up from shop
    if dmg == 0:
        print("  [FIX] no weapon — gearing up from shop")
        gear_up(s, nav)

    print("[SELF-CHECK] === Ready ===\n")
    return dmg, arm


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

    # ── INIT: full self-awareness check ───────────────────────────────
    dmg, arm = self_check(s, nav)

    # ── MAIN LOOP ─────────────────────────────────────────────────────
    kills = 0
    nf_name, nf_count = None, 0
    _lm_name, _, _, _, _ = load_mission()
    pending_guai = _lm_name
    session_stuck_count = 0      # consecutive stuck events this session
    SESSION_STUCK_LIMIT = 5      # rollback map if stuck this many times

    for attempt in range(120):
        if kills >= TARGET_KILLS:
            break

        print(f"\n[ATTEMPT {attempt+1}] kills={kills}/{TARGET_KILLS}")

        # ── Position re-confirm: look to validate current_rid ─────────
        try:
            rid_check, _, _, _ = nav.look_and_identify()
            if rid_check is None:
                print("  [LOOP] can't identify position — localizing")
                nav._localize_and_retry(None)
            elif not any(rid_check.startswith(d) for d in ACCESSIBLE_DIRS):
                print(f"  [LOOP] inaccessible region {rid_check} — trying recall first")
                # Try recall/go commands before quitting (might just be 1 room off)
                for escape_cmd in ("recall", "go out", "go south", "go east", "go west", "go north"):
                    m(s, escape_cmd, q=2.0)
                    rid2, _, sh2, _ = nav.look_and_identify()
                    if rid2 and any(rid2.startswith(d) for d in ACCESSIBLE_DIRS):
                        print(f"  [LOOP] escaped to {sh2} ({rid2}) via {escape_cmd}")
                        nav.current_rid = rid2
                        break
                else:
                    print(f"  [LOOP] couldn't escape — quit+relog")
                    s = recover_to_kezhan(s, nav)
                    nav.s = s
        except OSError:
            print("  [LOOP] socket dead — reconnecting")
            s = recover_to_kezhan(s, nav)
            nav.s = s

        # ── MISSION: ask Yuan ─────────────────────────────────────────
        try:
            name, ids, region, landmark, t_start, cleared = ask_yuan(s, nav)
        except OSError:
            print("  [LOOP] socket died during ask_yuan — reconnecting")
            s = recover_to_kezhan(s, nav)
            nav.s = s
            continue

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
            if region is None and name:
                # Reminder form — no region data. Try global sweep instead of waiting.
                print(f"  no region for {name} — launching global sweep")
                result = global_sweep(s, nav, M, name, ids)
                if result is True:
                    kills += 1
                    total = tally_add(1)
                    pending_guai = None
                    session_stuck_count = 0
                    print(f"\n  *** KILL #{kills} (global sweep): {name} | LIFETIME: {total} ***")
                    time.sleep(2)
                    m(s, "get all", q=1.5)
                    bank_deposit(s, nav)
                elif result == "dead":
                    s = recover_to_kezhan(s, nav)
                    nav.s = s
                elif result == "mission_lost":
                    smart_eat_drink(s, nav)
                    wait_full_hp(s)
                elif result == "stuck":
                    session_stuck_count += 1
                    # Don't know gear_expendable here; be conservative
                    print("  [GLOBAL SWEEP] stuck — skipping quit+relog, waiting 30s")
                    time.sleep(30)
                # After global sweep (found or not), re-ask Yuan next iteration
                continue
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

        # ── Pre-mission self-check ─────────────────────────────────────
        # Quick condition check: verify gear, HP, food/water before each mission
        quick_sc = m(s, "score", q=2.0)
        import re
        _dm = re.search(r"兵器伤害力：\[\s*(\d+)", quick_sc)
        cur_dmg = int(_dm.group(1)) if _dm else 0
        from economy import _money_from_score
        cur_money = _money_from_score(quick_sc)

        # Check HP + food/water
        quick_hp = parse_hp(m(s, "hp", q=1.0))
        qixue = quick_hp.get("气血", (1, 1))
        food = quick_hp.get("食物", (0, 0))
        water = quick_hp.get("饮水", (0, 0))

        # No weapon? Check inventory + gear up
        if cur_dmg == 0:
            print("  [PRE-MISSION] no weapon — checking inventory")
            inv = m(s, "i", q=1.0)
            if any(w in inv for w in ("刀", "剑", "枪", "叉", "棍", "棒", "斧", "锤", "杖", "匕")):
                print("  [PRE-MISSION] weapon in bag — wielding")
                m(s, "wield all", q=1.0)
            else:
                print("  [PRE-MISSION] no weapon anywhere — gearing up")
                gear_up(s, nav)

        # Food/water low? Smart restock (check inventory first, shop only if needed)
        if food[0] < 150 or water[0] < 150:
            print("  [PRE-MISSION] food/water low — smart restock")
            smart_eat_drink(s, nav)

        # HP low? Rest
        if qixue[0] < qixue[1] * 0.8:
            print("  [PRE-MISSION] HP below 80% — resting")
            wait_full_hp(s)

        # Re-read dmg after corrective actions
        if cur_dmg == 0:
            sc2 = m(s, "score", q=2.0)
            _dm2 = re.search(r"兵器伤害力：\[\s*(\d+)", sc2)
            cur_dmg = int(_dm2.group(1)) if _dm2 else 0

        # ── Determine if gear is expendable ────────────────────────────
        # If weapon dmg <= 25 (钢刀, 5两) and armor <= 16 (牛皮盾, 10两),
        # then quit+relog is cheap — total replacement cost ~15两.
        # If gear is better than shop-baseline, NEVER quit (irreplaceable).
        gear_expendable = (cur_dmg <= 25 and True)  # will re-check armor below
        if cur_dmg > 25:
            gear_expendable = False
        sc3 = m(s, "score", q=2.0)
        _am = re.search(r"盔甲保护力：\[\s*(\d+)", sc3)
        cur_arm = int(_am.group(1)) if _am else 0
        if cur_arm > 16:
            gear_expendable = False

        # Check gear/money for dangerous areas
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
            smart_eat_drink(s, nav)
            wait_full_hp(s)
            continue

        if result is True:
            kills += 1
            total = tally_add(1)
            pending_guai = None
            session_stuck_count = 0   # successful mission = navigation is working fine
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

        elif result == "stuck":
            # Navigation got stuck — decide whether to quit+relog based on gear
            session_stuck_count += 1
            print(f"  [STUCK] session stuck count: {session_stuck_count}/{SESSION_STUCK_LIMIT}")

            # Too many stucks this session? Map overrides might be poisoned — rollback
            if session_stuck_count >= SESSION_STUCK_LIMIT:
                print("  [STUCK] too many stucks — rolling back map overrides!")
                M.rollback_overrides()
                session_stuck_count = 0

            if gear_expendable:
                print("  [STUCK] gear is basic (replaceable for ~15两) — quit+relog to kezhan")
                s = recover_to_kezhan(s, nav)
                nav.s = s
            else:
                print(f"  [STUCK] gear is GOOD (dmg={cur_dmg} arm={cur_arm}) — NOT quitting, giving up mission")
                # Try walking to hub manually from wherever we are
                rid, _, _, _ = nav.look_and_identify()
                if rid:
                    hub_path = M.path(rid, LANDMARKS["hub"])
                    if hub_path is not None:
                        print(f"  [STUCK] walking to hub ({len(hub_path)} steps)")
                        nav.goto(LANDMARKS["hub"], max_steps=100)
                # Give up this mission, wait for timer
                remain = MISSION_TTL - mission_age(t_start)
                nap = max(30, min(remain + 5, 600))
                print(f"  [STUCK] waiting {nap}s for mission to expire")
                time.sleep(nap)

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
