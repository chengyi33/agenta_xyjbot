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

print("Round 6: Buy weapon, grind skills, fight monsters...")
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
# STEP 1: Grind skills at 武馆 - learn multiple times
# Inn -> west -> north -> east -> north
# ============================================
print("\n========== GRINDING SKILLS AT WUGUAN ==========")
b = send(s, b"west\r\n", quiet=2.0)
b = send(s, b"north\r\n", quiet=2.0)
b = send(s, b"east\r\n", quiet=2.0)
b = send(s, b"north\r\n", quiet=2.0)
b = send(s, b"look\r\n", quiet=2.0)
show("AT WUGUAN", b)

# Learn each skill multiple times to level up
for i in range(5):
    send(s, b"learn unarmed from fan\r\n", quiet=2.0)
    send(s, b"learn dodge from fan\r\n", quiet=2.0)
    send(s, b"learn parry from fan\r\n", quiet=2.0)
    send(s, b"learn force from fan\r\n", quiet=2.0)

b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS AFTER GRINDING", b)

# Learn more
for i in range(5):
    send(s, b"learn unarmed from fan\r\n", quiet=2.0)
    send(s, b"learn dodge from fan\r\n", quiet=2.0)
    send(s, b"learn parry from fan\r\n", quiet=2.0)
    send(s, b"learn force from fan\r\n", quiet=2.0)

b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS AFTER MORE GRINDING", b)

b = send(s, b"hp\r\n", quiet=2.0)
show("HP AFTER LEARNING", b)

# ============================================
# STEP 2: Buy a weapon from 兵器铺子
# Wuguan -> south (青龙) -> south (兵器铺子)
# ============================================
print("\n========== BUYING WEAPON ==========")
b = send(s, b"south\r\n", quiet=2.0)  # back to qinglong
show("BACK TO QINGLONG", b)

b = send(s, b"south\r\n", quiet=2.0)  # to weapon shop
show("SOUTH TO WEAPON SHOP", b)

b = send(s, b"look\r\n", quiet=2.0)
show("WEAPON SHOP LOOK", b)

b = send(s, b"list\r\n", quiet=3.0)
show("WEAPON SHOP LIST", b)

# Buy a cheap weapon we can use
b = send(s, b"buy dagger from xiaoxiao\r\n", quiet=2.0)
show("BUY DAGGER", b)

# Try other vendor names
resp = clean(b)
if "谁" in resp or "什么" in resp:
    b = send(s, b"buy dagger from boss\r\n", quiet=2.0)
    show("BUY DAGGER FROM BOSS", b)

resp = clean(b)
if "谁" in resp or "什么" in resp:
    # Look for the shop NPC
    b = send(s, b"look\r\n", quiet=2.0)
    show("LOOK FOR NPC", b)

# Wield it
b = send(s, b"wield dagger\r\n", quiet=2.0)
show("WIELD", b)

# ============================================
# STEP 3: Find and fight starter monsters
# Yuan said 灰狼怪 at 高老庄, but that's far
# Let's fight the 武馆弟子 (trainee) or find city monsters
# ============================================
print("\n========== LOOKING FOR FIGHTS ==========")

# Try fighting a wuguan trainee first
b = send(s, b"north\r\n", quiet=2.0)  # back to qinglong
b = send(s, b"north\r\n", quiet=2.0)  # back to wuguan
b = send(s, b"fight dizi\r\n", quiet=2.0)
show("FIGHT DIZI", b)

# Wait for combat
time.sleep(4)
b = drain(s, quiet=2.0, maxt=6.0)
show("COMBAT 1", b)

time.sleep(4)
b = drain(s, quiet=2.0, maxt=6.0)
show("COMBAT 2", b)

time.sleep(4)
b = drain(s, quiet=2.0, maxt=6.0)
show("COMBAT 3", b)

time.sleep(4)
b = drain(s, quiet=2.0, maxt=6.0)
show("COMBAT 4", b)

# Check if fight is over
b = send(s, b"hp\r\n", quiet=2.0)
show("HP AFTER FIGHT", b)

b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS AFTER FIGHT", b)

# ============================================
# STEP 4: If we survived, eat to recover and check status
# ============================================
b = send(s, b"eat jitui\r\n", quiet=2.0)
show("EAT CHICKEN", b)

b = send(s, b"drink jiudai\r\n", quiet=2.0)
show("DRINK", b)

# ============================================
# STEP 5: Final status & park at kezhan
# ============================================
print("\n========== FINAL STATUS ==========")
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)

b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS", b)

b = send(s, b"i\r\n", quiet=2.0)
show("INVENTORY", b)

# Navigate back to kezhan
# wuguan -> south -> west -> south -> east
b = send(s, b"south\r\n", quiet=2.0)
b = send(s, b"west\r\n", quiet=2.0)
b = send(s, b"south\r\n", quiet=2.0)
b = send(s, b"east\r\n", quiet=2.0)
b = send(s, b"look\r\n", quiet=2.0)
show("PARKED AT KEZHAN", b)

print("\n*** Round 6 ended - character stays at kezhan ***")
time.sleep(1)
s.close()
