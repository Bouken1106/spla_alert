# spla_alert

Splatoon の配信画面から、画面中央上部の味方4人・敵4人のイカ/タコアイコンを読み取り、生存人数をリアルタイムに数えるツールです。

現在の実装範囲:

- 10フレームごとに上部 HUD を解析
- 味方最大4人、敵最大4人をカウント
- 生存アイコンは色付き、デス中アイコンは灰色として判定
- アイコンサイズの多少の変化に対応するため、各枠を相対座標で切り出し
- AverMedia/ReCentral の映像を Ubuntu 側に持ってきた入力を読み取り
- ブキ種別、スペシャル発光の識別は未実装。ただし発光していても「生存」として扱う想定

## セットアップ

Python 3.10 以上を使います。

```bash
cd /home/bouken/project_ken/spla_alert
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

既に依存関係だけ入れたい場合:

```bash
pip install -r requirements.txt
```

## 映像入力の用意

このツールは OpenCV で読める入力を扱います。代表的には次のどれかです。

### 1. AverMedia が Ubuntu で `/dev/video*` として見える場合

キャプチャデバイスを確認します。

```bash
spla-alert devices
```

例:

```bash
spla-alert run --source /dev/video0 --width 1920 --height 1080 --fps 60
```

### 2. ReCentral から Ubuntu の RTMP サーバーへ配信する場合

ReCentral 側の配信先を Ubuntu 上の RTMP URL にします。Ubuntu 側で nginx-rtmp などを起動し、ReCentral から以下のような URL に送ります。

```text
rtmp://<UbuntuのIP>/live/splatoon
```

Ubuntu 側の nginx-rtmp 設定例:

```nginx
rtmp {
    server {
        listen 1935;
        chunk_size 4096;

        application live {
            live on;
            record off;
        }
    }
}
```

ReCentral の配信先を分けて入力する画面では、URL を `rtmp://<UbuntuのIP>/live`、ストリームキーを `splatoon` にします。

読み取りは次のようにします。

```bash
spla-alert run --source rtmp://127.0.0.1/live/splatoon
```

別 PC の ReCentral から送る場合は `127.0.0.1` ではなく Ubuntu マシンの LAN IP を指定してください。

### 3. Ubuntu 上に表示されている配信画面を直接読む場合

画面領域を指定してキャプチャできます。

```bash
spla-alert run --source screen:0,0,1920,1080
```

形式は `screen:left,top,width,height` です。配信プレビュー画面だけを指定すると、余計な UI が入りにくくなります。

## 実行

基本実行:

```bash
spla-alert run --source /dev/video0 --width 1920 --height 1080 --fps 60
```

デフォルトで10フレームごとに解析します。出力例:

```text
14:32:10 frame=120 friendly=3/4 enemy=2/4
```

JSON Lines で出したい場合:

```bash
spla-alert run --source /dev/video0 --json-lines
```

プレビュー画面に検出枠を重ねる場合:

```bash
spla-alert run --source /dev/video0 --show
```

`q` または `Esc` で終了します。

## 位置合わせ

画面上部 HUD の位置は解像度や配信レイアウトで少し変わります。まずスナップショットを出してください。

```bash
spla-alert snapshot --source /dev/video0 --output snapshot_overlay.jpg
```

`snapshot_overlay.jpg` を開き、8個の枠が上部のイカ/タコアイコンに重なっているか確認します。ずれている場合は `configs/default.json` をコピーして調整します。

```bash
cp configs/default.json configs/my_capture.json
```

主に調整する値:

- `slot_center_y`: アイコン中心の縦位置。画面高さに対する割合
- `slot_size`: 1アイコンを切り出す正方形サイズ。画面高さに対する割合
- `friendly_slot_centers_x`: 左4人の中心x座標。画面幅に対する割合
- `enemy_slot_centers_x`: 右4人の中心x座標。画面幅に対する割合

調整した設定で実行します。

```bash
spla-alert run --source /dev/video0 --config configs/my_capture.json --show
```

## 判定ロジック

各アイコン枠を HSV 色空間に変換し、楕円マスク内で彩度の高いピクセルが一定以上あれば生存と判定します。デス中の灰色アイコンは彩度が低いため、生存として数えません。

試合ごとに味方色・敵色が変わっても、色そのものを固定していないため動きます。味方と敵の色が必ず異なることは、今後スペシャルやブキ識別を追加するときの追加情報として使えます。

## テスト

```bash
python -m unittest discover
```

## 今後追加しやすい機能

- スペシャル発光判定: 現在の `SlotStatus` に発光スコアを追加
- ブキ認識: 各アイコン中央のブキ部分を切り出し、テンプレートマッチングまたは軽量分類器で判定
- HUD 自動キャリブレーション: 上部中央から8個のアイコン候補を自動探索
