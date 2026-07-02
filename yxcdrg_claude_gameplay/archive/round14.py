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
    if expected_keyword in r2:
        return True, b2
    return False, b2

def nav_to_kezhan(s):
    b = send(s, b"look\r\n", quiet=2.0)
    r = clean(b)
    if "客栈" in r and "南城" in r:
        return
    if "武馆" in r:
        send(s, b"south\r\n", quiet=2.0); r = "青龙"
    if "兵器" in r:
        send(s, b"north\r\n", quiet=2.0); r = "青龙"
    if "青龙" in r:
        send(s, b"west\r\n", quiet=2.0); r = "十字"
    if "天监" in r:
        send(s, b"east\r\n", quiet=2.0); r = "玄武"
    if "玄武" in r:
        send(s, b"south\r\n", quiet=2.0); r = "十字"
    if "国子监" in r:
        send(s, b"west\r\n", quiet=2.0); r = "玄武"
        send(s, b"south\r\n", quiet=2.0); r = "十字"
    if "十字" in r:
        send(s, b"south\r\n", quiet=2.0); r = "朱雀"
    if "当铺" in r:
        send(s, b"east\r\n", quiet=2.0); r = "朱雀"
    if "朱雀" in r:
        send(s, b"east\r\n", quiet=2.0)

print("Round 14: Ask Yuan for current guai, then go kill it!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
resp = clean(b)
if "y/n" in resp:
    b = send(s, b"y\r\n", quiet=4.0)

# Set wimpy low so we actually fight
send(s, b"set wimpy 20\r\n", quiet=1.0)

b = send(s, b"look\r\n", quiet=2.0)
show("START", b)

b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)

# ============================================
# STEP 1: Go to Yuan Tiangang and ask about kill
# kezhan -> west(朱雀) -> north(十字) -> north(玄武) -> west(天监台)
# ============================================
print("\n========== ASKING YUAN ABOUT KILL ==========")
nav_to_kezhan(s)

ok, b = move_and_verify(s, "west", "朱雀")
if not ok: show("NAV FAIL", b)
ok, b = move_and_verify(s, "north", "十字")
if not ok: show("NAV FAIL", b)
ok, b = move_and_verify(s, "north", "玄武")
if not ok: show("NAV FAIL", b)
ok, b = move_and_verify(s, "west", "天监")
if not ok: show("NAV FAIL", b)

b = send(s, b"look\r\n", quiet=2.0)
show("AT TIANJIANTAI", b)

b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
show("ASK YUAN ABOUT KILL", b)

# Parse the response for monster name and location
resp = clean(b)
print(f"\n  Yuan's response: {resp.strip()}")

# Ask again to see if there's a different one
time.sleep(2)
b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
show("ASK YUAN ABOUT KILL (2nd)", b)

# ============================================
# STEP 2: Go to the location Yuan mentioned and fight
# First let's check what yuan said and find the path
# ============================================
print("\n========== GOING TO HUNT ==========")

# Parse location from yuan's response
resp_all = clean(b)
# Yuan typically says something like "XX怪 在 YY 出没"
# Let's go to wherever he said

# For now, navigate to the location. Common spots:
# 高老庄 = /d/gao/  (south from changan, through nanchengkou)
# Let's navigate there: tianjiantai -> east -> south -> south -> south -> south (nanchengkou) -> south

# First go back to shizikou
send(s, b"east\r\n", quiet=2.0)   # xuanwu
send(s, b"south\r\n", quiet=2.0)  # shizikou
send(s, b"south\r\n", quiet=2.0)  # zhuque (kezhan level)

# Go south toward nanchengkou
b = send(s, b"south\r\n", quiet=2.0)  # zhuque south
show("SOUTH 1", b)
b = send(s, b"south\r\n", quiet=2.0)
show("SOUTH 2", b)
b = send(s, b"south\r\n", quiet=2.0)
show("SOUTH 3", b)
b = send(s, b"look\r\n", quiet=2.0)
show("CURRENT LOCATION", b)

# Check if we can go further south
b = send(s, b"south\r\n", quiet=2.0)
show("SOUTH 4", b)
b = send(s, b"look\r\n", quiet=2.0)
show("LOOK", b)

# Look for any monsters around here
resp = clean(b)
print(f"\n  Looking for monsters in: {resp[:80]}")

# If there are NPCs that look like monsters, fight them
# Check for common monster indicators: 怪, 妖, 精, 鬼
monster_found = False
for keyword in ["怪", "妖", "精", "狼", "虎", "蛇", "鬼"]:
    if keyword in resp:
        print(f"  >> Found potential monster with '{keyword}'!")
        monster_found = True
        break

if monster_found:
    # Try to fight - extract NPC name
    # Look for lines with monster-like NPCs
    lines = resp.split("\n")
    for line in lines:
        line = line.strip()
        if any(k in line for k in ["怪", "妖", "精", "狼", "虎"]):
            # Extract the ID in parentheses
            m = re.search(r'\(([^)]+)\)', line)
            if m:
                npc_id = m.group(1).split()[0].lower()
                print(f"  >> Fighting: {line.strip()} (id: {npc_id})")
                b = send(s, f"kill {npc_id}\r\n".encode(), quiet=2.0)
                show("KILL", b)

                for i in range(15):
                    time.sleep(4)
                    b = drain(s, quiet=2.0, maxt=6.0)
                    if b:
                        r = clean(b)
                        if "死了" in r:
                            show("KILLED IT!", b)
                            break
                        elif "承让" in r or "逃跑" in r:
                            show("LOST/FLED", b)
                            break
                        elif i % 3 == 0:
                            show(f"COMBAT {i+1}", b)
                break
else:
    print("  >> No monsters found here, exploring more...")
    # Try going in different directions
    for d in ["south", "east", "west"]:
        b = send(s, f"{d}\r\n".encode(), quiet=2.0)
        r = clean(b)
        show(f"TRY {d.upper()}", b)
        if any(k in r for k in ["怪", "妖", "精", "狼", "虎"]):
            print(f"  >> Found monster going {d}!")
            break

# ============================================
# STEP 3: Final status
# ============================================
print("\n========== FINAL STATUS ==========")
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)
b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS", b)

# Park at kezhan
nav_to_kezhan(s)
b = send(s, b"look\r\n", quiet=2.0)
show("PARKED", b)

print("\n*** Round 14 ended - NO QUIT ***")
time.sleep(1)
s.close()
