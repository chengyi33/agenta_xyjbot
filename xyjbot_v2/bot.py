"""
bot.py — Main loop + state machine for XYJ2000 autonomous kill bot.

Architecture: Dead reckoning navigation + incremental position tracking.
States: INIT → GEARING → MISSION → TRAVELING → SEARCHING → FIGHTING → LOOTING → BANKING → MISSION
Recovery: any → LOST → quit+relog → GEARING
"""
import re, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import *
from map_engine import XYJMap
from nav import Navigator
from net import connect, disconnect, m, drain, clean, parse_short, parse_exits, is_dead, send
from economy import gear_up, eat_drink, smart_eat_drink, wait_full_hp, bank_deposit, already_geared
from net import connect, disconnect, m, drain, clean, parse_short, parse_exits, is_dead, send, parse_hp
from training import train_at_difu
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
        elif rid.startswith("d/death/"):
            print(f"  [POS] in 阴曹地府 ({short}) — valid training location")
        elif not any(rid.startswith(d + '/') or rid.startswith(d) for d in _ACCESSIBLE_DIRS) or \
                nav.M.path(rid, LANDMARKS["hub"]) is None:
            # Either wrong region, OR in accessible region but map can't route back
            # (e.g. stuck in locked monastery sub-area in nanhai) — recall first, then quit
            print(f"  [POS] no path to hub from {rid} — trying recall")
            escaped = False
            for escape_cmd in ("recall", "out", "south", "east", "west", "north", "up", "down"):
                m(s, escape_cmd, q=2.0)
                rid2, _, short2, _ = nav.look_and_identify()
                if rid2 and any(rid2.startswith(d) for d in _ACCESSIBLE_DIRS):
                    print(f"  [POS] escaped to {short2} ({rid2}) via {escape_cmd}")
                    rid = rid2
                    escaped = True
                    break
            if not escaped:
                # Before quitting, check gear — never quit with precious gear
                _sc_sc = m(s, "score", q=2.0, log_path=LOG_PATH)
                _dm_sc = re.search(r"兵器伤害力：\[\s*(\d+)", _sc_sc)
                _am_sc = re.search(r"盔甲保护力：\[\s*(\d+)", _sc_sc)
                _sc_dmg = int(_dm_sc.group(1)) if _dm_sc else 0
                _sc_arm = int(_am_sc.group(1)) if _am_sc else 0
                if _sc_dmg > 25 or _sc_arm > 16:
                    print(f"  [POS] gear precious (dmg={_sc_dmg} arm={_sc_arm}) — NOT quitting; waiting 30s for recovery")
                    time.sleep(30)
                    return _sc_dmg, _sc_arm  # return best-guess gear stats, let main loop handle it
                print(f"  [POS] couldn't escape — quit+relog to return home")
                try:
                    m(s, "quit", q=3.0)
                except Exception:
                    pass
                from net import disconnect, connect
                disconnect(s)
                time.sleep(3)
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
    dmg = int((re.search(r"兵器伤害力：\[\s*(\d+)", sc) or [0,0])[1]) if re.search(r"兵器伤害力：\[\s*(\d+)", sc) else 0
    arm = int((re.search(r"盔甲保护力：\[\s*(\d+)", sc) or [0,0])[1]) if re.search(r"盔甲保护力：\[\s*(\d+)", sc) else 0
    print(f"  [GEAR] dmg={dmg} armor={arm}")

    # 5. Money (score doesn't show money — use inventory)
    from economy import _money_from_score
    inv = m(s, "i", q=1.0)
    money = _money_from_score(inv)
    print(f"  [GOLD] {money:.1f}两 on hand")

    # ── Corrective actions ───────────────────────────────────────────

    # Wield weapon if in inventory but not equipped
    if dmg == 0 and has_weapon:
        print("  [FIX] weapon in inventory but not wielded — wielding")
        m(s, "wield all", q=1.0)
        sc = m(s, "score", q=2.0)
        dmg = int((re.search(r"兵器伤害力：\[\s*(\d+)", sc) or [0,0])[1]) if re.search(r"兵器伤害力：\[\s*(\d+)", sc) else 0
        print(f"  [FIX] dmg after wield: {dmg}")

    # Prefer 金箍棒 (250 dmg) as primary weapon if it's in inventory
    inv_chk = m(s, "i", q=1.0)
    if ("金箍棒" in inv_chk or "jingubang" in inv_chk.lower()) and dmg < 250:
        print(f"  [FIX] jingubang available but dmg={dmg} — swapping to jingubang")
        m(s, "unwield blade", q=1.0)   # free primary hand (钢刀 uses English name)
        m(s, "unwield dao", q=0.5)
        r = m(s, "wield jingubang", q=1.5)
        sc = m(s, "score", q=2.0)
        mm = re.search(r"兵器伤害力：\[\s*(\d+)", sc)
        dmg = int(mm.group(1)) if mm else dmg
        print(f"  [FIX] dmg after jingubang wield: {dmg}")

    # Wear armor if in inventory but not equipped
    if arm < 10 and has_armor:
        print("  [FIX] armor in inventory but not worn — wearing")
        m(s, "wear all", q=1.0)
        sc = m(s, "score", q=2.0)
        arm = int((re.search(r"盔甲保护力：\[\s*(\d+)", sc) or [0,0])[1]) if re.search(r"盔甲保护力：\[\s*(\d+)", sc) else 0
        print(f"  [FIX] armor after wear: {arm}")

    # Food/water low? Restock before anything else
    if food[0] < 150 or water[0] < 150:
        if rid and rid.startswith("d/death/"):
            print("  [FIX] food/water low in 地府 — training loop will restock at 客栈")
        else:
            print("  [FIX] food/water low — smart restock")
            smart_eat_drink(s, nav)
            hr = m(s, "hp", q=1.5)
            hp = parse_hp(hr)
            food = hp.get("食物", (0, 0))
            water = hp.get("饮水", (0, 0))
            print(f"  [FIX] food {food[0]}/{food[1]}  water {water[0]}/{water[1]}")

    # HP/Sen low? Rest until full
    # kee/eff_kee format: 0/300 (100%) means current HP 0, body at full potential
    if qixue[0] < qixue[1] * 0.6 or jingshen[0] < jingshen[1] * 0.6:
        print("  [FIX] HP/Sen below 60% — resting to full")
        wait_full_hp(s)

    # No weapon at all? Gear up from shop
    if dmg == 0:
        print("  [FIX] no weapon — gearing up from shop")
        gear_up(s, nav)

    # Acquire 避水咒 if we don't have it (enables dive to 龙宫)
    from economy import get_bishui_zhou
    get_bishui_zhou(s, nav)

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
    for cmd in ("recall", "east", "north", "west", "south", "out", "up", "down"):
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
        for cmd in ("recall", "east", "north", "west", "south"):
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


