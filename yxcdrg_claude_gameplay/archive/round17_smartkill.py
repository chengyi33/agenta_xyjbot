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

def where(s):
    """Get current room short name."""
    b = send(s, b"look\r\n", quiet=2.0)
    r = clean(b)
    # Extract room short name from first line
    for line in r.split("\n"):
        line = line.strip()
        if line and " - " in line:
            return line.split(" - ")[0].strip(), r, b
        elif line and len(line) > 2 and ">" not in line and "出口" not in line:
            return line.strip(), r, b
    return "unknown", r, b

def go(s, direction):
    """Move and return new room description."""
    b = send(s, direction.encode() + b"\r\n", quiet=2.0)
    return clean(b), b

def goto_shizikou(s):
    """Navigate to 十字街头 from any common location."""
    name, desc, _ = where(s)
    print(f"  Current: {name}")

    if "十字" in name: return True
    if "客栈" in name or "南城客栈" in name:
        go(s, "west"); go(s, "north"); return True
    if "朱雀" in name:
        go(s, "north")
        n, _, _ = where(s)
        if "十字" in n: return True
        if "朱雀" in n: go(s, "north"); return True  # might need 2 norths
        n2, _, _ = where(s)
        if "十字" in n2: return True
        go(s, "north"); return True
    if "当铺" in name:
        go(s, "east"); go(s, "north"); return True
    if "白虎" in name:
        go(s, "east")
        n, _, _ = where(s)
        if "十字" in n: return True
        go(s, "east"); return True
    if "青龙" in name:
        go(s, "west"); return True
    if "玄武" in name:
        go(s, "south"); return True
    if "武馆" in name:
        go(s, "south"); go(s, "west"); return True
    if "兵器" in name:
        go(s, "north"); go(s, "west"); return True
    if "化生" in name:
        go(s, "south"); go(s, "east"); return True
    if "南城口" in name:
        go(s, "north"); go(s, "north"); go(s, "north"); return True
    if "泾水" in name:
        go(s, "north"); go(s, "north"); go(s, "north"); go(s, "north"); return True
    if "背阴" in name or "minju" in name.lower() or "民居" in name:
        go(s, "north"); go(s, "east"); go(s, "north"); return True
    if "国子监" in name:
        go(s, "west"); go(s, "south"); return True
    if "天监" in name:
        go(s, "east"); go(s, "south"); return True
    if "钱庄" in name:
        go(s, "north"); return True
    # Fallback
    print(f"  !! Unknown location: {name}, trying east then north")
    go(s, "east"); go(s, "north")
    return True

print("Round 17: Smart navigation - BUY WEAPON then KILL!")
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
# STEP 1: Navigate to 十字街头 (hub)
# ============================================
print("\n========== NAVIGATING TO HUB ==========")
goto_shizikou(s)
name, desc, b = where(s)
show("AT HUB?", b)

# ============================================
# STEP 2: Go to weapon shop (十字 -> east -> south)
# ============================================
print("\n========== BUYING WEAPON ==========")
go(s, "east")   # qinglong
go(s, "south")  # weapon shop
name, desc, b = where(s)
show("WEAPON SHOP?", b)

if "兵器" in name or "萧萧" in desc:
    b = send(s, b"buy blade from xiao xiao\r\n", quiet=2.0)
    show("BUY BLADE", b)
    b = send(s, b"wield blade\r\n", quiet=2.0)
    show("WIELD", b)

b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)

# ============================================
# STEP 3: Navigate to minju4 (boy)
# Path: weapon shop -> north (qinglong) -> west (shizikou) -> south x4 -> west (beiyin5) -> south (minju4)
# ============================================
print("\n========== TO MINJU4 (BOY) ==========")
go(s, "north")   # qinglong
go(s, "west")    # shizikou
go(s, "south")   # zhuque (kezhan level)
name, _, _ = where(s)
print(f"  After south: {name}")

go(s, "south")   # zhuque-s2
name, _, _ = where(s)
print(f"  After south: {name}")

go(s, "south")   # zhuque-s3
name, _, _ = where(s)
print(f"  After south: {name}")

go(s, "south")   # zhuque-s4
name, _, _ = where(s)
print(f"  After south: {name}")

go(s, "west")    # beiyin5
name, desc, b = where(s)
print(f"  After west: {name}")
show("BEIYIN5?", b)

go(s, "south")   # minju4
name, desc, b = where(s)
show("MINJU4 (BOY)?", b)

# ============================================
# STEP 4: Find and KILL target
# ============================================
print("\n========== KILLING! ==========")

target_id = None
if "男孩" in desc:
    target_id = "boy"
elif "女孩" in desc:
    target_id = "girl"
elif "老鼠" in desc:
    target_id = "rat"

if not target_id:
    # Not at minju4, try going to minju3 for rats
    print("  >> No target at minju4, trying beiyin3 -> minju3 for rats")
    go(s, "north")       # back to beiyin5
    go(s, "northwest")   # beiyin4
    go(s, "west")        # beiyin3
    go(s, "south")       # minju3
    name, desc, b = where(s)
    show("MINJU3 (RATS)?", b)
    if "老鼠" in desc or "rat" in desc.lower():
        target_id = "rat"

if not target_id:
    # Still nothing, try beiyin1 -> minju1 for girl
    print("  >> No rats, trying minju1 for girl")
    go(s, "north")       # beiyin3
    go(s, "north")       # beiyin2 or beiyin1
    go(s, "northwest")   # beiyin1
    go(s, "east")        # minju1
    name, desc, b = where(s)
    show("MINJU1 (GIRL)?", b)
    if "女孩" in desc:
        target_id = "girl"

if target_id:
    print(f"\n  >> TARGET FOUND: {target_id}! ATTACKING!")
    b = send(s, f"kill {target_id}\r\n".encode(), quiet=2.0)
    show("KILL!", b)

    killed = False
    for i in range(25):
        time.sleep(3)
        b = drain(s, quiet=2.0, maxt=5.0)
        if b:
            r = clean(b)
            if "死了" in r:
                show("*** KILLED! ***", b)
                killed = True
                break
            elif "承让" in r:
                show("LOST", b)
                break
            elif "逃跑" in r or "找机会" in r:
                show("FLED", b)
                break
            elif i % 5 == 0:
                show(f"COMBAT {i+1}", b)

    if killed:
        print("\n  ****************************")
        print("  *** FIRST KILL ACHIEVED! ***")
        print("  ****************************")
else:
    print("  !! No killable target found anywhere!")

# ============================================
# FINAL STATUS
# ============================================
print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)
b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS", b)

print("\n*** Round 17 ended - NO QUIT ***")
time.sleep(1)
s.close()
