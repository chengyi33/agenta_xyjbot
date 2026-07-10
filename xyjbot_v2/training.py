"""
training.py — 阴曹地府 skill training module (UPDATED).

Fixes applied (July 9):
  - STOP_QN changed from 600 → 100 (train until 潜能 < 100)
  - After bridge entry, navigate from 白无常 to 王方平 (was missing this step)
  - Bridge entrance uses nav.goto() instead of blind walking
  - Added post-enter verification (阴阳界 check)
  - Added verification before training: confirm at 王方平 before learning
  - Added learn failure detection: abort after 3 consecutive failed learns
  - SKILLS: 5 working skills (dodge/force/parry/stick/ghost-steps)
  - Sleep at 司房, exit-aware return (e→n→n or e→n→w→w→n)
  - Source-verified: 王方平 teaches ALL basic + special skills
"""
import re, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import LANDMARKS, LOG_PATH
from net import m, send, parse_hp, drain, clean
from economy import smart_eat_drink

# ── 地府 landmarks ─────────────────────────────────────────────────
BRIDGE_ROOM = "d/changan/bridge"
DEATH_GATE = "d/death/gate"
BAIWUCHANG_ROOM = "d/death/new-zhaopo"
WANGFANGPING_ROOM = "d/death/new-lunhui"
SIFANG_ROOM = "d/death/new-sifang1"  # 司房 — sleep room

GATE_TO_WUCHANG = ["north", "north"]
WUCHANG_TO_WANG = ["north", "west", "north"]

# Exit path: 轮回司 → 长安城中心 (source-verified by yxc)
# s,e,e,e,e,s,s,s,se,out → open guancai → out → w → n×9 → 长安城中心
EXIT_DIFU_PATH = ["south","east","east","east","east","south","south","south","southeast","out"]
EXIT_GUANCAI_PATH = ["west"] + ["north"] * 9

MASTER_NAME = "wang fangping"
MASTER_ROOM = WANGFANGPING_ROOM

# ── Skills: 5 working skills (source-verified that 王方平 teaches all) ──
# REMOVED: tonsillit (needs 杀气), kusang-bang (needs 内力)
# Both will be added later after 杀气 farming and 内力 building
SKILLS_TO_LEARN = [
    ("dodge", MASTER_NAME),
    ("force", MASTER_NAME),
    ("parry", MASTER_NAME),
    ("stick", MASTER_NAME),
    ("ghost-steps", MASTER_NAME),
]

SPIRIT_SLEEP_RATIO = 0.20       # sleep at <20% spirit (buffer for navigation)
TRAIN_FOOD_MIN = 120
TRAIN_WATER_MIN = 120
STOP_QN = 100                   # stop when 潜能 below this


def _parse_skills(output):
    skills = {}
    for line in output.split("\n"):
        m = re.search(r'\((\S+)\)\s.*?(\d+)\s*/\s*(\d+)', line)
        if m:
            skills[m.group(1)] = int(m.group(2))
        m2 = re.search(r'^\s*(\S+)\s*:\s*(\d+)', line)
        if m2 and m2.group(1) not in skills:
            skills[m2.group(1)] = int(m2.group(2))
    return skills


def _get_lowest_skill(s, skill_names):
    r = m(s, "skills", q=2.0, log_path=LOG_PATH)
    parsed = _parse_skills(r)
    lowest, lowest_level = None, 9999
    for name in skill_names:
        lvl = parsed.get(name, 0)
        if lvl < lowest_level:
            lowest_level, lowest = lvl, name
    return lowest, lowest_level, parsed


def _get_exits(desc):
    """Parse exit directions from room look."""
    m_ex = re.search(r'出口[^。\n]*?[是：:]\s*(.+)', desc)
    if not m_ex:
        return []
    seg = re.split(r'[。\n]', m_ex.group(1))[0]
    dirs = re.findall(r'[a-zA-Z]+', seg.lower())
    valid = {"north","south","east","west","up","down","enter","out"}
    return [d for d in dirs if d in valid]


def _has_master(look_output):
    return "王方平" in look_output


def _sleep_at_sifang(s):
    """Sleep at 司房: s,s,w from 轮回司 → sleep."""
    for d in ("south", "south", "west"):
        m(s, d, q=0.3)
    r = m(s, "sleep", q=3.0)
    return r


