# 演習01：マップとステージ管理
担当案：代表者 kusupon / 共通準備と統合も担当

## 今回決めた実装方針

- 同じ27×17マスで、校舎Aは従来配置、校舎Bは中央下のエントランスホールから左右対称に棟が伸び、中庭を囲む弧状の形にする。
- 各Stageは別々のgrid・巡回経路を生成し、共有リストを書き換えない。
- Stageの末尾へroom_labels・desk_cells・corridor_cellsを追加する。初期値は全て空tuple。
- 各敵の巡回地点は、扉を開けずに行き来できる配置を必須にする。
- 01ではPlayer・Guardをgame.pyに残してWorldへ接続する。別ファイルへの移動と追加機能は各担当で行う。
- 01の実ステージは扉・スイッチなし。開放APIと進行検証はテスト用配置で確認する。

実装済みの構成と接続APIはルートのREADME.mdを参照してください。
この節と以下の変更はMarkdown版へ反映しています。既存PDF・スライドは更新前の教材です。

## 到達目標
固定の学校を2種類のステージへ拡張し、壁・扉・経路・視界をWorldで一元管理します。各担当が同じマップを参照できる状態が完成条件です。
先に00_commonの4〜9節を読み、starter/contracts.pyをゲームのルートに置きます。既存のmake_map、center、cell_at、walkable、find_path、visible、WALLSが主な移動対象です。
必須：2ステージ、World、到達可能性の確認、タイトルでの選択。任意：3ステージ目、装飾、ランダム生成。

## 練習1：マップをデータにする
stages.pyを作り、現在のGRIDを最初のStageへ移します。最初は表示や挙動を変えません。第2ステージは独立したgridを作るか、第1ステージを深くコピーしてから通路を変えます。共有リストを直接変更しないようにします。
Stageの項目はcontracts.pyの定義どおりです。gridは0が床、1が固定壁。鍵は `{鍵ID: Cell}`、扉・スイッチ・隠れ場所は独立したデータです。
```python
stage = Stage(
    stage_id='school_a', name='校舎A', grid=grid_a,
    player_spawn=(4, 3), guard_routes=routes_a,
    keys={'red': (22, 3), 'blue': (4, 14), 'green': (22, 14)},
    exit_cell=(13, 15), heal_cell=(24, 13),
    hiding_spots=((6, 3),), doors=(), switches=(),
    required_keys=frozenset({'red', 'blue', 'green'}),
)
```
最初は扉とスイッチを空にします。これで従来のゲームが動くことを確認してから仕掛け担当のデータを追加します。
確認：2つのStageのgridを書き換えても、もう片方のgridは変わらない。

## 練習2：座標と通行判定を移す
World(stage)を作り、stageとopened_doorsを保持します。centerとcell_atは現在の処理をメソッドへ移し、TILEとORIGINはsettings.pyから読みます。
walkableは「範囲内」「固定壁でない」「未開放の扉でない」の3条件を確認します。負の添字で反対側のマスを参照しないよう、範囲判定を先に行います。
```python
def walkable(self, cell: Cell) -> bool:
    col, row = cell
    # TODO: 範囲外ならFalse
    # TODO: 固定壁ならFalse
    # TODO: このマスの扉が未開放ならFalse
    return True
```
wallsには固定壁と閉じた扉のRectを含めます。Player.moveの `for wall in WALLS` を `for wall in world.walls` に変更し、updateからmoveへworldを渡します。
確認：範囲外はFalse、床はTrue、壁はFalse。位置とRectの対応が1マスずれていない。

## 練習3：経路と視線を移す
既存find_pathのwalkable呼び出しをself.walkableに置き換えます。経路は開始マスを除き、目的地を含めます。経路を作れない場合は空リストを返します。
visibleもself.walkableで判定します。扉の前後で視線と通行の結果が一致するようにします。直接GRIDだけを見ている処理が残っていないか検索します。
open_doorはdoor_idが未開放ならopened_doorsへ追加し、wallsを再構築してTrueを返します。既に開いているときはFalse、存在しないIDにはValueErrorを使う、という仕様で統一します。
確認：閉じた扉で経路が遮られ、開いた後は同じstart/goalで経路が得られる。敵担当へ変更の反映タイミングを伝える。

