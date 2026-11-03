"""地形、扉、経路、視線とステージの配置検証。"""
from __future__ import annotations

import math
from collections import deque

import pygame as pg

from contracts import Cell, Stage
from settings import COLS, ROWS, TILE, ORIGIN, MUTED, GOLD, FONT_NAMES, BG


def neighbors(cell: Cell) -> tuple[Cell, ...]:
    x, y = cell
    return (x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)


def is_floor(stage: Stage, cell: Cell) -> bool:
    x, y = cell
    return (0 <= y < len(stage.grid) and 0 <= x < len(stage.grid[y])
            and stage.grid[y][x] == 0)


def reachable_cells(stage: Stage, start: Cell, blocked: set[Cell]) -> set[Cell]:
    """閉じた扉を避け、開始地点から行ける床を集める。"""
    if not is_floor(stage, start) or start in blocked:
        return set()
    reached = {start}
    queue = deque([start])
    while queue:
        for cell in neighbors(queue.popleft()):
            if cell not in reached and cell not in blocked and is_floor(stage, cell):
                reached.add(cell)
                queue.append(cell)
    return reached


def validate_stage(stage: Stage) -> None:
    """配置が不正、または進行不能なら理由付きのValueErrorを送出する。"""
    def fail(message: str) -> None:
        raise ValueError(f'{stage.stage_id}: {message}')

    grid = stage.grid
    if not grid or not grid[0]:
        fail('gridが空です')
    rows, cols = len(grid), len(grid[0])
    if not (3 <= rows <= ROWS and 3 <= cols <= COLS):
        fail(f'gridは3×3以上、{COLS}列×{ROWS}行以下にしてください')
    if any(len(row) != cols for row in grid):
        fail('gridの列数が揃っていません')
    if any(type(value) is not int or value not in (0, 1) for row in grid for value in row):
        fail('gridには整数の0か1を指定してください')
    if any(grid[y][x] != 1 for y in range(rows) for x in range(cols)
           if x in (0, cols - 1) or y in (0, rows - 1)):
        fail('マップの外周は壁にしてください')

    def check_cell(label: str, cell: Cell) -> None:
        if (not isinstance(cell, tuple) or len(cell) != 2
                or any(type(value) is not int for value in cell)):
            fail(f'{label}: 座標{cell!r}は整数の(列, 行)で指定してください')
        if not is_floor(stage, cell):
            fail(f'{label}: {cell}は範囲内の床ではありません')

    check_cell('player_spawn', stage.player_spawn)
    check_cell('exit_cell', stage.exit_cell)
    if stage.heal_cell is not None:
        check_cell('heal_cell', stage.heal_cell)
    for key_id, cell in stage.keys.items():
        if not isinstance(key_id, str) or not key_id:
            fail('鍵IDは空でない文字列にしてください')
        check_cell(f'key {key_id}', cell)
    if not stage.required_keys <= stage.keys.keys():
        fail(f'required_keysに存在しない鍵があります: {stage.required_keys - stage.keys.keys()}')
    for index, cell in enumerate(stage.hiding_spots):
        check_cell(f'hiding_spots[{index}]', cell)
    for index, route in enumerate(stage.guard_routes):
        if len(route) < 2:
            fail(f'guard_routes[{index}]には巡回地点が2つ以上必要です')
        for cell in route:
            check_cell(f'guard_routes[{index}]', cell)

    doors = {}
    door_cells = set()
    for door in stage.doors:
        if not isinstance(door.door_id, str) or not door.door_id or door.door_id in doors:
            fail(f'扉IDが空、不正、または重複しています: {door.door_id!r}')
        check_cell(f'door {door.door_id}', door.cell)
        if door.cell in door_cells:
            fail(f'扉の位置が重複しています: {door.cell}')
        if door.key_id is not None and door.key_id not in stage.keys:
            fail(f'door {door.door_id}: 鍵{door.key_id!r}が存在しません')
        doors[door.door_id] = door
        door_cells.add(door.cell)
    switch_ids = set()
    for switch in stage.switches:
        if (not isinstance(switch.switch_id, str) or not switch.switch_id
                or switch.switch_id in switch_ids):
            fail(f'スイッチIDが空、不正、または重複しています: {switch.switch_id!r}')
        switch_ids.add(switch.switch_id)
        check_cell(f'switch {switch.switch_id}', switch.cell)
        if not switch.door_ids or any(door_id not in doors for door_id in switch.door_ids):
            fail(f'switch {switch.switch_id}: 開く扉が未指定、または存在しません')

    if stage.player_spawn in door_cells:
        fail('開始地点を閉じた扉に重ねることはできません')
    all_reached = reachable_cells(stage, stage.player_spawn, set())
    for index, route in enumerate(stage.guard_routes):
        if not set(route) <= all_reached:
            fail(f'guard_routes[{index}]に到達不能な巡回地点があります')
        initial_reached = reachable_cells(stage, route[0], door_cells)
        if not set(route) <= initial_reached:
            fail(f'guard_routes[{index}]は扉を開けないと巡回できません')

    for label, cell in stage.room_labels:
        check_cell(f'room_labels {label}', cell)
    for cell in stage.desk_cells:
        check_cell('desk_cells', cell)
    for cell in stage.corridor_cells:
        check_cell('corridor_cells', cell)

    inventory: set[str] = set()
    opened: set[str] = set()
    while True:
        blocked = {door.cell for door in stage.doors if door.door_id not in opened}
        reached = reachable_cells(stage, stage.player_spawn, blocked)
        inventory.update(key_id for key_id, cell in stage.keys.items() if cell in reached)
        available = {door_id for switch in stage.switches if switch.cell in reached
                     for door_id in switch.door_ids}
        available.update(door.door_id for door in stage.doors
                         if door.key_id in inventory and any(cell in reached for cell in neighbors(door.cell)))
        if available <= opened:
            break
        opened.update(available)
    if not stage.required_keys <= inventory:
        fail(f'必須鍵に到達できません: {sorted(stage.required_keys - inventory)}')
    if stage.exit_cell not in reached:
        fail(f'出口{stage.exit_cell}に到達できません')


