"""
config.py — Constants, landmarks, and spawn configuration for XYJ2000 bot.

Server: 146.190.143.182:6666
Character: yxcdrg (大龙)
"""
import os

# ── Connection ─────────────────────────────────────────────────────────
HOST, PORT = "146.190.143.182", 6666
USER, PASS = "honua", "198633"

# ── Paths ──────────────────────────────────────────────────────────────
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
WORLD_DIR = os.path.join(BOT_DIR, "..", "world")
MAP_PATH = os.path.join(BOT_DIR, "xyj2000_map.json")
# Use WORLD_DIR (not realpath) — the symlink target may be on a different machine
FINDMAP_PATH = os.path.join(WORLD_DIR, "adm", "daemons", "find.map")
LOG_PATH = os.path.join(os.environ.get("TEMP", "/tmp"), "xyjbot.log")
MISSION_FILE = os.path.join(os.environ.get("TEMP", "/tmp"), "xyjbot_mission.txt")
TALLY_PATH = os.path.join(BOT_DIR, "kill_tally.txt")

# ── Combat ─────────────────────────────────────────────────────────────
WIMPY = 10           # flee at 10% HP (low enough to commit, high enough to survive)
COMBAT_TIMEOUT = 210  # max seconds in one fight
VICTORY_SIGNS = ("死了", "服了", "投降", "化做一道青光", "原形", "领罪", "走开", "大赦")
DEATH_SIGNS = ("你死了", "你已经死亡", "你在地狱", "你升天了")
COMBAT_SIGNS = ("想杀死你", "正盯着", "缓缓地移动脚步", "寻找进攻")
KO_SIGN = "清醒"
LOSS_SIGN = "承让"
MONSTER_FLEE = ("落荒而逃", "仓皇逃走", "逃跑", "夺路而逃")

# ── Mission ────────────────────────────────────────────────────────────
MISSION_TTL = 1800       # 30 min guai lifetime
STUCK_SECS = 600         # 10 min per sweep
MAX_STEPS_PER_NAV = 200  # max BFS steps before giving up
TARGET_KILLS = int(os.environ.get("XYJ_TARGET", "9999"))

# ── Economy ────────────────────────────────────────────────────────────
KEEP_ON_HAND = 50        # silver to keep on hand
FOOD_THRESHOLD = 100     # eat/drink if below this
WATER_THRESHOLD = 100

# ── Navigation ─────────────────────────────────────────────────────────
STEP_TIMEOUT = 0.7       # seconds to wait after a step
LOOK_TIMEOUT = 1.2       # seconds to wait after look
DRAIN_QUIET = 0.3        # quiet period for drain
MAX_STEPS_NO_PROGRESS = 5 # consecutive failed steps before re-identifying

# ── Region hierarchy ──────────────────────────────────────────────────
# Directory prefix → human-readable region name
# This gives the bot hierarchical spatial awareness:
#   "Am I in 长安? Then '街道' means one of 3 rooms, not 61"
# Regions are ordered coarse→fine: d/ (world) → d/city (city) → d/city/street3 (room)
REGIONS = {
    # ── 长安 area (central hub) ──────────────────────────────────────
    "d/city":       "长安城",
    "d/changan":    "长安郊外",
    "d/westway":    "西行路",
    "d/eastway":    "东行路",
    "d/huanggong":  "皇宫",
    # ── 开封 area ────────────────────────────────────────────────────
    "d/kaifeng":    "开封城",
    # ── 高老庄 area ──────────────────────────────────────────────────
    "d/gao":        "高老庄",
    # ── 东海 / 龙宫 area ─────────────────────────────────────────────
    "d/sea":        "东海龙宫",
    "d/nanhai":     "南海普陀",
    # ── 取经路 (largest region, 2127 rooms) ──────────────────────────
    "d/qujing":     "取经路",
    # ── 其他区域 ──────────────────────────────────────────────────────
    "d/lingtai":    "灵台方寸",
    "d/moon":       "月宫",
    "d/penglai":    "蓬莱仙岛",
    "d/xueshan":    "大雪山",
    "d/meishan":    "梅山",
    "d/death":      "地府",
    "d/ourhome":    "新手村",
    "d/jjf":        "将军府",
    "d/sky":        "天宫",
    "d/cloud":      "云栈洞",
    "d/southern":   "南瞻部洲",
    "d/pantao":     "蟠桃园",
    "d/dntg":       "大闹天宫",
    "d/obj":        "物品",
}

