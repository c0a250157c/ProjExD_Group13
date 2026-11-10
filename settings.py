"""画面とゲーム調整に使う共通設定。"""
import pygame as pg

WIDTH, HEIGHT = 1080, 800
TILE = 36
COLS, ROWS = 27, 17
ORIGIN = pg.Vector2(54, 132)
FONT_NAMES = 'meiryo,yugothic,hiraginosans,ヒラキノ角コシックw3,notosanscjkjp,notosansjp'
TIME_LIMIT = 120.0
BG = (12, 19, 31)
TEXT = (230, 239, 246)
MUTED = (143, 166, 187)
TEAL = (101, 225, 199)
GOLD = (255, 205, 105)
RED = (255, 116, 125)
MAX_HP = 3
MAX_STAMINA = 100.0
PLAYER_SPEED = 160
DASH_SPEED = 245
STAMINA_COST = 38
STAMINA_RECOVERY = 24
DASH_RECOVERY_THRESHOLD = 30
INVINCIBLE_TIME = 3.0
GUARD_STUN_TIME = 1.0

# 隠れる・足音（メンバーA）
HIDE_RANGE = 24  # 隠れ場所からこの距離(px)以内なら隠れられる
NOISE_RADIUS = 240  # ダッシュの足音が聞こえる距離(px)
NOISE_INTERVAL = 0.35  # 足音を出す間隔(秒)
STEP_SOUND = "sound/boom.wav"  # 足音に使う効果音（授業のex1の音）
STEP_SOUND_MS = 150  # 足音を鳴らす長さ(ミリ秒)
