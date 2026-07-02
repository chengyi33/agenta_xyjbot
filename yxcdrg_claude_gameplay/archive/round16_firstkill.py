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

def mv(s, d):
    return send(s, d.encode() + b"\r\n", quiet=2.0)

print("Round 16: FIRST KILL - go to minju, kill rats/boy!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
resp = clean(b)
if "y/n" in resp:
    b = send(s, b"y\r\n", quiet=4.0)

send(s, b"set wimpy 10\r\n", quiet=1.0)

# ============================================
# STEP 1: Buy a weapon first! We lost all gear.
# kezhan -> west -> north -> east -> south (weapon shop)
# ============================================
print("\n========== BUYING WEAPON ==========")
b = send(s, b"look\r\n", quiet=2.0)
show("START", b)

# Go to weapon shop
mv(s, "west")   # zhuque
mv(s, "north")  # shizikou
mv(s, "east")   # qinglong
mv(s, "south")  # weapon shop
b = send(s, b"look\r\n", quiet=2.0)
show("WEAPON SHOP?", b)

r = clean(b)
if "兵器" in r or "萧萧" in r:
    b = send(s, b"buy blade from xiao xiao\r\n", quiet=2.0)
    show("BUY BLADE", b)
    b = send(s, b"wield blade\r\n", quiet=2.0)
    show("WIELD", b)
    # Also buy a shield
    b = send(s, b"buy shield from xiao xiao\r\n", quiet=2.0)
    show("BUY SHIELD", b)
    b = send(s, b"wear shield\r\n", quiet=2.0)
    show("WEAR SHIELD", b)
else:
    show("NOT AT WEAPON SHOP", b)

b = send(s, b"score\r\n", quiet=3.0)
show("SCORE WITH NEW GEAR", b)

# ============================================
# STEP 2: Navigate to minju4 (boy, combat_exp 100)
# weapon shop -> north -> west -> south -> south -> south -> south -> west -> south
# (qinglong -> shizikou -> zhuque -> zhuque-s2 -> zhuque-s3 -> zhuque-s4 -> beiyin5 -> minju4)
# ============================================
print("\n========== NAVIGATING TO WEAKEST MOBS ==========")
mv(s, "north")    # qinglong
mv(s, "west")     # shizikou
mv(s, "south")    # zhuque (kezhan level)
mv(s, "south")    # zhuque-s2 (乐府)
mv(s, "south")    # zhuque-s3 (毛货铺)
mv(s, "south")    # zhuque-s4
b = mv(s, "west") # beiyin5
show("BEIYIN5?", b)

b = mv(s, "south") # minju4 (boy!)
b = send(s, b"look\r\n", quiet=2.0)
show("MINJU4 - BOY?", b)

# ============================================
# STEP 3: KILL the boy (combat_exp 100, should be easy)
# ============================================
r = clean(b)
target_id = None
if "男孩" in r:
    target_id = "boy"
    print("  >> Found 男孩 (boy)!")
elif "女孩" in r:
    target_id = "girl"
    print("  >> Found 女孩 (girl)!")
else:
    # Check for any NPC
    for line in r.split("\n"):
        if "(" in line and ")" in line and "Board" not in line:
            m = re.search(r'\(([^)]+)\)', line)
            if m:
                tid = m.group(1).split()[0].lower()
                if tid not in ["agenta", "xiao", "snoopl"]:
                    target_id = tid
                    print(f"  >> Found target: {line.strip()} (id: {target_id})")
                    break

if target_id:
    print(f"\n========== KILLING {target_id}! ==========")
    b = send(s, f"kill {target_id}\r\n".encode(), quiet=2.0)
    show("KILL!", b)

    killed = False
    for i in range(25):
        time.sleep(3)
        b = drain(s, quiet=2.0, maxt=5.0)
        if b:
            r = clean(b)
            if "死了" in r:
                show("*** TARGET DIED! ***", b)
                killed = True
                break
            elif "承让" in r:
                show("LOST", b)
                break
            elif "逃跑" in r or "找机会逃跑" in r:
                show("FLED", b)
                break
            elif i % 5 == 0:
                show(f"COMBAT {i+1}", b)

    if killed:
        print("\n  ****************************")
        print("  *** FIRST KILL ACHIEVED! ***")
        print("  ****************************")
    else:
        # If we lost/fled, try the rats instead (even weaker)
        print("\n  >> Trying rats instead (combat_exp 20)...")
        # Navigate: minju4 -> north -> northwest -> south -> minju3
        # beiyin5 -> northwest -> beiyin4 -> west -> beiyin3 -> south -> minju3
        mv(s, "north")       # beiyin5
        mv(s, "northwest")   # beiyin4
        mv(s, "west")        # beiyin3
        mv(s, "south")       # minju3
        b = send(s, b"look\r\n", quiet=2.0)
        show("MINJU3 - RATS?", b)

        r = clean(b)
        if "老鼠" in r or "rat" in r.lower():
            print("  >> Found rats!")
            b = send(s, b"kill rat\r\n", quiet=2.0)
            show("KILL RAT!", b)

            for i in range(20):
                time.sleep(3)
                b = drain(s, quiet=2.0, maxt=5.0)
                if b:
                    r = clean(b)
                    if "死了" in r:
                        show("*** RAT DIED! ***", b)
                        killed = True
                        break
                    elif i % 5 == 0:
                        show(f"RAT COMBAT {i+1}", b)

            if killed:
                print("\n  ****************************")
                print("  *** FIRST KILL ACHIEVED! ***")
                print("  ****************************")
else:
    print("  >> No target found! Looking around...")
    # Try going to minju3 for rats
    mv(s, "north")       # back to beiyin5
    mv(s, "northwest")   # beiyin4
    mv(s, "west")        # beiyin3
    mv(s, "south")       # minju3
    b = send(s, b"look\r\n", quiet=2.0)
    show("MINJU3 - RATS?", b)

    r = clean(b)
    if "老鼠" in r or "rat" in r.lower():
        print("  >> Found rats!")
        b = send(s, b"kill rat\r\n", quiet=2.0)
        show("KILL RAT!", b)

        killed = False
        for i in range(20):
            time.sleep(3)
            b = drain(s, quiet=2.0, maxt=5.0)
            if b:
                r = clean(b)
                if "死了" in r:
                    show("*** RAT DIED! ***", b)
                    killed = True
                    break
                elif i % 5 == 0:
                    show(f"RAT COMBAT {i+1}", b)

        if killed:
            print("\n  ****************************")
            print("  *** FIRST KILL ACHIEVED! ***")
            print("  ****************************")

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

print("\n*** Round 16 ended - NO QUIT ***")
time.sleep(1)
s.close()
