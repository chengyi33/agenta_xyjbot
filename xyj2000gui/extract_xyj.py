#!/usr/bin/env python3
"""
XYJ2000 LPC -> JSON extractor
---------------------------------
Walks the mudlib world/ tree and pulls out game content (rooms, NPCs, items)
into clean JSON that a Godot (or any) engine can load.

This is the foundation step for the ink-wash 2D graphics port (Strategy B).
Pure Python, no engine deps.

Run:  python3 extract_xyj.py /path/to/world  out/
"""
import os, re, json, sys, hashlib

# ---- tiny LPC value parser ------------------------------------------------
# We don't need a full LPC interpreter. We just scrape the set()/mapping
# literals that define content. Good enough for room/npc/item data.

def strip_comments(src):
    # remove // line comments and /* */ blocks
    src = re.sub(r"/\*.*?\*/", "", src, flags=re.S)
    src = re.sub(r"//[^\n]*", "", src)
    return src

def extract_set_calls(src):
    """Return dict of set("key", value) and set("a/b", x) pairs.
    Also captures set_name("x", (...)) as key "name"."""
    out = {}
    # set( "key" , <expr> )  -- allow arbitrary whitespace
    for m in re.finditer(r'set\s*\(\s*"([^"]+)"\s*,\s*(.*?)\)\s*;', src, flags=re.S):
        key = m.group(1)
        val = m.group(2).strip()
        out[key] = val
    # set_name("x", ({...})) -> store under "name"
    for m in re.finditer(r'set_name\s*\(\s*(.*?)\)\s*;', src, flags=re.S):
        out.setdefault("name", m.group(1).strip())
    return out

def extract_set_skill(src):
    skills = {}
    for m in re.finditer(r'set_skill\s*\(\s*"([^"]+)"\s*,\s*(\d+)\s*\)', src):
        skills[m.group(1)] = int(m.group(2))
    return skills

def extract_objects_mapping(src):
    """Parse set("objects", ([ "/path": count, ... ]))"""
    m = re.search(r'set\s*\(\s*"objects"\s*,\s*\(\[\s*(.*?)\s*\]\)\s*\)', src, flags=re.S)
    if not m: return {}
    body = m.group(1)
    out = {}
    for km in re.finditer(r'"([^"]+)"\s*:\s*(\d+)', body):
        out[km.group(1)] = int(km.group(2))
    return out

def extract_exits_mapping(src):
    """Parse set("exits", ([ "dir" : "/path", ... ]))"""
    m = re.search(r'set\s*\(\s*"exits"\s*,\s*\(\[\s*(.*?)\s*\]\)\s*\)', src, flags=re.S)
    if not m: return {}
    body = m.group(1)
    out = {}
    for km in re.finditer(r'"([^"]+)"\s*:\s*("(?:[^"\\]|\\.)*"|__DIR__"[^,]*|/[^\s,]+)', body):
        dir_ = km.group(1)
        target = km.group(2).strip().strip('"')
        out[dir_] = target
    return out

def resolve_dirdir(src, file_path, world_root):
    """Replace __DIR__"foo" with absolute mudlib path based on file location."""
    base = os.path.dirname(file_path)
    def repl(m):
        rel = m.group(1) if m.group(1) else ""
        # __DIR__"rel" -> absolute path from file's dir
        absdir = base
        joined = os.path.normpath(os.path.join(absdir, rel))
        return '"' + "/" + os.path.relpath(joined, world_root) + '"'
    return re.sub(r'__DIR__"([^"]*)"', repl, src)

def literal_to_value(tok):
    """Best-effort: turn an LPC literal token into a Python value."""
    tok = tok.strip()
    # handle @LONG ... LONG heredoc blocks -> keep inner text (not quote-wrapped)
    m = re.search(r'@LONG\s*(.*?)\s*LONG', tok, flags=re.S)
    if m:
        return m.group(1).strip()
    if tok.startswith('"'):
        # string (may contain escapes)
        s = tok.strip('"')
        # only unicode-escape-decode real escape sequences (ANSI color etc),
        # never plain Chinese text (that would mojibake it)
        if '\\e' in s or '\\033' in s or '\\n' in s:
            s = s.encode('latin-1', 'ignore').decode('unicode_escape', 'ignore')
        return s.strip()
    if re.fullmatch(r'-?\d+', tok):
        return int(tok)
    if re.fullmatch(r'-?\d+\.\d+', tok):
        return float(tok)
    return tok  # leave expressions as-is

def read_src(path):
    """Read LPC source, handling mixed UTF-8 / GBK encoding in the mudlib."""
    with open(path, "rb") as f:
        raw = f.read()
    for enc in ("utf-8", "gb18030", "gbk"):
        try:
            return raw.decode(enc)
        except UnicodeDecodeError:
            continue
    return raw.decode("utf-8", errors="replace")

def basename(path):
    return "/" + path.lstrip("./")

def area_of(rid):
    """/d/pantao/foo.c -> pantao ; /d/city/... -> city ; else unknown"""
    parts = rid.split('/')
    # parts: ['', 'd', <area>, ...]  or ['', 'cmds'/'std'/'obj', ...]
    if len(parts) >= 3 and parts[1] == 'd':
        return parts[2]
    return parts[1] if len(parts) >= 2 else "unknown"

def clean_name(tok):
    """set_name may be ("中文名", ({"id1","id2"})) -> take first quoted string.
    Works on the raw LPC token (do NOT pre-strip quotes)."""
    if not isinstance(tok, str):
        return tok
    m = re.search(r'"([^"]+)"', tok)
    return m.group(1) if m else tok

