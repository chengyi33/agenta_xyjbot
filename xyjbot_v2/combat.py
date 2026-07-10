"""
combat.py — Combat logic: engage, monitor, victory/defeat detection.

Simplified from original: wimpy at 10%, re-engage immediately after fleeing.
"""
import time, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (WIMPY, COMBAT_TIMEOUT, VICTORY_SIGNS, DEATH_SIGNS,
                    KO_SIGN, LOSS_SIGN, MONSTER_FLEE, CN_DIR, LOG_PATH)
from net import drain, clean, m, parse_short


def engage(s, name, ids=None):
    """Engage the monster. Try preferred ids, then fallback to guai/jing."""
    print(f"  >> ENGAGING {name}")
    tids = list(ids or []) + ["guai", "jing"]

    # Follow first
    for tid in tids:
        m(s, f"follow {tid}", q=0.8)

    # Try to start combat
    for _ in range(3):
        for tid in tids:
            r = m(s, f"kill {tid}", q=1.5, log_path=LOG_PATH)
            if any(w in r for w in ("喝道", "想杀", "领教", "奉陪", "杀死")):
                print(f"  >> engaged with kill {tid}")
                return True
        time.sleep(1)

    print("  !! could not engage")
    return False


def monitor_combat(s, name, ids=None):
    """Wait for combat to resolve. Returns: True (victory), False (loss),
    "dead", "mission_lost" (KO'd), "fled" (we fled), "monster_fled"."""
    for j in range(COMBAT_TIMEOUT // 3):
        time.sleep(3)
        r = clean(drain(s, quiet=1.8, maxt=5.0))
        if not r:
            continue

        # Victory
        if any(w in r for w in VICTORY_SIGNS) and (name in r or "领罪" in r or "大赦" in r):
            print("  *** VICTORY ***")
            return True

        # We died
        if any(w in r for w in DEATH_SIGNS):
            print("  !! WE DIED")
            return "dead"

        # We lost (sparring)
        if LOSS_SIGN in r:
            print("  LOST")
            return False

        # KO'd (passed out — guai despawns)
        if KO_SIGN in r:
            print("  !! KO'd — guai gone")
            return "mission_lost"

        # Monster fled — chase it
        if any(w in r for w in MONSTER_FLEE):
            if name in r:
                d = _chase_dir(r)
                if d:
                    print(f"  [CHASE] {name} fled {d} — pursuing")
                    s.sendall((d + "\r\n").encode())
                    time.sleep(0.8)
                    r2 = clean(drain(s, quiet=1.2))
                    # Re-engage with all known IDs
                    re_engaged = False
                    for tid in (list(ids or []) + ["guai", "jing", "jing2"]):
                        rr = m(s, f"kill {tid}", q=1.5)
                        if any(w in rr for w in ("喝道", "想杀", "领教", "奉陪", "缓缓")):
                            re_engaged = True
                            break
                    if re_engaged:
                        continue
                    # Try one more adjacent room in same direction
                    s.sendall((d + "\r\n").encode())
                    time.sleep(0.8)
                    for tid in (list(ids or []) + ["guai", "jing"]):
                        rr = m(s, f"kill {tid}", q=1.5)
                        if any(w in rr for w in ("喝道", "想杀", "领教", "奉陪")):
                            re_engaged = True
                            break
                    if re_engaged:
                        continue
                print(f"  [CHASE] {name} fled but lost track")
                return "monster_fled"
            # We fled (wimpy)
            print("  [WIMPY] we fled — recovering")
            return "fled"

    print("  [combat] timeout")
    return False


def _chase_dir(text):
    """Parse '往<dir>落荒而逃了' → English direction."""
    mm = re.search(r"往([东西南北上下]+)", text)
    if not mm:
        return None
    return CN_DIR.get(mm.group(1))


def fight(s, name, ids=None):
    """Full combat: engage + monitor. Returns result from monitor_combat."""
    if not engage(s, name, ids):
        return False
    return monitor_combat(s, name, ids=ids)
