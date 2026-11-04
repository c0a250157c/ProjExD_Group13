from __future__ import annotations

import math
import os
from collections import deque

import pygame as pg

os.chdir(os.path.dirname(os.path.abspath(__file__)))

WIDTH, HEIGHT = 1080, 800
TILE = 36
COLS, ROWS = 27, 17
ORIGIN = pg.Vector2(54, 132)
TIME_LIMIT = 120.0
BG = (12, 19, 31)
TEXT = (230, 239, 246)
MUTED = (143, 166, 187)
TEAL = (101, 225, 199)
GOLD = (255, 205, 105)
RED = (255, 116, 125)
KEY_CELLS = [(22, 3), (4, 14), (22, 14)]
EXIT_CELL = (13, 15)
START_CELL = (4, 3)
HEAL_CELL = (24, 13)
MAX_HP = 3
MAX_STAMINA = 100.0
PLAYER_SPEED = 160
DASH_SPEED = 245
STAMINA_COST = 38
STAMINA_RECOVERY = 24
DASH_RECOVERY_THRESHOLD = 30
INVINCIBLE_TIME = 3.0
GUARD_STUN_TIME = 1.0
GUARD_ROUTES = [
    [(13, 7), (4, 7), (4, 3), (4, 7), (22, 7), (22, 3)],
    [(22, 10), (22, 14), (22, 10), (4, 10), (4, 14)],
]
# 隠れる・足音（メンバーA）
HIDING_SPOTS = [(7, 2), (16, 3), (25, 3), (7, 13), (16, 14), (25, 15)]  # 隠れ場所のマス
HIDE_RANGE = 24  # 隠れ場所からこの距離(px)以内なら隠れられる
NOISE_RADIUS = 240  # ダッシュの足音が聞こえる距離(px)
NOISE_INTERVAL = 0.35  # 足音を出す間隔(秒)
STEP_SOUND = "sound/boom.wav"  # 足音に使う効果音（授業のex1の音）
STEP_SOUND_MS = 150  # 足音を鳴らす長さ(ミリ秒)


def make_map() -> list[list[int]]:
    """1を壁、0を通行可能な床とする固定マップを作る。"""
    grid = [[int(x in (0, COLS - 1) or y in (0, ROWS - 1))
             for x in range(COLS)] for y in range(ROWS)]
    for y in (5, 11):
        for x in range(1, COLS - 1):
            grid[y][x] = int(x not in (4, 13, 22))
    for x in (9, 18):
        for y in list(range(1, 5)) + list(range(12, 16)):
            grid[y][x] = 1
    for x in (8, 18):
        grid[8][x] = 1
        grid[9][x] = 1
    return grid


GRID = make_map()


def center(cell: tuple[int, int]) -> pg.Vector2:
    """マス目を画面上の中心座標へ変換する。"""
    return ORIGIN + pg.Vector2((cell[0] + 0.5) * TILE, (cell[1] + 0.5) * TILE)


def cell_at(position: pg.Vector2) -> tuple[int, int]:
    """画面上の位置をマス目へ変換する。"""
    local = (position - ORIGIN) / TILE
    return math.floor(local.x), math.floor(local.y)


def walkable(cell: tuple[int, int]) -> bool:
    """マップの範囲内で、壁でないかを判定する。"""
    x, y = cell
    return 0 <= x < COLS and 0 <= y < ROWS and GRID[y][x] == 0


def find_path(start: tuple[int, int], goal: tuple[int, int]) -> list[tuple[int, int]]:
    """幅優先探索で、壁を通らない最短経路を返す。開始マスは含まない。"""
    if not walkable(start) or not walkable(goal):
        return []
    queue = deque([start])
    previous: dict[tuple[int, int], tuple[int, int] | None] = {start: None}
    while queue:
        node = queue.popleft()
        if node == goal:
            path = []
            while node != start:
                path.append(node)
                node = previous[node]  # type: ignore[assignment]
            return list(reversed(path))
        x, y = node
        for nxt in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if walkable(nxt) and nxt not in previous:
                previous[nxt] = node
                queue.append(nxt)
    return []


def visible(a: pg.Vector2, b: pg.Vector2) -> bool:
    """2点間に壁がないかを細かくサンプリングする。"""
    steps = max(1, math.ceil(a.distance_to(b) / 8))
    return all(walkable(cell_at(a.lerp(b, i / steps))) for i in range(steps + 1))


