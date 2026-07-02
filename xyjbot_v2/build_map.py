"""
build_map.py — Rebuild xyj2000_map.json with improved parsing.

Improvements over original:
1. Parse add_action verbs (dive, swim, climb, jump) as special edges
2. Store room long descriptions (for identification fallback)
3. Store item_desc (for interactive object detection)
4. Track room "outdoors" flag (from set("outdoors", 1))
5. Better target resolution (handles concatenated paths, variables)
"""
import os, re, json, sys

sys.stdout.reconfigure(encoding="utf-8")

WORLD = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'world')
WORLD = os.path.realpath(WORLD)
DROOT = os.path.join(WORLD, "d")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "xyj2000_map.json")

DIRS = {"north","south","east","west","up","down","enter","out",
        "northeast","northwest","southeast","southwest",
        "eastup","westdown","northup","southdown","westup","eastdown",
        "northdown","southup"}

RE_SHORT = re.compile(r'set\s*\(\s*"short"\s*,\s*"([^"]*)"')
RE_EXITS_BLOCK = re.compile(r'set\s*\(\s*"exits"\s*,\s*\(\[(.*?)\]\)\s*\)', re.S)
RE_ENTRY = re.compile(r'"([a-z]+)"\s*:\s*([^,\n]+?)\s*,', re.S)
RE_LONG = re.compile(r'set\s*\(\s*"long"\s*,\s*@(\w+)(.*?)\w+\s*\)', re.S)
RE_OUTDOORS = re.compile(r'set\s*\(\s*"outdoors"\s*,\s*1\s*\)')


def room_id(abspath):
    rel = os.path.relpath(abspath, WORLD).replace("\\", "/")
    if rel.endswith(".c"):
        rel = rel[:-2]
    return rel


def resolve_target(expr, file_dir_id):
    e = expr.strip()
    if e.startswith("__DIR__"):
        rest = e[len("__DIR__"):]
        parts = re.findall(r'"([^"]*)"', rest)
        if not parts: return None
        name = "".join(parts)
        if not name: return None
        return f"{file_dir_id}/{name.strip('/')}"
    mq = re.fullmatch(r'"([^"]*)"', e)
    if mq:
        val = mq.group(1)
        if val.startswith("/"):
            return val.lstrip("/")
        if "/" in val:
            return f"{file_dir_id}/{val.strip('/')}"
        return f"{file_dir_id}/{val}"
    return None


def parse_exits(content, file_dir_id):
    block = RE_EXITS_BLOCK.search(content)
    if not block:
        return {}
    raw = block.group(1)
    exits = {}
    for m in RE_ENTRY.finditer(raw):
        d, expr = m.group(1), m.group(2)
        if d not in DIRS:
            continue
        target = resolve_target(expr, file_dir_id)
        if target:
            exits[d] = target
    return exits


def parse_long(content):
    m = RE_LONG.search(content)
    if m:
        return m.group(2).strip()[:200]  # first 200 chars
    return ""


def parse_outdoors(content):
    return bool(RE_OUTDOORS.search(content))


def parse_special_verbs(content, file_dir_id):
    """Find add_action calls that lead to movement (dive, swim, climb, jump).
    Returns list of (verb, destination_room_id or None)."""
    results = []
    # Look for add_action("do_X", "verb") patterns
    for m in re.finditer(r'add_action\s*\(\s*"do_(\w+)"\s*,\s*"(\w+)"\s*\)', content):
        func_name = "do_" + m.group(1)
        verb = m.group(2)
        if verb not in ("dive", "swim", "climb", "jump", "fly"):
            continue
        # Try to find the destination: look for me->move("...") or this_player()->move("...")
        # in the function body
        func_pattern = rf'int\s+{func_name}\s*\([^)]*\)\s*\{{(.*?)\}}'
        func_match = re.search(func_pattern, content, re.S)
        if func_match:
            body = func_match.group(1)
            move_match = re.search(r'move\s*\(\s*"([^"]+)"', body)
            if move_match:
                dest = move_match.group(1).lstrip("/")
                results.append((verb, dest))
            else:
                # Some moves use variables — mark as unknown destination
                results.append((verb, None))
    return results


def main():
    print(f"Parsing rooms from {DROOT}...")
    rooms = {}
    special_edges = []

    for root, dirs, files in os.walk(DROOT):
        for fn in files:
            if not fn.endswith(".c"):
                continue
            path = os.path.join(root, fn)
            try:
                with open(path, encoding="utf-8", errors="replace") as f:
                    content = f.read()
            except Exception:
                continue

            rid = room_id(path)
            dir_id = rid.rsplit("/", 1)[0] if "/" in rid else rid

            short_m = RE_SHORT.search(content)
            short = short_m.group(1) if short_m else ""

            exits = parse_exits(content, dir_id)
            long_desc = parse_long(content)
            outdoors = parse_outdoors(content)

            rooms[rid] = {
                "short": short,
                "area": dir_id.split("/")[-1] if "/" in dir_id else dir_id,
                "exits": exits,
                "long": long_desc,
                "outdoors": outdoors,
            }

            # Parse special verb transitions
            verbs = parse_special_verbs(content, dir_id)
            for verb, dest in verbs:
                if dest:
                    special_edges.append((rid, dest, verb))
                    print(f"  SPECIAL: {rid} --{verb}--> {dest}")

    print(f"\nTotal rooms: {len(rooms)}")
    print(f"Rooms with short name: {sum(1 for v in rooms.values() if v['short'])}")
    print(f"Rooms with exits: {sum(1 for v in rooms.values() if v['exits'])}")
    print(f"Special edges found: {len(special_edges)}")
    for e in special_edges:
        print(f"  {e[0]} --{e[2]}--> {e[1]}")

    # Add special edges to the JSON as a top-level field
    output = {
        "rooms": rooms,
        "special_edges": special_edges,
    }

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=None, separators=(",", ":"))
    print(f"\nWritten to {OUT} ({os.path.getsize(OUT)//1024}KB)")


if __name__ == "__main__":
    main()