# ── 红楼一梦 Entry (黄粱枕 sleep mechanic) ────────────────────────────
# Source-verified flow (sleep.c + pillow.c):
#   1. Kill 卢生 (lusheng) at d/changan/wside3 → drops 黄粱枕
#   2. Navigate to sleep room (d/jjf/guest_bedroom, sleep_room=1 if_bed=1)
#   3. Issue `sleep` → wakeup1() checks for pillow in inventory
#      → if found: move to d/ourhome/honglou/kat, pillow destroyed
#   4. Hunt target inside honglou (all rooms in map)
#   5. Exit: quit+relog (honglou has no map path back)

LUSHENG_ROOM   = "d/changan/wside3"      # 泾水之滨 — 卢生 spawns here
SLEEP_ROOM     = "d/jjf/guest_bedroom"   # 将军府客房 (sleep_room=1, if_bed=1)
HONGLOU_ENTRY  = "d/ourhome/honglou/kat" # 荡悠悠三更梦 — wakeup lands here
HONGLOU_PREFIX = "d/ourhome/honglou"
PILLOW_IDS     = ("黄粱枕", "huangliang zhen", "pillow")


def has_pillow(s):
    """Return True if 黄粱枕 is in inventory."""
    inv = m(s, "i", q=1.5)
    return any(tok in inv for tok in PILLOW_IDS)


