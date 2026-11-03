"""夜の学校から脱出：相談用のAI生成プロトタイプ。"""

from __future__ import annotations

import math
import os
from collections import deque
from dataclasses import dataclass

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


@dataclass
class Guard:
    """マスの中心間を移動する見回り役。発見した相手を短時間追う。"""

    route: list[tuple[int, int]]
    route_index: int = 1
    alert: float = 0.0
    stunned: float = 0.0
    position: pg.Vector2 | None = None
    next_cell: tuple[int, int] | None = None
    last_seen: tuple[int, int] | None = None

    def __post_init__(self) -> None:
        self.position = center(self.route[0])

    def update(self, dt: float, player: pg.Vector2) -> None:
        """視界内なら追跡し、見失ったら巡回へ戻る。"""
        assert self.position is not None
        if self.stunned > 0:
            self.stunned = max(0.0, self.stunned - dt)
            return
        if self.position.distance_to(player) < 185 and visible(self.position, player):
            self.alert = 1.8
            self.last_seen = cell_at(player)
        else:
            self.alert = max(0.0, self.alert - dt)
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
        self.reset()
        self.state = 'title'

    def reset(self) -> None:
        """再挑戦時にもプレイに関わる全状態を初期化する。"""
        self.player = center(START_CELL)
        self.hp = 3
        self.time_left = TIME_LIMIT
        self.invincible = 0.0
        self.stamina = 100.0
        self.sprinting = False
        self.exhausted = False
        self.keys: set[tuple[int, int]] = set()
        self.heal = True
        self.guards = [Guard([(13, 7), (4, 7), (4, 3), (4, 7), (22, 7), (22, 3)]),
                       Guard([(22, 10), (22, 14), (22, 10), (4, 10), (4, 14)])]
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
        elif event.type == pg.WINDOWFOCUSLOST and self.state == 'playing':
            self.state = 'paused'
        elif event.type == pg.MOUSEBUTTONDOWN and event.button == 1:
            if self.button.collidepoint(event.pos):
                if self.state in ('title', 'won', 'lost'):
                    self.reset()
                elif self.state == 'paused':
                    self.state = 'playing'

    def move_player(self, movement: pg.Vector2) -> None:
        """軸ごとに衝突を解決する。大きな移動は小分けにして壁抜けを防ぐ。"""
        steps = max(1, math.ceil(movement.length() / 8))
        movement = movement / steps
        for _ in range(steps):
            for axis in (0, 1):
                self.player[axis] += movement[axis]
                rect = pg.Rect(0, 0, 23, 23)
                rect.center = (round(self.player.x), round(self.player.y))
                for wall in WALLS:
                    if rect.colliderect(wall):
                        if axis == 0:
                            if movement.x > 0:
                                rect.right = wall.left
                            elif movement.x < 0:
                                rect.left = wall.right
                            self.player.x = rect.centerx
                        else:
                            if movement.y > 0:
                                rect.bottom = wall.top
                            elif movement.y < 0:
                                rect.top = wall.bottom
                            self.player.y = rect.centery

    def update(self, dt: float, keys: pg.key.ScancodeWrapper | None = None) -> None:
        """プレイ中だけ時間・移動・取得・接触・勝敗を更新する。"""
        if self.state != 'playing':
            return
        keys = pg.key.get_pressed() if keys is None else keys
        self.time_left = max(0.0, self.time_left - dt)
        self.invincible = max(0.0, self.invincible - dt)
        self.message_time = max(0.0, self.message_time - dt)
        direction = pg.Vector2(int(keys[pg.K_RIGHT] or keys[pg.K_d])
                              - int(keys[pg.K_LEFT] or keys[pg.K_a]),
                              int(keys[pg.K_DOWN] or keys[pg.K_s])
                              - int(keys[pg.K_UP] or keys[pg.K_w]))
        requested = bool(keys[pg.K_LSHIFT] or keys[pg.K_RSHIFT])
        if self.stamina <= 1:
            self.exhausted = True
        elif self.stamina >= 30:
            self.exhausted = False
        self.sprinting = bool(requested and direction.length_squared() and not self.exhausted)
        if self.sprinting:
            self.stamina = max(0.0, self.stamina - 38 * dt)
        else:
            self.stamina = min(100.0, self.stamina + 24 * dt)
        if direction.length_squared():
            self.move_player(direction.normalize() * (245 if self.sprinting else 160) * dt)
        for key in KEY_CELLS:
            if key not in self.keys and self.player.distance_to(center(key)) < 24:
                self.keys.add(key)
                self.say('鍵がそろった！ 下中央の出口へ' if len(self.keys) == 3
                         else f'鍵を見つけた！ あと{3-len(self.keys)}個')
        if self.heal and self.hp < 3 and self.player.distance_to(center((24, 13))) < 25:
            self.hp += 1
            self.heal = False
            self.say('保健室でHPが1回復した')
        for guard in self.guards:
            guard.update(dt, self.player)
            if self.invincible == 0 and self.player.distance_to(guard.position) < 25:
                self.hp -= 1
                self.invincible = 3.0
                guard.stunned = 1.0
                self.say('見つかった！ 点滅している間に逃げよう')
        if self.hp <= 0:
            self.state, self.reason = 'lost', '見回りに捕まってしまった'
        elif self.time_left <= 0:
            self.state, self.reason = 'lost', '時間切れ。校門が閉まってしまった'
        elif self.player.distance_to(center(EXIT_CELL)) < 25:
            if len(self.keys) == 3:
                self.state = 'won'
            else:
                self.say(f'出口は施錠中。あと{3-len(self.keys)}個の鍵が必要')

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
        """部屋・壁・アイテム・キャラクターを描画する。"""
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
        for cell in KEY_CELLS:
            if cell not in self.keys:
                p = center(cell)
                pg.draw.circle(self.screen, (77, 66, 42), p, 17 + int(2 * math.sin(t * 3)))
                self.draw_key(p, GOLD)
        if self.heal:
            p = center((24, 13))
            pg.draw.rect(self.screen, (41, 94, 84), (int(p.x-12), int(p.y-12), 24, 24), border_radius=5)
            pg.draw.line(self.screen, TEAL, (p.x-6, p.y), (p.x+6, p.y), 4)
            pg.draw.line(self.screen, TEAL, (p.x, p.y-6), (p.x, p.y+6), 4)
        p = center(EXIT_CELL)
        unlocked = len(self.keys) == 3
        pg.draw.rect(self.screen, (37, 105, 92) if unlocked else (70, 58, 51),
                     (int(p.x-30), int(p.y-15), 60, 30), border_radius=5)
        self.text('EXIT' if unlocked else 'LOCK', (int(p.x), int(p.y)), 14,
                  TEAL if unlocked else GOLD, True)
        for guard in self.guards:
            p = guard.position
            assert p is not None
            color = RED if guard.alert > 0 else (178, 143, 219)
            pg.draw.circle(self.screen, (10, 17, 28), (int(p.x), int(p.y+5)), 15)
            pg.draw.rect(self.screen, color, (int(p.x-12), int(p.y-12), 24, 24), border_radius=7)
            pg.draw.rect(self.screen, (37, 36, 57), (int(p.x-13), int(p.y-12), 26, 7), border_radius=2)
            pg.draw.circle(self.screen, BG, (int(p.x-4), int(p.y)), 2)
            pg.draw.circle(self.screen, BG, (int(p.x+4), int(p.y)), 2)
            if guard.alert > 0:
                self.text('!', (int(p.x), int(p.y-24)), 20, RED, True)
        if not self.invincible or int(t * 12) % 2 == 0:
            p = self.player
            pg.draw.circle(self.screen, (10, 17, 28), (int(p.x), int(p.y+5)), 15)
            pg.draw.rect(self.screen, GOLD, (int(p.x-11), int(p.y-12), 22, 24), border_radius=8)
            pg.draw.circle(self.screen, BG, (int(p.x-4), int(p.y-3)), 2)
            pg.draw.circle(self.screen, BG, (int(p.x+4), int(p.y-3)), 2)
            pg.draw.rect(self.screen, (212, 139, 72), (int(p.x-8), int(p.y+5), 16, 5), border_radius=2)

    def draw(self) -> None:
        """ゲーム画面と、状態に応じた案内を描画する。"""
        self.screen.fill(BG)
        self.text('NIGHT SCHOOL', (54, 23), 24)
        self.text('夜の学校から脱出', (55, 60), 16, MUTED)
        self.text(f'KEYS  {len(self.keys)} / 3', (400, 28), 24, GOLD)
        self.text('HP', (620, 34), 16, MUTED)
        for i in range(3):
            pg.draw.rect(self.screen, RED if i < self.hp else (55, 46, 57),
                         (658+i*25, 34, 17, 17), border_radius=5)
        seconds = math.ceil(self.time_left)
        self.text(f'{seconds//60:02}:{seconds%60:02}', (884, 20), 32,
                  RED if seconds < 30 else TEXT)
        pg.draw.rect(self.screen, (38, 53, 67), (620, 69, 110, 6), border_radius=3)
        if self.stamina > 0:
            pg.draw.rect(self.screen, TEAL, (620, 69, round(110*self.stamina/100), 6), border_radius=3)
        self.text('DASH', (740, 60), 14, MUTED)
        objective = self.message if self.message_time > 0 else (
            '下中央の出口へ向かおう！' if len(self.keys) == 3 else '鍵を3つ集めて、下中央の出口から脱出')
        self.text(objective, (55, 98), 16, TEAL)
        self.draw_map()
        self.text('移動  WASD / 矢印     ダッシュ  Shift     一時停止  Esc', (54, 762), 16, MUTED)
        self.text('PROTOTYPE / AI生成の試作', (800, 765), 14, MUTED)
        if self.state != 'playing':
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
                lines = [f'脱出時間  {elapsed:.1f}秒', f'残りHP  {self.hp} / 3',
                         '鍵をそろえて、無事に学校を出られた。']
                label = 'もう一度遊ぶ  [R]'
            else:
                self.text('脱出失敗', (540, 278), 42, RED, True)
                lines = [self.reason, f'集めた鍵  {len(self.keys)} / 3',
                         '見回り役の進路を見て、ダッシュで切り抜けよう。']
                label = 'もう一度挑戦  [R]'
            for i, line in enumerate(lines):
                self.text(line, (540, 368+i*34), 18, MUTED, True)
            pg.draw.rect(self.screen, TEAL, self.button, border_radius=12)
            self.text(label, self.button.center, 20, BG, True)
            self.text('終了するにはウィンドウの × を押す', (540, 613), 14, MUTED, True)
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
