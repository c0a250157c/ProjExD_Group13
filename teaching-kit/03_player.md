# 演習03：隠れる機能と足音
担当案：メンバーA / 氏名は話し合いで記入

## 到達目標
主人公が隠れ場所を使って敵から見えなくなり、ダッシュすると足音が敵へ伝わるようにします。既存の移動・ダッシュ・HP管理を維持しながら拡張します。
最初に00_commonの4〜8節を読みます。既存Playerをplayer.pyへ移し、設定値をsettings.pyへまとめます。Worldは引数で受け取り、game.pyをimportしません。
必須：Eで隠れる／出る、hidden共有、隠れている間の制限、足音イベント。任意：しゃがみ移動、音の大きさの変化。

## 練習1：Worldを使う移動へ変える
Playerの初期化を `Player(cell, world)` にし、初期座標はworld.center(cell)で求めます。moveは `move(movement, world)` に変え、衝突先はworld.wallsを使います。
updateの形は `update(dt, keys, world) -> tuple[NoiseEvent, ...]` にします。足音未実装の段階では空tupleを返します。初めに従来どおり移動・ダッシュできることを確認します。
rect.centerは位置の変更後に更新します。ゲーム全体で座標を参照するときはposition、当たり判定ではrectを使い、二重に別の位置を管理しないようにします。

## 練習2：隠れる状態を追加する
初期化時に `hidden=False`、`hiding_cell=None`、`noise_cooldown=0.0` を用意します。隠れ場所はworld.stage.hiding_spotsです。
handle_event(event, world)を作り、KEYDOWNかつK_eのときだけ切り替えます。キーを押し続けた毎フレームで切り替えると点滅するので、get_pressedで切り替えないでください。
```python
if event.type == pg.KEYDOWN and event.key == pg.K_e:
    if self.hidden:
        # TODO: 隠れ状態を解除する
        ...
    else:
        # TODO: 24px以内の最も近い隠れ場所を探す
        ...
```
隠れる際に主人公を瞬間移動させません。現在位置でhiddenをTrueにし、選んだ場所をhiding_cellへ保存します。遠くからEを押しても何も起きない仕様です。

## 練習3：隠れている間の動作を決める
hidden中は移動とダッシュを止め、sprinting=Falseにします。無敵時間は通常どおり減らし、スタミナは回復させます。足音は発生させません。
GimmicksとGameにもhiddenを伝え、鍵・回復の取得と敵の接触ダメージを止めます。Playerの変更だけでは全体のルールが揃わないので、仕掛け・敵AI担当へ接続仕様を連絡します。
隠れ場所から出るときはhidden=False、hiding_cell=Noneへ戻します。今回の扉は一度開くと閉じないため、出る場所を閉じた扉が塞ぐ状況は作りません。
確認：隠れている間にWASDとShiftを押しても位置が変わらず、Eで出た後は再び動ける。

## 練習4：ダッシュの足音を作る
NoiseEventは発生時の座標と半径を持ちます。ダッシュ中、実際に移動したときだけ、0.35秒に1回、半径240ピクセルを目安に通知します。
前後のpositionを比較して移動を判定します。壁へ押し付けているだけで、足音を連続発生させないようにします。数値は共通仕様へ定数として記載します。
```python
before = self.position.copy()
# 既存の移動処理を実行する
moved = self.position.distance_squared_to(before) > 0.01
self.noise_cooldown = max(0.0, self.noise_cooldown - dt)
noises = []
# TODO: sprinting / moved / hidden / cooldownで発生を判定
return tuple(noises)
```
発生時は `NoiseEvent((self.position.x, self.position.y), 240.0)` を追加し、cooldownを0.35へ戻します。Vector2そのものを渡すと、後の移動で過去の音の位置が変わるおそれがあるため数値tupleにします。
通常歩行の足音は必須にしません。発展課題として入れるなら、ダッシュより小さい半径を全員で決めます。

## 練習5：Gameと敵へ渡す
Game.handle_eventのplaying中の分岐で `self.player.handle_event(event, self.world)` を呼びます。開始画面・停止中・結果画面では呼びません。
Game.updateでupdateの返り値を受け取り、同じnoisesを全てのGuard.updateへ渡します。敵ごとにリストを空にしないでください。
```python
noises = self.player.update(dt, keys, self.world)
for guard in self.guards:
    guard.update(dt, self.player, self.world, noises)
```
敵担当が未完成なら、まず `print(noises)` で「走って移動したときだけ発生し、座標が固定される」ことを確認します。確認後は毎フレームのprintを削除します。

## 練習6：状態を見えるようにする
World側で隠れ場所を描画し、主人公が24px以内なら「E：隠れる」、hiddenなら「E：出る」と表示する案です。表示担当を代表者と決め、同じ案内を2か所で描かないようにします。
Player.drawではhidden中の表示を薄い色や輪郭に変え、操作が効かなくなった理由を伝えます。hiddenは無敵時間とは別の状態なので、同じ変数を使わないでください。

## 動作確認表
| 準備・操作 | 期待する結果 |
|---|---|
| 隠れ場所から遠くでE | hiddenはFalseのまま |
| 近くでEを1回 | hidden=True、位置は変わらない |
| Eを押し続ける | 意図せず毎フレーム切り替わらない |
| 隠れてWASD / Shift | 移動と足音が止まる |
| 隠れて鍵や敵に重なる | 取得も被弾もしない |
| Eで出て移動 | 通常操作へ戻る |
| 1秒間ダッシュ | 連続する毎フレームではなく約3回の音 |
| 壁に向かってダッシュ | 実移動がないので音が出ない |
| 再挑戦 | hiddenと足音タイマーが初期化 |

## よくある不具合と提出
位置は止まるのに敵に見つかる場合はGuard.can_seeでhiddenを見ているかを確認します。隠れている間だけタイマーが壊れる場合は、早期returnより前に無敵時間・スタミナ更新を置いたかを見ます。
player.py、必要な接続、READMEの操作説明をコミットします。PRに足音の半径・間隔、hiddenの意味、敵AIと仕掛けへの依頼を記載してください。
基準コード：https://github.com/kusupon/ProjExD_Group13/blob/33fe9905c183b321d1988d66041feb8b7e74998f/game.py