def acquire_pillow(s, nav):
    """Kill 卢生 and loot 黄粱枕. Returns True on success."""
    print("[HONGLOU] acquiring 黄粱枕 — heading to 泾水之滨")
    if has_pillow(s):
        print("[HONGLOU] already have pillow")
        return True

    # Navigate to 卢生's spawn room via nanchengkou
    # Path: hub → nanchengkou (south×4+1) → wside1 (west) → wside2 (west) → wside3 (west)
    ok = nav.goto(LUSHENG_ROOM)
    if not ok:
        print("[HONGLOU] can't reach wside3 — abort")
        return False

    rid, short, _, _ = nav.look_and_identify()
    print(f"[HONGLOU] at {rid} ({short})")

    # Look for 卢生
    look = m(s, "look", q=2.0)
    
    # Check if pillow is already on the ground (previous kill, drop, etc.)
    if "黄粱枕" in look or "huangliang zhen" in look.lower() or "pillow" in look.lower():
        print("[HONGLOU] pillow already on ground — picking up")
        m(s, "get huangliang zhen", q=1.0)
        m(s, "get pillow", q=1.0)
        m(s, "get all", q=1.0)
        time.sleep(1)
        if has_pillow(s):
            print("[HONGLOU] ✅ picked up pillow from ground")
            return True
    
    if "卢生" not in look and "lu sheng" not in look.lower():
        print("[HONGLOU] 卢生 not here — waiting 60s for respawn")
        time.sleep(60)
        look = m(s, "look", q=2.0)
        # Re-check for dropped pillow
        if "黄粱枕" in look or "huangliang zhen" in look.lower():
            print("[HONGLOU] pillow appeared on ground — picking up")
            m(s, "get huangliang zhen", q=1.0)
            m(s, "get pillow", q=1.0)
            time.sleep(1)
            if has_pillow(s):
                print("[HONGLOU] ✅ picked up pillow from ground")
                return True
        if "卢生" not in look:
            print("[HONGLOU] still no 卢生 — aborting pillow acquisition")
            return False

    print("[HONGLOU] found 卢生 — attacking")
    from combat import fight
    result = fight(s, "卢生", ids=["lu", "sheng", "lusheng"])
    print(f"[HONGLOU] fight result: {result}")

    if result not in ("win", "done", True):
        print("[HONGLOU] failed to kill 卢生")
        return False

    # Loot — wait for corpse items to drop, then get everything
    time.sleep(2)
    m(s, "get all", q=2.0)
    m(s, "get all from corpse", q=1.5)
    m(s, "get pillow", q=1.0)
    m(s, "get pillow from corpse", q=1.0)
    m(s, "get zhen", q=1.0)
    m(s, "get huangliang zhen", q=1.0)
    time.sleep(1)

    if has_pillow(s):
        print("[HONGLOU] ✅ 黄粱枕 acquired!")
        return True

    # DEBUG: show what's on ground and in inventory
    look = m(s, "look", q=2.0)
    inv = m(s, "i", q=1.5)
    print(f"[HONGLOU] loot debug: inv_has_pillow={'黄粱枕' in inv}", flush=True)
    if "黄粱枕" in look or "pillow" in look.lower():
        # pillow is still on the ground — try more specific get
        m(s, "get huangliang zhen from corpse", q=2.0)
        m(s, "get all", q=2.0)
        time.sleep(1)

    if has_pillow(s):
        print("[HONGLOU] ✅ 黄粱枕 acquired on second try!")
        return True

    print("[HONGLOU] looted but no pillow in inventory")
    return False


def honglou_entry(s, nav):
    """Use 黄粱枕 to enter 红楼一梦 via sleep mechanic. Returns new socket s."""
    print("[HONGLOU] entering 红楼一梦 via sleep")

    if not has_pillow(s):
        ok = acquire_pillow(s, nav)
        if not ok:
            print("[HONGLOU] couldn't get pillow — aborting entry")
            return s, False

    # Need full HP before sleep (wakeup checks sen/kee > 0)
    wait_full_hp(s)

    # Navigate to sleep room (将军府客房)
    print(f"[HONGLOU] navigating to sleep room {SLEEP_ROOM}")
    ok = nav.goto(SLEEP_ROOM)
    if not ok:
        print("[HONGLOU] can't reach sleep room — abort")
        return s, False

    print("[HONGLOU] issuing sleep command")
    resp = m(s, "sleep", q=5.0)
    print(f"[HONGLOU] sleep response: {resp[:120]}")

    if "不是睡觉的地方" in resp:
        print("[HONGLOU] not a sleep room?! abort")
        return s, False
    if "正忙着" in resp or "战斗中" in resp:
        print("[HONGLOU] busy/fighting — wait then retry")
        time.sleep(10)
        return s, False

    # Wait for wakeup (wakeup1 is called_out after random(45-con)+10 seconds)
    # con(体格)=30 → random(45-30)=random(15) → 10-25s sleep time
    print("[HONGLOU] sleeping... waiting for wakeup (10–30s)")
    wakeup_text = drain(s, quiet=30.0, maxt=40.0)
    print(f"[HONGLOU] wakeup output: {wakeup_text[:200] if wakeup_text else '(empty)'}")

    if "梦的世界" in (wakeup_text or "") or "进入了梦" in (wakeup_text or ""):
        print("[HONGLOU] ✅ entered 红楼一梦!")
        nav.current_rid = HONGLOU_ENTRY
        return s, True
    else:
        # Woke up normally (pillow check may have failed), try to confirm location
        rid, short, _, _ = nav.look_and_identify()
        print(f"[HONGLOU] woke at {rid} ({short})")
        if rid and rid.startswith(HONGLOU_PREFIX):
            print("[HONGLOU] ✅ we're in honglou!")
            return s, True
        else:
            print("[HONGLOU] woke outside honglou — pillow may have failed (1% chance was needed)")
            return s, False