class World:
    """1プレイ分の地形と、開いた扉を管理する。"""

    def __init__(self, stage: Stage):
        validate_stage(stage)
        self.stage = stage
        self.opened_doors: set[str] = set()
        self._doors = {door.door_id: door for door in stage.doors}
        self._blocked_doors: set[Cell] = set()
        self.walls: list[pg.Rect] = []
        self._font: pg.font.Font | None = None
        self._rebuild_walls()

    def center(self, cell: Cell) -> pg.Vector2:
        return ORIGIN + pg.Vector2((cell[0] + 0.5) * TILE, (cell[1] + 0.5) * TILE)

    def cell_at(self, position: pg.Vector2) -> Cell:
        local = (position - ORIGIN) / TILE
        return math.floor(local.x), math.floor(local.y)

    def walkable(self, cell: Cell) -> bool:
        return is_floor(self.stage, cell) and cell not in self._blocked_doors

    def _rebuild_walls(self) -> None:
        self._blocked_doors = {door.cell for door in self.stage.doors
                               if door.door_id not in self.opened_doors}
        self.walls = [pg.Rect(int(ORIGIN.x + x * TILE), int(ORIGIN.y + y * TILE), TILE, TILE)
                      for y, row in enumerate(self.stage.grid) for x, _ in enumerate(row)
                      if not self.walkable((x, y))]

    def open_door(self, door_id: str) -> bool:
        if door_id not in self._doors:
            raise ValueError(f'{self.stage.stage_id}: 存在しない扉IDです: {door_id}')
        if door_id in self.opened_doors:
            return False
        self.opened_doors.add(door_id)
        self._rebuild_walls()
        return True

    def find_path(self, start: Cell, goal: Cell) -> list[Cell]:
        """開始マスを除いた最短経路を返す。到達不能なら空リスト。"""
        if not self.walkable(start) or not self.walkable(goal):
            return []
        queue = deque([start])
        previous = {start: start}
        while queue:
            current = queue.popleft()
            if current == goal:
                path = []
                while current != start:
                    path.append(current)
                    current = previous[current]
                return path[::-1]
            for cell in neighbors(current):
                if self.walkable(cell) and cell not in previous:
                    previous[cell] = current
                    queue.append(cell)
        return []

    def visible(self, a: pg.Vector2, b: pg.Vector2) -> bool:
        """壁と閉じた扉で視線を遮る。"""
        steps = max(1, math.ceil(a.distance_to(b) / 8))
        return all(self.walkable(self.cell_at(a.lerp(b, i / steps))) for i in range(steps + 1))

    def draw(self, screen: pg.Surface) -> None:
        """ステージ固有の地形、装飾、扉を描く。机は通行を妨げない。"""
        corridors = set(self.stage.corridor_cells)
        for y, row in enumerate(self.stage.grid):
            for x, wall in enumerate(row):
                rect = pg.Rect(int(ORIGIN.x + x * TILE), int(ORIGIN.y + y * TILE), TILE, TILE)
                if wall:
                    # 床から離れた部分は屋外として描き、校舎の輪郭を見せる。
                    if not any(is_floor(self.stage, (x + dx, y + dy))
                               for dx in (-1, 0, 1) for dy in (-1, 0, 1)):
                        pg.draw.rect(screen, BG, rect)
                        continue
                    pg.draw.rect(screen, (49, 65, 83), rect)
                    pg.draw.line(screen, (66, 83, 99), rect.topleft, rect.topright, 2)
                    pg.draw.line(screen, (24, 34, 48), rect.bottomleft, rect.bottomright, 3)
                else:
                    color = (24, 38, 52) if (x, y) in corridors else (29, 44, 57)
                    pg.draw.rect(screen, color, rect)
                    pg.draw.rect(screen, (35, 50, 64), rect, 1)
        if self.stage.room_labels and self._font is None:
            self._font = pg.font.SysFont(FONT_NAMES, 16)
        for label, cell in self.stage.room_labels:
            image = self._font.render(label, True, MUTED)
            screen.blit(image, image.get_rect(center=self.center(cell)))
        for cell in self.stage.desk_cells:
            p = self.center(cell)
            pg.draw.rect(screen, (54, 73, 85), (int(p.x-12), int(p.y-8), 24, 16), border_radius=3)
        for door in self.stage.doors:
            rect = pg.Rect(0, 0, TILE, TILE)
            rect.center = self.center(door.cell)
            if door.door_id in self.opened_doors:
                pg.draw.rect(screen, (37, 105, 92), rect, 2)
            else:
                pg.draw.rect(screen, (101, 73, 56), rect, border_radius=3)
                pg.draw.circle(screen, GOLD, (rect.right - 8, rect.centery), 3)
