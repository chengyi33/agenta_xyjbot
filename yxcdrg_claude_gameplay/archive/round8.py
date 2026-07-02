import socket, time, re, sys
sys.stdout.reconfigure(line_buffering=True)  # flush every line

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

print("Round 8: Learn sword, grind skills, fight with weapon...")
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

# Check current sen - need it recovered to learn
b = send(s, b"hp\r\n", quiet=2.0)
show("HP CHECK", b)

# ============================================
# STEP 1: Go to 武馆 and learn SWORD skill + grind
# The 楚妃剑 is a sword type weapon, need sword skill
# Also need to learn from fan: he teaches unarmed/dodge/parry/force
# For sword, need a sword teacher - check if fan teaches it
# Path: dangpu -> east (朱雀) -> north (十字) -> east (青龙) -> north (武馆)
# ============================================
print("\n========== TO WUGUAN ==========")
b = send(s, b"east\r\n", quiet=2.0)  # zhuque from dangpu
b = send(s, b"north\r\n", quiet=2.0)  # shizikou
b = send(s, b"east\r\n", quiet=2.0)  # qinglong
b = send(s, b"north\r\n", quiet=2.0)  # wuguan
b = send(s, b"look\r\n", quiet=2.0)
show("AT WUGUAN", b)

# Try learning sword from fan
b = send(s, b"learn sword from fan\r\n", quiet=2.0)
show("LEARN SWORD", b)

# Try learning literate from fan
b = send(s, b"learn literate from fan\r\n", quiet=2.0)
show("LEARN LITERATE", b)

# Grind all skills - learn each one in rotation
print("\n========== GRINDING SKILLS ==========")
learned_something = True
round_num = 0
while learned_something and round_num < 12:
    round_num += 1
    b = send(s, b"learn unarmed from fan\r\n", quiet=1.5)
    r1 = clean(b)
    b = send(s, b"learn dodge from fan\r\n", quiet=1.5)
    b = send(s, b"learn parry from fan\r\n", quiet=1.5)
    b = send(s, b"learn force from fan\r\n", quiet=1.5)
    r4 = clean(b)
    if "太累" in r1 or "太累" in r4 or "精神不够" in r1:
        print(f"  >> Too tired after {round_num} rounds")
        learned_something = False

b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS AFTER WUGUAN GRIND", b)

b = send(s, b"hp\r\n", quiet=2.0)
show("HP AFTER GRIND", b)

# ============================================
# STEP 2: Check help longgong for Dragon Palace info
# ============================================
print("\n========== DRAGON PALACE INFO ==========")
b = send(s, b"help longgong\r\n", quiet=3.0)
show("HELP LONGGONG", b)
# Get more pages
b = send(s, b"\r\n", quiet=3.0)
show("LONGGONG PAGE 2", b)

# ============================================
# STEP 3: Go to 国子监 and learn literate
# wuguan -> south -> west -> north -> east
# ============================================
print("\n========== TO GUOZIJIAN ==========")
b = send(s, b"south\r\n", quiet=2.0)  # qinglong
b = send(s, b"west\r\n", quiet=2.0)   # shizikou
b = send(s, b"north\r\n", quiet=2.0)  # xuanwu
b = send(s, b"east\r\n", quiet=2.0)   # guozijian
b = send(s, b"look\r\n", quiet=2.0)
show("AT GUOZIJIAN", b)

# Try learning literate from the scholars
b = send(s, b"learn literate from xiucai\r\n", quiet=2.0)
show("LEARN LITERATE FROM XIUCAI", b)

# Try with full name
b = send(s, b"learn literate from gao xiucai\r\n", quiet=2.0)
show("LEARN LITERATE GAO", b)

# Try asking
b = send(s, b"ask xiucai about literate\r\n", quiet=2.0)
show("ASK ABOUT LITERATE", b)

# ============================================
# STEP 4: Try to fight something with the sword
# Set wimpy, find a weak NPC
# ============================================
print("\n========== COMBAT WITH SWORD ==========")
b = send(s, b"set wimpy 60\r\n", quiet=2.0)
show("SET WIMPY 60", b)

# Go find the 疥顶小僧 again - now we have sword equipped
b = send(s, b"west\r\n", quiet=2.0)   # xuanwu
b = send(s, b"south\r\n", quiet=2.0)  # shizikou
b = send(s, b"south\r\n", quiet=2.0)  # zhuque
b = send(s, b"look\r\n", quiet=2.0)
show("ZHUQUE LOOK", b)

resp = clean(b)
if "小僧" in resp:
    b = send(s, b"fight jieding\r\n", quiet=2.0)
    show("FIGHT MONK", b)

    # Watch combat
    for i in range(6):
        time.sleep(4)
        b = drain(s, quiet=2.0, maxt=6.0)
        if b:
            show(f"COMBAT {i+1}", b)
            r = clean(b)
            if "死了" in r or "承让" in r or "逃" in r or "当铺" in r or "客栈" in r:
                break
else:
    # Look for other mobs - go south
    b = send(s, b"south\r\n", quiet=2.0)
    b = send(s, b"look\r\n", quiet=2.0)
    show("SOUTH ZHUQUE", b)
    # Check for any NPCs to fight
    resp = clean(b)
    # Look in 背阴巷 for weak mobs
    b = send(s, b"west\r\n", quiet=2.0)
    b = send(s, b"look\r\n", quiet=2.0)
    show("WEST FROM ZHUQUE-S", b)

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

# Park at kezhan
b = send(s, b"look\r\n", quiet=2.0)
resp = clean(b)
# Navigate back to kezhan from wherever
if "朱雀" in resp and "客栈" in resp:
    b = send(s, b"east\r\n", quiet=2.0)
elif "朱雀" in resp:
    b = send(s, b"north\r\n", quiet=2.0)
    resp2 = clean(b)
    if "客栈" in resp2:
        b = send(s, b"east\r\n", quiet=2.0)
    else:
        b = send(s, b"north\r\n", quiet=2.0)
        b = send(s, b"east\r\n", quiet=2.0)
elif "十字" in resp:
    b = send(s, b"south\r\n", quiet=2.0)
    b = send(s, b"east\r\n", quiet=2.0)
elif "当铺" in resp:
    b = send(s, b"east\r\n", quiet=2.0)
    b = send(s, b"east\r\n", quiet=2.0)

b = send(s, b"look\r\n", quiet=2.0)
show("PARKED", b)

print("\n*** Round 8 ended - NO QUIT ***")
time.sleep(1)
s.close()
