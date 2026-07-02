import socket, time, re, sys
sys.stdout.reconfigure(line_buffering=True)

def drain(s, quiet=1.5, maxt=10.0):
    s.setblocking(False); buf=b""; start=time.time(); last=time.time()
    while True:
        try:
            c=s.recv(4096)
            if c: buf+=c; last=time.time()
            else: break
        except BlockingIOError:
            if buf and (time.time()-last)>quiet: break
            if (time.time()-start)>maxt: break
            time.sleep(0.04)
    return buf

def send(s, d, quiet=2.0):
    s.sendall(d); return drain(s, quiet=quiet)

def clean(b):
    for enc in ["utf-8", "gbk"]:
        try:
            t = b.replace(b"\x00", b"").decode(enc)
            return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", t)
        except:
            pass
    return b.replace(b"\x00", b"").decode("gbk", errors="replace")

def show(label, b):
    t = clean(b)
    print(f"\n--- {label} ---")
    print(t[-2000:] if len(t) > 2000 else t)

def get_hp(s):
    b = send(s, b"hp\r\n", quiet=2.0)
    t = clean(b)
    sen_m = re.search(r"精神：\s*(\d+)/\s*(\d+)", t)
    hp_m = re.search(r"气血：\s*(\d+)/\s*(\d+)", t)
    sen = (int(sen_m.group(1)), int(sen_m.group(2))) if sen_m else (0, 0)
    hp = (int(hp_m.group(1)), int(hp_m.group(2))) if hp_m else (0, 0)
    return hp, sen, b

def move_and_verify(s, direction, expected_keyword):
    """Move in a direction and verify we arrived at the expected room."""
    b = send(s, direction.encode() + b"\r\n", quiet=2.0)
    r = clean(b)
    if expected_keyword in r:
        return True, b
    # Try look to confirm
    b2 = send(s, b"look\r\n", quiet=2.0)
    r2 = clean(b2)
    if expected_keyword in r2:
        return True, b2
    return False, b2

def nav_to_wuguan(s):
    """Navigate from kezhan to wuguan with verification."""
    ok, b = move_and_verify(s, "west", "朱雀")
    if not ok:
        print(f"  !! west didn't reach 朱雀: {clean(b)[:60]}")
        return False
    ok, b = move_and_verify(s, "north", "十字")
    if not ok:
        print(f"  !! north didn't reach 十字: {clean(b)[:60]}")
        return False
    ok, b = move_and_verify(s, "east", "青龙")
    if not ok:
        print(f"  !! east didn't reach 青龙: {clean(b)[:60]}")
        return False
    ok, b = move_and_verify(s, "north", "武馆")
    if not ok:
        print(f"  !! north didn't reach 武馆: {clean(b)[:60]}")
        return False
    print("  >> At 武馆!")
    return True

def nav_to_kezhan(s):
    """Navigate back to kezhan from common locations."""
    b = send(s, b"look\r\n", quiet=2.0)
    r = clean(b)
    if "客栈" in r and "南城" in r:
        return True
    if "武馆" in r:
        send(s, b"south\r\n", quiet=2.0)
        r = "青龙"
    if "兵器" in r:
        send(s, b"north\r\n", quiet=2.0)
        r = "青龙"
    if "青龙" in r:
        send(s, b"west\r\n", quiet=2.0)
        r = "十字"
    if "十字" in r:
        send(s, b"south\r\n", quiet=2.0)
        r = "朱雀"
    if "玄武" in r:
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"south\r\n", quiet=2.0)
        r = "朱雀"
    if "国子监" in r:
        send(s, b"west\r\n", quiet=2.0)
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"south\r\n", quiet=2.0)
        r = "朱雀"
    if "当铺" in r:
        send(s, b"east\r\n", quiet=2.0)
        r = "朱雀"
    if "朱雀" in r:
        send(s, b"east\r\n", quiet=2.0)
    return True

