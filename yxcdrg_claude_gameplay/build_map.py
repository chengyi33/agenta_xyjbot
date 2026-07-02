"""
build_map.py — Parse the XYJ2000 MUD LPC source into a complete room graph.

Reads every world/d/**/*.c room file, extracts the room 'short' name and its
'exits' mapping, resolves exit targets to canonical room ids, and writes
xyj2000_map.json:

  {
    "d/lingtai/baixi": {
        "short": "白石溪",
        "area": "lingtai",
        "exits": {"northwest": "d/lingtai/baixi2", "southeast": "d/lingtai/uphill3"}
    },
    ...
  }

Only real room links are kept (targets via __DIR__"name" or absolute "/d/...").
Decorative exit values (Chinese strings, 0, "no", variables) are dropped.
"""
import os, re, json, sys

sys.stdout.reconfigure(encoding="utf-8")

WORLD = os.path.join(os.path.dirname(__file__), "..", "world")
WORLD = os.path.abspath(WORLD)
DROOT = os.path.join(WORLD, "d")
OUT = os.path.join(os.path.dirname(__file__), "xyj2000_map.json")

DIRS = {"north","south","east","west","up","down","enter","out",
        "northeast","northwest","southeast","southwest",
        "eastup","westdown","northup","southdown","westup","eastdown",
        "northdown","southup"}

# set ("short", "白石溪")  — capture the quoted string (note: space before paren allowed)
RE_SHORT = re.compile(r'set\s*\(\s*"short"\s*,\s*"([^"]*)"')
# the whole exits block:  set ("exits", ([ .... ]));
RE_EXITS_BLOCK = re.compile(r'set\s*\(\s*"exits"\s*,\s*\(\[(.*?)\]\)\s*\)', re.S)
# one entry inside the block: "dir" : <target-expr> ,
RE_ENTRY = re.compile(r'"([a-z]+)"\s*:\s*([^,\n]+?)\s*,', re.S)


def room_id(abspath):
    """Canonical id: path relative to world root, forward slashes, no .c"""
    rel = os.path.relpath(abspath, WORLD).replace("\\", "/")
    if rel.endswith(".c"):
        rel = rel[:-2]
    return rel


def resolve_target(expr, file_dir_id):
    """Resolve an exit target expression to a canonical room id, or None.

    file_dir_id: the room id of the containing directory, e.g. 'd/lingtai'
    Handles:
      __DIR__"name"            -> file_dir_id + "/name"
      __DIR__ "a" "b"          -> concatenated segments after dir
      "/d/city/east1"          -> "d/city/east1"
      "relative/thing"         -> file_dir_id + "/relative/thing"  (rare)
    Returns None for 0, "no", variables, Chinese decorative strings, etc.
    """
    e = expr.strip()

    # __DIR__ form, possibly with trailing concatenated quoted parts
    if e.startswith("__DIR__"):
        rest = e[len("__DIR__"):]
        parts = re.findall(r'"([^"]*)"', rest)
        if not parts:
            return None
        name = "".join(parts)
        if not name:
            return None
        return f"{file_dir_id}/{name.strip('/')}"

    # Plain quoted string
    mq = re.fullmatch(r'"([^"]*)"', e)
    if mq:
        val = mq.group(1)
        if val.startswith("/"):
            # absolute path like /d/city/east1
            rid = val.lstrip("/")
            return rid if rid.startswith("d/") else None
        # Non-path quoted value: Chinese exit label, "no", etc. -> not a link
        if re.search(r'[A-Za-z0-9_]/', val) or ("/" in val and val[0].isalnum()):
            # looks like a relative path fragment
            return f"{file_dir_id}/{val.strip('/')}"
        return None

    # ROOM_DIR"x" or other define-prefixed — best effort: grab quoted tail
    mdef = re.match(r'[A-Z_][A-Z0-9_]*\s*"([^"]*)"', e)
    if mdef and "/" in mdef.group(1):
        rid = mdef.group(1).lstrip("/")
        return rid if rid.startswith("d/") else None

    return None


def parse_file(abspath):
    try:
        txt = open(abspath, encoding="utf-8", errors="replace").read()
    except Exception:
        return None
    ms = RE_SHORT.search(txt)
    short = ms.group(1) if ms else ""
    rid = room_id(abspath)
    file_dir_id = rid.rsplit("/", 1)[0]  # 'd/lingtai'
    area = rid.split("/")[1] if rid.count("/") >= 1 else "?"

    exits = {}
    mb = RE_EXITS_BLOCK.search(txt)
    if mb:
        block = mb.group(1)
        for md in RE_ENTRY.finditer(block + ","):  # trailing comma safety
            d = md.group(1)
            if d not in DIRS:
                continue
            tgt = resolve_target(md.group(2), file_dir_id)
            if tgt:
                exits[d] = tgt
    return rid, {"short": short, "area": area, "exits": exits}


def main():
    graph = {}
    n_files = 0
    for root, _dirs, files in os.walk(DROOT):
        for fn in files:
            if not fn.endswith(".c"):
                continue
            n_files += 1
            res = parse_file(os.path.join(root, fn))
            if res:
                rid, data = res
                graph[rid] = data

    # Stats
    n_exits = sum(len(v["exits"]) for v in graph.values())
    # Dangling: exit targets not present as nodes
    ids = set(graph)
    dangling = 0
    for v in graph.values():
        for t in v["exits"].values():
            if t not in ids:
                dangling += 1
    json.dump(graph, open(OUT, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"parsed {n_files} .c files")
    print(f"rooms in graph: {len(graph)}")
    print(f"total exit edges: {n_exits}")
    print(f"dangling edges (target not a known room): {dangling}")
    print(f"rooms with a short name: {sum(1 for v in graph.values() if v['short'])}")
    print(f"wrote {OUT}")

    # areas
    from collections import Counter
    ac = Counter(v["area"] for v in graph.values())
    print("top areas:", dict(ac.most_common(12)))


if __name__ == "__main__":
    main()
