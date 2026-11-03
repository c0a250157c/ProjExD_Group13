"""共通仕様。代表者がゲームのルートへコピーしてから全員で使用する。"""
from __future__ import annotations
from dataclasses import dataclass

Cell = tuple[int, int]


@dataclass(frozen=True)
class NoiseEvent:
    position: tuple[float, float]
    radius: float


@dataclass(frozen=True)
class DoorSpec:
    door_id: str
    cell: Cell
    key_id: str | None = None


@dataclass(frozen=True)
class SwitchSpec:
    switch_id: str
    cell: Cell
    door_ids: tuple[str, ...]


@dataclass(frozen=True)
class Stage:
    stage_id: str
    name: str
    grid: list[list[int]]
    player_spawn: Cell
    guard_routes: list[list[Cell]]
    keys: dict[str, Cell]
    exit_cell: Cell
    heal_cell: Cell | None
    hiding_spots: tuple[Cell, ...]
    doors: tuple[DoorSpec, ...]
    switches: tuple[SwitchSpec, ...]
    required_keys: frozenset[str]


@dataclass(frozen=True)
class Result:
    stage_id: str
    won: bool
    score: int
    time_left: float
    hp: int
    key_count: int
    damage_count: int
    no_damage: bool
    fast_escape: bool
    breakdown: dict[str, int]

# frozen=Trueは属性の再代入を防ぐ。gridやdictの内容までは凍結しない。
# 取得鍵・開いた扉などのプレイ中の状態をStageへ書き込まないこと。