def hunt_in_honglou(s, nav, M, name, ids):
    """Navigate and hunt inside 红楼一梦. Returns 'kill', 'dead', or 'fail'.
    After hunt, quit+relog to escape (no map path out of dream world)."""
    print(f"[HONGLOU] hunting {name} inside 红楼一梦")

    # Identify entry position
    rid, short, _, exits = nav.look_and_identify()
    print(f"[HONGLOU] entry point: {rid} ({short})")

    if not rid or not rid.startswith(HONGLOU_PREFIX):
        print("[HONGLOU] not in honglou?!")
        return "fail"

    # Sweep honglou rooms for target
    # BFS-search all honglou rooms from current position
    from mission import sweep_vicinity
    honglou_anchor = rid
    # Collect all honglou rooms as search directions
    honglou_dirs = (HONGLOU_PREFIX,)
    result = sweep_vicinity(s, nav, M, honglou_anchor, honglou_dirs, name, ids, t_start=time.time())
    print(f"[HONGLOU] sweep result: {result}")

    # Always exit via quit+relog regardless of result
    print("[HONGLOU] exiting dream world via quit+relog")
    try:
        m(s, "quit", q=3.0)
    except Exception:
        pass
    disconnect(s)
    time.sleep(3)
    s2 = connect()
    nav.s = s2
    nav.current_rid = None

    # Verify we're back in normal world
    rid2, short2, _, _ = nav.look_and_identify()
    print(f"[HONGLOU] back in world at {rid2} ({short2})")

    if result is True or result == "win":
        return "kill"
    elif result == "dead":
        return "dead"
    else:
        return "fail"


# ── Main ──────────────────────────────────────────────────────────────
QIANNENG_TARGET = int(os.environ.get("XYJ_QIANNENG", "5000"))  # target 5000 潜能
FAILED_MISSIONS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "failed_missions.json")

# Regions known to require fly/dive/special access — skip immediately
# These are Yuan's region strings, not room short names
KNOWN_UNREACHABLE_REGIONS = {
    # 月宫 interior (requires special celestial access)
    "月宫", "玉女峰", "玉阶", "桂树叶间", "蟠桃园", "凌霄宝殿",
    "广寒宫", "广寒宫正殿", "练功房",
    # 海底莽林 maze — avoid even with 避水咒 (user instruction)
    "海底莽林",
    # 红楼一梦 — NOW REACHABLE via 黄粱枕 sleep mechanic (handled specially below)
    # "红楼一梦",  ← removed; bot handles this region via acquire_pillow+honglou_entry
    # 西天取经路 (far out of range)
    "取经路", "五庄观", "万寿山", "流沙河", "通天河",
    # NOTE: 方寸山/灵台方寸 now reachable with door-opening nav
    # NOTE: 普陀山/南海普陀 reachable via swim from 南海之滨 (gate door now handled)
    # NOTE: 东海龙宫/海底/回廊/广场/云房 reachable with 避水咒 (dive from 东海之滨)
    # NOTE: 崎岖小路 reachable via westway/jincheng → NE → d/moon/xiaolu3
}


def check_qianneng(s, target=5000):
    """Read 潜能 from hp. Returns current value."""
    r = m(s, "hp", q=1.5, log_path=LOG_PATH)
    hp = parse_hp(r)
    val = hp.get("潜能", 0)
    print(f"  [潜能] {val} / {target}")
    return val


def load_failed_missions():
    """Load persisted failed missions from file. Returns set of (name,region,landmark)."""
    try:
        import json
        data = json.load(open(FAILED_MISSIONS_FILE, encoding="utf-8"))
        # Filter out old entries (>4h)
        cutoff = time.time() - 4 * 3600
        valid = {tuple(k) for k in data if len(k) == 4 and k[3] > cutoff}
        print(f"  [FAILED_CACHE] loaded {len(valid)} persisted failed missions")
        return valid
    except Exception:
        return set()


