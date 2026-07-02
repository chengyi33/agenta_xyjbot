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

print("Round 5: Escape 2F, reach Wuguan, learn skills, find Yuan...")
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
show("START (should be 2F)", b)

# ============================================
# STEP 1: ESCAPE 2ND FLOOR
# 系统公告室 -> west -> 二楼雅座 -> down -> 南城客栈 (main floor)
# ============================================
print("\n========== ESCAPING 2ND FLOOR ==========")
b = send(s, b"west\r\n", quiet=2.0)
show("WEST to 二楼雅座", b)

b = send(s, b"down\r\n", quiet=2.0)
show("DOWN to main inn", b)

b = send(s, b"look\r\n", quiet=2.0)
show("MAIN INN FLOOR", b)

# Verify we're at the inn main floor with exits east/west/up
resp = clean(b)
if "南城客栈" not in resp:
    # Try alternate escape
    b = send(s, b"down\r\n", quiet=2.0)
    show("DOWN again", b)
    b = send(s, b"look\r\n", quiet=2.0)
    show("LOOK", b)

# ============================================
# STEP 2: Navigate to 长安武馆
# Inn -> west (朱雀大街) -> north (十字街头) -> east (青龙大街) -> north (武馆)
# ============================================
print("\n========== NAVIGATING TO WUGUAN ==========")
b = send(s, b"west\r\n", quiet=2.0)
show("WEST to 朱雀大街", b)

resp = clean(b)
if "朱雀" in resp:
    print("  >> ON ZHUQUE STREET - going north")
    b = send(s, b"north\r\n", quiet=2.0)
    show("NORTH to 十字街头", b)

    resp = clean(b)
    if "十字" in resp:
        print("  >> AT CROSSROADS - going east")
        b = send(s, b"east\r\n", quiet=2.0)
        show("EAST to 青龙大街", b)

        resp = clean(b)
        if "青龙" in resp:
            print("  >> ON QINGLONG ST - going north to wuguan")
            b = send(s, b"north\r\n", quiet=2.0)
            show("NORTH to 武馆", b)

# ============================================
# STEP 3: Apprentice & Learn at 武馆
# ============================================
print("\n========== AT WUGUAN - LEARNING ==========")
b = send(s, b"look\r\n", quiet=2.0)
show("WUGUAN LOOK", b)

# Try apprentice command
b = send(s, b"bai fan luping wei shi\r\n", quiet=3.0)
show("BAI SHI", b)

# Learn all 4 skills
b = send(s, b"learn unarmed from fan\r\n", quiet=3.0)
show("LEARN UNARMED", b)

b = send(s, b"learn dodge from fan\r\n", quiet=3.0)
show("LEARN DODGE", b)

b = send(s, b"learn parry from fan\r\n", quiet=3.0)
show("LEARN PARRY", b)

b = send(s, b"learn force from fan\r\n", quiet=3.0)
show("LEARN FORCE", b)

# Check skills
b = send(s, b"skills\r\n", quiet=2.0)
show("MY SKILLS", b)

# Try to practice
b = send(s, b"practice unarmed\r\n", quiet=3.0)
show("PRACTICE UNARMED", b)

# ============================================
# STEP 4: Navigate to 天监台 for Yuan Tiangang
# Wuguan -> south (青龙) -> west (十字街头) -> north (玄武) -> west (天监台)
# ============================================
print("\n========== NAVIGATING TO TIANJIANTAI ==========")
b = send(s, b"south\r\n", quiet=2.0)
show("S to 青龙", b)
b = send(s, b"west\r\n", quiet=2.0)
show("W to 十字街头", b)
b = send(s, b"north\r\n", quiet=2.0)
show("N to 玄武", b)
b = send(s, b"west\r\n", quiet=2.0)
show("W to 天监台", b)

b = send(s, b"look\r\n", quiet=2.0)
show("TIANJIANTAI LOOK", b)

# Ask Yuan Tiangang about kill
b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
show("ASK YUAN ABOUT KILL", b)

b = send(s, b"ask yuan about guai\r\n", quiet=3.0)
show("ASK YUAN ABOUT GUAI", b)

b = send(s, b"ask yuan about longgong\r\n", quiet=3.0)
show("ASK YUAN ABOUT LONGGONG", b)

# ============================================
# STEP 5: Final status check
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
# STEP 6: Go back to kezhan and STAY (no quit)
# tianjiantai -> east (玄武) -> south (十字) -> south (朱雀) -> east (kezhan)
# ============================================
b = send(s, b"east\r\n", quiet=2.0)
b = send(s, b"south\r\n", quiet=2.0)
b = send(s, b"south\r\n", quiet=2.0)
b = send(s, b"east\r\n", quiet=2.0)
b = send(s, b"look\r\n", quiet=2.0)
show("PARKED AT KEZHAN", b)

# NO QUIT - just disconnect
print("\n*** Round 5 ended - character stays at kezhan ***")
time.sleep(1)
s.close()