def grind_at_wuguan(s):
    """Learn skills from Fan Luping until exhausted."""
    total = 0
    for i in range(30):
        b = send(s, b"learn unarmed from fan\r\n", quiet=1.5)
        r = clean(b)
        if "太累" in r or "向谁" in r:
            break
        total += 1
        b = send(s, b"learn dodge from fan\r\n", quiet=1.5)
        r = clean(b)
        if "太累" in r:
            break
        total += 1
        b = send(s, b"learn parry from fan\r\n", quiet=1.5)
        total += 1
        b = send(s, b"learn force from fan\r\n", quiet=1.5)
        total += 1
    return total

def sleep_recover(s, target_pct=0.9):
    """Sleep until sen recovers to target percentage."""
    hp, sen, _ = get_hp(s)
    if sen[0] >= sen[1] * target_pct:
        return sen
    print(f"  Sleeping... sen {sen[0]}/{sen[1]}")
    send(s, b"sleep\r\n", quiet=1.0)
    for i in range(4):  # max 60 seconds
        time.sleep(15)
        drain(s, quiet=1.0, maxt=2.0)
        hp, sen, _ = get_hp(s)
        print(f"  Sen: {sen[0]}/{sen[1]}")
        if sen[0] >= sen[1] * target_pct:
            break
    send(s, b"wake\r\n", quiet=1.0)
    send(s, b"stand\r\n", quiet=1.0)
    return sen

# ================================================================
# LOGIN
# ================================================================
print("Rounds 11-13: Verified nav, grind, fight x3")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
resp = clean(b)
if "y/n" in resp:
    b = send(s, b"y\r\n", quiet=4.0)

send(s, b"set wimpy 50\r\n", quiet=1.0)

# ================================================================
# ROUND 11: Grind skills with verified navigation
# ================================================================
print("\n" + "="*60)
print("  ROUND 11: Grind skills at wuguan")
print("="*60)

# Make sure we're at kezhan
nav_to_kezhan(s)
b = send(s, b"look\r\n", quiet=2.0)
show("R11 START", b)

hp, sen, hpb = get_hp(s)
print(f"  HP: {hp[0]}/{hp[1]}, Sen: {sen[0]}/{sen[1]}")

# Sleep if needed
if sen[0] < sen[1] * 0.8:
    sleep_recover(s)

# Navigate to wuguan with verification
print("  Navigating to wuguan...")
if nav_to_wuguan(s):
    # GRIND!
    total = grind_at_wuguan(s)
    print(f"  Learned {total} times!")
    b = send(s, b"skills\r\n", quiet=2.0)
    show("R11 SKILLS", b)

    # Sleep and grind again
    sleep_recover(s)
    # Navigate back to wuguan (we might have moved during sleep)
    b = send(s, b"look\r\n", quiet=2.0)
    r = clean(b)
    if "武馆" not in r:
        nav_to_kezhan(s)
        nav_to_wuguan(s)

    total2 = grind_at_wuguan(s)
    print(f"  Learned {total2} more times!")
    b = send(s, b"skills\r\n", quiet=2.0)
    show("R11 SKILLS AFTER 2ND GRIND", b)
else:
    print("  !! Navigation to wuguan FAILED")
    b = send(s, b"look\r\n", quiet=2.0)
    show("R11 LOST AT", b)

hp, sen, hpb = get_hp(s)
show("R11 HP", hpb)

# ================================================================
# ROUND 12: Fight the monk
# ================================================================
print("\n" + "="*60)
print("  ROUND 12: Fight!")
print("="*60)

# Sleep to recover
sleep_recover(s)

# Navigate to zhuque to find the monk
nav_to_kezhan(s)
ok, b = move_and_verify(s, "west", "朱雀")
show("R12 ZHUQUE", b)

r = clean(b)
fought = False
if "小僧" in r:
    print("  >> Found 疥顶小僧! Fighting...")
    b = send(s, b"fight xiaoseng\r\n", quiet=2.0)
    show("R12 FIGHT START", b)
    r = clean(b)
    if "领教" in r or "赐教" in r or "奉陪" in r:
        fought = True
        for i in range(12):
            time.sleep(4)
            b = drain(s, quiet=2.0, maxt=6.0)
            if b:
                r = clean(b)
                # Only show important combat events
                if "死了" in r or "承让" in r or "逃" in r or "道行" in r:
                    show(f"R12 COMBAT END", b)
                    break
                elif i % 3 == 0:
                    show(f"R12 COMBAT {i+1}", b)
    else:
        show("R12 FIGHT FAILED", b)