def save_failed_missions(failed_set):
    """Persist failed missions to file."""
    try:
        import json
        ts = time.time()
        data = [[k[0], k[1], k[2], ts] for k in failed_set if len(k) >= 3]
        json.dump(data, open(FAILED_MISSIONS_FILE, "w", encoding="utf-8"), ensure_ascii=False)
    except Exception:
        pass


def idle_maintenance(s, nav):
    """Do useful work while waiting for an unreachable mission to expire."""
    from economy import smart_eat_drink, wait_full_hp, bank_deposit, gear_up
    # Wait in 南城客栈 — safe zone, 2 steps from hub
    try:
        nav.goto("d/city/kezhan", max_steps=20)
    except Exception:
        pass
    smart_eat_drink(s, nav)
    hp = parse_hp(m(s, "hp", q=1.0))
    qixue = hp.get("气血", (1, 1))
    if qixue[0] < qixue[1]:
        print("  [IDLE] resting to full HP")
        wait_full_hp(s)
    # Always check gear — even while idling on unreachable missions
    import re as _re
    sc = m(s, "score", q=1.5)
    _dmg = _re.search(r"兵器伤害力：\[\s*(\d+)", sc)
    _arm = _re.search(r"盔甲保护力：\[\s*(\d+)", sc)
    cur_dmg = int(_dmg.group(1)) if _dmg else 0
    cur_arm = int(_arm.group(1)) if _arm else 0
    if cur_dmg == 0 or cur_arm < 10:
        print(f"  [IDLE] no gear (dmg={cur_dmg} arm={cur_arm}) — gearing up now")
        gear_up(s, nav)
    # Deposit excess money (keep 50两 on hand)
    from economy import _money_from_score, _parse_chinese_number
    inv = m(s, "i", q=1.0)
    cur_money = _money_from_score(inv)
    if cur_money > 100:
        print(f"  [IDLE] excess money ({cur_money:.0f}两) — depositing")
        bank_deposit(s, nav, keep=50)


def notify_done(val):
    """Send Telegram notification when target is reached."""
    try:
        import subprocess
        msg = f"🎯 XYJ2000: 潜能 reached {val}! Bot stopping — time to train at 武馆."
        subprocess.Popen(["openclaw", "send", msg], stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL)
    except Exception as e:
        print(f"  [NOTIFY] failed: {e}")


