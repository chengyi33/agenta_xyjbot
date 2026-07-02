"""
economy.py — Gear purchasing, food/water management, banking.

Handles: gear up at start of session, eat/drink, deposit/withdraw money.
"""
import re, time, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (LANDMARKS, KEEP_ON_HAND, FOOD_THRESHOLD, WATER_THRESHOLD,
                    FULL_MSGS, EMPTY_MSGS, LOG_PATH)
from net import m, send, parse_hp, drain, clean
from nav import Navigator


def gear_up(s, nav):
    """Ensure we have weapon + shield. Self-aware: check i + score first.

    Logic:
    1. Check `i` (inventory) + `score` (equipped stats)
    2. If weapon in inventory but dmg=0 → wield it (was dropped on disconnect)
    3. If armor in inventory but armor<10 → wear it
    4. If no weapon in inventory → check yuan's floor → then buy from shop
    5. Re-check after each action
    """
    # ── Self-aware gear check ─────────────────────────────────────────
    inv = m(s, "i", q=1.5, log_path=LOG_PATH)
    sc = m(s, "score", q=2.5, log_path=LOG_PATH)
    dmg = _parse_stat(sc, r"兵器伤害力：\[\s*(\d+)")
    arm = _parse_stat(sc, r"盔甲保护力：\[\s*(\d+)")
    has_weapon_in_bag = any(w in inv for w in ("刀", "剑", "枪", "叉", "棍", "斧", "锤", "杖", "匕"))
    has_armor_in_bag = any(w in inv for w in ("甲", "盾", "袍", "衣", "护"))
    print(f"  [GEAR] dmg={dmg} armor={arm} | weapon_in_bag={has_weapon_in_bag} armor_in_bag={has_armor_in_bag}")

    # Wield weapon from inventory if not equipped
    if dmg == 0 and has_weapon_in_bag:
        print("  [GEAR] weapon in bag but not wielded — wielding")
        m(s, "wield all", q=1.0)
        sc = m(s, "score", q=2.0)
        dmg = _parse_stat(sc, r"兵器伤害力：\[\s*(\d+)")
        print(f"  [GEAR] dmg after wield: {dmg}")

    # Wear armor from inventory if not equipped
    if arm < 10 and has_armor_in_bag:
        print("  [GEAR] armor in bag but not worn — wearing")
        m(s, "wear all", q=1.0)
        sc = m(s, "score", q=2.0)
        arm = _parse_stat(sc, r"盔甲保护力：\[\s*(\d+)")
        print(f"  [GEAR] armor after wear: {arm}")

    if dmg > 0 and arm >= 10:
        print("  [GEAR] fully equipped — no shopping needed")
        return dmg, arm

    # ── Check yuan's floor for dropped gear ───────────────────────────
    nav.goto(LANDMARKS["yuan"])
    r = m(s, "look", q=1.5, log_path=LOG_PATH)
    if any(w in r for w in ("甲", "盔", "盾", "刀", "剑", "枪", "叉", "袍", "衣", "护")):
        print("  [GEAR] items at yuan — picking up")
        m(s, "get all", q=1.5)
        # Remove inferior gear before equipping better
        m(s, "unwield all", q=1.0)
        m(s, "remove all", q=1.0)
        m(s, "drop coarse", q=1.0)   # drop starting linen shirt
        m(s, "wield all", q=1.0)
        m(s, "wear all", q=1.0)
        sc = m(s, "score", q=2.5)
        dmg = _parse_stat(sc, r"兵器伤害力：\[\s*(\d+)")
        arm = _parse_stat(sc, r"盔甲保护力：\[\s*(\d+)")
        print(f"  [GEAR] after pickup: dmg={dmg} armor={arm}")

    if dmg > 0 and arm >= 10:
        return dmg, arm

    # Need to buy
    _bank_withdraw(s, nav, need=20)

    # Buy from 兵器铺
    nav.goto(LANDMARKS["shop"])
    print("  --- 兵器铺 stock ---")
    stock = m(s, "list", q=1.5)
    for ln in stock.split("\n"):
        if ln.strip():
            print(f"    {ln.strip()}")

    if dmg == 0:
        for wpn in ("blade", "spear", "sword", "fork", "dagger"):
            r = m(s, f"buy {wpn} from xiao xiao", q=1.3)
            if "钱不够" not in r and "什么" not in r:
                print(f"  [GEAR] bought {wpn}")
                break
    if arm < 10:
        r = m(s, "buy shield from xiao xiao", q=1.3)
        if "钱不够" not in r and "什么" not in r:
            print("  [GEAR] bought shield")

    m(s, "wield all", q=1.0)
    m(s, "wear all", q=1.0)

    # Check 当铺 (pawn shop) for better gear
    nav.goto(LANDMARKS.get("pawn", LANDMARKS["shop"]))
    pawn_stock = m(s, "list", q=1.5)
    if any(w in pawn_stock for w in ("甲", "盾", "刀", "剑", "枪")):
        print("  [GEAR] checking pawn shop for upgrades")
        for line in pawn_stock.split("\n"):
            if any(w in line for w in ("甲", "盾", "刀", "剑", "枪")) and "两" in line:
                # Try to buy the first good item
                # Parse the item id from the line
                m2 = re.search(r"\((\w+)\)", line)
                if m2:
                    item_id = m2.group(1)
                    r = m(s, f"buy {item_id} from dongpushen", q=1.3)
                    if "钱不够" not in r and "什么" not in r:
                        print(f"  [GEAR] bought {item_id} from pawn shop")
                        m(s, "wield all", q=1.0)
                        m(s, "wear all", q=1.0)
                        break

    sc = m(s, "score", q=2.5)
    dmg = _parse_stat(sc, r"兵器伤害力：\[\s*(\d+)")
    arm = _parse_stat(sc, r"盔甲保护力：\[\s*(\d+)")
    print(f"  gear final: dmg={dmg} armor={arm}")
    return dmg, arm