# Region name aliases — Yuan Tiangang sometimes uses different names for the same region
# Maps alternate mission region names → canonical name in find.map
REGION_ALIASES = {
    "灵台方寸":  "方寸山",       # 方寸山's formal name → d/lingtai
    "南海普陀":  "普陀山",       # 普陀山 alias → d/nanhai
    "东海龙宫":  "龙宫",         # 龙宫 alias → d/sea
    "东海":      "龙宫",
    "普陀":      "普陀山",
    # 龙宫 room names used directly as region by Yuan (no separate region field)
    "云房":      "龙宫",         # d/sea/girl4
    "卧龙阁":    "龙宫",         # d/sea/boy3
    "沁玉殿":    "龙宫",         # d/sea/boy1
    "休息室":    "龙宫",         # d/sea/wolongrest (or d/sea nearest match)
}

# Coarse region grouping — which regions are "near 长安" vs "far away"
# Used for sanity checking: if bot was in 长安 and suddenly sees a 开封 room,
# something went wrong (teleport? death? wrong identification?)
REGION_NEIGHBORS = {
    "长安城":   {"长安郊外", "西行路", "东行路", "高老庄", "皇宫", "开封城"},
    "长安郊外": {"长安城", "西行路", "东行路", "东海龙宫", "南海普陀"},
    "西行路":   {"长安城", "长安郊外", "高老庄", "开封城"},
    "东行路":   {"长安城", "长安郊外"},
    "高老庄":   {"长安城", "西行路", "取经路", "长安郊外"},
    # 开封城 is directly reachable from 西行路 (west1 east exit → kaifeng/chengmen)
    "开封城":   {"西行路", "长安城", "取经路"},
    "东海龙宫": {"长安郊外"},
    "南海普陀": {"长安郊外"},
    "取经路":   {"高老庄", "开封城", "大雪山", "梅山"},
    "皇宫":     {"长安城"},
}


def region_of(rid):
    """Get the region directory prefix for a room id.
    e.g. 'd/city/street3' → 'd/city'
    """
    parts = rid.split("/")
    if len(parts) >= 2:
        return "/".join(parts[:2])
    return rid


def region_name_of(rid):
    """Get human-readable region name for a room id.
    e.g. 'd/city/street3' → '长安城'
    """
    return REGIONS.get(region_of(rid), region_of(rid))


# ── Landmarks (source-verified unique room ids) ────────────────────────
LANDMARKS = {
    "hub":    "d/city/center",        # 十字街头
    "yuan":   "d/city/tianjiantai",   # 天监台 (袁天罡)
    "kezhan": "d/city/kezhan",        # 南城客栈 (food/water/sleep)
    "shop":   "d/city/bingqipu",      # 兵器铺 (萧萧)
    "bank":   "d/city/bank",          # 相记钱庄
    "pawn":   "d/city/dangpu",        # 董记当铺 (董朴升)
    "wuguan": "d/city/wuguan",        # 长安武馆 (范芦平)
    "caotang":"d/city/caotang",       # 袁氏草堂 (袁守诚) — NOTE: d/city/yuancao does not exist in map
}

# ── Region → directory mapping (from find.map) ────────────────────────
# Parsed at runtime by map_engine._load_findmap()

