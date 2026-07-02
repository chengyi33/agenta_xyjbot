import socket, time, re

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

print("Round 7: Grab free gear, buy weapon, grind & fight...")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
resp = clean(b)
if "y/n" in resp:
    b = send(s, b"y\r\n", quiet=4.0)

b = send(s, b"look\r\n", quiet=2.0)
show("START", b)

# ============================================
# STEP 1: Pick up free gear on inn floor
# ============================================
print("\n========== GRABBING FREE GEAR ==========")
b = send(s, b"get chufei sword\r\n", quiet=2.0)
show("GET SWORD", b)
b = send(s, b"get golden armor\r\n", quiet=2.0)
show("GET ARMOR", b)
b = send(s, b"get zhan pao\r\n", quiet=2.0)
show("GET ZHANPAO", b)
b = send(s, b"get zhangmu dun\r\n", quiet=2.0)
show("GET SHIELD", b)
# Try alternate IDs
b = send(s, b"get sword\r\n", quiet=2.0)
show("GET SWORD2", b)
b = send(s, b"get armor\r\n", quiet=2.0)
show("GET ARMOR2", b)
b = send(s, b"get all\r\n", quiet=2.0)
show("GET ALL", b)

# Equip what we got
b = send(s, b"wield sword\r\n", quiet=2.0)
show("WIELD SWORD", b)
b = send(s, b"wear armor\r\n", quiet=2.0)
show("WEAR ARMOR", b)
b = send(s, b"wear zhan pao\r\n", quiet=2.0)
show("WEAR ZHANPAO", b)

b = send(s, b"i\r\n", quiet=2.0)
show("INVENTORY AFTER GEAR", b)

b = send(s, b"score\r\n", quiet=3.0)
show("SCORE WITH GEAR", b)

# ============================================
# STEP 2: Buy weapon from shop if needed
# ============================================
print("\n========== BUYING WEAPON ==========")
# Go to weapon shop: west -> north -> east -> south
b = send(s, b"west\r\n", quiet=2.0)
b = send(s, b"north\r\n", quiet=2.0)
b = send(s, b"east\r\n", quiet=2.0)
b = send(s, b"south\r\n", quiet=2.0)
b = send(s, b"look\r\n", quiet=2.0)
show("AT WEAPON SHOP", b)

# Buy with correct NPC name: xiao xiao
b = send(s, b"buy dagger from xiao xiao\r\n", quiet=2.0)
show("BUY DAGGER", b)
b = send(s, b"buy blade from xiao xiao\r\n", quiet=2.0)
show("BUY BLADE", b)

b = send(s, b"wield blade\r\n", quiet=2.0)
show("WIELD BLADE", b)

b = send(s, b"i\r\n", quiet=2.0)
show("INVENTORY", b)

# ============================================
# STEP 3: Grind more skills at wuguan
# ============================================
print("\n========== SKILL GRINDING ==========")
b = send(s, b"north\r\n", quiet=2.0)  # back to qinglong
b = send(s, b"north\r\n", quiet=2.0)  # to wuguan

# Check sen first
b = send(s, b"hp\r\n", quiet=2.0)
show("HP BEFORE LEARNING", b)

# Learn as much as sen allows
for i in range(8):
    b = send(s, b"learn unarmed from fan\r\n", quiet=1.5)
    b = send(s, b"learn dodge from fan\r\n", quiet=1.5)
    b = send(s, b"learn parry from fan\r\n", quiet=1.5)
    b = send(s, b"learn force from fan\r\n", quiet=1.5)
    resp = clean(b)
    if "精神不够" in resp or "太累" in resp or "没有" in resp:
        show(f"LEARNING STOPPED at round {i}", b)
        break

b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS AFTER GRIND", b)

b = send(s, b"hp\r\n", quiet=2.0)
show("HP AFTER GRIND", b)

# ============================================
# STEP 4: Fight something weaker
# Try 疥顶小僧 on 朱雀大街 or look for weak mobs
# ============================================
print("\n========== LOOKING FOR WEAK FIGHTS ==========")
# Set wimpy high so we don't die
b = send(s, b"set wimpy 50\r\n", quiet=2.0)
show("SET WIMPY", b)

# Go find the 疥顶小僧 on 朱雀大街
b = send(s, b"south\r\n", quiet=2.0)  # qinglong
b = send(s, b"west\r\n", quiet=2.0)   # shizikou
b = send(s, b"south\r\n", quiet=2.0)  # zhuque
b = send(s, b"look\r\n", quiet=2.0)
show("ZHUQUE - LOOKING FOR MOBS", b)

# Fight the monk if present
resp = clean(b)
if "小僧" in resp or "xiaoseng" in resp.lower():
    b = send(s, b"fight xiaoseng\r\n", quiet=2.0)
    show("FIGHT XIAOSENG", b)

    # Wait for combat rounds
    time.sleep(5)
    b = drain(s, quiet=2.0, maxt=8.0)
    show("COMBAT 1", b)

    time.sleep(5)
    b = drain(s, quiet=2.0, maxt=8.0)
    show("COMBAT 2", b)

    time.sleep(5)
    b = drain(s, quiet=2.0, maxt=8.0)
    show("COMBAT 3", b)

    time.sleep(5)
    b = drain(s, quiet=2.0, maxt=8.0)
    show("COMBAT 4", b)
else:
    # Try to find other weak NPCs
    show("NO MONK HERE - exploring", b)
    b = send(s, b"south\r\n", quiet=2.0)
    b = send(s, b"look\r\n", quiet=2.0)
    show("SOUTH ZHUQUE", b)

# ============================================
# STEP 5: Final status
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

# ============================================
# Park at kezhan - navigate back
# ============================================
# Find way back to kezhan from wherever we are
b = send(s, b"look\r\n", quiet=2.0)
resp = clean(b)
if "朱雀" in resp:
    # on zhuque, go east to kezhan or north first
    if "当铺" in resp or "客栈" in resp:
        b = send(s, b"east\r\n", quiet=2.0)
    else:
        b = send(s, b"north\r\n", quiet=2.0)
        b = send(s, b"east\r\n", quiet=2.0)
elif "十字" in resp:
    b = send(s, b"south\r\n", quiet=2.0)
    b = send(s, b"east\r\n", quiet=2.0)

b = send(s, b"look\r\n", quiet=2.0)
show("PARKED", b)

print("\n*** Round 7 ended - NO QUIT ***")
time.sleep(1)
s.close()
