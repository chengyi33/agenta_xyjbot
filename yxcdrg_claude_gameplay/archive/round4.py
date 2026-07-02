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

# Connect & Login
print("Round 4: Learn skills at Wuguan, find Yuan Tiangang...")
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
# STEP 1: Navigate to 长安武馆 (Martial Hall)
# Path: Inn -> west (朱雀) -> north (十字街头) -> east (青龙) -> north (武馆)
# ============================================
print("\n========== GOING TO WUGUAN ==========")
b = send(s, b"west\r\n", quiet=2.0)
show("W to Zhuque", b)
b = send(s, b"north\r\n", quiet=2.0)
show("N to Shizikou", b)
b = send(s, b"east\r\n", quiet=2.0)
show("E to Qinglong", b)
b = send(s, b"north\r\n", quiet=2.0)
show("N to Wuguan", b)

b = send(s, b"look\r\n", quiet=2.0)
show("WUGUAN LOOK", b)

# ============================================
# STEP 2: Apprentice to Fan Luping (武馆教头)
# ============================================
print("\n========== APPRENTICING ==========")
# First try to bai shi (拜师)
b = send(s, b"bai fan\r\n", quiet=3.0)
show("BAI FAN", b)

# Try alternate commands
b = send(s, b"worship fan\r\n", quiet=3.0)
show("WORSHIP FAN", b)

b = send(s, b"ask fan about apprentice\r\n", quiet=3.0)
show("ASK ABOUT APPRENTICE", b)

# The command might be: bai fan luping wei shi
b = send(s, b"bai fan luping wei shi\r\n", quiet=3.0)
show("BAI FAN LUPING WEI SHI", b)

# Or just: apprentice fan
b = send(s, b"apprentice fan\r\n", quiet=3.0)
show("APPRENTICE FAN", b)

# ============================================
# STEP 3: Learn skills from Fan Luping
# ============================================
print("\n========== LEARNING SKILLS ==========")
b = send(s, b"learn unarmed from fan\r\n", quiet=3.0)
show("LEARN UNARMED", b)

b = send(s, b"learn dodge from fan\r\n", quiet=3.0)
show("LEARN DODGE", b)

b = send(s, b"learn parry from fan\r\n", quiet=3.0)
show("LEARN PARRY", b)

b = send(s, b"learn force from fan\r\n", quiet=3.0)
show("LEARN FORCE", b)

# Check skills now
b = send(s, b"skills\r\n", quiet=2.0)
show("MY SKILLS NOW", b)

# ============================================
# STEP 4: Navigate to 天监台 to find Yuan Tiangang
# Path: wuguan -> south (青龙) -> west (十字街头) -> north (玄武) -> west (天监台)
# ============================================
print("\n========== GOING TO TIANJIANTAI ==========")
b = send(s, b"south\r\n", quiet=2.0)  # back to qinglong
b = send(s, b"west\r\n", quiet=2.0)   # shizikou
b = send(s, b"north\r\n", quiet=2.0)  # xuanwu
b = send(s, b"west\r\n", quiet=2.0)   # tianjiantai
b = send(s, b"look\r\n", quiet=2.0)
show("TIANJIANTAI", b)

# Ask Yuan about kill
b = send(s, b"ask yuan about kill\r\n", quiet=3.0)
show("ASK YUAN ABOUT KILL", b)

# Ask more useful things
b = send(s, b"ask yuan about longgong\r\n", quiet=3.0)
show("ASK YUAN ABOUT LONGGONG", b)

b = send(s, b"ask yuan about menpai\r\n", quiet=3.0)
show("ASK YUAN ABOUT MENPAI", b)

# ============================================
# STEP 5: Try to practice skills / fight something
# ============================================
print("\n========== TRAINING ==========")
# Practice unarmed
b = send(s, b"practice unarmed\r\n", quiet=3.0)
show("PRACTICE UNARMED", b)

b = send(s, b"practice dodge\r\n", quiet=3.0)
show("PRACTICE DODGE", b)

# ============================================
# STEP 6: Check status and navigate back to kezhan
# ============================================
b = send(s, b"hp\r\n", quiet=2.0)
show("HP", b)

b = send(s, b"score\r\n", quiet=3.0)
show("SCORE", b)

b = send(s, b"skills\r\n", quiet=2.0)
show("SKILLS", b)

b = send(s, b"i\r\n", quiet=2.0)
show("INVENTORY", b)

# Go back to kezhan: tianjiantai -> east (xuanwu) -> south (shizikou) -> south (zhuque) -> east (kezhan)
b = send(s, b"east\r\n", quiet=2.0)
b = send(s, b"south\r\n", quiet=2.0)
b = send(s, b"south\r\n", quiet=2.0)
b = send(s, b"east\r\n", quiet=2.0)
b = send(s, b"look\r\n", quiet=2.0)
show("BACK AT KEZHAN", b)

# DO NOT QUIT - just disconnect
print("\n*** Round 4 ended - character stays logged in ***")
time.sleep(1)
s.close()
