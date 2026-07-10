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


def _prefer_jingubang(s):
    """If 金箍棒 (250 dmg) is in inventory, make it the primary weapon.

    gear_up/smart_eat_drink call 'wield all' which re-equips 钢刀 (25 dmg)
    as primary, dropping the jingubang. Re-assert jingubang so the bot
    keeps 250 dmg after any gear/restock action.
    """
    inv = m(s, "i", q=1.0, log_path=LOG_PATH)
    if "金箍棒" in inv or "jingubang" in inv.lower():
        sc = m(s, "score", q=2.0, log_path=LOG_PATH)
        dmg = _parse_stat(sc, r"兵器伤害力：\[\s*(\d+)")
        if dmg < 250:
            m(s, "unwield blade", q=1.0)
            m(s, "wield jingubang", q=1.5)


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
    has_weapon_in_bag = any(w in inv for w in ("刀", "剑", "枪", "叉", "棍", "棒", "斧", "锤", "杖", "匕"))
    has_armor_in_bag = any(w in inv for w in ("甲", "盾", "袍", "衣", "护"))
    print(f"  [GEAR] dmg={dmg} armor={arm} | weapon_in_bag={has_weapon_in_bag} armor_in_bag={has_armor_in_bag}")

    # Wield weapon from inventory if not equipped
    if dmg == 0 and has_weapon_in_bag:
        print("  [GEAR] weapon in bag but not wielded — wielding")
        m(s, "wield all", q=1.0)
        _prefer_jingubang(s)
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
        _prefer_jingubang(s)
        m(s, "wear all", q=1.0)
        sc = m(s, "score", q=2.5)
        dmg = _parse_stat(sc, r"兵器伤害力：\[\s*(\d+)")
        arm = _parse_stat(sc, r"盔甲保护力：\[\s*(\d+)")
        print(f"  [GEAR] after pickup: dmg={dmg} armor={arm}")

    if dmg > 0 and arm >= 10:
        return dmg, arm

    # Need to buy
    # ── Check bank for money (score doesn't show money on this server) ──
    print("  [GEAR] unarmed + broke — trying bank")
    nav.goto(LANDMARKS["bank"])
    bal_r = m(s, "account", q=2.0)
    bal = _parse_account(bal_r)
    print(f"  [BANK] account balance: {bal}两")
    if bal > 0:
        to_withdraw = min(bal, 15)  # enough for blade+shield
        m(s, f"withdraw {to_withdraw} silver", q=2.0)
        # Verify we got the money by trying to buy
        nav.goto(LANDMARKS["shop"])
        print("  [SHOP] trying to buy basic gear...")
        r = m(s, "buy blade from xiao xiao", q=1.5)
        if "你从萧萧" in r or "买了" in r:
            print("  [GEAR] bought blade (5两)")
        r = m(s, "buy shield from xiao xiao", q=1.5)
        if "你从萧萧" in r or "买了" in r:
            print("  [GEAR] bought shield (10两)")
        m(s, "wield all", q=1.0)
        _prefer_jingubang(s)
        m(s, "wear all", q=1.0)
        sc = m(s, "score", q=2.0)
        dmg = _parse_stat(sc, r"兵器伤害力：\[\s*(\d+)")
        arm = _parse_stat(sc, r"盔甲保护力：\[\s*(\d+)")
        print(f"  gear final: dmg={dmg} armor={arm}")
        return dmg, arm
    else:
        print("  [GEAR] truly broke — 0 in bank, proceeding unarmed")
        sc = m(s, "score", q=2.5)
        dmg = _parse_stat(sc, r"兵器伤害力：\[\s*(\d+)")
        arm = _parse_stat(sc, r"盔甲保护力：\[\s*(\d+)")
        print(f"  gear final: dmg={dmg} armor={arm}")
        return dmg, arm
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
    _prefer_jingubang(s)
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
                        _prefer_jingubang(s)
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
    # ── Check gold: withdraw from bank if needed ──
    # NOTE: score doesn't show money on this server — use inventory (i) instead
    inv_check = m(s, "i", q=1.5)
    gold_on_hand = _money_from_score(inv_check)
    if gold_on_hand < 1:
        # Try bank withdraw before giving up
        print("  [FOOD] 0 gold on hand — checking bank")
        nav.goto(LANDMARKS["bank"])
        bal_r = m(s, "account", q=2.0)
        bal = _parse_account(bal_r)
        if bal > 0:
            to_withdraw = min(bal, 15)
            m(s, f"withdraw {to_withdraw} silver", q=2.0)
            print(f"  [FOOD] withdrew {to_withdraw}两 from bank (had {bal}两)")
            inv_check = m(s, "i", q=1.5)
            gold_on_hand = _money_from_score(inv_check)
    if gold_on_hand < 1:
        print(f"  [FOOD] 0 gold — skipping shop, proceeding broke (will earn gold from kills)")
        return
    # ── END PATCH ──
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

    # Buy food if still needed AND we don't already have it
    if needs_f and not has_food_in_inv(inv):
        print("  [FOOD] buying gou rou")
        for _ in range(8):
            r = m(s, "buy gourou from xiao er", q=0.6)
            if any(w in r for w in ("钱不够", "没有卖", "什么")):
                break
    elif needs_f and has_food_in_inv(inv):
        print("  [FOOD] already have food in inventory — skipping buy")

    # Eat/drink to full
    eat_drink(s)
    needs_f, needs_w, food_cur, water_cur = needs_food_or_water(s)
    print(f"  [FOOD] final: food={food_cur} water={water_cur}")