WALLS = [pg.Rect(int(ORIGIN.x + x * TILE), int(ORIGIN.y + y * TILE), TILE, TILE)
         for y in range(ROWS) for x in range(COLS) if GRID[y][x]]


class Player:
    """プレイヤーの移動、ダッシュ、HP、被弾後の無敵時間を管理する。"""

    def __init__(self, cell: tuple[int, int]) -> None:
        self.position = center(cell)
        self.rect = pg.Rect(0, 0, 23, 23)
        self.rect.center = (round(self.position.x), round(self.position.y))
        self.hp = MAX_HP
        self.invincible = 0.0
        self.stamina = MAX_STAMINA
        self.sprinting = False
        self.exhausted = False
        self.hidden = False  # 隠れている間はTrue
        self.noise = None  # 今フレームに出た足音（x, y, 半径）。出ていなければNone
        self.noise_cooldown = 0.0

    def toggle_hide(self) -> None:
        """Eキー：隠れ場所の近くなら隠れる。すでに隠れていれば出る。"""
        if self.hidden:
            self.hidden = False
        elif any(self.position.distance_to(center(cell)) <= HIDE_RANGE for cell in HIDING_SPOTS):
            self.hidden = True

    def move(self, movement: pg.Vector2) -> None:
        """軸ごとに衝突を解決する。大きな移動は小分けにして壁抜けを防ぐ。"""
        steps = max(1, math.ceil(movement.length() / 8))
        movement = movement / steps
        for _ in range(steps):
            for axis in (0, 1):
                self.position[axis] += movement[axis]
                rect = self.rect
                rect.center = (round(self.position.x), round(self.position.y))
                for wall in WALLS:
                    if rect.colliderect(wall):
                        if axis == 0:
                            if movement.x > 0:
                                rect.right = wall.left
                            elif movement.x < 0:
                                rect.left = wall.right
                            self.position.x = rect.centerx
                        else:
                            if movement.y > 0:
                                rect.bottom = wall.top
                            elif movement.y < 0:
                                rect.top = wall.bottom
                            self.position.y = rect.centery

    def update(self, dt: float, keys: pg.key.ScancodeWrapper) -> None:
        """入力に応じて移動し、スタミナと無敵時間を更新する。"""
        self.invincible = max(0.0, self.invincible - dt)
        self.noise = None
        self.noise_cooldown = max(0.0, self.noise_cooldown - dt)
        if self.hidden:  # 隠れている間は動けず、ダッシュも足音もなし
            self.sprinting = False
            self.stamina = min(MAX_STAMINA, self.stamina + STAMINA_RECOVERY * dt)
            return
        direction = pg.Vector2(int(keys[pg.K_RIGHT] or keys[pg.K_d])
                              - int(keys[pg.K_LEFT] or keys[pg.K_a]),
                              int(keys[pg.K_DOWN] or keys[pg.K_s])
                              - int(keys[pg.K_UP] or keys[pg.K_w]))
        requested = bool(keys[pg.K_LSHIFT] or keys[pg.K_RSHIFT])
        if self.stamina <= 1:
            self.exhausted = True
        elif self.stamina >= DASH_RECOVERY_THRESHOLD:
            self.exhausted = False
        self.sprinting = bool(requested and direction.length_squared() and not self.exhausted)
        if self.sprinting:
            self.stamina = max(0.0, self.stamina - STAMINA_COST * dt)
        else:
            self.stamina = min(MAX_STAMINA, self.stamina + STAMINA_RECOVERY * dt)
        before = self.position.copy()
        if direction.length_squared():
            self.move(direction.normalize() * (DASH_SPEED if self.sprinting else PLAYER_SPEED) * dt)
        if self.sprinting and self.position != before and self.noise_cooldown == 0.0:
            self.noise = (self.position.x, self.position.y, NOISE_RADIUS)  # ダッシュで実際に動いたときだけ
            self.noise_cooldown = NOISE_INTERVAL

    def take_damage(self) -> bool:
        """無敵中でなければHPを減らし、被弾したかを返す。"""
        if self.invincible > 0:
            return False
        self.hp -= 1
        self.invincible = INVINCIBLE_TIME
        return True

    def recover(self) -> bool:
        """HPが満タンでなければ1回復する。"""
        if self.hp >= MAX_HP:
            return False
        self.hp += 1
        return True

    def draw(self, screen: pg.Surface) -> None:
        """無敵中は点滅させて描画する。"""
        if self.hidden:
            p = self.position
            pg.draw.rect(screen, TEAL, (int(p.x-11), int(p.y-12), 22, 24), 2, border_radius=8)
            return
        t = pg.time.get_ticks() / 1000
        if not self.invincible or int(t * 12) % 2 == 0:
            p = self.position
            pg.draw.circle(screen, (10, 17, 28), (int(p.x), int(p.y+5)), 15)
            pg.draw.rect(screen, GOLD, (int(p.x-11), int(p.y-12), 22, 24), border_radius=8)
            pg.draw.circle(screen, BG, (int(p.x-4), int(p.y-3)), 2)
            pg.draw.circle(screen, BG, (int(p.x+4), int(p.y-3)), 2)
            pg.draw.rect(screen, (212, 139, 72), (int(p.x-8), int(p.y+5), 16, 5), border_radius=2)