def eat_drink(s):
    """Eat/drink from inventory until full or items run out.
    Returns set of labels still low — caller decides whether to restock."""
    hr = m(s, "hp", q=1.5)
    hp = parse_hp(hr)
    still_low = set()
    for label, cmd in [("食物", "eat gourou"), ("饮水", "drink jiudai")]:
        if label not in hp:
            continue
        cur, mx = hp[label]
        if cur < mx:
            print(f"  [{label}] {cur}/{mx} — eating/drinking from inventory")
            ran_out = False
            for _ in range(15):
                r = m(s, cmd, q=0.5)
                if any(w in r for w in FULL_MSGS):
                    break
                if any(w in r for w in EMPTY_MSGS):
                    ran_out = True
                    break
            if ran_out:
                still_low.add(label)
    return still_low


FOOD_THRESHOLD = 150   # ~40% of max 360
WATER_THRESHOLD = 150


def needs_food_or_water(s):
    """Check hp — return (needs_food, needs_water, food_cur, water_cur)."""
    hr = m(s, "hp", q=1.5)
    hp = parse_hp(hr)
    food = hp.get("食物", (999, 360))
    water = hp.get("饮水", (999, 360))
    return food[0] < FOOD_THRESHOLD, water[0] < WATER_THRESHOLD, food[0], water[0]


def has_food_in_inv(inv):
    return any(w in inv for w in ("狗肉", "鸡腿", "gourou", "jitui", "肉"))


def has_jiudai_in_inv(inv):
    return "酒袋" in inv or "jiudai" in inv


def smart_eat_drink(s, nav):
    """Self-aware food/water management.

    Decision tree:
    1. Check hp — if food AND water >= 150, nothing to do
    2. Check inventory (i):
       - Have food in bag? → eat now (no trip)
       - Have jiudai in bag? → drink now (no trip)
    3. If still low after eating from inventory → go to kezhan:
       - No jiudai in inventory? → buy jiudai first (1两)
       - Fill jiudai (refills existing bag cheaply)
       - Buy gou rou if food still low
       - Eat/drink to full
    """
    needs_f, needs_w, food_cur, water_cur = needs_food_or_water(s)
    if not needs_f and not needs_w:
        return  # all good

    print(f"  [FOOD] food={food_cur} water={water_cur} — checking inventory")
    inv = m(s, "i", q=1.5, log_path=LOG_PATH)

    # Try eating/drinking from what we have
    still_low = eat_drink(s)

    # Re-check after eating from inventory
    needs_f, needs_w, food_cur, water_cur = needs_food_or_water(s)
    if not needs_f and not needs_w:
        print("  [FOOD] satisfied from inventory — no shop trip needed")
        return

    # Need to go to kezhan
    print(f"  [FOOD] still low (food={food_cur} water={water_cur}) — heading to kezhan")
    nav.goto(LANDMARKS["kezhan"])

    # Re-check inventory after arriving
    inv = m(s, "i", q=1.0)

    # Buy jiudai if we don't have one at all
    if not has_jiudai_in_inv(inv):
        print("  [FOOD] no jiudai in inventory — buying one")
        r = m(s, "buy jiudai from xiao er", q=1.3)
        if "钱不够" in r or "什么" in r:
            print("  [FOOD] couldn't buy jiudai!")
        else:
            print("  [FOOD] bought jiudai — MUST fill with water before drinking (alcohol!)")
            m(s, "fill jiudai", q=1.0)  # CRITICAL: replace alcohol with water

    # Fill jiudai (refill existing bag — much cheaper than buying new)
    # Also re-fills a freshly bought bag (which contains alcohol, not water)
    m(s, "fill jiudai", q=1.0)

    # Buy food if still needed
    if needs_f:
        print("  [FOOD] buying gou rou")
        for _ in range(8):
            r = m(s, "buy gourou from xiao er", q=0.6)
            if any(w in r for w in ("钱不够", "没有卖", "什么")):
                break

    # Eat/drink to full
    eat_drink(s)
    needs_f, needs_w, food_cur, water_cur = needs_food_or_water(s)
    print(f"  [FOOD] final: food={food_cur} water={water_cur}")