## 練習4：配置を検証する
validate_stage(stage)を作り、問題があれば理由付きのValueErrorを返します。問題なければ何も返さず終了します。
1. gridが空でなく、列数が揃い、値が整数の0/1であるか。外周は壁とし、表示領域の27列×17行以内か。
2. 開始、出口、鍵、回復、隠れ場所、巡回地点、扉、スイッチが範囲内の床か。
3. 扉・スイッチのID重複、扉の座標重複、存在しない鍵を要求する扉・required_keys、存在しない扉を指すスイッチがないか。
4. 巡回経路は2地点以上か。全巡回地点に扉を全開にした床マップ上で開始地点から到達でき、各敵は扉を全閉じにした状態でも自分の巡回地点を行き来できるか。
5. 鍵・スイッチを順番に使えば、必須鍵と出口まで進めるか。
5は全扉を閉じて到達できるかだけでは判定できません。初期状態で行ける範囲を探索し、届く鍵を拾い、届くスイッチと取得鍵で扉を開きます。鍵扉は取得鍵があり、到達範囲の上下左右に隣接する扉を開けます。新しい鍵・扉がなくなるまで繰り返し、最後に必須鍵と出口を検査します。回復地点はNoneなら位置検証と描画を省略します。
この検査は「仕掛けとして進行可能か」を調べるものです。敵を避けられるか、時間内に終わるかは実際に遊んで別に確認します。

## 練習5：タイトルから選ぶ
Game.__init__でstage_index=0を設定します。タイトル中に1/2キーで選び、Enterを押すと選んだStageでresetします。プレイ中にステージ変更はしません。
```python
# Game.reset内の接続例
self.world = World(STAGES[self.stage_index])
self.player = Player(self.world.stage.player_spawn, self.world)
self.guards = [Guard(route, self.world)
               for route in self.world.stage.guard_routes]
```
これに合わせてPlayer/Guardのコンストラクタを変更します。旧center呼び出しはworld.centerへ置き換えます。各クラスがgame.pyをimportしない構成にしてください。
再挑戦は同じステージを初期状態に戻します。結果画面でTを押すとstate='title'へ戻る分岐をGame.handle_eventへ追加します。タイトルでは1/2で選び直せます。プレイ中のTは無効です。タイトルと結果画面の操作案内にもTを追記します。

## 練習6：描画と統合
World.draw(screen)でgridと扉を描きます。教室名・机・廊下の床色はStageのroom_labels・desk_cells・corridor_cellsを参照します。追加項目の初期値は空tupleです。旧Game.draw_mapの固定配置をそのまま第2ステージへ描かないでください。
鍵やスイッチはGimmicks.draw、キャラクターは各クラスが描きます。Gameは描画順だけを管理します。world.open_doorを呼んだフレームの後に敵を更新します。
代表者は各機能を1つずつ接続し、起動と基本操作を確認してから次を取り込みます。

## 動作確認表
| 入力・準備 | 期待する結果 |
|---|---|
| タイトルで1 / 2を選ぶ | それぞれ違うマップになる |
| 不正な鍵座標を設定 | 起動前の検証で位置が分かるエラー |
| 自分の鍵を扉の奥へ置く | 進行不能として検出 |
| 扉を2回開く | 初回True、2回目False |
| 壁越しに敵と主人公を置く | visibleがFalse |
| 再挑戦 | 開けた扉、取得鍵、敵位置が初期状態 |

## 提出前の確認
world.py、stages.py、必要な共通接続、READMEの担当欄をコミットします。基本機能の移動と新しい2ステージ・配置検証を区別して説明します。
PRには、Stage追加方法、World API、他担当が直す呼び出し箇所、動作確認の結果を記載します。
基準コード：https://github.com/kusupon/ProjExD_Group13/blob/33fe9905c183b321d1988d66041feb8b7e74998f/game.py
