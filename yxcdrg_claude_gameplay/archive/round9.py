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
        return int(m.group(1)), int(m.group(2))
    return 0, 0

print("Round 9: Stay connected, recover sen, then BIG grind session...")
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
# STEP 1: Get to kezhan and park
# ============================================
b = send(s, b"look\r\n", quiet=2.0)
show("START", b)
resp = clean(b)

# Navigate to kezhan from wherever we are
if "兵器铺" in resp:
    send(s, b"north\r\n", quiet=2.0)  # to qinglong
    send(s, b"west\r\n", quiet=2.0)   # to shizikou
    send(s, b"south\r\n", quiet=2.0)  # to zhuque
    send(s, b"east\r\n", quiet=2.0)   # to kezhan
elif "当铺" in resp:
    send(s, b"east\r\n", quiet=2.0)   # to zhuque
    send(s, b"east\r\n", quiet=2.0)   # to kezhan
elif "朱雀" in resp:
    send(s, b"east\r\n", quiet=2.0)

b = send(s, b"look\r\n", quiet=2.0)
show("AT KEZHAN?", b)

# Eat remaining food to help recovery
send(s, b"eat jitui\r\n", quiet=2.0)
send(s, b"eat jitui\r\n", quiet=2.0)
send(s, b"drink jiudai\r\n", quiet=2.0)

# ============================================
# STEP 2: Wait for sen recovery - check every 60 seconds
# ============================================
print("\n========== WAITING FOR SEN RECOVERY ==========")
sen_cur, sen_max = get_sen(s)
print(f"  Starting sen: {sen_cur}/{sen_max}")

for tick in range(6):  # wait up to 6 minutes
    print(f"  Waiting 60s... (tick {tick+1}/6)")
    time.sleep(60)
    # Drain any incoming messages (chat, events)
    drain(s, quiet=1.0, maxt=2.0)
    sen_cur, sen_max = get_sen(s)
    print(f"  Sen now: {sen_cur}/{sen_max}")
    if sen_cur >= sen_max * 0.8:  # 80% recovered
        print(f"  >> Sen recovered enough! ({sen_cur}/{sen_max})")
        break

b = send(s, b"hp\r\n", quiet=2.0)
show("HP AFTER RECOVERY", b)

# ============================================
# STEP 3: BIG GRIND SESSION at wuguan
# ============================================
print("\n========== BIG GRIND AT WUGUAN ==========")
# Navigate: kezhan -> west -> north -> east -> north
send(s, b"west\r\n", quiet=2.0)   # zhuque
send(s, b"north\r\n", quiet=2.0)  # shizikou
send(s, b"east\r\n", quiet=2.0)   # qinglong
send(s, b"north\r\n", quiet=2.0)  # wuguan
b = send(s, b"look\r\n", quiet=2.0)
show("AT WUGUAN", b)

# Grind all skills until exhausted
total_rounds = 0
for i in range(20):
    b1 = send(s, b"learn unarmed from fan\r\n", quiet=1.5)
    r = clean(b1)
    if "太累" in r:
        print(f"  >> Exhausted after {total_rounds} learn commands")
        break
    send(s, b"learn dodge from fan\r\n", quiet=1.5)
    send(s, b"learn parry from fan\r\n", quiet=1.5)
    b4 = send(s, b"learn force from fan\r\n", quiet=1.5)
    r = clean(b4)
    total_rounds += 4
    if "太累" in r:
        print(f"  >> Exhausted after {total_rounds} learn commands")
        break

b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS AFTER BIG GRIND", b)

b = send(s, b"hp\r\n", quiet=2.0)
show("HP AFTER BIG GRIND", b)

# ============================================
# STEP 4: Navigate to 国子监 to learn literate
# wuguan -> south -> west -> north -> east
# Cancel any pagination first
# ============================================
print("\n========== TO GUOZIJIAN FOR LITERATE ==========")
send(s, b"q\r\n", quiet=1.0)  # cancel any pending pagination
send(s, b"south\r\n", quiet=2.0)  # qinglong
send(s, b"west\r\n", quiet=2.0)   # shizikou
send(s, b"north\r\n", quiet=2.0)  # xuanwu
send(s, b"east\r\n", quiet=2.0)   # guozijian
b = send(s, b"look\r\n", quiet=2.0)
show("GUOZIJIAN?", b)

resp = clean(b)
if "国子监" in resp or "秀才" in resp.lower() or "xiucai" in resp.lower():
    b = send(s, b"learn literate from xiucai\r\n", quiet=2.0)
    show("LEARN LITERATE", b)
    # Try more times
    for i in range(3):
        b = send(s, b"learn literate from xiucai\r\n", quiet=2.0)
else:
    show("NOT AT GUOZIJIAN - current location", b)

b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS WITH LITERATE?", b)

# ============================================
# STEP 5: Try a fight if we have sen left
# ============================================
print("\n========== COMBAT ATTEMPT ==========")
sen_cur, sen_max = get_sen(s)
print(f"  Sen: {sen_cur}/{sen_max}")

if sen_cur > 30:
    # Go find 疥顶小僧 on zhuque
    send(s, b"q\r\n", quiet=1.0)
    # Navigate to zhuque: guozijian->west->south->south
    send(s, b"west\r\n", quiet=2.0)
    send(s, b"south\r\n", quiet=2.0)
    send(s, b"south\r\n", quiet=2.0)
    b = send(s, b"look\r\n", quiet=2.0)
    show("LOOKING FOR FIGHT", b)

    resp = clean(b)
    if "小僧" in resp:
        send(s, b"set wimpy 50\r\n", quiet=1.0)
        b = send(s, b"fight jieding\r\n", quiet=2.0)
        show("FIGHT START", b)

        for i in range(8):
            time.sleep(4)
            b = drain(s, quiet=2.0, maxt=6.0)
            if b:
                show(f"COMBAT {i+1}", b)
                r = clean(b)
                if "死了" in r or "承让" in r or "逃" in r:
                    break
    else:
        print("  >> No monk found, skipping combat")
else:
    print("  >> Sen too low for combat, skipping")

# ============================================
# STEP 6: Final status, park at kezhan
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

# Navigate to kezhan
send(s, b"q\r\n", quiet=1.0)
b = send(s, b"look\r\n", quiet=2.0)
resp = clean(b)
if "客栈" not in resp:
    if "朱雀" in resp and "客栈" in resp:
        send(s, b"east\r\n", quiet=2.0)
    elif "朱雀" in resp:
        send(s, b"north\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)
    elif "十字" in resp:
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)
    elif "青龙" in resp:
        send(s, b"west\r\n", quiet=2.0)
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)
    elif "武馆" in resp:
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"west\r\n", quiet=2.0)
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)
    elif "兵器" in resp:
        send(s, b"north\r\n", quiet=2.0)
        send(s, b"west\r\n", quiet=2.0)
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)
    elif "玄武" in resp:
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)
    elif "国子监" in resp:
        send(s, b"west\r\n", quiet=2.0)
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"south\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)
    elif "当铺" in resp:
        send(s, b"east\r\n", quiet=2.0)
        send(s, b"east\r\n", quiet=2.0)

b = send(s, b"look\r\n", quiet=2.0)
show("PARKED AT KEZHAN", b)

# Stay connected but don't quit
print("\n*** Round 9 ended - character stays at kezhan, NO QUIT ***")
time.sleep(1)
s.close()
