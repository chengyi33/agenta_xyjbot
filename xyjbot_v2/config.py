"""
config.py — Constants, landmarks, and spawn configuration for XYJ2000 bot.

Server: 146.190.143.182:6666
Character: yxcdrg (大龙)
"""
import os

# ── Connection ─────────────────────────────────────────────────────────
HOST, PORT = "146.190.143.182", 6666
USER, PASS = "yxcdrg", "198633"

# ── Paths ──────────────────────────────────────────────────────────────
BOT_DIR = os.path.dirname(os.path.abspath(__file__))
WORLD_DIR = os.path.join(BOT_DIR, "..", "world")
MAP_PATH = os.path.join(BOT_DIR, "xyj2000_map.json")
FINDMAP_PATH = os.path.realpath(os.path.join(BOT_DIR, "world", "adm", "daemons", "find.map"))
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
TARGET_KILLS = int(os.environ.get("XYJ_TARGET", "5"))

# ── Economy ────────────────────────────────────────────────────────────
KEEP_ON_HAND = 50        # silver to keep on hand
FOOD_THRESHOLD = 100     # eat/drink if below this
WATER_THRESHOLD = 100

# ── Navigation ─────────────────────────────────────────────────────────
STEP_TIMEOUT = 0.7       # seconds to wait after a step
LOOK_TIMEOUT = 1.2       # seconds to wait after look
DRAIN_QUIET = 0.3        # quiet period for drain
MAX_STEPS_NO_PROGRESS = 5 # consecutive failed steps before re-identifying

# ── Landmarks (source-verified unique room ids) ────────────────────────
LANDMARKS = {
    "hub":    "d/city/center",        # 十字街头
    "yuan":   "d/city/tianjiantai",   # 天监台 (袁天罡)
    "kezhan": "d/city/kezhan",        # 南城客栈 (food/water/sleep)
    "shop":   "d/city/bingqipu",      # 兵器铺 (萧萧)
    "bank":   "d/city/bank",          # 相记钱庄
    "pawn":   "d/city/dangpu",        # 董记当铺 (董朴升)
    "wuguan": "d/city/wuguan",        # 长安武馆 (范芦平)
    "caotang":"d/city/yuancao",       # 袁氏草堂 (袁守诚)
}

# ── Region → directory mapping (from find.map) ────────────────────────
# Parsed at runtime by map_engine._load_findmap()

# ── Spawn directories (from yaoguai.c dirs1/2/3) ──────────────────────
SPAWN_DIRS = (
    "d/city", "d/westway", "d/kaifeng", "d/lingtai", "d/moon", "d/gao",
    "d/sea", "d/nanhai", "d/eastway", "d/ourhome/honglou",
    "d/xueshan", "d/qujing", "d/penglai", "d/death", "d/meishan",
)

# Dirs reachable on foot (plus d/sea via dive for 龙宫 members)
ACCESSIBLE_DIRS = (
    "d/city", "d/westway", "d/kaifeng", "d/lingtai", "d/gao", "d/eastway",
    "d/sea", "d/nanhai",
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

# ── Food/water ────────────────────────────────────────────────────────
FULL_MSGS = ("饱了", "不想喝", "喝不下", "吃不下", "喝太多", "灌不下", "吃太多")
EMPTY_MSGS = ("一滴也不剩", "一点也不剩", "没有", "什么", "不懂", "干干净净")

# ── Chinese direction → English ───────────────────────────────────────
CN_DIR = {
    "东北": "northeast", "西北": "northwest", "东南": "southeast", "西南": "southwest",
    "东": "east", "西": "west", "南": "south", "北": "north",
    "上": "up", "下": "down",
}

# ── Ourhome escape ─────────────────────────────────────────────────────
OURHOME_PREFIX = "d/ourhome/"
