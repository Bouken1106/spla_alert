# spla_alert

Splatoon の配信画面から、画面中央上部の味方4人・敵4人のイカ/タコアイコンを読み取り、生存人数をリアルタイムに数えるツールです。

現在の実装範囲:

- 10フレームごとに上部 HUD を解析
- 味方最大4人、敵最大4人をカウント
- 生存アイコンは色付き、デス中アイコンは灰色として判定
- 中央のブキ表示やスペシャル発光の白っぽいハイライトを避けるため、アイコン外周寄りの色成分を優先して判定
- Xマーク付きのデス/切断アイコンは、ブキ色が残っていてもデス扱い
- アイコンサイズの変化に対応するため、各枠を相対座標で切り出し、見えている領域内の色比率も使って判定
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

おすすめの順番は次の通りです。

1. AverMedia が Ubuntu で `/dev/video*` として直接見えるなら、それを読む
2. ReCentral を別 PC で使うなら、ReCentral から Ubuntu の RTMP サーバーへ配信して、その URL を読む
3. Ubuntu 上に ReCentral や配信プレビュー画面を表示できるなら、画面領域を直接読む

### 1. AverMedia が Ubuntu で `/dev/video*` として見える場合

キャプチャデバイスを確認します。

```bash
spla-alert devices
```

例:

```bash
spla-alert run --source /dev/video0 --width 1920 --height 1080 --fps 60
```

AVerMedia のUVC入力で 1080p60 が不安定な場合は、MJPG を明示すると安定することがあります。

```bash
spla-alert run --source /dev/video0 --width 1920 --height 1080 --fps 60 --fourcc MJPG
```

`/dev/video*` や RTMP/RTSP 入力では、OpenCV の入力バッファを小さくして遅延を減らすため、デフォルトで `--buffer-size 1` を指定した扱いになります。環境によって映像が不安定な場合だけ値を大きくしてください。

### 2. ReCentral から Ubuntu の RTMP サーバーへ配信する場合

ReCentral 側の配信先を Ubuntu 上の RTMP URL にします。Ubuntu 側で nginx-rtmp や MediaMTX などの RTMP サーバーを起動し、ReCentral から以下のような URL に送ります。

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

Ubuntu の IP は Ubuntu 側で確認します。

```bash
hostname -I
```

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

Ubuntu の Wayland セッションでは画面キャプチャが制限されることがあります。その場合はログイン画面で Xorg セッションを選ぶか、RTMP / `/dev/video*` 入力を使ってください。

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

10フレーム以外の間隔で処理したい場合:

```bash
spla-alert run --source /dev/video0 --every 5
```

動作確認だけしてすぐ止めたい場合:

```bash
spla-alert run --source /dev/video0 --max-frames 300
```

## 位置合わせ

画面上部 HUD の位置は解像度や配信レイアウトで少し変わります。まずスナップショットを出してください。

```bash
spla-alert snapshot --source /dev/video0 --output snapshot_overlay.jpg
```

`snapshot_overlay.jpg` を開き、8個の枠が上部のイカ/タコアイコンに重なっているか確認します。ずれている場合は `configs/default.json` をコピーして調整します。

判定の詳細を見たい場合は、JSON と各アイコンの切り出しも保存できます。

```bash
spla-alert snapshot \
  --source /dev/video0 \
  --output snapshot_overlay.jpg \
  --json-output snapshot_result.json \
  --crops-dir snapshot_slots
```

`snapshot_result.json` には各スロットの色付きピクセル比率、見えている領域、支配的な色相などが入ります。`snapshot_slots/` には `friendly_1_alive.jpg` のような名前で8個の切り出し画像が保存されます。枠位置やしきい値の調整時は、この2つを見ながら変更してください。
`x_mark_score` と `x_mark_min_line_ratio` は、灰色/白のXマークらしさを示すデバッグ値です。

```bash
cp configs/default.json configs/my_capture.json
```

主に調整する値:

- `slot_center_y`: アイコン中心の縦位置。画面高さに対する割合
- `slot_size`: 1アイコンを切り出す正方形サイズ。画面高さに対する割合
- `friendly_slot_centers_x`: 左4人の中心x座標。画面幅に対する割合
- `enemy_slot_centers_x`: 右4人の中心x座標。画面幅に対する割合
- `saturation_threshold`: 色付き判定に使う HSV 彩度の下限
- `channel_spread_threshold`: BGR の最大値と最小値の差。灰色誤判定を減らすための下限
- `lab_chroma_threshold`: Lab 色空間の色度下限。彩度だけでは拾いにくい色を補助
- `visible_colored_ratio_threshold`: 明るく見えている領域のうち、色付きとみなす割合
- `inner_ignore_ratio`: 中央のブキ表示をどの程度無視するか。値を大きくすると外周寄りだけを見る
- `x_mark_*`: デス/切断時のXマーク検出。ブキ色が残るアイコンを生存と誤判定する場合に調整

調整した設定で実行します。

```bash
spla-alert run --source /dev/video0 --config configs/my_capture.json --show
```

## 判定ロジック

各アイコン枠を HSV / Lab 色空間に変換し、楕円マスク内で色成分のあるピクセルが一定以上あれば生存と判定します。デス中の灰色アイコンは彩度・色度・BGR チャンネル差が低いため、生存として数えません。

ブキ表示はアイコン中央に重なるため、判定では中央を少し無視して外周寄りを重視します。スペシャル発光は白っぽいハイライトとして入ることがありますが、白は色付きピクセルとして扱わず、残っているチーム色部分で生存判定します。

試合ごとに味方色・敵色が変わっても、色そのものを固定していないため動きます。味方と敵の色が必ず異なることは、今後スペシャルやブキ識別を追加するときの追加情報として使えます。

デス/切断時にXマークが重なる場合は、低彩度で明るい斜め線が2本あるかを追加で見ます。これにより、切断表示などでブキ色が一部残っていても生存として数えにくくしています。

## ネット上の実画像で検証

公開されている Splatoon のスクリーンショットをダウンロードして、期待値と照合できます。ネット接続が必要です。画像そのものは著作権付きのため、リポジトリには含めず、指定した出力先にだけ保存します。

```bash
PYTHONPATH=src python -m spla_alert.cli webtest --output-dir /tmp/spla_alert_webtest
```

editable install 済みなら次でも動きます。

```bash
spla-alert webtest --output-dir /tmp/spla_alert_webtest
```

現在の検証セット:

- Inkipedia の Splatoon 3 リプレイスクリーンショット: `friendly=4/4 enemy=4/4`
- Reddit の上部HUDクロップ: Xマーク付きの左1人をデス扱いし、`friendly=3/4 enemy=4/4`

実行後、`*_overlay.jpg` で枠位置と判定、`*.json` で各スロットの指標を確認できます。

## テスト

```bash
python -m unittest discover
```

editable install せずに作業ツリーから直接テストする場合:

```bash
PYTHONPATH=src python -m unittest discover
```

## 今後追加しやすい機能

- スペシャル発光判定: 現在の `SlotStatus` に発光スコアを追加
- ブキ認識: 各アイコン中央のブキ部分を切り出し、テンプレートマッチングまたは軽量分類器で判定
- HUD 自動キャリブレーション: 上部中央から8個のアイコン候補を自動探索