def _wake_and_return(s):
    """Wake from 司房, navigate back to 王方平 using exit detection."""
    m(s, "wake", q=1.5)
    time.sleep(0.5)
    
    lk = m(s, "look", q=2.0)
    exits = _get_exits(lk)
    print(f"  [TRAIN] wake at 司房, exits={exits}")
    
    # Take the available exit from 司房 toward yinsi area
    moved = False
    for d in exits:
        m(s, d, q=0.3)
        moved = True
        break
    
    if moved:
        # Now in yinsi — go north to幽司, then try north again
        m(s, "north", q=0.3)  # yinsi→幽司
        lk = m(s, "look", q=0.5)
        m(s, "north", q=0.3)  # try →轮回司
        if not _has_master(m(s, "look", q=0.5)):
            # Wrong幽司 (walk3) — go W,W,N instead
            m(s, "south", q=0.3)   # back to幽司
            m(s, "west", q=0.3)    # → walk2(奉祭场)
            m(s, "west", q=0.3)    # → walk4(幽司)
            m(s, "north", q=0.3)   # → 轮回司
    
    # Final verify
    if not _has_master(m(s, "look", q=0.5)):
        for d in ("north", "south", "east", "west"):
            m(s, d, q=0.2)
            if _has_master(m(s, "look", q=0.3)):
                break
    return _has_master(m(s, "look", q=0.5))


def _sleep_recover(s, nav):
    """Sleep at 司房, wait 90s for recovery, return to master."""
    print(f"  [TRAIN] sleeping at 司房...")
    _sleep_at_sifang(s)
    time.sleep(90)
    if _wake_and_return(s):
        print(f"  [TRAIN] ✅ back at 王方平")
    else:
        print(f"  [TRAIN] ⚠️ lost after sleep — trying bridge re-entry")
        _navigate_to_wangfangping(s, nav)


def _restock_and_return(s, nav):
    """Exit 地府 → 长安客栈 → buy food + fill jiudai → return to 王方平."""
    print(f"  [TRAIN] 🍜 restocking food/water at 客栈...")

    # 1. Exit 地府 → 荒坟堆 (d/changan/fendui)
    print(f"  [TRAIN] exiting 地府...")
    for d in EXIT_DIFU_PATH:
        m(s, d, q=1.0)
        time.sleep(0.3)
    m(s, "open guancai", q=2.0)   # kicks open coffin → 荒坟堆 (长安郊外)
    time.sleep(0.5)

    # 2. Walk toward city center (w + n×9), then sync nav position
    for d in EXIT_GUANCAI_PATH:
        m(s, d, q=1.0)
        time.sleep(0.3)

    # CRITICAL: raw moves don't update nav.current_rid — force re-sync
    nav.current_rid = None
    rid, short, _, _ = nav.look_and_identify()
    print(f"  [TRAIN] out of 地府, now at {short} ({rid})")

    # 3. Go to kezhan via map nav
    try:
        nav.goto(LANDMARKS["kezhan"], max_steps=60)
    except Exception as e:
        print(f"  [TRAIN] ⚠️ nav to kezhan failed ({e}) — using recall")
        m(s, "recall", q=2.0)
        nav.current_rid = None
        nav.look_and_identify()
        nav.goto(LANDMARKS["kezhan"], max_steps=60)

    # 3. Buy food + fill jiudai
    from economy import smart_eat_drink
    smart_eat_drink(s, nav)
    # Also explicitly fill jiudai if we have one (covers edge cases)
    inv = m(s, "i", q=1.0)
    if "酒袋" in inv or "jiudai" in inv:
        m(s, "fill jiudai", q=1.0)
        m(s, "drink jiudai", q=1.0)

    # 4. Return to 地府 and 王方平
    print(f"  [TRAIN] returning to 地府...")
    _navigate_to_wangfangping(s, nav)

    # Verify we're back
    if not _has_master(m(s, "look", q=0.3)):
        print(f"  [TRAIN] ⚠️ not at 王方平 after restock — re-navigating")
        _navigate_to_wangfangping(s, nav)


