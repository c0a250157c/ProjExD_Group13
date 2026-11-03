# 共通型と接続練習用コード

これは完成ゲームではなく、各自が担当機能を実装するための補助教材です。

## 内容

- `contracts.py`：Stage、NoiseEvent、Resultなど、全員が共有する型。
- `sandbox.py`：7×7マスの練習用Worldと、位置・hiddenを持つ仮Player。
- `requirements.txt`：練習に必要なpygame。

## 最初の確認

PowerShellで、このstarterフォルダを開きます。Pythonをインストール済みなら次を実行します。

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe sandbox.py
```

最後にOKと表示されれば座標・視線・経路・扉の練習用処理は使えます。ウィンドウは開きません。
既に授業用仮想環境がある人は、そのpython.exeでsandbox.pyを実行しても構いません。

## 自分の担当コードと組み合わせる

代表者が本番のルートへcontracts.pyを置き、同じ定義を全員が使います。
練習時はcontracts.py、sandbox.py、自分のenemy_ai.pyなどを同じ練習フォルダへ置きます。
既存クラスが必要とする定数はsettings.pyへ移し、同じ場所に置いてください。
全員がgame.pyをimportする形にはしません。

```python
from sandbox import SandboxWorld, SandboxPlayer
world = SandboxWorld()
player = SandboxPlayer(world.center((3, 1)))
assert world.visible(world.center((1, 1)), player.position)
player.hidden = True  # 敵担当はこの値で視認しないことを確認
```

扉IDはdoor_red、鍵IDはred、スイッチIDはswitch_aです。
扉を開けると上側と下側がつながります。WorldのAPIは共通演習と同じですが、
配置検証・描画・本番の原点はありません。完成Worldの代用品として出荷しないでください。
SandboxPlayerのrectはpositionから生成される確認用です。HPや移動の完成実装は含みません。

EnemyStateやGuard、隠れる処理、得点計算は演習で実装する部分です。
授業に提出する際は、この補助教材を使った範囲と自分の追加実装を区別してください。
