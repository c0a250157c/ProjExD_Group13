# 夜の学校から脱出 - School Escape Demo

![ゲーム画面](preview_play.png)

## どんなゲーム？

120秒以内に学校の中にある鍵を3つ集め、下中央の玄関から脱出する見下ろし型ゲームです。
見回り役を避け、必要なときはダッシュで逃げましょう。
タイトルで校舎A（従来配置）／校舎B（左右対称）を選べます。どちらも27×17マスです。校舎Bは中庭を囲む左右対称の形で、左側にE101〜E104講義室、下中央にエントランスホール、右側にバイオホールを配置しています。

- 鍵：触れると自動で取得。3つ集めると出口を開けられます。
- 見回り役：紫色で巡回し、壁に視線を遮られていない近くのプレイヤーを見つけると赤くなって追跡します。
- HP：最初は3。接触で1減り、3秒間は再被弾しません。接触した敵は1秒停止します。
- 回復：「＋」で、HPを一度だけ1回復できます。校舎Aは保健室、校舎Bはエントランスホールにあります。
- ダッシュ：スタミナを消費。使い切ったら30%まで回復する間は使用できません。
- 失敗条件：時間切れ、またはHPが0。
- 机は背景の飾りです。壁が通行を妨げます。

## 動かし方

確認環境は **Python 3.13.12 / Pygame 2.6.1** です。Python 3.13を推奨します。
画像・音声の追加ダウンロードは不要です。日本語表示にはメイリオ、ヒラギノ、Noto Sans CJK JP等の日本語フォントが必要です。利用可能な候補を自動で選びます。

### Windows

GitHubの緑色の **Code → Download ZIP** からダウンロードし、ZIPを展開します。
展開先のフォルダでターミナルを開き、以下を実行してください。

```powershell
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe game.py
```

初回設定後は `run_game.cmd` のダブルクリックでも起動できます。
この起動ファイルは、このフォルダの `.venv` を使用します。

### macOS / Linux

Pygame 2.6.1が利用できるPython環境で、以下を実行してください。
今回のWorld追加はmacOSのConda環境で自動検証しました。Linuxでの表示は未確認です。

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python game.py
```

## 操作

| 操作 | キー |
|---|---|
| ステージ選択 | タイトルで1 / 2 |
| ゲーム開始 | Enter / 開始ボタン |
| 移動 | WASD / 矢印キー |
| ダッシュ | Shift |
| 一時停止・再開 | Esc |
| 再挑戦 | 結果画面でR / Enter / ボタン（同じステージ） |
| タイトルへ戻る | 結果画面でT |
| 終了 | ウィンドウの×。タイトル・結果画面ではEscも使用可 |

別のウィンドウへ切り替えると自動で一時停止します。

## ファイルと編集箇所

| ファイル | 役割 |
|---|---|
| `game.py` | Player・Guardと、入力・アイテム・勝敗・画面の統合 |
| `settings.py` | 画面サイズ、速度、フォントなどの共通設定 |
| `contracts.py` | Stage・扉・スイッチ・足音・結果の共通型 |
| `stages.py` | 校舎A／Bの地形・アイテム・巡回・装飾の配置 |
| `world.py` | 通行・扉・経路・視線・描画・配置検証 |
| `tests/test_world.py` | Worldと既存機能の接続テスト |
| `requirements.txt` | 必要なPygameのバージョン |
| `run_game.cmd` | Windows向けの起動ファイル |
| `preview_play.png` | 紹介用の画面画像 |

`game.py` の主な構成：

- `Player`：移動・壁との衝突・ダッシュ・HP・無敵時間・描画
- `Guard`：巡回・追跡・停止時間・描画
- `MAX_HP` / `PLAYER_SPEED` / `DASH_SPEED` など：settings.pyから読み込む定数
- `Game.reset`：初期化・再挑戦
- `Game.update`：各処理の呼び出しと残り時間の管理
- `Game.collect_items` / `update_guards` / `check_result`：アイテム・敵との接触・勝敗
- `Game.draw_map` / `draw_hud` / `draw_overlay`：マップ・ステータス・タイトルと結果画面

## 追加機能01：マップ・ステージ（kusupon）

共通ベースから、固定マップ・座標変換・経路探索・視線判定をWorldへ移しました。
新規部分は左右対称の弧状校舎B、タイトルでのステージ選択、配置検証、開放状態を持つ扉APIです。

Stageを追加するときは、stages.pyで独立したgrid・巡回経路・鍵配置を作り、STAGESへ登録します。
現在の選択画面は2ステージ用です。教室名はroom_labels、机はdesk_cells、廊下の床色はcorridor_cellsで指定します。
装飾項目は空tupleが初期値なので、従来のStage作成コードも使えます。机に衝突判定はありません。

`World(stage)`は配置を検証し、範囲外・外周の穴・不正ID・短すぎる巡回経路・進行不能をValueErrorで知らせます。
鍵とスイッチによる順次開放を確認し、巡回経路は扉を全閉じにした状態でもつながることを必須にしています。
回復地点はNoneも指定できます。Stageは配置専用とし、プレイ中は書き換えません。

他担当向けの接続変更：

- `Player(cell, world)` / `move(movement, world)` / `update(dt, keys, world)`
- `Guard(route, world)` / `update(dt, player, world, noises)`：playerはPlayerオブジェクト
- `world.center` / `cell_at` / `walkable` / `find_path` / `visible` / `walls`：旧グローバル関数・壁リストの代わり
- `world.open_door(id)`：初回True、開放済みFalse、未知のIDはValueError

01の段階では両ステージの扉・スイッチは空です。Worldの扉APIと配置検証はテスト用の配置で確認しています。
Player・Guardはgame.pyに残し、各担当が別ファイルへ移せる状態にしています。
足音の返り値は空tuple、hiddenはFalseです。隠れる操作・新しい敵AI・色付き鍵の解錠・スイッチ・ランキングは後続担当の実装です。
取得鍵は当面Game.keysでID管理し、仕掛け担当の統合時にGimmicks.inventoryへ移します。

## 確認したこと

Pygameが入った環境で、ルートから以下を実行できます。画面を開かずに15件を検証します。

```sh
python -m unittest discover -s tests -v
```

移動と壁の衝突、鍵の取得、敵の経路、HPと無敵時間、回復、時間切れ、クリア、
一時停止、再挑戦の初期化を自動確認しました。
敵を有効にした模擬操作で、校舎A・Bともに鍵3個を集めて脱出できることを確認しています。
難易度は仮調整なので、実際に遊んで感想を出してください。

## グループで相談したいこと

- 敵の速さやダッシュの強さはちょうどよいか？
- 鍵のランダム配置、懐中電灯、隠れ場所などを追加するか？
- 正式に採用する場合、共通ベースと各自の担当機能をどう分けるか？