def _navigate_to_wangfangping(s, nav):
    """Navigate to 王方平. Handles in-地府 and outside."""
    print("  [JOIN] navigating to 王方平 (轮回司)...")
    rid, _, short, _ = nav.look_and_identify()
    
    # Already at 王方平? Skip all navigation
    look_now = m(s, "look", q=0.3)
    if _has_master(look_now):
        print(f"  [JOIN] ✅ already at 轮回司 ({rid})")
        nav.current_rid = MASTER_ROOM
        # Apprentice (once, no-op if already)
        m(s, "apprentice wang fangping", q=1.5)
        return
    
    in_difu = rid and rid.startswith("d/death/")

    if not in_difu:
        print("  [JOIN] not physically in 地府 — taking bridge route")
        _enter_difu_via_bridge(s, nav)
        # After bridge entry, we're at 招魂司 (白无常) — walk to 轮回司 (王方平)
        print("  [JOIN] at 白无常 — walking to 王方平 (轮回司)")
        for direction in WUCHANG_TO_WANG:
            look_dir = m(s, "look", q=0.3)
            m(s, direction, q=1.5)
            time.sleep(0.5)
    else:
        print(f"  [JOIN] in 地府 ({short}) — walking to 轮回司")
        for direction in WUCHANG_TO_WANG:
            m(s, direction, q=1.5)
            time.sleep(0.5)
        look = m(s, "look", q=1.0)
        if not _has_master(look):
            for d in ("north", "south", "east", "west"):
                m(s, d, q=0.5)
                if _has_master(m(s, "look", q=0.5)):
                    break
            else:
                print("  [JOIN] direct walk failed — using bridge route")
                _enter_difu_via_bridge(s, nav)

    look = m(s, "look", q=1.0)
    if _has_master(look):
        print("  [JOIN] arrived at 轮回司 (王方平) ✅")
        nav.current_rid = MASTER_ROOM
    else:
        print("  [JOIN] ⚠️ still not at 王方平 — apprenticing from current room")

    # Apprentice (once)
    print("  [JOIN] apprenticing to 王方平...")
    r = m(s, "apprentice wang fangping", q=2.0)
    print(f"  [JOIN] wang apprentice: {r[:200] if r else '(none)'}")


def _enter_difu_via_bridge(s, nav):
    """Enter 地府 via bridge → gate → walk to 招魂司."""
    print("  [ENTER] entering 地府 via bridge...")
    
    # Navigate to bridge using map system (not manual walk-around)
    nav.goto(BRIDGE_ROOM, max_steps=40)
    out = m(s, "look", q=0.5)
    if "泾水桥" not in out:
        print("  [ENTER] ⚠️ not at bridge — walking to find it")
        for _ in range(20):
            out = m(s, "look", q=0.3)
            if "泾水桥" in out:
                print("  [ENTER] at 泾水桥 ✅")
                break
            m_ex = re.findall(r'出口[^。\n]*?[是：:]\s*(.+)', out)
            if m_ex:
                dirs = re.findall(r'[a-zA-Z]+', m_ex[0].lower())
                if "south" in dirs:
                    m(s, "south", q=0.3)
                    time.sleep(0.3)
                    continue
            for d in ("south", "west", "east"):
                m(s, d, q=0.3)
                break
        else:
            print("  [ENTER] ⚠️ bridge not found — trying jump anyway")

    m(s, "remove follower", q=0.5)
    time.sleep(0.3)
    m(s, "jump bridge", q=3.0)
    time.sleep(1)
    
    # Verify we entered 地府
    look_after = m(s, "look", q=0.5)
    if "阴阳界" in look_after or "鬼门关" in look_after:
        print("  [ENTER] ✅ arrived at 阴阳界")
    else:
        print(f"  [ENTER] ⚠️ bridge jump may have failed: {look_after[:100]}")
    
    for direction in GATE_TO_WUCHANG:
        m(s, direction, q=1.5)
        time.sleep(0.5)


