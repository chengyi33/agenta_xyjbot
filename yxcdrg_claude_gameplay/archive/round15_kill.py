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

def move_and_verify(s, direction, expected_keyword):
    b = send(s, direction.encode() + b"\r\n", quiet=2.0)
    r = clean(b)
    if expected_keyword in r:
        return True, b
    b2 = send(s, b"look\r\n", quiet=2.0)
    r2 = clean(b2)
    return expected_keyword in r2, b2

print("Round 15: GEAR UP AND GET FIRST KILL!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
resp = clean(b)
if "y/n" in resp:
    b = send(s, b"y\r\n", quiet=4.0)

# ============================================
# STEP 1: Navigate to kezhan and pick up ALL gear
# ============================================
print("\n========== GEAR UP ==========")

# Navigate to kezhan from wherever
b = send(s, b"look\r\n", quiet=2.0)
r = clean(b)
if "客栈" not in r:
    # Try common paths
    if "泾水" in r:
        send(s, b"north\r\n", quiet=2.0)
        send(s, b"north\r\n", quiet=2.0)
    if "朱雀" in r:
        send(s, b"east\r\n", quiet=2.0)
    elif "十字" in r:
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)
    elif "南城口" in r:
        send(s, b"north\r\n", quiet=2.0)
        send(s, b"north\r\n", quiet=2.0)
        send(s, b"north\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)

b = send(s, b"look\r\n", quiet=2.0)
show("AT KEZHAN?", b)

# Pick up everything on the floor
b = send(s, b"get all\r\n", quiet=2.0)
show("GET ALL", b)

# Equip the best gear
b = send(s, b"wield chufei sword\r\n", quiet=2.0)
show("WIELD SWORD", b)
r = clean(b)
if "没有" in r:
    b = send(s, b"wield sword\r\n", quiet=2.0)
    show("WIELD SWORD2", b)

b = send(s, b"wear golden armor\r\n", quiet=2.0)
show("WEAR ARMOR", b)
r = clean(b)
if "没有" in r:
    b = send(s, b"wear armor\r\n", quiet=2.0)
    show("WEAR ARMOR2", b)

b = send(s, b"wear zhan pao\r\n", quiet=2.0)
show("WEAR ZHANPAO", b)

# Check score to see weapon/armor values
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE WITH GEAR", b)

b = send(s, b"i\r\n", quiet=2.0)
show("INVENTORY", b)

# ============================================
# STEP 2: Buy food
# ============================================
print("\n========== BUY FOOD ==========")
b = send(s, b"buy jitui from xiao er\r\n", quiet=2.0)
show("BUY FOOD", b)
b = send(s, b"buy jitui from xiao er\r\n", quiet=2.0)
send(s, b"buy jiudai from xiao er\r\n", quiet=2.0)
b = send(s, b"eat jitui\r\n", quiet=2.0)
send(s, b"drink jiudai\r\n", quiet=2.0)

b = send(s, b"hp\r\n", quiet=2.0)
show("HP READY", b)

# ============================================
# STEP 3: Set wimpy LOW and go fight
# ============================================
print("\n========== HUNTING ==========")
send(s, b"set wimpy 15\r\n", quiet=1.0)

# Go to zhuque to find the monk
ok, b = move_and_verify(s, "west", "朱雀")
show("ZHUQUE", b)

r = clean(b)
target = None
target_id = None

# Check for any fightable NPCs
if "小僧" in r:
    target = "疥顶小僧"
    target_id = "xiaoseng"
elif "癞头" in r:
    target = "癞头和尚"
    target_id = "laitou"

if not target:
    # Try going south on zhuque
    ok, b = move_and_verify(s, "south", "朱雀")
    r = clean(b)
    show("SOUTH ZHUQUE", b)
    if "小僧" in r:
        target = "疥顶小僧"
        target_id = "xiaoseng"
    elif "癞头" in r:
        target = "癞头和尚"
        target_id = "laitou"

if not target:
    # Try 背阴巷 for weaker NPCs
    ok, b = move_and_verify(s, "south", "朱雀")
    r = clean(b)
    if "背阴" in r or "west" in r.lower():
        ok, b = move_and_verify(s, "west", "")
        r = clean(b)
        show("WEST FROM ZHUQUE", b)
        # Look for any NPCs
        for keyword in ["流氓", "老头", "小", "乞丐"]:
            if keyword in r:
                # Try to find the ID
                lines = r.split("\n")
                for line in lines:
                    if keyword in line:
                        m = re.search(r'\(([^)]+)\)', line)
                        if m:
                            target_id = m.group(1).split()[0].lower()
                            target = line.strip()
                            break
                if target:
                    break

if not target:
    # Go to wuguan and fight a dizi
    print("  >> No street mobs found, going to fight wuguan dizi")
    # Navigate: wherever -> kezhan -> west -> north -> east -> north
    b = send(s, b"look\r\n", quiet=2.0)
    r = clean(b)
    # Get to shizikou first
    if "朱雀" in r:
        send(s, b"north\r\n", quiet=2.0)
    elif "背阴" in r:
        send(s, b"east\r\n", quiet=2.0)  # back to zhuque
        send(s, b"north\r\n", quiet=2.0)
    # Now at shizikou
    ok, b = move_and_verify(s, "east", "青龙")
    ok, b = move_and_verify(s, "north", "武馆")
    show("AT WUGUAN FOR FIGHT", b)
    target = "武馆弟子"
    target_id = "dizi"

# ============================================
# STEP 4: FIGHT!
# ============================================
if target and target_id:
    print(f"\n========== FIGHTING: {target} (id: {target_id}) ==========")
    b = send(s, f"kill {target_id}\r\n".encode(), quiet=2.0)
    r = clean(b)
    show("KILL COMMAND", b)

    # If kill didn't work, try fight
    if "想攻击谁" in r or "什么" in r:
        b = send(s, f"fight {target_id}\r\n".encode(), quiet=2.0)
        show("FIGHT COMMAND", b)

    # Watch combat - up to 20 rounds (80 seconds)
    killed = False
    fled = False
    for i in range(20):
        time.sleep(4)
        b = drain(s, quiet=2.0, maxt=6.0)
        if b:
            r = clean(b)
            if "死了" in r:
                show("*** KILLED IT! ***", b)
                killed = True
                break
            elif "承让" in r:
                show("LOST (opponent won)", b)
                fled = True
                break
            elif "逃跑" in r or "逃命" in r or "找机会逃跑" in r:
                show("FLED (wimpy)", b)
                fled = True
                break
            elif i % 4 == 0:
                show(f"COMBAT round {i+1}", b)

    if killed:
        print("\n  *** FIRST KILL ACHIEVED! ***")
    elif not fled:
        # Fight might still be going, check
        b = send(s, b"hp\r\n", quiet=2.0)
        show("HP MID-FIGHT", b)

    # If we fled or lost, try again with a different target
    if fled and not killed:
        print("\n  >> Fled/Lost. Recovering and trying weaker target...")
        # Eat to recover
        send(s, b"eat jitui\r\n", quiet=2.0)
        time.sleep(10)
        drain(s, quiet=1.0, maxt=2.0)

        # Try fighting a liumang in 背阴巷
        b = send(s, b"look\r\n", quiet=2.0)
        r = clean(b)
        # Navigate to 背阴巷
        if "武馆" in r:
            send(s, b"south\r\n", quiet=2.0)
            send(s, b"west\r\n", quiet=2.0)
            send(s, b"south\r\n", quiet=2.0)
            # Now on zhuque near kezhan
        if "客栈" in r or "朱雀" in r:
            if "客栈" in r:
                send(s, b"west\r\n", quiet=2.0)
            send(s, b"south\r\n", quiet=2.0)  # south zhuque
            send(s, b"south\r\n", quiet=2.0)  # further south
            send(s, b"south\r\n", quiet=2.0)  # even further
            send(s, b"west\r\n", quiet=2.0)   # toward beiyin
        b = send(s, b"look\r\n", quiet=2.0)
        show("LOOKING FOR WEAK TARGET", b)
        r = clean(b)

        # Fight anything here
        fight_target = None
        for line in r.split("\n"):
            line = line.strip()
            for keyword in ["流氓", "老头", "小", "乞丐", "苦力", "伙计"]:
                if keyword in line and "(" in line:
                    m = re.search(r'\(([^)]+)\)', line)
                    if m:
                        fight_target = m.group(1).split()[0].lower()
                        print(f"  >> Found weak target: {line} (id: {fight_target})")
                        break
            if fight_target:
                break

        if fight_target:
            b = send(s, f"kill {fight_target}\r\n".encode(), quiet=2.0)
            r = clean(b)
            if "想攻击谁" in r:
                b = send(s, f"fight {fight_target}\r\n".encode(), quiet=2.0)
            show("FIGHT WEAK TARGET", b)

            for i in range(20):
                time.sleep(4)
                b = drain(s, quiet=2.0, maxt=6.0)
                if b:
                    r = clean(b)
                    if "死了" in r:
                        show("*** KILLED IT! ***", b)
                        killed = True
                        break
                    elif "承让" in r or "逃跑" in r or "找机会逃跑" in r:
                        show("FLED/LOST AGAIN", b)
                        break
                    elif i % 4 == 0:
                        show(f"COMBAT2 round {i+1}", b)

            if killed:
                print("\n  *** FIRST KILL ACHIEVED! ***")

# ============================================
# FINAL STATUS
# ============================================
print("\n========== FINAL STATUS ==========")
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)
b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS", b)
b = send(s, b"i\r\n", quiet=2.0)
show("INVENTORY", b)

print("\n*** Round 15 ended - NO QUIT ***")
time.sleep(1)
s.close()
