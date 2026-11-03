"""担当間の接続を練習する小さな代用品。本番のWorldではない。"""
from __future__ import annotations
from collections import deque
import pygame
from contracts import DoorSpec, Stage, SwitchSpec


class SandboxWorld:
    TILE = 36

    def __init__(self):
        grid = [[1 if x in (0, 6) or y in (0, 6) else 0
                 for x in range(7)] for y in range(7)]
        # 上下を隔てる壁。中央の扉だけが通路になる。
        for x in (2, 3, 4, 5):
            grid[4][x] = 1
        self.stage = Stage(
            stage_id='sandbox', name='接続練習用', grid=grid,
            player_spawn=(3, 1), guard_routes=[[(1, 1), (1, 3)]],
            keys={'red': (2, 1)}, exit_cell=(5, 5), heal_cell=(4, 5),
            hiding_spots=((4, 1),),
            doors=(DoorSpec('door_red', (1, 4), 'red'),),
            switches=(SwitchSpec('switch_a', (5, 1), ('door_red',)),),
            required_keys=frozenset({'red'}),
        )
        self.opened_doors = set()
        self._rebuild_walls()

    def center(self, cell):
        x, y = cell
        return pygame.Vector2((x + .5) * self.TILE, (y + .5) * self.TILE)

    def cell_at(self, position):
        return int(position[0] // self.TILE), int(position[1] // self.TILE)

    def walkable(self, cell):
        x, y = cell
        grid = self.stage.grid
        if not (0 <= y < len(grid) and 0 <= x < len(grid[y])):
            return False
        if grid[y][x] != 0:
            return False
        return not any(d.cell == cell and d.door_id not in self.opened_doors
                       for d in self.stage.doors)

    def _rebuild_walls(self):
        self.walls = [pygame.Rect(x * self.TILE, y * self.TILE,
                                 self.TILE, self.TILE)
                      for y, row in enumerate(self.stage.grid)
                      for x, _ in enumerate(row) if not self.walkable((x, y))]

    def open_door(self, door_id):
        if door_id not in {d.door_id for d in self.stage.doors}:
            raise ValueError(f'unknown door: {door_id}')
        if door_id in self.opened_doors:
            return False
        self.opened_doors.add(door_id)
        self._rebuild_walls()
        return True

    def find_path(self, start, goal):
        if not self.walkable(start) or not self.walkable(goal):
            return []
        queue = deque([start])
        previous = {start: None}
        while queue:
            current = queue.popleft()
            if current == goal:
                path = []
                while current != start:
                    path.append(current)
                    current = previous[current]
                return path[::-1]
            x, y = current
            for cell in ((x+1,y), (x-1,y), (x,y+1), (x,y-1)):
                if cell not in previous and self.walkable(cell):
                    previous[cell] = current
                    queue.append(cell)
        return []

    def visible(self, a, b):
        a, b = pygame.Vector2(a), pygame.Vector2(b)
        steps = max(1, int(a.distance_to(b) / 8) + 1)
        return all(self.walkable(self.cell_at(a.lerp(b, i / steps)))
                   for i in range(steps + 1))


class SandboxPlayer:
    def __init__(self, position):
        self.position = pygame.Vector2(position)
        self.hidden = False
        self.hp = 3
        self.stamina = 100.0

    @property
    def rect(self):
        rect = pygame.Rect(0, 0, 24, 24)
        rect.center = self.position
        return rect


if __name__ == '__main__':
    world = SandboxWorld()
    assert world.cell_at(world.center((3, 1))) == (3, 1)
    assert world.visible(world.center((1, 1)), world.center((3, 1)))
    assert not world.walkable((-1, 1))
    assert world.find_path((1, 1), (1, 5)) == []
    assert world.open_door('door_red')
    assert not world.open_door('door_red')
    path = world.find_path((1, 1), (1, 5))
    assert path[0] == (1, 2) and path[-1] == (1, 5)
    assert world.visible(world.center((1, 1)), world.center((1, 5)))
    print('OK: 練習用の座標・視線・経路・扉を確認しました。')