def _join_difu(s, nav):
    """Join 阴曹地府 via 白无常 → 王方平. Returns True on success."""
    print("\n[JOIN] === Joining 阴曹地府 ===")
    print("  [JOIN] navigating to 长安桥...")
    nav.goto(BRIDGE_ROOM, max_steps=30)

    print("  [JOIN] dismissing follower NPC...")
    m(s, "remove follower", q=1.0)
    m(s, "stop follow", q=0.5)

    print("  [JOIN] jumping off bridge...")
    r = m(s, "jump bridge", q=3.0)
    if "噗嗵" in r or "掉到水中" in r or "水" in r:
        print("  [JOIN] fell in water! Climbing out and retrying...")
        m(s, "out", q=1.0)
        m(s, "east", q=1.0)
        nav.goto(BRIDGE_ROOM, max_steps=15)
        r = m(s, "jump bridge", q=3.0)
        if "噗嗵" in r or "掉到水中" in r:
            print("  [JOIN] fell in water again — may already be in a sect")
            return False

    look = m(s, "look", q=1.0)
    if "阴阳界" in look or "鬼门关" in look:
        print("  [JOIN] arrived at 阴阳界 (gate)")
    else:
        for d in ("south", "north", "east", "west"):
            m(s, d, q=0.5)
            if "阴阳界" in m(s, "look", q=0.5):
                break

    print("  [JOIN] walking to 招魂司 (白无常)...")
    for direction in GATE_TO_WUCHANG:
        m(s, direction, q=2.0)
        time.sleep(0.5)

    look = m(s, "look", q=1.5)
    if "白无常" not in look:
        for d in ("north", "south", "east", "west"):
            m(s, d, q=0.5)
            if "白无常" in m(s, "look", q=0.5):
                break
        else:
            print("  [JOIN] ⚠️ 白无常 not found — join may fail")

    print("  [JOIN] apprenticing to 白无常...")
    r = m(s, "apprentice bai wuchang", q=2.0)
    print(f"  [JOIN] apprentice response: {r[:200] if r else '(none)'}")

    sc = m(s, "score", q=2.0)
    if "阎罗地府" not in sc:
        print("  [JOIN] ⚠️ Join failed — aborting")
        return False
    print("  [JOIN] ✅ Successfully joined 阴曹地府!")

    print(f"  [JOIN] navigating to 王方平 (轮回司)...")
    for direction in WUCHANG_TO_WANG:
        m(s, direction, q=1.5)
        time.sleep(0.5)
    look = m(s, "look", q=1.0)
    if not _has_master(look):
        for d in ("north", "south", "east", "west"):
            m(s, d, q=0.5)
            if _has_master(m(s, "look", q=0.5)):
                break

    print("  [JOIN] apprenticing to 王方平...")
    r2 = m(s, "apprentice wang fangping", q=2.0)
    print(f"  [JOIN] wang apprentice response: {r2[:200] if r2 else '(none)'}")
    nav.current_rid = MASTER_ROOM
    return True