class Guard:
    """マスの中心間を巡回し、発見したプレイヤーを追跡する。"""

    def __init__(self, route: list[tuple[int, int]]) -> None:
        self.route = route
        self.route_index = 1
        self.alert = 0.0
        self.stunned = 0.0
        self.position = center(route[0])
        self.next_cell: tuple[int, int] | None = None
        self.last_seen: tuple[int, int] | None = None

    def update(self, dt: float, player: pg.Vector2, hidden: bool = False, noise=None) -> None:
        """視界内なら追跡し、見失ったら巡回へ戻る。隠れているプレイヤーは見えない。足音が聞こえたら音の場所へ向かう。"""
        if self.stunned > 0:
            self.stunned = max(0.0, self.stunned - dt)
            return
        if not hidden and self.position.distance_to(player) < 185 and visible(self.position, player):
            self.alert = 1.8
            self.last_seen = cell_at(player)
        else:
            self.alert = max(0.0, self.alert - dt)
        if noise and self.position.distance_to((noise[0], noise[1])) <= noise[2]:  # 足音の輪の中にいたら
            self.alert = 1.8
            self.last_seen = cell_at(pg.Vector2(noise[0], noise[1]))
        # 進行中のマスへ到達してから経路を選び直し、角の壁抜けを防ぐ。
        if self.next_cell is None:
            current = cell_at(self.position)
            if self.alert > 0 and self.last_seen is not None:
                goal = self.last_seen
            else:
                goal = self.route[self.route_index]
                if current == goal:
                    self.route_index = (self.route_index + 1) % len(self.route)
                    goal = self.route[self.route_index]
            path = find_path(current, goal)
            if path:
                self.next_cell = path[0]
        if self.next_cell is not None:
            target = center(self.next_cell)
            delta = target - self.position
            distance = delta.length()
            step = (132 if self.alert > 0 else 88) * dt
            if distance <= step:
                self.position = target
                self.next_cell = None
            elif distance:
                self.position += delta / distance * step

    def draw(self, screen: pg.Surface, font: pg.font.Font) -> None:
        """追跡中は赤色と感嘆符で表示する。"""
        p = self.position
        color = RED if self.alert > 0 else (178, 143, 219)
        pg.draw.circle(screen, (10, 17, 28), (int(p.x), int(p.y+5)), 15)
        pg.draw.rect(screen, color, (int(p.x-12), int(p.y-12), 24, 24), border_radius=7)
        pg.draw.rect(screen, (37, 36, 57), (int(p.x-13), int(p.y-12), 26, 7), border_radius=2)
        pg.draw.circle(screen, BG, (int(p.x-4), int(p.y)), 2)
        pg.draw.circle(screen, BG, (int(p.x+4), int(p.y)), 2)
        if self.alert > 0:
            image = font.render('!', True, RED)
            screen.blit(image, image.get_rect(center=(int(p.x), int(p.y-24))))


