"""
net.py — Low-level MUD network I/O and text parsing.

Handles: socket connect, send/recv, ANSI stripping, encoding detection,
room parsing (short name + exits from look output).
"""
import socket, time, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from config import (HOST, PORT, USER, PASS, EXIT_TOKENS, MOVE_FAIL,
                    DEATH_SIGNS, COMBAT_SIGNS, LOOK_TIMEOUT, STEP_TIMEOUT,
                    DRAIN_QUIET)


def drain(s, quiet=DRAIN_QUIET, maxt=8.0):
    """Read all available data from socket. Returns bytes."""
    s.setblocking(False)
    buf = b""
    start = last = time.time()
    while True:
        try:
            c = s.recv(4096)
            if c:
                buf += c
                last = time.time()
            else:
                break
        except BlockingIOError:
            if buf and (time.time() - last) > quiet:
                break
            if (time.time() - start) > maxt:
                break
            time.sleep(0.02)
    return buf


def clean(b):
    """Decode bytes to string, strip ANSI codes, handle GBK/UTF-8."""
    for enc in ("utf-8", "gbk"):
        try:
            t = b.replace(b"\x00", b"").decode(enc)
            return re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", t)
        except Exception:
            pass
    return b.replace(b"\x00", b"").decode("gbk", errors="replace")


def send(s, cmd, quiet=1.0):
    """Send a command and read the response."""
    s.sendall((cmd + "\r\n").encode())
    return clean(drain(s, quiet=quiet))


def m(s, cmd, q=1.0, log_path=None):
    """Send command, log to file, return response."""
    r = send(s, cmd, quiet=q)
    if log_path:
        try:
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f">> {cmd}\n{r}\n")
        except Exception:
            pass
    return r


# ── Room Parsing ──────────────────────────────────────────────────────
# Short names that should be treated as garbage (confusion responses)
_GARBAGE_SHORTS = {"什么", "什么？", "嗯？", "哦", "嗯", "啊", "哦？", "啊？"}

def parse_short(desc):
    """Extract room short name from the first non-empty, non-prompt line."""
    for line in desc.split("\n")[:6]:
        line = line.strip()
        if line and not line.startswith(">"):
            # Room header: "南海之滨 - description" or "南海之滨－"
            line = re.split(r"\s*[-－]\s*", line)[0].strip()
            # Sanity check: reject known garbage responses
            if line in _GARBAGE_SHORTS:
                continue
            # Reject single-char or question-only lines
            if len(line) <= 1 or line in ("？", "！", "。"):
                continue
            return line
    return ""


def parse_exits(desc):
    """Parse exit directions from the game's explicit exit line."""
    mk = re.search(r"出口[是有为]?\s*(.+)", desc)
    if not mk:
        return set()
    seg = re.split(r"[。\n]", mk.group(1))[0]
    return {tok for tok in re.findall(r"[a-zA-Z]+", seg.lower()) if tok in EXIT_TOKENS}


def parse_hp(hr):
    """Parse `hp` output. Returns dict with (cur, max) for 气血/精神/食物/饮水."""
    out = {}
    for label in ("气血", "精神", "食物", "饮水"):
        mm = re.search(rf"{label}：\s*(\d+)\s*/\s*(\d+)", hr)
        if mm:
            out[label] = (int(mm.group(1)), int(mm.group(2)))
    return out


def is_dead(r):
    return any(w in r for w in DEATH_SIGNS)


def has_monster(desc, name):
    """Check if a monster with given name is in the room description."""
    for line in desc.split("\n"):
        if "(" in line and ")" in line and name in line:
            return True
    return False


# ── Connection ────────────────────────────────────────────────────────
def connect():
    """Open socket and log in. Returns socket."""
    s = socket.create_connection((HOST, PORT), timeout=15)
    drain(s, quiet=3.0, maxt=12.0)
    m(s, "gb")
    m(s, "no")
    m(s, USER)
    r = send(s, PASS, quiet=4.0)
    if "y/n" in r:
        m(s, "y", q=4.0)
    m(s, "set wimpy 10")
    return s


def disconnect(s):
    """Close socket without quitting (preserves items)."""
    try:
        s.close()
    except Exception:
        pass


def quit_relog():
    """Quit (lose items) and reconnect. Returns new socket at kezhan."""
    # This is called on the old socket which we close
    s = connect()
    return s