def wait_full_hp(s, tries=40):
    """Rest until 气血 AND 精神 are full."""
    for _ in range(tries):
        hr = m(s, "hp", q=1.0)
        hp = parse_hp(hr)
        qixue = hp.get("气血", (1, 1))
        jingshen = hp.get("精神", (1, 1))
        print(f"  [HP] 气血 {qixue[0]}/{qixue[1]}  精神 {jingshen[0]}/{jingshen[1]}")
        if qixue[0] >= qixue[1] and jingshen[0] >= jingshen[1]:
            return True
        time.sleep(6)
    print("  [HP] timed out — proceeding anyway")
    return False


def bank_deposit(s, nav):
    """Deposit excess money. Convert gold to silver first.

    Bank path from hub: west → north → west → south (d/city/bank)
    """
    nav.goto(LANDMARKS["bank"])
    # Deposit all gold coins into account first
    m(s, "deposit gold", q=2.0)
    # Convert gold to silver if we have gold on hand (for NPC payments)
    sc = m(s, "score", q=2.0)
    has_gold = re.search(r"黄金[^0-9]*(\d+)", sc)
    if has_gold and int(has_gold.group(1)) > 0:
        gold_amt = int(has_gold.group(1))
        print(f"  [BANK] converting {gold_amt} gold → {gold_amt * 100} silver")
        m(s, f"convert {gold_amt} gold to silver", q=2.0)
    # Check silver on hand
    sc = m(s, "score", q=2.0)
    on_hand = _money_from_score(sc)
    if on_hand <= KEEP_ON_HAND:
        # Withdraw enough to keep 50两 on hand
        if on_hand < KEEP_ON_HAND:
            need = int(KEEP_ON_HAND - on_hand)
            m(s, f"withdraw {need} silver", q=2.0)
            print(f"  [BANK] withdrew {need}两 for expenses")
        return
    to_deposit = int(on_hand - KEEP_ON_HAND)
    m(s, f"deposit {to_deposit} silver", q=2.0)
    print(f"  [BANK] deposited {to_deposit}两 (kept {KEEP_ON_HAND} on hand)")


def _bank_withdraw(s, nav, need=20):
    """Withdraw from bank if needed. Convert gold to silver first."""
    sc = m(s, "score", q=2.0)
    on_hand = _money_from_score(sc)
    if on_hand >= need:
        return on_hand
    nav.goto(LANDMARKS["bank"])
    # Deposit any gold coins first
    m(s, "deposit gold", q=2.0)
    # Convert gold to silver if available
    sc = m(s, "score", q=2.0)
    has_gold = re.search(r"黄金[^0-9]*(\d+)", sc)
    if has_gold and int(has_gold.group(1)) > 0:
        gold_amt = int(has_gold.group(1))
        print(f"  [BANK] converting {gold_amt} gold → silver")
        m(s, f"convert {gold_amt} gold to silver", q=2.0)
    sc = m(s, "score", q=2.0)
    on_hand = _money_from_score(sc)
    if on_hand >= need:
        return on_hand
    to_withdraw = need - int(on_hand)
    m(s, f"withdraw {to_withdraw} silver", q=2.0)
    print(f"  [BANK] withdrew {to_withdraw}两")
    return _money_from_score(m(s, "score", q=2.0))


def _money_from_score(sc):
    """Parse total silver from score."""
    mm = re.search(r"(\d+)\s*两", sc)
    liang = int(mm.group(1)) if mm else 0
    mm2 = re.search(r"(\d+)\s*钱", sc)
    qian = int(mm2.group(1)) if mm2 else 0
    mm3 = re.search(r"黄金[^0-9]*(\d+)", sc)
    gold = int(mm3.group(1)) if mm3 else 0
    return liang + qian / 10.0 + gold * 100


def _parse_stat(sc, pattern):
    mm = re.search(pattern, sc)
    return int(mm.group(1)) if mm else 0


def already_geared(s):
    """Check if weapon is equipped."""
    sc = m(s, "score", q=2.0)
    dmg = _parse_stat(sc, r"兵器伤害力：\[\s*(\d+)")
    return dmg > 0
