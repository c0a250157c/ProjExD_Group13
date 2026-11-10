from __future__ import annotations

import math
import os

import pygame as pg

from contracts import Cell, NoiseEvent
from settings import (
    WIDTH, HEIGHT, TIME_LIMIT, BG, TEXT, MUTED, TEAL, GOLD, RED, FONT_NAMES,
    MAX_HP, MAX_STAMINA, PLAYER_SPEED, DASH_SPEED, STAMINA_COST,
    STAMINA_RECOVERY, DASH_RECOVERY_THRESHOLD, INVINCIBLE_TIME, GUARD_STUN_TIME,
)
from stages import STAGES
from world import World, validate_stage

os.chdir(os.path.dirname(os.path.abspath(__file__)))


class Player:
    """プレイヤーの移動、ダッシュ、HP、被弾後の無敵時間を管理する。"""

    def __init__(self, cell: Cell, world: World) -> None:
        self.position = world.center(cell)
        self.rect = pg.Rect(0, 0, 23, 23)
        self.rect.center = (round(self.position.x), round(self.position.y))
        self.hp = MAX_HP
        self.hidden = False
        self.invincible = 0.0
        self.stamina = MAX_STAMINA
        self.sprinting = False
        self.exhausted = False

    def move(self, movement: pg.Vector2, world: World) -> None:
        """軸ごとに衝突を解決する。大きな移動は小分けにして壁抜けを防ぐ。"""
        steps = max(1, math.ceil(movement.length() / 8))
        movement = movement / steps
        for _ in range(steps):
            for axis in (0, 1):
                self.position[axis] += movement[axis]
                rect = self.rect
                rect.center = (round(self.position.x), round(self.position.y))
                for wall in world.walls:
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

    def update(self, dt: float, keys: pg.key.ScancodeWrapper,
               world: World) -> tuple[NoiseEvent, ...]:
        """入力に応じて移動し、スタミナと無敵時間を更新する。"""
        self.invincible = max(0.0, self.invincible - dt)
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
        if direction.length_squared():
            self.move(direction.normalize() * (DASH_SPEED if self.sprinting else PLAYER_SPEED) * dt, world)
        return ()  # 足音は主人公担当が追加する

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

    def __init__(self, route: list[Cell], world: World) -> None:
        self.route = route
        self.route_index = 1
        self.search_time = 0.0
        self.search_arrived = False
        self.search_targets: list[tuple[int, int]] = []
        self.state = "PATROL"
        self.stunned = 0.0
        self.position = world.center(route[0])
        self.next_cell: tuple[int, int] | None = None
        self.last_seen: tuple[int, int] | None = None
        self.search_center: tuple[int, int] | None = None

    def can_see(self, player: Player, world: World) -> bool:
        """主人公が隠れておらず、近くにいて壁や閉じた扉に遮られていなければTrue。"""
        distance = self.position.distance_to(player.position)
        return (not player.hidden and distance < 185
                and world.visible(self.position, player.position))

    def get_search_targets(self, world: World) -> list[Cell]:
        """捜索先の上下左右から、通れるマスを選ぶ。"""
        if self.search_center is None:
            return []

        x, y = self.search_center

        candidates = [
            (x, y - 1),  # 上
            (x, y + 1),  # 下
            (x - 1, y),  # 左
            (x + 1, y),  # 右
        ]

        targets = []
        for cell in candidates:
            if world.walkable(cell):
                targets.append(cell)

        return targets

    def get_search_goal(self, current: tuple[int, int]) -> tuple[int, int]:
        """捜索中に次に向かうマスを決める。"""
        if self.search_center is None:
            return current

        # まず捜索先へ向かう
        if not self.search_arrived:
            if current != self.search_center:
                return self.search_center

            self.search_arrived = True

        # 先頭の候補へ到着したら、一覧から取り除く
        if self.search_targets and current == self.search_targets[0]:
            self.search_targets.pop(0)

        # 候補が残っていれば、先頭の場所へ向かう
        if self.search_targets:
            return self.search_targets[0]

        # 全部調べ終わったら、その場で待つ
        return current

    def hear_noise(
        self,
        noise_position: pg.Vector2,
        world: World,
        radius: float = 240.0,
    ) -> bool:
        """音が聞こえる距離なら、その場所の捜索を始める。"""
        if self.stunned > 0:
            return False

        distance = self.position.distance_to(noise_position)

        if distance > radius:
            return False

        self.start_search(world.cell_at(noise_position), world)
        return True

    def start_search(self, cell: Cell, world: World) -> None:
        """指定したマスを中心に捜索を始める。"""
        self.state = "SEARCH"
        self.search_center = cell
        self.search_time = 3.0
        self.search_arrived = False
        self.search_targets = self.get_search_targets(world)

    def update(self, dt: float, player: Player, world: World,
               noises: tuple[NoiseEvent, ...] = ()) -> None:
        """視認と現在の状態に応じて、追跡・捜索・巡回を更新する。"""
        if self.stunned > 0:
            self.stunned = max(0.0, self.stunned - dt)
            return
        if self.can_see(player, world):
            # 見えている主人公の追跡を、音の捜索より優先する。
            self.state = "CHASE"
            self.last_seen = world.cell_at(player.position)
        else:
            if self.state == "CHASE" and self.last_seen is not None:
                self.start_search(self.last_seen, world)
            # 主人公担当から届いた音の位置と範囲を、既存の捜索処理につなぐ。
            for noise in noises:
                if self.hear_noise(pg.Vector2(noise.position), world, noise.radius):
                    break
        # 進行中のマスへ到達してから経路を選び直し、角の壁抜けを防ぐ。
        # マスの中心に着いたら、次の行動を決める

        # 到着後は、周囲を歩いている間も捜索時間を減らす
        if self.state == "SEARCH" and self.search_arrived:
            self.search_time = max(0.0, self.search_time - dt)

            if self.search_time <= 0:
                self.state = "PATROL"

        if self.next_cell is None:
            current = world.cell_at(self.position)

            if self.state == "CHASE" and self.last_seen is not None:
                goal = self.last_seen

            elif self.state == "SEARCH":
                goal = self.get_search_goal(current)

            else:
                goal = self.route[self.route_index]
                if current == goal:
                    self.route_index = (self.route_index + 1) % len(self.route)
                    goal = self.route[self.route_index]

            path = world.find_path(current, goal)
            if path:
                self.next_cell = path[0]
            elif current != goal and self.state == "SEARCH":
                # 捜索先へ行く道がない場合は、巡回へ戻る
                self.state = "PATROL"
        if self.next_cell is not None:
            target = world.center(self.next_cell)
            delta = target - self.position
            distance = delta.length()
            if self.state == "CHASE":
                speed = 132
            elif self.state == "SEARCH":
                speed = 100
            else:
                speed = 88

            step = speed * dt
            if distance <= step:
                self.position = target
                self.next_cell = None
            elif distance:
                self.position += delta / distance * step

    def draw(self, screen: pg.Surface, font: pg.font.Font) -> None:
        """巡回は紫、追跡は赤、捜索は黄色で描き、状態名を表示する。"""
        p = self.position
        if self.state == "CHASE":
            color = RED
        elif self.state == "SEARCH":
            color = GOLD
        else:
            color = (178, 143, 219)
        pg.draw.circle(screen, (10, 17, 28), (int(p.x), int(p.y + 5)), 15)
        pg.draw.rect(
            screen, color, (int(p.x - 12), int(p.y - 12), 24, 24), border_radius=7
        )
        pg.draw.rect(
            screen, (37, 36, 57), (int(p.x - 13), int(p.y - 12), 26, 7), border_radius=2
        )
        pg.draw.circle(screen, BG, (int(p.x - 4), int(p.y)), 2)
        pg.draw.circle(screen, BG, (int(p.x + 4), int(p.y)), 2)
        # 敵の頭上に状態名を表示する
        image = font.render(self.state, True, color)
        screen.blit(image, image.get_rect(center=(int(p.x), int(p.y - 24))))