# ── Spawn directories (from yaoguai.c dirs1/2/3) ──────────────────────
SPAWN_DIRS = (
    "d/city", "d/westway", "d/kaifeng", "d/lingtai", "d/moon", "d/gao",
    "d/sea", "d/nanhai", "d/eastway", "d/ourhome/honglou",
    "d/xueshan", "d/qujing", "d/penglai", "d/death", "d/meishan",
    "d/huanggong",  # 皇宫 — reachable from hub in ~4 steps via 长安城
)

# Dirs reachable on foot (plus d/sea via dive for 龙宫 members)
ACCESSIBLE_DIRS = (
    "d/city", "d/changan",           # core hub + outskirts (always navigable transit)
    "d/westway", "d/kaifeng", "d/lingtai", "d/gao", "d/eastway",
    "d/sea",    # 龙宫 — accessible with 避水咒 (dive from 东海之滨); avoid maze via KNOWN_UNREACHABLE
    "d/nanhai", # 普陀山 — accessible via swim from 南海之滨 (costs 20hp/sp)
    "d/huanggong",  # 皇宫 (Imperial Palace) — 4-step walk from hub, confirmed reachable
    "d/ourhome/honglou",  # 红楼一梦 — accessible via 黄粱枕 sleep mechanic (special entry)
)

# ── Special edges (verb-based transitions) ────────────────────────────
# (from_room, to_room, command) — parsed from LPC add_action + move() calls
SPECIAL_EDGES = [
    # dive: 东海之滨 → 海底 (龙宫 members can dive without 避水咒)
    ("d/changan/eastseashore", "d/sea/under1", "dive"),
    # swim: 南海之滨 ↔ 小岛 (普陀山 access)
    ("d/changan/southseashore", "d/nanhai/island", "swim"),
    ("d/nanhai/island", "d/changan/southseashore", "swim"),
]

# ── Direction reverse mapping ──────────────────────────────────────────
REVERSE = {
    "north": "south", "south": "north", "east": "west", "west": "east",
    "up": "down", "down": "up", "enter": "out", "out": "enter",
    "northeast": "southwest", "southwest": "northeast",
    "northwest": "southeast", "southeast": "northwest",
    "northup": "southdown", "southdown": "northup",
    "eastup": "westdown", "westdown": "eastup",
    "westup": "eastdown", "eastdown": "westup",
    "northdown": "southup", "southup": "northdown",
}

# Valid exit direction tokens
EXIT_TOKENS = {
    "northeast", "northwest", "southeast", "southwest",
    "eastup", "westdown", "northup", "southdown",
    "westup", "eastdown", "northdown", "southup",
    "north", "south", "east", "west", "up", "down", "enter", "out",
}

# ── Move failure indicators ────────────────────────────────────────────
MOVE_FAIL = ("方向没有", "不能往", "没有出口", "无法往", "那个方向",
             "没有路", "走不通", "这个方向", "不能到")

# Door-closed indicators — treat like MOVE_FAIL but try opening first
DOOR_CLOSED_MSGS = ("关着呢", "关着", "挡住了", "必须要先打开", 
                     "必须先打开", "有门", "门关", "紧闭")

# ── Food/water ────────────────────────────────────────────────────────
FULL_MSGS = ("饱了", "不想喝", "喝不下", "吃不下", "喝太多", "灌不下", "吃太多")
EMPTY_MSGS = ("一滴也不剩", "一滴不剩", "一点也不剩", "没有", "什么", "不懂", "干干净净")

# ── Chinese direction → English ───────────────────────────────────────
CN_DIR = {
    "东北": "northeast", "西北": "northwest", "东南": "southeast", "西南": "southwest",
    "东": "east", "西": "west", "南": "south", "北": "north",
    "上": "up", "下": "down",
}

# ── Ourhome escape ─────────────────────────────────────────────────────
OURHOME_PREFIX = "d/ourhome/"

# ── Dangerous areas (skip missions here if unprepared) ─────────────────
DANGEROUS_DIRS = ("d/westway", "d/qujing")