class Game:
    """タイトル・プレイ・一時停止・結果を含むゲーム本体。"""

    def __init__(self) -> None:
        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        pg.display.set_caption("学校脱出 / NIGHT SCHOOL - prototype")
        self.clock = pg.time.Clock()
        self.fonts = {size: pg.font.SysFont('meiryo', size, bold=(size >= 24))
                      for size in (14, 16, 18, 20, 24, 32, 42)}
        self.button = pg.Rect(380, 534, 320, 58)
        self.alive = True
        try:
            pg.mixer.init()
            self.step_sound = pg.mixer.Sound(STEP_SOUND)  # 授業のsound_sample.pyと同じ読み込み方
        except (pg.error, FileNotFoundError):
            self.step_sound = None  # 音のファイルや音の出力先がなくても動く
        self.reset()
        self.state = 'title'

    def reset(self) -> None:
        """再挑戦時にもプレイに関わる全状態を初期化する。"""
        self.player = Player(START_CELL)
        self.noise_rings: list[list] = []  # 足音の輪 [(x, y, 半径), 残り時間]
        self.time_left = TIME_LIMIT
        self.keys: set[tuple[int, int]] = set()
        self.heal = True
        self.guards = [Guard(route) for route in GUARD_ROUTES]
        self.state = 'playing'
        self.message = '教室を探索して、3つの鍵を集めよう'
        self.message_time = 4.0
        self.reason = ''

    def say(self, message: str) -> None:
        """一時的な案内を表示する。"""
        self.message = message
        self.message_time = 2.8

    def handle_event(self, event: pg.event.Event) -> None:
        """各画面で有効な操作を処理する。"""
        if event.type == pg.QUIT:
            self.alive = False
        elif event.type == pg.KEYDOWN:
            if event.key == pg.K_ESCAPE:
                if self.state == 'playing':
                    self.state = 'paused'
                elif self.state == 'paused':
                    self.state = 'playing'
                else:
                    self.alive = False
            elif event.key in (pg.K_RETURN, pg.K_SPACE) and self.state == 'title':
                self.reset()
            elif event.key in (pg.K_r, pg.K_RETURN) and self.state in ('won', 'lost'):
                self.reset()
            elif event.key == pg.K_RETURN and self.state == 'paused':
                self.state = 'playing'
            elif event.key == pg.K_e and self.state == 'playing':
                self.player.toggle_hide()
        elif event.type == pg.WINDOWFOCUSLOST and self.state == 'playing':
            self.state = 'paused'
        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if self.button.collidepoint(event.pos):
                if self.state in ('title', 'won', 'lost'):
                    self.reset()
                elif self.state == 'paused':
                    self.state = 'playing'

    def update(self, dt: float, keys: pg.key.ScancodeWrapper | None = None) -> None:
        """プレイ中だけ時間・移動・取得・接触・勝敗を更新する。"""
        if self.state != 'playing':
            return
        keys = pg.key.get_pressed() if keys is None else keys
        self.time_left = max(0.0, self.time_left - dt)
        self.message_time = max(0.0, self.message_time - dt)
        self.player.update(dt, keys)
        if self.player.noise:
            self.noise_rings.append([self.player.noise, 0.5])
            if self.step_sound:
                self.step_sound.play(maxtime=STEP_SOUND_MS)  # 足音を鳴らす
        for ring in self.noise_rings:
            ring[1] -= dt
        self.noise_rings = [ring for ring in self.noise_rings if ring[1] > 0]
        self.collect_items()
        self.update_guards(dt)
        self.check_result()

    def collect_items(self) -> None:
        """鍵と、一度だけ使える回復アイテムの取得を処理する。隠れている間は取得しない。"""
        if self.player.hidden:
            return
        for key in KEY_CELLS:
            if key not in self.keys and self.player.position.distance_to(center(key)) < 24:
                self.keys.add(key)
                self.say('鍵がそろった！ 下中央の出口へ' if len(self.keys) == len(KEY_CELLS)
                         else f'鍵を見つけた！ あと{len(KEY_CELLS)-len(self.keys)}個')
        if (self.heal and self.player.position.distance_to(center(HEAL_CELL)) < 25
                and self.player.recover()):
            self.heal = False
            self.say('保健室でHPが1回復した')

    def update_guards(self, dt: float) -> None:
        """見回り役を移動させ、プレイヤーとの接触を処理する。"""
        for guard in self.guards:
            guard.update(dt, self.player.position, self.player.hidden, self.player.noise)
            if (not self.player.hidden and self.player.position.distance_to(guard.position) < 25
                    and self.player.take_damage()):
                guard.stunned = GUARD_STUN_TIME
                self.say('見つかった！ 点滅している間に逃げよう')

    def check_result(self) -> None:
        """HP、残り時間、出口への到達から勝敗を判定する。"""
        if self.player.hp <= 0:
            self.state, self.reason = 'lost', '見回りに捕まってしまった'
        elif self.time_left <= 0:
            self.state, self.reason = 'lost', '時間切れ。校門が閉まってしまった'
        elif self.player.position.distance_to(center(EXIT_CELL)) < 25:
            if len(self.keys) == len(KEY_CELLS):
                self.state = 'won'
            else:
                self.say(f'出口は施錠中。あと{len(KEY_CELLS)-len(self.keys)}個の鍵が必要')

    def text(self, value: str, position: tuple[int, int], size: int = 18,
             color: tuple[int, int, int] = TEXT, centered: bool = False) -> None:
        """指定の位置へ文字を描画する。"""
        surface = self.fonts[size].render(value, True, color)
        rect = surface.get_rect(center=position) if centered else surface.get_rect(topleft=position)
        self.screen.blit(surface, rect)

    def draw_key(self, position: pg.Vector2, color: tuple[int, int, int]) -> None:
        """画像に依存せず鍵のアイコンを描画する。"""
        x, y = round(position.x), round(position.y)
        pg.draw.circle(self.screen, color, (x - 5, y - 3), 7, 3)
        pg.draw.line(self.screen, color, (x, y + 1), (x + 10, y + 11), 4)
        pg.draw.line(self.screen, color, (x + 8, y + 8), (x + 12, y + 4), 3)

    def draw_map(self) -> None:
        """部屋・壁・アイテム・出口を描画する。"""
        t = pg.time.get_ticks() / 1000
        for y, row in enumerate(GRID):
            for x, wall in enumerate(row):
                rect = pg.Rect(int(ORIGIN.x + x * TILE), int(ORIGIN.y + y * TILE), TILE, TILE)
                if wall:
                    pg.draw.rect(self.screen, (49, 65, 83), rect)
                    pg.draw.line(self.screen, (66, 83, 99), rect.topleft, rect.topright, 2)
                    pg.draw.line(self.screen, (24, 34, 48), rect.bottomleft, rect.bottomright, 3)
                else:
                    col = (24, 38, 52) if 6 <= y <= 10 else (29, 44, 57)
                    pg.draw.rect(self.screen, col, rect)
                    pg.draw.rect(self.screen, (35, 50, 64), rect, 1)
        for label, cell in [('教室 A', (4, 1)), ('職員室', (13, 1)), ('理科室', (22, 1)),
                            ('図書室', (4, 12)), ('玄関', (13, 12)), ('保健室', (22, 12))]:
            p = center(cell)
            self.text(label, (int(p.x), int(p.y)), 16, MUTED, True)
        # 家具は見た目の補助。壁以外は通行可能にしてルールを単純にする。
        for cell in [(2, 2), (6, 2), (11, 2), (15, 2), (20, 2), (24, 2)]:
            p = center(cell)
            pg.draw.rect(self.screen, (54, 73, 85), (int(p.x-12), int(p.y-8), 24, 16), border_radius=3)
        for cell in HIDING_SPOTS:
            p = center(cell)
            pg.draw.rect(self.screen, (40, 58, 74), (int(p.x-13), int(p.y-15), 26, 30), border_radius=3)
            pg.draw.rect(self.screen, MUTED, (int(p.x-13), int(p.y-15), 26, 30), 2, border_radius=3)
        for cell in KEY_CELLS:
            if cell not in self.keys:
                p = center(cell)
                pg.draw.circle(self.screen, (77, 66, 42), p, 17 + int(2 * math.sin(t * 3)))
                self.draw_key(p, GOLD)
        if self.heal:
            p = center(HEAL_CELL)
            pg.draw.rect(self.screen, (41, 94, 84), (int(p.x-12), int(p.y-12), 24, 24), border_radius=5)
            pg.draw.line(self.screen, TEAL, (p.x-6, p.y), (p.x+6, p.y), 4)
            pg.draw.line(self.screen, TEAL, (p.x, p.y-6), (p.x, p.y+6), 4)
        p = center(EXIT_CELL)
        unlocked = len(self.keys) == len(KEY_CELLS)
        pg.draw.rect(self.screen, (37, 105, 92) if unlocked else (70, 58, 51),
                     (int(p.x-30), int(p.y-15), 60, 30), border_radius=5)
        self.text('EXIT' if unlocked else 'LOCK', (int(p.x), int(p.y)), 14,
                  TEAL if unlocked else GOLD, True)

    def draw_hud(self) -> None:
        """鍵、HP、残り時間、スタミナを表示する。"""
        self.text('NIGHT SCHOOL', (54, 23), 24)
        self.text('夜の学校から脱出', (55, 60), 16, MUTED)
        self.text(f'KEYS  {len(self.keys)} / {len(KEY_CELLS)}', (400, 28), 24, GOLD)
        self.text('HP', (620, 34), 16, MUTED)
        for i in range(MAX_HP):
            pg.draw.rect(self.screen, RED if i < self.player.hp else (55, 46, 57),
                         (658+i*25, 34, 17, 17), border_radius=5)
        seconds = math.ceil(self.time_left)
        self.text(f'{seconds//60:02}:{seconds%60:02}', (884, 20), 32,
                  RED if seconds < 30 else TEXT)
        pg.draw.rect(self.screen, (38, 53, 67), (620, 69, 110, 6), border_radius=3)
        if self.player.stamina > 0:
            pg.draw.rect(self.screen, TEAL, (620, 69, round(110*self.player.stamina/MAX_STAMINA), 6), border_radius=3)
        self.text('DASH', (740, 60), 14, MUTED)
        objective = self.message if self.message_time > 0 else (
            '下中央の出口へ向かおう！' if len(self.keys) == len(KEY_CELLS) else '鍵を3つ集めて、下中央の出口から脱出')
        self.text(objective, (55, 98), 16, TEAL)

    def draw_overlay(self) -> None:
        """タイトル、一時停止、結果画面を重ねて表示する。"""
        shade = pg.Surface((WIDTH, HEIGHT), pg.SRCALPHA)
        shade.fill((5, 11, 20, 195))
        self.screen.blit(shade, (0, 0))
        panel = pg.Rect(220, 180, 640, 465)
        pg.draw.rect(self.screen, (22, 35, 51), panel, border_radius=22)
        pg.draw.rect(self.screen, (68, 94, 112), panel, 1, border_radius=22)
        if self.state == 'title':
            self.text('放課後、最後のチャイム。', (540, 228), 18, TEAL, True)
            self.text('夜の学校から脱出', (540, 295), 42, TEXT, True)
            lines = ['3つの鍵を集めて、下中央の出口を開こう。',
                     '紫の見回り役は、近づくと赤くなって追ってくる。',
                     'Shiftでダッシュ。保健室の＋でHPを1回復。',
                     '制限時間は120秒。捕まるとHPが1減る。']
            label = '探索を始める  [Enter]'
        elif self.state == 'paused':
            self.text('PAUSED', (540, 270), 42, TEAL, True)
            lines = ['一時停止中です。残り時間は減りません。',
                     'WASD / 矢印：移動　　Shift：ダッシュ',
                     '鍵を3つ集めて、下中央の出口へ。']
            label = '探索に戻る  [Esc]'
        elif self.state == 'won':
            self.text('脱出成功！', (540, 278), 42, TEAL, True)
            elapsed = TIME_LIMIT - self.time_left
            lines = [f'脱出時間  {elapsed:.1f}秒', f'残りHP  {self.player.hp} / {MAX_HP}',
                     '鍵をそろえて、無事に学校を出られた。']
            label = 'もう一度遊ぶ  [R]'
        else:
            self.text('脱出失敗', (540, 278), 42, RED, True)
            lines = [self.reason, f'集めた鍵  {len(self.keys)} / {len(KEY_CELLS)}',
                     '見回り役の進路を見て、ダッシュで切り抜けよう。']
            label = 'もう一度挑戦  [R]'
        for i, line in enumerate(lines):
            self.text(line, (540, 368+i*34), 18, MUTED, True)
        pg.draw.rect(self.screen, TEAL, self.button, border_radius=12)
        self.text(label, self.button.center, 20, BG, True)
        self.text('終了するにはウィンドウの × を押す', (540, 613), 14, MUTED, True)

    def draw(self) -> None:
        """背景、キャラクター、案内を順に描画する。"""
        self.screen.fill(BG)
        self.draw_hud()
        self.draw_map()
        for guard in self.guards:
            guard.draw(self.screen, self.fonts[20])
        for (x, y, radius), life in self.noise_rings:
            pg.draw.circle(self.screen, GOLD, (int(x), int(y)), int(radius * (1 - life / 0.5)) + 10, 1)
        self.player.draw(self.screen)
        self.text('移動  WASD / 矢印   ダッシュ  Shift   隠れる・出る  E   一時停止  Esc', (54, 762), 16, MUTED)
        self.text('PROTOTYPE / AI生成の試作', (800, 765), 14, MUTED)
        if self.state != 'playing':
            self.draw_overlay()
        pg.display.flip()

    def run(self) -> None:
        """毎秒60回を目安に入力・更新・描画する。"""
        while self.alive:
            dt = min(self.clock.tick(60)/1000, 0.05)
            for event in pg.event.get():
                self.handle_event(event)
            if not self.alive:
                break
            self.update(dt)
            self.draw()


def main() -> None:
    """Pygameを初期化して起動し、終了処理を保証する。"""
    pg.init()
    try:
        Game().run()
    finally:
        pg.quit()


if __name__ == '__main__':
    main()
