"""校舎の配置データ。プレイ中の取得・開放状態は持たせない。"""
from contracts import Stage
from settings import COLS, ROWS


def make_school_a() -> Stage:
    """従来の教室配置と巡回経路を保った校舎A。"""
    grid = [[int(x in (0, COLS - 1) or y in (0, ROWS - 1))
             for x in range(COLS)] for y in range(ROWS)]
    for y in (5, 11):
        for x in range(1, COLS - 1):
            grid[y][x] = int(x not in (4, 13, 22))
    for x in (9, 18):
        for y in list(range(1, 5)) + list(range(12, 16)):
            grid[y][x] = 1
    for x in (8, 18):
        grid[8][x] = grid[9][x] = 1
    return Stage(
        stage_id='school_a', name='研究等A(仮)', grid=grid,
        player_spawn=(4, 3),
        guard_routes=[
            [(13, 7), (4, 7), (4, 3), (4, 7), (22, 7), (22, 3)],
            [(22, 10), (22, 14), (22, 10), (4, 10), (4, 14)],
        ],
        keys={'red': (22, 3), 'blue': (4, 14), 'green': (22, 14)},
        exit_cell=(13, 15), heal_cell=(24, 13),
        hiding_spots=((6, 3),), doors=(), switches=(),
        required_keys=frozenset({'red', 'blue', 'green'}),
        room_labels=(('教室 A', (4, 1)), ('職員室', (13, 1)), ('理科室', (22, 1)),
                     ('図書室', (4, 12)), ('玄関', (13, 12)), ('保健室', (22, 12))),
        desk_cells=((2, 2), (6, 2), (11, 2), (15, 2), (20, 2), (24, 2)),
        corridor_cells=tuple((x, y) for y in range(6, 11)
                             for x in range(1, COLS - 1) if grid[y][x] == 0),
    )


def make_school_b() -> Stage:
    """中央玄関から左右の棟が対称に伸びる、中庭沿いの校舎B。"""
    grid = [[1] * COLS for _ in range(ROWS)]
    rooms = ((1, 1, 5, 2), (2, 4, 6, 5), (4, 7, 8, 8), (5, 10, 9, 11))
    passages = ((7, 1, 8, 3), (8, 4, 9, 6), (10, 7, 11, 9), (11, 10, 12, 12))
    corridor_cells = set()
    # 左棟を作り、中央の列を軸に反転して右棟を作る。
    for left, top, right, bottom in rooms + passages:
        for y in range(top, bottom + 1):
            for x in range(left, right + 1):
                grid[y][x] = grid[y][COLS - 1 - x] = 0
                if (left, top, right, bottom) in passages:
                    corridor_cells.update(((x, y), (COLS - 1 - x, y)))
    for x, y in ((6, 2), (7, 4), (9, 7), (10, 10)):
        grid[y][x] = grid[y][COLS - 1 - x] = 0
    grid[12][13] = 0
    corridor_cells.add((13, 12))
    for y in range(13, 16):
        for x in range(9, 18):
            grid[y][x] = 0
            corridor_cells.add((x, y))
    route_left = [(11, 9), (8, 2), (8, 5), (11, 8), (12, 12), (13, 14)]
    desks_left = ((4, 2), (5, 5), (6, 8), (8, 11))
    return Stage(
        stage_id='school_b', name='片柳研究棟', grid=grid,
        player_spawn=(3, 2),
        guard_routes=[route_left, [(COLS - 1 - x, y) for x, y in route_left]],
        keys={'red': (3, 5), 'blue': (7, 11), 'green': (23, 2)},
        exit_cell=(13, 15), heal_cell=(15, 14),
        hiding_spots=((4, 8), (22, 5)), doors=(), switches=(),
        required_keys=frozenset({'red', 'blue', 'green'}),
        room_labels=(('E104', (3, 1)), ('E103', (4, 4)),
                     ('E102 講義室', (6, 7)), ('E101 講義室', (7, 10)),
                     ('エントランスホール', (13, 13)), ('バイオホール', (19, 10))),
        desk_cells=desks_left + tuple((COLS - 1 - x, y) for x, y in desks_left),
        corridor_cells=tuple(sorted(corridor_cells)),
    )


STAGES = (make_school_a(), make_school_b())
