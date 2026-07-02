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
    print(t[-3000:] if len(t) > 3000 else t)

def go(s, d):
    return clean(send(s, d.encode() + b"\r\n", quiet=1.0))

def look(s):
    b = send(s, b"look\r\n", quiet=1.5)
    return clean(b), b

print("Round 32: KILLSHOT — go to 粮仓, kill jing!")
s = socket.create_connection(("146.190.143.182", 6666), timeout=15)
drain(s, quiet=3.0, maxt=12.0)
send(s, b"gb\r\n", quiet=3.0)
send(s, b"no\r\n", quiet=3.0)
send(s, b"yxcdrg\r\n", quiet=3.0)
b = send(s, b"198633\r\n", quiet=4.0)
if "y/n" in clean(b):
    send(s, b"y\r\n", quiet=4.0)
send(s, b"set wimpy 10\r\n", quiet=1.0)

# Get to shizikou
print("\n  Getting to shizikou...")
for _ in range(15):
    desc, _ = look(s)
    if "十字街头" in desc: print("  >> SHIZIKOU!"); break
    if "粮仓" in desc or "粮店" in desc: go(s,"west"); continue  # liangdian -> beiyin4
    if "南城客栈" in desc: go(s,"west"); go(s,"north"); continue
    if "朱雀" in desc: go(s,"north"); continue
    if "白虎" in desc: go(s,"east"); continue
    if "青龙" in desc: go(s,"west"); continue
    if "玄武" in desc: go(s,"south"); continue
    if "天监" in desc: go(s,"east"); go(s,"south"); continue
    if "背阴" in desc: go(s,"north"); continue
    if "当铺" in desc: go(s,"east"); go(s,"north"); continue
    if "南城口" in desc: go(s,"north"); go(s,"north"); go(s,"north"); go(s,"north"); continue
    go(s,"north")

# Sprint to 粮仓: south x4 → west → northwest → east
print("  Sprinting to 粮仓...")
go(s,"south"); go(s,"south"); go(s,"south"); go(s,"south")
go(s,"west")
go(s,"northwest")
go(s,"east")

desc, b = look(s)
show("AT 粮仓?", b)

# Try to kill with correct IDs
if "黑狮" in desc or "jing" in desc.lower() or "guai" in desc.lower():
    print("\n  ** MONSTER IS HERE! Trying kill commands... **")

    # Try all possible ID formats
    for cmd in ["kill jing", "kill heishi jing", "fight jing", "fight heishi jing",
                "kill guai", "fight guai"]:
        print(f"  Trying: {cmd}")
        r = go(s, cmd)
        if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
            print(f"  >> ENGAGED with '{cmd}'!")
            show("FIGHT START", send(s, b"", quiet=0.5))

            killed = False
            for j in range(50):
                time.sleep(3)
                b = drain(s, quiet=2.0, maxt=5.0)
                if b:
                    r = clean(b)
                    if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                        show("**** VICTORY! ****", b)
                        killed = True
                        break
                    elif "承让" in r:
                        print("  >> LOST")
                        break
                    elif "找机会逃跑" in r:
                        print("  >> FLED")
                        break
                    elif j % 6 == 0:
                        lines = [l for l in r.split("\n") if l.strip() and ">" not in l]
                        if lines: print(f"  [combat {j}] {lines[-1].strip()[:70]}")

            if killed:
                print("\n  ********************************************")
                print("  ***    FIRST KILL!!!                     ***")
                print("  ***    YUAN MISSION COMPLETE!!!          ***")
                print("  ********************************************")
                time.sleep(3)
                b2 = drain(s, quiet=2.0, maxt=5.0)
                if b2: show("AFTERMATH", b2)
            break
        elif "想攻击谁" in r or "没有" in r:
            continue
        else:
            print(f"  Response: {r[:60]}")
else:
    print("\n  !! Monster not at 粮仓 anymore — it may have wandered")
    # Quick search of adjacent rooms
    print("  Searching adjacent rooms...")
    for d in ["west","west","north","south","south","east","southeast","south","north","northwest",
              "east","east","north","north","north","south","south","south","east"]:
        go(s, d)
        desc, _ = look(s)
        if "黑狮" in desc or ("jing" in desc.lower() and "精" in desc):
            print(f"  ** FOUND after wandering! **")
            for cmd in ["kill jing","kill guai","fight jing"]:
                r = go(s, cmd)
                if any(w in r for w in ["喝道","想杀","领教","奉陪"]):
                    print(f"  >> ENGAGED!")
                    killed = False
                    for j in range(50):
                        time.sleep(3)
                        b = drain(s, quiet=2.0, maxt=5.0)
                        if b:
                            r = clean(b)
                            if any(w in r for w in ["死了","服了","投降","青烟","原形","领罪","走开","大赦"]):
                                show("**** VICTORY! ****", b)
                                killed = True
                                break
                            elif "承让" in r: break
                            elif "找机会逃跑" in r: break
                            elif j % 6 == 0:
                                lines = [l for l in r.split("\n") if l.strip() and ">" not in l]
                                if lines: print(f"  [combat {j}] {lines[-1].strip()[:70]}")
                    if killed:
                        print("\n  *** FIRST KILL!!! ***")
                    break
            break

# FINAL
print("\n========== FINAL ==========")
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)
b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)
b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS", b)
print("\n*** Round 32 - NO QUIT ***")
time.sleep(1)
s.close()
