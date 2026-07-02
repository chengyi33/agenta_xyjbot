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

def get_sen(s):
    b = send(s, b"hp\r\n", quiet=2.0)
    t = clean(b)
    m = re.search(r"精神：\s*(\d+)/\s*(\d+)", t)
    if m:
        return int(m.group(1)), int(m.group(2)), b
    return 0, 0, b

print("Round 10: Sleep to recover sen, grind skills, FIGHT!")
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

# Navigate to kezhan if not there
resp = clean(b)
if "客栈" not in resp:
    if "朱雀" in resp:
        send(s, b"east\r\n", quiet=2.0)
    elif "当铺" in resp:
        send(s, b"east\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)

# ============================================
# STEP 1: SLEEP to recover sen
# ============================================
print("\n========== SLEEPING TO RECOVER SEN ==========")
sen_cur, sen_max, b = get_sen(s)
print(f"  Sen before sleep: {sen_cur}/{sen_max}")

b = send(s, b"sleep\r\n", quiet=2.0)
show("SLEEP", b)

# Wait a bit while sleeping
time.sleep(30)
drain(s, quiet=1.0, maxt=2.0)

sen_cur, sen_max, b = get_sen(s)
print(f"  Sen after 30s sleep: {sen_cur}/{sen_max}")

# Sleep more if needed
if sen_cur < sen_max * 0.8:
    time.sleep(30)
    drain(s, quiet=1.0, maxt=2.0)
    sen_cur, sen_max, b = get_sen(s)
    print(f"  Sen after 60s sleep: {sen_cur}/{sen_max}")

# Wake up
b = send(s, b"wake\r\n", quiet=2.0)
show("WAKE UP", b)

b = send(s, b"stand\r\n", quiet=2.0)
show("STAND", b)

sen_cur, sen_max, hpb = get_sen(s)
show("HP AFTER SLEEP", hpb)

# ============================================
# STEP 2: GRIND SKILLS at wuguan
# ============================================
print("\n========== GRINDING SKILLS ==========")
# Navigate: kezhan -> west -> north -> east -> north
send(s, b"west\r\n", quiet=2.0)
send(s, b"north\r\n", quiet=2.0)
send(s, b"east\r\n", quiet=2.0)
send(s, b"north\r\n", quiet=2.0)
b = send(s, b"look\r\n", quiet=2.0)
show("AT WUGUAN", b)

total = 0
for i in range(25):
    b1 = send(s, b"learn unarmed from fan\r\n", quiet=1.5)
    r = clean(b1)
    if "太累" in r:
        print(f"  >> Exhausted after {total} learns")
        break
    total += 1
    send(s, b"learn dodge from fan\r\n", quiet=1.5)
    total += 1
    send(s, b"learn parry from fan\r\n", quiet=1.5)
    total += 1
    b4 = send(s, b"learn force from fan\r\n", quiet=1.5)
    total += 1
    r = clean(b4)
    if "太累" in r:
        print(f"  >> Exhausted after {total} learns")
        break

print(f"  Total learns: {total}")
b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS AFTER GRIND", b)

# ============================================
# STEP 3: Sleep again to recover, then grind more
# ============================================
print("\n========== SLEEP + GRIND CYCLE 2 ==========")
b = send(s, b"sleep\r\n", quiet=2.0)
time.sleep(30)
drain(s, quiet=1.0, maxt=2.0)
b = send(s, b"wake\r\n", quiet=2.0)
b = send(s, b"stand\r\n", quiet=2.0)

sen_cur, sen_max, _ = get_sen(s)
print(f"  Sen after 2nd sleep: {sen_cur}/{sen_max}")

total2 = 0
for i in range(25):
    b1 = send(s, b"learn unarmed from fan\r\n", quiet=1.5)
    r = clean(b1)
    if "太累" in r:
        break
    total2 += 1
    send(s, b"learn dodge from fan\r\n", quiet=1.5)
    total2 += 1
    send(s, b"learn parry from fan\r\n", quiet=1.5)
    total2 += 1
    send(s, b"learn force from fan\r\n", quiet=1.5)
    total2 += 1
    r = clean(send(s, b"", quiet=0.5))

print(f"  Cycle 2 learns: {total2}")
b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS AFTER CYCLE 2", b)

# ============================================
# STEP 4: FIGHT the monk on 朱雀大街
# ============================================
print("\n========== FIGHTING ==========")
send(s, b"set wimpy 50\r\n", quiet=1.0)

# Go to zhuque: wuguan -> south -> west -> south
send(s, b"south\r\n", quiet=2.0)
send(s, b"west\r\n", quiet=2.0)
send(s, b"south\r\n", quiet=2.0)
b = send(s, b"look\r\n", quiet=2.0)
show("LOOKING FOR MONK", b)

resp = clean(b)
if "小僧" in resp:
    # Use correct ID: xiaoseng
    b = send(s, b"fight xiaoseng\r\n", quiet=2.0)
    show("FIGHT!", b)

    for i in range(10):
        time.sleep(4)
        b = drain(s, quiet=2.0, maxt=6.0)
        if b:
            show(f"COMBAT {i+1}", b)
            r = clean(b)
            if "死了" in r or "承让" in r or "逃跑" in r or "当铺" in r:
                break
else:
    print("  >> Monk not here, trying south")
    send(s, b"south\r\n", quiet=2.0)
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

# Park - navigate to kezhan
b = send(s, b"look\r\n", quiet=2.0)
resp = clean(b)
if "客栈" not in resp:
    if "朱雀" in resp:
        if "客栈" in resp:
            send(s, b"east\r\n", quiet=2.0)
        else:
            send(s, b"north\r\n", quiet=2.0)
            send(s, b"east\r\n", quiet=2.0)
    elif "当铺" in resp:
        send(s, b"east\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)
    elif "十字" in resp:
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)

b = send(s, b"look\r\n", quiet=2.0)
show("PARKED", b)

print("\n*** Round 10 ended - NO QUIT ***")
time.sleep(1)
s.close()