def train_at_difu(s, nav):
    """Full training routine: join, learn 5 skills evenly until 潜能 < 600."""
    sc = m(s, "score", q=2.0)
    in_difu = "阎罗地府" in sc

    if not in_difu:
        if not _join_difu(s, nav):
            print("  [TRAIN] ❌ Failed to join 地府 — aborting training")
            return False
    else:
        print("\n[TRAIN] Already in 阴曹地府 — navigating to 王方平")
        _navigate_to_wangfangping(s, nav)

    skill_names = [s[0] for s in SKILLS_TO_LEARN]
    print(f"\n[TRAIN] === Training {len(skill_names)} skills: {', '.join(skill_names)} ===")
    print(f"  [TRAIN] Stop when 潜能 < {STOP_QN}")

    # Verify we're at 王方平 before starting training
    verify_look = m(s, "look", q=0.5)
    if not _has_master(verify_look):
        print(f"  [TRAIN] ⚠️ not at {MASTER_NAME} — re-navigating")
        _navigate_to_wangfangping(s, nav)
        verify_look = m(s, "look", q=0.5)
        if not _has_master(verify_look):
            print(f"  [TRAIN] ❌ can't reach {MASTER_NAME} — aborting training")
            return False
    print(f"  [TRAIN] ✅ at 轮回司 (王方平) — beginning training")

    cycle = 0
    total_learns = 0
    failed_learn_count = 0
    last_qn = None

    while True:
        cycle += 1
        hp = parse_hp(m(s, "hp", q=1.0))
        qn = hp.get("潜能", 0)
        
        if qn < STOP_QN:
            print(f"\n[TRAIN] ✅ 潜能={qn} < {STOP_QN} — training complete!")
            break

        jingshen = hp.get("精神", (0, 1))
        food = hp.get("食物", (0, 400))
        water = hp.get("饮水", (0, 400))

        # Food/water — exit 地府 to restock if low
        if food[0] < TRAIN_FOOD_MIN or water[0] < TRAIN_WATER_MIN:
            print(f"  [TRAIN] food={food[0]} water={water[0]} — need restock")
            _restock_and_return(s, nav)
            # Re-check after restock
            hp = parse_hp(m(s, "hp", q=0.5))
            food = hp.get("食物", (0, 400))
            water = hp.get("饮水", (0, 400))
            jingshen = hp.get("精神", (0, 1))
            print(f"  [TRAIN] after restock: food={food[0]} water={water[0]}")

        # Spirit check
        spirit_ratio = jingshen[0] / max(jingshen[1], 1)
        if spirit_ratio < SPIRIT_SLEEP_RATIO:
            print(f"  [TRAIN] 精神 low ({jingshen[0]}/{jingshen[1]}) — sleeping")
            _sleep_recover(s, nav)
            continue

        # Learn lowest skill (round-robin for even leveling)
        lowest, lowest_lvl, all_skills = _get_lowest_skill(s, skill_names)
        if lowest is None:
            lowest = "force"

        if cycle % 10 == 1:
            levels = ", ".join(f"{k}={all_skills.get(k, '?')}" for k in skill_names)
            print(f"  [TRAIN] cycle={cycle} | 潜能={qn} | 精神={jingshen[0]}/{jingshen[1]} | {levels} | → {lowest}({lowest_lvl})")

        r = m(s, f"learn {lowest} from {MASTER_NAME}", q=1.5)
        total_learns += 1

        # Success detection: "你从...那里" (old), "你向...请教...似乎有些心得" (XYJ2000)
        learn_success = False
        if r:
            if "你从" in r:
                learn_success = True
            elif "似乎有些心得" in r or ("你向" in r and "指导" in r):
                learn_success = True
            elif "这项技能你已经学得" in r or "已经是" in r:
                learn_success = True
                print(f"  [TRAIN] ✅ skill maxed — {r[:60]}")

        if learn_success:
            failed_learn_count = 0  # reset on success
        else:
            failed_learn_count += 1
            print(f"  [TRAIN] ⚠️ learn failed (×{failed_learn_count}): {r[:100] if r else '(no response)'}")

        # Recheck every learn
        hp2 = parse_hp(m(s, "hp", q=0.5))
        qn2 = hp2.get("潜能", 0)
        if qn2 < STOP_QN:
            print(f"\n[TRAIN] ✅ 潜能={qn2} < {STOP_QN} — complete!")
            break

        # Detect stuck learns: if 潜能 hasn't changed after 3 learns, break
        if last_qn is not None and qn2 >= last_qn and failed_learn_count >= 3:
            print(f"\n[TRAIN] ❌ 潜能 stuck at {qn2} after {failed_learn_count} failed learns — aborting")
            print(f"  [TRAIN] Probably not at {MASTER_NAME} — check navigation")
            break
        last_qn = qn2

    # Final report
    print(f"\n[TRAIN] === Training finished ===")
    print(f"  Total cycles: {cycle}, learns: {total_learns}")
    final_skills = _get_lowest_skill(s, skill_names)[2]
    if final_skills:
        levels = ", ".join(f"{k}={final_skills.get(k, '?')}" for k in skill_names)
        print(f"  Final skills: {levels}")

    # Return to hub via proper exit path
    print("  [TRAIN] returning to 长安...")
    try:
        for d in EXIT_DIFU_PATH:
            m(s, d, q=0.5)
            time.sleep(0.3)
        m(s, "open guancai", q=1.0)
        m(s, "out", q=0.5)
        # Now at 长安 south — walk to center
        for d in EXIT_GUANCAI_PATH:
            m(s, d, q=0.5)
            time.sleep(0.3)
        # Should be in recognizable area — nav to hub
        nav.goto(LANDMARKS["hub"], max_steps=40)
    except Exception:
        m(s, "recall", q=2.0)

    return True


# ── Standalone test ─────────────────────────────────────────────────
if __name__ == "__main__":
    from nav import Navigator
    from map_engine import XYJMap
    from net import connect
    M = XYJMap()
    s = connect()
    nav = Navigator(s, M)
    train_at_difu(s, nav)