def wait_full_hp(s, tries=40):
    """Rest until 气血 AND 精神 are full.
    Format: kee/eff_kee (eff_kee%of-max) - current HP vs effective HP.
    Full when kee >= eff_kee (current HP restored to effective max).
    """
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


def bank_deposit(s, nav, keep=None):
    """Deposit excess money. Convert gold to silver first.

    Bank path from hub: west → north → west → south (d/city/bank)
    """
    threshold = keep if keep is not None else KEEP_ON_HAND
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
    # Check silver on hand (use i not score — score doesn't show money on this server)
    inv = m(s, "i", q=2.0)
    on_hand = _money_from_score(inv)
    if on_hand <= threshold:
        # Withdraw enough to keep threshold on hand
        if on_hand < threshold:
            need = int(threshold - on_hand)
            m(s, f"withdraw {need} silver", q=2.0)
            print(f"  [BANK] withdrew {need}两 for expenses")
        return
    to_deposit = int(on_hand - threshold)
    m(s, f"deposit {to_deposit} silver", q=2.0)
    print(f"  [BANK] deposited {to_deposit}两 (kept {threshold} on hand)")


def _bank_withdraw(s, nav, need=20):
    """Withdraw from bank if needed. Convert gold to silver first."""
    inv = m(s, "i", q=2.0)  # score doesn't show money on this server
    on_hand = _money_from_score(inv)
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
    inv = m(s, "i", q=2.0)
    on_hand = _money_from_score(inv)
    if on_hand >= need:
        return on_hand
    to_withdraw = need - int(on_hand)
    m(s, f"withdraw {to_withdraw} silver", q=2.0)
    print(f"  [BANK] withdrew {to_withdraw}两")
    return _money_from_score(m(s, "i", q=2.0))


def _parse_chinese_number(s):
    """Parse Chinese number string: 八十→80, 八十八→88, 一百二十三→123."""
    cn_digits = {'零':0,'一':1,'二':2,'三':3,'四':4,'五':5,'六':6,'七':7,'八':8,'九':9}
    cn_units = {'十':10,'百':100,'千':1000,'万':10000}
    result = 0
    current = 0
    for ch in s:
        if ch in cn_digits:
            current = cn_digits[ch]
        elif ch in cn_units:
            unit = cn_units[ch]
            if current == 0:
                current = 1  # bare unit like 十=10
            result += current * unit
            current = 0
        else:
            return 0  # unknown char
    result += current
    return result