# ---- extraction -----------------------------------------------------------

def find_files(world_root, marker):
    res = []
    for dp, _, fns in os.walk(world_root):
        for fn in fns:
            if not fn.endswith('.c'):
                continue
            p = os.path.join(dp, fn)
            try:
                head = read_src(p)[:4000]
            except Exception:
                continue
            if marker in head:
                res.append(p)
    return res

def extract_room(path, world_root):
    src = read_src(path)
    src = strip_comments(src)
    src = resolve_dirdir(src, path, world_root)
    sets = extract_set_calls(src)
    exits = extract_exits_mapping(src)
    objects = extract_objects_mapping(src)
    rid = basename(os.path.relpath(path, world_root)).replace('\\', '/')
    # normalize exits that still look like __DIR__ -> already resolved
    norm_exits = {}
    for d, t in exits.items():
        t = t.strip('"')
        if t.startswith('/'):
            norm_exits[d] = t
        else:
            norm_exits[d] = t
    return {
        "id": rid,
        "name": literal_to_value(sets.get("short", '""')),
        "desc": literal_to_value(sets.get("long", '""')),
        "exits": norm_exits,
        "objects": objects,
        "outdoors": sets.get("outdoors", "0") not in ("0", "0;", ""),
        "area": area_of(rid),
    }

def extract_npc(path, world_root):
    src = read_src(path)
    src = strip_comments(src)
    sets = extract_set_calls(src)
    skills = extract_set_skill(src)
    nid = basename(os.path.relpath(path, world_root)).replace('\\', '/')
    def num(k):
        v = sets.get(k)
        return int(v) if v and re.fullmatch(r'-?\d+', v.strip()) else None
    raw_name = sets.get("name", "")
    name = clean_name(literal_to_value(raw_name)) if ("(" not in raw_name) else None
    dynamic = "(" in raw_name or "(" in sets.get("long", "")
    return {
        "id": nid,
        "name": name,
        "dynamic": dynamic,
        "long": literal_to_value(sets.get("long", '""')),
        "gender": literal_to_value(sets.get("gender", '""')),
        "attitude": literal_to_value(sets.get("attitude", '""')),
        "str": num("str"), "int": num("int"), "con": num("con"),
        "dex": num("dex"), "per": num("per"),
        "combat_exp": num("combat_exp"), "daoxing": num("daoxing"),
        "max_gin": num("max_gin"), "max_kee": num("max_kee"), "max_sen": num("max_sen"),
        "skills": skills,
        "area": area_of(nid),
    }

def extract_item(path, world_root):
    src = read_src(path)
    src = strip_comments(src)
    sets = extract_set_calls(src)
    iid = basename(os.path.relpath(path, world_root)).replace('\\', '/')
    # armor_prop/foo and weapon_prop/foo
    props = {}
    for k, v in sets.items():
        if k.startswith("armor_prop/") or k.startswith("weapon_prop/"):
            props[k.split("/", 1)[1]] = literal_to_value(v)
    return {
        "id": iid,
        "name": clean_name(sets.get("name", '""')),
        "long": literal_to_value(sets.get("long", '""')),
        "type": "cloth" if "inherit CLOTH" in src else ("weapon" if "inherit WEAPON" in src else "obj"),
        "material": literal_to_value(sets.get("material", '""')),
        "weight": sets.get("weight"),
        "props": props,
        "area": area_of(iid),
    }

def main():
    if len(sys.argv) < 3:
        print("usage: extract_xyj.py <world_root> <out_dir>")
        sys.exit(1)
    world_root = sys.argv[1]
    out_dir = sys.argv[2]
    os.makedirs(out_dir, exist_ok=True)

    print("Scanning rooms...")
    rooms = [extract_room(p, world_root) for p in find_files(world_root, "inherit ROOM")]
    print(f"  {len(rooms)} rooms")
    print("Scanning NPCs...")
    npcs = [extract_npc(p, world_root) for p in find_files(world_root, "inherit NPC")]
    print(f"  {len(npcs)} npcs")
    print("Scanning items...")
    items = []
    for p in find_files(world_root, "inherit CLOTH") + find_files(world_root, "inherit WEAPON") + find_files(world_root, "inherit OBJECT"):
        items.append(extract_item(p, world_root))
    # dedupe
    seen=set(); uitems=[]
    for it in items:
        if it["id"] in seen: continue
        seen.add(it["id"]); uitems.append(it)
    items = uitems
    print(f"  {len(items)} items")

    # index by area for easy loading
    areas = {}
    for r in rooms:
        areas.setdefault(r["area"], {"rooms": 0, "npcs": 0, "items": 0})
        areas[r["area"]]["rooms"] += 1

    with open(os.path.join(out_dir, "rooms.json"), "w", encoding="utf-8") as f:
        json.dump(rooms, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "npcs.json"), "w", encoding="utf-8") as f:
        json.dump(npcs, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "items.json"), "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=1)
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"room_count": len(rooms), "npc_count": len(npcs),
                   "item_count": len(items), "areas": areas}, f, ensure_ascii=False, indent=2)

    # build exit-graph adjacency for pathing
    adj = {}
    for r in rooms:
        adj[r["id"]] = r["exits"]
    with open(os.path.join(out_dir, "graph.json"), "w", encoding="utf-8") as f:
        json.dump(adj, f, ensure_ascii=False)

    print("Wrote:", out_dir, "/ {rooms,npcs,items,graph,manifest}.json")
    print("Areas:", ", ".join(sorted(areas.keys())))

if __name__ == "__main__":
    main()