def main():
    open(LOG_PATH, "w", encoding="utf-8").write("=== XYJBOT v2 ===\n")
    M = XYJMap()
    print(f"[MAP] {len(M.g)} rooms loaded, {len(M.adj)} adjacency entries")

    s = connect()
    nav = Navigator(s, M)
    print("[CONNECTED]")

    # ── INIT: full self-awareness check ───────────────────────────────
    dmg, arm = self_check(s, nav)

    # ── SECT CHECK: join 阴曹地府 + train if not in a family ──────────
    sc_fam = m(s, "score", q=2.0)
    in_difu = "阎罗地府" in sc_fam

    if not in_difu:
        print("\n*** NO SECT — joining 阴曹地府 + training skills ***\n")
        train_at_difu(s, nav)
        dmg, arm = self_check(s, nav)
    else:
        # Already in sect — check if we have 潜能 to train
        hp_train = parse_hp(m(s, "hp", q=1.0))
        qn_train = hp_train.get("潜能", 0)
        if qn_train > 0:
            print(f"\n*** 潜能={qn_train} — training skills at 阴曹地府 ***\n")
            train_at_difu(s, nav)
            dmg, arm = self_check(s, nav)

    # ── MAIN LOOP ─────────────────────────────────────────────────────
    kills = 0
    nf_name, nf_count = None, 0
    _lm_name, _, _, _, _ = load_mission()
    pending_guai = _lm_name
    session_stuck_count = 0      # consecutive stuck events this session
    SESSION_STUCK_LIMIT = 5      # rollback map if stuck this many times
    honglou_fail_count = 0       # consecutive HONGLOU entry failures
    failed_missions = load_failed_missions()  # persisted across restarts

    attempt = 0
    while True:  # run forever until 潜能 target reached
        attempt += 1
        if kills >= TARGET_KILLS:
            break

        print(f"\n[ATTEMPT {attempt}] kills={kills}/{TARGET_KILLS}")

        # ── Position re-confirm: look to validate current_rid ─────────
        try:
            rid_check, _, _, _ = nav.look_and_identify()
            if rid_check is None:
                print("  [LOOP] can't identify position — localizing")
                nav._localize_and_retry(None)
            elif not any(rid_check.startswith(d) for d in ACCESSIBLE_DIRS) or \
                    nav.M.path(rid_check, LANDMARKS["hub"]) is None:
                # Either inaccessible region OR accessible but no map path to hub
                # (e.g. locked monastery sub-area with self-looping doors)
                print(f"  [LOOP] no path to hub from {rid_check} — trying recall first")
                # Check current gear before deciding whether to quit
                _sc_loop = m(s, "score", q=2.0)
                import re as _re
                _dm_loop = _re.search(r"兵器伤害力：\[\s*(\d+)", _sc_loop)
                _am_loop = _re.search(r"盔甲保护力：\[\s*(\d+)", _sc_loop)
                _loop_dmg = int(_dm_loop.group(1)) if _dm_loop else 0
                _loop_arm = int(_am_loop.group(1)) if _am_loop else 0
                _loop_gear_precious = (_loop_dmg > 25 or _loop_arm > 16)
                for escape_cmd in ("recall", "out", "south", "east", "west", "north", "up", "down"):
                    m(s, escape_cmd, q=2.0)
                    rid2, _, sh2, _ = nav.look_and_identify()
                    if rid2 and any(rid2.startswith(d) for d in ACCESSIBLE_DIRS) and \
                            nav.M.path(rid2, LANDMARKS["hub"]) is not None:
                        print(f"  [LOOP] escaped to {sh2} ({rid2}) via {escape_cmd}")
                        nav.current_rid = rid2
                        break
                else:
                    if _loop_gear_precious:
                        # NEVER quit with good gear — just wait and retry next attempt
                        print(f"  [LOOP] gear precious (dmg={_loop_dmg} arm={_loop_arm}) — NOT quitting; waiting 30s")
                        time.sleep(30)
                    else:
                        # Try recall as absolute last resort before quit+relog
                        print(f"  [LOOP] gear basic, no escape route — recall first, then quit+relog")
                        m(s, "recall", q=2.0)
                        time.sleep(2)
                        rid3, _, _, _ = nav.look_and_identify()
                        if rid3 and any(rid3.startswith(d) for d in ACCESSIBLE_DIRS) and \
                                nav.M.path(rid3, LANDMARKS["hub"]) is not None:
                            print(f"  [LOOP] recall rescued us! at {rid3}")
                            nav.current_rid = rid3
                        else:
                            print(f"  [LOOP] recall failed — quit+relog (last resort)")
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
            # Deposit excess money after kill (keep 50两 on hand)
            try:
                from economy import _money_from_score
                inv_c = m(s, "i", q=1.0)
                money_on_hand = _money_from_score(inv_c)
                if money_on_hand > 50:
                    print(f"  [deposit] {money_on_hand:.0f}两 on hand → depositing to bank")
                    bank_deposit(s, nav, keep=50)
            except Exception:
                pass
            if kills >= TARGET_KILLS:
                break

        if not name:
            print("  no mission; wait 20s")
            idle_maintenance(s, nav)
            time.sleep(20)
            continue

        age = mission_age(t_start)
        print(f"  Mission: {name} ids={ids} region={region} landmark={landmark} (age {age}s/{MISSION_TTL}s)")

        # Check expiry
        if mission_expired(t_start):
            print(f"  mission expired — re-asking (sleeping 60s to avoid hammering Yuan)")
            failed_missions.discard((name, region, landmark))
            save_failed_missions(failed_missions)
            # Sleep 60s not 2s: the guai can persist up to 90 min in-game even
            # after our 30-min TTL. Tight-looping ask_yuan every 2s hammers the
            # server and wastes CPU for up to 60 extra minutes.
            idle_maintenance(s, nav)
            time.sleep(60)
            continue

        # ── Fast-skip known unreachable regions ───────────────────────
        if region and any(region.startswith(ur) or region == ur
                          for ur in KNOWN_UNREACHABLE_REGIONS):
            remain = MISSION_TTL - mission_age(t_start)
            print(f"  [SKIP] {region} is known unreachable — idling {min(remain,120):.0f}s")
            idle_maintenance(s, nav)
            time.sleep(max(0, min(remain, 120)))
            continue

        # ── 红楼一梦 — special dream-world entry via 黄粱枕 ───────────
        if region and "红楼一梦" in region:
            print(f"  [HONGLOU] mission in 红楼一梦 — attempting dream-entry for {name}")
            s, entered = honglou_entry(s, nav)
            nav.s = s
            if entered:
                honglou_fail_count = 0  # reset on success
                result = hunt_in_honglou(s, nav, M, name, ids)
                if result == "kill":
                    kills += 1
                    total = tally_add(1)
                    pending_guai = None
                    session_stuck_count = 0
                    print(f"\n  *** KILL #{kills} (honglou): {name} | LIFETIME: {total} ***")
                    # Re-gear after quit+relog
                    if not already_geared(s):
                        gear_up(s, nav)
                elif result == "dead":
                    s = recover_to_kezhan(s, nav)
                    nav.s = s
                else:
                    print("  [HONGLOU] hunt failed — sleeping 60s")
                    idle_maintenance(s, nav)
                    time.sleep(60)
            else:
                # Couldn't enter — track failures to break infinite loop
                honglou_fail_count += 1
                print(f"  [HONGLOU] entry failed ({honglou_fail_count}/3)")
                if honglou_fail_count >= 3:
                    print(f"  [HONGLOU] 3 consecutive entry failures — marking mission as failed")
                    failed_missions.add((name, region or "", landmark or "", t_start))
                    save_failed_missions(failed_missions)
                    honglou_fail_count = 0
                    time.sleep(5)
                    continue
                # Wait out mission TTL
                remain = MISSION_TTL - mission_age(t_start)
                print(f"  [HONGLOU] entry failed — idling {min(remain,120):.0f}s")
                idle_maintenance(s, nav)
                time.sleep(max(0, min(remain, 120)))
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
                    print("  [GLOBAL SWEEP] stuck — skipping quit+relog, waiting 30s")
                    time.sleep(30)
                continue
            remain = MISSION_TTL - mission_age(t_start)
            nap = min(remain + 5, 120)  # don't sleep more than 2 min at a time
            print(f"  unreachable region ({region}); idling {nap:.0f}s")
            idle_maintenance(s, nav)
            time.sleep(nap)
            continue

        # Check reachability from hub
        mission_key = (name, region, landmark)
        if mission_key in failed_missions:
            remain = MISSION_TTL - mission_age(t_start)
            nap = min(remain + 5, 90)  # short nap, keep checking
            print(f"  [SKIP] {name} confirmed unreachable — idling {nap:.0f}s")
            idle_maintenance(s, nav)
            time.sleep(nap)
            continue

        test_path = M.path(LANDMARKS["hub"], anchor)
        if test_path is None:
            remain = MISSION_TTL - mission_age(t_start)
            nap = min(remain + 5, 90)
            print(f"  {search_dirs} unreachable from hub; idling {nap:.0f}s")
            failed_missions.add(mission_key)
            save_failed_missions(failed_missions)
            idle_maintenance(s, nav)
            time.sleep(nap)
            continue

        # ── Pre-mission self-check ─────────────────────────────────────
        # Quick condition check: verify gear, HP, food/water before each mission
        quick_sc = m(s, "score", q=2.0)
        _dm = re.search(r"兵器伤害力：\[\s*(\d+)", quick_sc)
        cur_dmg = int(_dm.group(1)) if _dm else 0
        from economy import _money_from_score
        cur_money = _money_from_score(m(s, "i", q=1.0))  # use i not score

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
        if any(sd in DANGEROUS_DIRS for sd in search_dirs):
            if cur_dmg == 0:
                print(f"  [SKIP] dangerous area, no weapon — skipping 180s")
                idle_maintenance(s, nav)
                time.sleep(180)
                continue
            if cur_money < 10:
                print(f"  [DANGEROUS] low money ({cur_money:.1f}两) — withdrawing from bank first")
                from economy import _bank_withdraw
                cur_money = _bank_withdraw(s, nav, need=50)
                print(f"  [DANGEROUS] money after withdraw: {cur_money:.1f}两")
                if cur_money < 10:
                    print(f"  [SKIP] dangerous area, still broke after withdraw — skipping 180s")
                    idle_maintenance(s, nav)
                    time.sleep(180)
                    continue

        if cur_dmg == 0 and cur_money < 1:
            print("  [GEAR UP] unarmed + broke — trying bank")
            gear_up(s, nav)
            sc2 = m(s, "score", q=2.0)
            _dm2 = re.search(r"兵器伤害力：\[\s*(\d+)", sc2)
            if not (_dm2 and int(_dm2.group(1)) > 0):
                print("  still unarmed — attempting fight anyway (unarmed, no gold to buy gear)")
                # Don't skip — fall through to sweep_vicinity so we at least try to earn gold

        # ── SEARCHING + FIGHTING ──────────────────────────────────────
        t0 = time.time()
        result = sweep_vicinity(s, nav, M, anchor, search_dirs, name, ids, t_start=t_start)
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
            # ── Post-combat gear check: re-equip if weapon lost during fight ──
            sc_post = m(s, "score", q=2.0)
            _dm_post = re.search(r"兵器伤害力：\[\s*(\d+)", sc_post)
            dmg_post = int(_dm_post.group(1)) if _dm_post else 0
            if dmg_post == 0:
                print("  [POST-KILL] weapon lost during fight — re-equipping")
                inv_post = m(s, "i", q=1.0)
                if any(w in inv_post for w in ("刀", "剑", "枪", "叉", "棍", "棒", "斧", "锤", "杖", "匕")):
                    m(s, "wield all", q=1.0)
                else:
                    gear_up(s, nav)
            bank_deposit(s, nav)
            # ── 潜能 target check ──────────────────────────────────
            qn = check_qianneng(s, target=QIANNENG_TARGET)
            if qn >= QIANNENG_TARGET:
                print(f"\n  *** 潜能 TARGET REACHED: {qn} >= {QIANNENG_TARGET} — stopping ***")
                notify_done(qn)
                break

        elif result == "engaged_lost":
            print(f"  engaged {name} but unconfirmed — checking Yuan")
            pending_guai = name
            continue

        elif result == "dead":
            print("  !! WE DIED — recovering")
            s = recover_to_kezhan(s, nav)
            nav.s = s

        elif result == "stuck":
            # Navigation got stuck — mark mission as failed so we don't retry it
            # immediately (the d/sea tight-loop bug)
            failed_missions.add(mission_key)
            save_failed_missions(failed_missions)
            session_stuck_count += 1
            print(f"  [STUCK] {name} marked failed; session stuck count: {session_stuck_count}/{SESSION_STUCK_LIMIT}")

            # Too many stucks this session? Map overrides might be poisoned — rollback
            if session_stuck_count >= SESSION_STUCK_LIMIT:
                print("  [STUCK] too many stucks — rolling back map overrides!")
                M.rollback_overrides()
                session_stuck_count = 0

            # First: try to walk to hub manually — avoid quit+relog which drops all gear
            rid, _, _, _ = nav.look_and_identify()
            got_to_hub = False
            if rid:
                hub_path = M.path(rid, LANDMARKS["hub"])
                if hub_path is not None:
                    print(f"  [STUCK] walking to hub ({len(hub_path)} steps)")
                    try:
                        nav.goto(LANDMARKS["hub"], max_steps=100)
                        got_to_hub = True
                    except Exception:
                        print("  [STUCK] couldn't reach hub — will quit+relog")

            if not got_to_hub:
                # Can't escape — quit+relog as last resort
                if gear_expendable:
                    print("  [STUCK] gear basic, trapped — quit+relog (last resort)")
                    # Withdraw extra from bank BEFORE quitting so we can rebuy gear
                    from economy import _bank_withdraw, _money_from_score
                    try:
                        on_hand = _money_from_score(m(s, "i", q=1.0))
                        if on_hand < 30:
                            _bank_withdraw(s, nav, need=50)
                            print(f"  [STUCK] pre-quit bank withdrawal to cover gear rebuy")
                    except Exception:
                        pass
                    s = recover_to_kezhan(s, nav)
                    nav.s = s
                else:
                    print(f"  [STUCK] gear is GOOD (dmg={cur_dmg} arm={cur_arm}) — trapped but NOT quitting")
            else:
                # Made it to hub safely — gear intact, just give up this mission
                print(f"  [STUCK] safely at hub, gear intact (no quit needed) ✓")

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
    import traceback as _tb
    _attempt = 0
    while True:
        _attempt += 1
        try:
            main()
            break  # clean exit (target reached)
        except KeyboardInterrupt:
            print("\n[WATCHDOG] Interrupted — stopping.")
            break
        except Exception as _e:
            print(f"\n[WATCHDOG] CRASH (attempt {_attempt}): {type(_e).__name__}: {_e}")
            _tb.print_exc()
            print(f"[WATCHDOG] Restarting in 5s...")
            time.sleep(5)
