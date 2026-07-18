# xyj2000gui — 西游记2000 Graphics Port

Turning the text-based XYJ2000 LPMud (MudOS V22pre11, Annihilator/西游记 mudlib)
into a **水墨画 (ink-wash) 2D graphics game**.

## Plan (Strategy B — port the mudlib to a real engine)

1. **Content extraction (done)** — `extract_xyj.py` parses the 5,637 LPC `.c`
   files into clean JSON the engine loads. No game logic ported yet; this is the
   data foundation.
2. **Single-player prototype** — Godot (GDScript) project renders rooms as ink
   backdrops, NPCs as brush sprites, combat as particle/ink effects. Click-to-move
   along the exit graph. Runs locally, no server.
3. **Web build** — Godot exports to HTML5/WebGL so it runs in a browser.
4. **Multiplayer (later)** — flip on Godot's `MultiplayerAPI` + a small headless
   authoritative server. Same game code, different transport.

## What's extracted

| File | Contents |
|------|----------|
| `data/rooms.json`   | 2,504 rooms: name, desc, exits (nav graph), spawned objects, area |
| `data/npcs.json`    | 1,040 NPCs: str/dex/combat_exp/daoxing/hp pools/skills (41 static-named, 995 dynamic) |
| `data/items.json`   | 114 items: armor/weapon properties |
| `data/graph.json`   | full exit adjacency map (room id → {dir: target id}) |
| `data/manifest.json`| counts + per-area breakdown |

Areas: 蟠桃园, 龙宫, 月宫, 方寸山, 长安, 火焰山, 取经路 (1,337 rooms), etc. (28 total)

## Run the extractor

```bash
python3 extract_xyj.py /path/to/world out
```

The `world/` dir is the mudlib (LPC sources). Handles mixed UTF-8/GBK encoding.

## Notes

- Dynamic NPCs (those built via runtime helpers like `get_honor_str()`) have
  `"dynamic": true` and get a generic ink-sprite placeholder in the prototype.
- The exit graph is the game's level geometry — rooms are nodes, exits are edges.