class Game:
    """タイトル・プレイ・一時停止・結果を含むゲーム本体。"""

    def __init__(self) -> None:
        for stage in STAGES:
            validate_stage(stage)
        self.stage_index = 0
        self.screen = pg.display.set_mode((WIDTH, HEIGHT))
        pg.display.set_caption("学校脱出 / NIGHT SCHOOL - prototype")
        self.clock = pg.time.Clock()
        self.fonts = {size: pg.font.SysFont(FONT_NAMES, size, bold=(size >= 24))
                      for size in (14, 16, 18, 20, 24, 32, 42)}
        self.button = pg.Rect(380, 534, 320, 58)
        self.alive = True
        self.reset()
        self.state = 'title'

    def reset(self) -> None:
        """再挑戦時にもプレイに関わる全状態を初期化する。"""
        self.world = World(STAGES[self.stage_index])
        stage = self.world.stage
        self.player = Player(stage.player_spawn, self.world)
        self.time_left = TIME_LIMIT
        self.keys: set[str] = set()  # 仕掛け担当の統合時にinventoryへ移す
        self.heal = stage.heal_cell is not None
        self.guards = [Guard(route, self.world) for route in stage.guard_routes]
        self.state = 'playing'
        self.message = f'教室を探索して、{len(stage.required_keys)}つの鍵を集めよう'
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
            elif self.state == 'title' and event.key in (pg.K_1, pg.K_2):
                self.stage_index = event.key - pg.K_1
                self.reset()
                self.state = 'title'
            elif self.state in ('won', 'lost') and event.key == pg.K_t:
                self.reset()
                self.state = 'title'
            elif event.key in (pg.K_RETURN, pg.K_SPACE) and self.state == 'title':
                self.reset()
            elif event.key in (pg.K_r, pg.K_RETURN) and self.state in ('won', 'lost'):
                self.reset()
            elif event.key == pg.K_RETURN and self.state == 'paused':
                self.state = 'playing'
            elif event.key == pg.K_n and self.state == 'playing':
                heard = False
                for guard in self.guards:
                    if guard.can_see(self.player, self.world):
                        continue
                    if guard.hear_noise(self.player.position, self.world):
                        heard = True
                if heard:
                    self.say('仮の足音：敵が反応した！')
                else:
                    self.say('仮の足音：反応した敵はいない')
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
        noises = self.player.update(dt, keys, self.world)
        self.collect_items()
        self.update_guards(dt, noises)
        self.check_result()

    def collect_items(self) -> None:
        """鍵と、一度だけ使える回復アイテムの取得を処理する。"""
        if self.player.hidden:
            return
        stage = self.world.stage
        for key_id, cell in stage.keys.items():
            if key_id not in self.keys and self.player.position.distance_to(self.world.center(cell)) < 24:
                self.keys.add(key_id)
                remaining = len(stage.required_keys - self.keys)
                self.say('鍵がそろった！ 下中央の出口へ' if remaining == 0
                         else f'鍵を見つけた！ あと{remaining}個')
        if (self.heal and stage.heal_cell is not None
                and self.player.position.distance_to(self.world.center(stage.heal_cell)) < 25
                and self.player.recover()):
            self.heal = False
            self.say('回復ポイントでHPが1回復した')

    def update_guards(self, dt: float, noises: tuple[NoiseEvent, ...]) -> None:
        """見回り役を移動させ、プレイヤーとの接触を処理する。"""
        for guard in self.guards:
            guard.update(dt, self.player, self.world, noises)
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
        elif self.player.position.distance_to(self.world.center(self.world.stage.exit_cell)) < 25:
            if self.world.stage.required_keys <= self.keys:
                self.state = 'won'
            else:
                self.say(f'出口は施錠中。あと{len(self.world.stage.required_keys - self.keys)}個の鍵が必要')

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
        self.world.draw(self.screen)
        for key_id, cell in self.world.stage.keys.items():
            if key_id not in self.keys:
                p = self.world.center(cell)
                pg.draw.circle(self.screen, (77, 66, 42), p, 17 + int(2 * math.sin(t * 3)))
                self.draw_key(p, GOLD)
        if self.heal and self.world.stage.heal_cell is not None:
            p = self.world.center(self.world.stage.heal_cell)
            pg.draw.rect(self.screen, (41, 94, 84), (int(p.x-12), int(p.y-12), 24, 24), border_radius=5)
            pg.draw.line(self.screen, TEAL, (p.x-6, p.y), (p.x+6, p.y), 4)
            pg.draw.line(self.screen, TEAL, (p.x, p.y-6), (p.x, p.y+6), 4)
        p = self.world.center(self.world.stage.exit_cell)
        unlocked = self.world.stage.required_keys <= self.keys
        pg.draw.rect(self.screen, (37, 105, 92) if unlocked else (70, 58, 51),
                     (int(p.x-30), int(p.y-15), 60, 30), border_radius=5)
        self.text('EXIT' if unlocked else 'LOCK', (int(p.x), int(p.y)), 14,
                  TEAL if unlocked else GOLD, True)

    def draw_hud(self) -> None:
        """鍵、HP、残り時間、スタミナを表示する。"""
        self.text('NIGHT SCHOOL', (54, 23), 24)
        self.text(f'夜の学校から脱出 / {self.world.stage.name}', (55, 60), 16, MUTED)
        self.text(f'KEYS  {len(self.keys)} / {len(self.world.stage.keys)}', (400, 28), 24, GOLD)
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
            '下中央の出口へ向かおう！' if self.world.stage.required_keys <= self.keys else '鍵を3つ集めて、下中央の出口から脱出')
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
            for index, stage in enumerate(STAGES):
                color = TEAL if index == self.stage_index else MUTED
                self.text(f'[{index + 1}] {stage.name}', (380 + index * 320, 333), 16, color, True)
            lines = ['3つの鍵を集めて、下中央の出口を開こう。',
                     '紫の見回り役は、近づくと赤くなって追ってくる。',
                     'Shiftでダッシュ。＋でHPを1回復。',
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
            lines = [self.reason, f'集めた鍵  {len(self.keys)} / {len(self.world.stage.keys)}',
                     '見回り役の進路を見て、ダッシュで切り抜けよう。']
            label = 'もう一度挑戦  [R]'
        for i, line in enumerate(lines):
            self.text(line, (540, 368+i*34), 18, MUTED, True)
        pg.draw.rect(self.screen, TEAL, self.button, border_radius=12)
        self.text(label, self.button.center, 20, BG, True)
        if self.state == 'title':
            hint = '1 / 2：ステージ選択　　×：終了'
        elif self.state in ('won', 'lost'):
            hint = 'T：タイトルへ戻ってステージ選択　　×：終了'
        else:
            hint = '終了するにはウィンドウの × を押す'
        self.text(hint, (540, 613), 14, MUTED, True)

    def draw(self) -> None:
        """背景、キャラクター、案内を順に描画する。"""
        self.screen.fill(BG)
        self.draw_hud()
        self.draw_map()
        for guard in self.guards:
            guard.draw(self.screen, self.fonts[20])
        self.player.draw(self.screen)
        self.text('移動  WASD / 矢印     ダッシュ  Shift     一時停止  Esc', (54, 762), 16, MUTED)
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