if not fought:
    # Try alternate mob name or find another target
    b = send(s, b"fight jieding xiaoseng\r\n", quiet=2.0)
    show("R12 FIGHT ALT", b)
    r = clean(b)
    if "领教" in r or "赐教" in r or "奉陪" in r:
        fought = True
        for i in range(12):
            time.sleep(4)
            b = drain(s, quiet=2.0, maxt=6.0)
            if b:
                r = clean(b)
                if "死了" in r or "承让" in r or "逃" in r or "道行" in r:
                    show(f"R12 COMBAT END", b)
                    break
                elif i % 3 == 0:
                    show(f"R12 COMBAT {i+1}", b)

hp, sen, hpb = get_hp(s)
show("R12 HP AFTER FIGHT", hpb)
b = send(s, b"skills\r\n", quiet=2.0)
show("R12 SKILLS", b)

# ================================================================
# ROUND 13: More grinding + another fight
# ================================================================
print("\n" + "="*60)
print("  ROUND 13: Grind more + fight again")
print("="*60)

# Recover
sleep_recover(s)

# Grind at wuguan
nav_to_kezhan(s)
print("  Navigating to wuguan...")
if nav_to_wuguan(s):
    total3 = grind_at_wuguan(s)
    print(f"  Learned {total3} times!")

    sleep_recover(s)
    b = send(s, b"look\r\n", quiet=2.0)
    r = clean(b)
    if "武馆" not in r:
        nav_to_kezhan(s)
        nav_to_wuguan(s)
    total4 = grind_at_wuguan(s)
    print(f"  Learned {total4} more!")

    b = send(s, b"skills\r\n", quiet=2.0)
    show("R13 SKILLS", b)

# Fight again
sleep_recover(s)
nav_to_kezhan(s)
ok, b = move_and_verify(s, "west", "朱雀")
r = clean(b)
if "小僧" in r:
    print("  >> Fighting monk again!")
    b = send(s, b"fight xiaoseng\r\n", quiet=2.0)
    r = clean(b)
    if "领教" in r or "赐教" in r or "奉陪" in r:
        for i in range(12):
            time.sleep(4)
            b = drain(s, quiet=2.0, maxt=6.0)
            if b:
                r = clean(b)
                if "死了" in r or "承让" in r or "逃" in r or "道行" in r:
                    show(f"R13 COMBAT END", b)
                    break
                elif i % 3 == 0:
                    show(f"R13 COMBAT {i+1}", b)
else:
    print("  >> No monk on zhuque, trying fight dizi at wuguan")
    nav_to_kezhan(s)
    if nav_to_wuguan(s):
        b = send(s, b"fight dizi\r\n", quiet=2.0)
        show("R13 FIGHT DIZI", b)
        for i in range(12):
            time.sleep(4)
            b = drain(s, quiet=2.0, maxt=6.0)
            if b:
                r = clean(b)
                if "死了" in r or "承让" in r or "逃" in r:
                    show(f"R13 COMBAT END", b)
                    break
                elif i % 3 == 0:
                    show(f"R13 COMBAT {i+1}", b)

# ================================================================
# FINAL STATUS
# ================================================================
print("\n" + "="*60)
print("  FINAL STATUS")
print("="*60)
b = send(s, b"hp\r\n", quiet=2.0)
show("FINAL HP", b)
b = send(s, b"score\r\n", quiet=3.0)
show("FINAL SCORE", b)
b = send(s, b"skills\r\n", quiet=2.0)
show("FINAL SKILLS", b)
b = send(s, b"i\r\n", quiet=2.0)
show("FINAL INVENTORY", b)

# Park at kezhan
nav_to_kezhan(s)
b = send(s, b"look\r\n", quiet=2.0)
show("PARKED", b)

print("\n*** Rounds 11-13 complete - NO QUIT ***")
time.sleep(1)
s.close()