def _money_from_score(sc):
    """Parse total silver from score OR inventory output.
    Now parses BOTH gold (100两 each) and silver from inventory format."""
    total = 0

    # Try inventory format: "九两黄金(Gold)" + "四十一两银子(Silver)"
    mm_gold = re.search(r"(\S+?)两黄金", sc)
    mm_silver = re.search(r"(\S+?)两银子", sc)

    if mm_gold or mm_silver:
        if mm_gold:
            num_str = mm_gold.group(1)
            try:
                total += int(num_str) * 100
            except ValueError:
                total += _parse_chinese_number(num_str) * 100
        if mm_silver:
            num_str = mm_silver.group(1)
            try:
                total += int(num_str)
            except ValueError:
                total += _parse_chinese_number(num_str)
        return total

    # Fallback: score/bank format with Arabic numerals
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


def _parse_account(response):
    """Parse bank account balance including gold and silver.
    Format: '您在敝银庄共存有九两黄金六两白银'. Gold = 100 silver each.
    Also handles Arabic numerals: '5两黄金20两白银'."""
    total = 0
    # Pattern: <number>两<currency> where currency is 黄金 or 白银/银子
    # Use finditer to catch all occurrences
    for m in re.finditer(r'([\d一二三四五六七八九十百千万]+)\s*两\s*(黄金|白银|银子)?', response):
        num_str = m.group(1)
        currency = m.group(2) or ''
        # Parse the number
        try:
            val = int(num_str)
        except ValueError:
            val = _parse_chinese_number(num_str)
        if not val:
            continue
        # Multiply gold by 100
        if currency == '黄金':
            total += val * 100
        else:
            total += val
    # Fallback: old format with just "存有X两" (no currency labels at all)
    if total == 0:
        cn = {"一":1,"二":2,"三":3,"四":4,"五":5,"六":6,"七":7,"八":8,"九":9,"十":10}
        mm = re.search(r"存有(.+?)两", response)
        if mm:
            word = mm.group(1)
            try:
                return int(word)
            except ValueError:
                if word in cn:
                    return cn[word]
                val = cn.get(word[-1], 0)
                if "十" in word:
                    val += 10
                return val
    return total


def already_geared(s):
    """Check if weapon is equipped."""
    sc = m(s, "score", q=2.0)
    dmg = _parse_stat(sc, r"兵器伤害力：\[\s*(\d+)")
    return dmg > 0


def has_bishui_zhou(s):
    """Check if we have 避水咒 (bishui zhou) talisman in inventory."""
    inv = m(s, "i", q=1.5, log_path=LOG_PATH)
    return "避水咒" in inv or "bishui" in inv.lower()


def get_bishui_zhou(s, nav):
    """Acquire 避水咒 by trading jiudai to 袁守诚 at 袁氏草堂.

    Process: kezhan → buy jiudai (if needed) → caotang → give jiudai to yuan
    袁守诚 is at d/city/yuancao (caotang landmark).
    Returns True if we now have bishui zhou.
    """
    if has_bishui_zhou(s):
        print("  [BISHUI] already have 避水咒")
        return True

    print("  [BISHUI] getting 避水咒 from 袁守诚...")

    # ── PATCH: skip if broke — can't buy jiudai ──
    inv_b = m(s, "i", q=1.5)  # score doesn't show money on this server
    if _money_from_score(inv_b) < 1:
        print("  [BISHUI] 0 gold — skipping 避水咒 for now")
        return False
    # ── END PATCH ──

    # Ensure we have jiudai
    inv = m(s, "i", q=1.5)
    if not has_jiudai_in_inv(inv):
        print("  [BISHUI] buying jiudai at kezhan first")
        nav.goto(LANDMARKS["kezhan"])
        m(s, "buy jiudai from xiao er", q=1.5)

    # Go to 袁守诚 at 袁氏草堂 (caotang)
    nav.goto(LANDMARKS["caotang"])

    # Give jiudai to 袁守诚 to receive 避水咒
    r = m(s, "give jiudai to yuan", q=3.0)
    print(f"  [BISHUI] give response: {r[:120] if r else '(none)'}")

    if has_bishui_zhou(s):
        print("  [BISHUI] ✅ 避水咒 obtained!")
        return True
    else:
        print("  [BISHUI] ❌ failed to get 避水咒")
        return False
