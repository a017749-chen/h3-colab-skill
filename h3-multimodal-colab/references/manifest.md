# manifest.json

放在工作資料夾裡；`inputs`／`voices`／`first`／`last`／`extend` 的路徑都**相對於 manifest 所在的資料夾**。
成品下載到同一個資料夾的 `out/<id>.<副檔名>`，總結在 `out/results.json`。

```json
{
  "gpu": "L4",
  "stop_on_error": false,
  "jobs": [
    {"id": "cast_lin", "type": "image",
     "prompt": "A clean character sheet photo ...",
     "aspect": "9:16", "size": "2K", "seed": 1},

    {"id": "frame01", "type": "image",
     "prompt": "Edit <Picture 1>. The girl from @圖片1 sits at the reading table of @圖片2 ...",
     "inputs": ["inputs/lin.png", "inputs/library.png"], "aspect": "9:16", "size": "2K"},

    {"id": "shot01", "type": "video", "mode": "ref",
     "prompt": "subject_definitions:\n<Subject 1> is the girl from @圖片1 ...",
     "inputs": ["inputs/lin.png", "inputs/library.png"],
     "seconds": 10, "aspect": "9:16", "resolution": "720P", "intensity": "off", "fast": true},

    {"id": "shot01b", "type": "video", "mode": "ref", "extend": "shot01",
     "prompt": "...", "seconds": 8, "aspect": "9:16", "resolution": "720P", "intensity": "low"},

    {"id": "shot02", "type": "video", "mode": "frames",
     "first": "@frame01", "last": "inputs/end.png",
     "prompt": "...", "seconds": 6, "resolution": "720P"},

    {"id": "line01", "type": "tts", "seconds": 6, "voices": ["inputs/lin_voice.wav"],
     "prompt": "subject_definitions:\n<Subject 1> ...\n<Audio 1> is the voice-timbre reference for <Subject 1> (S1). ..."}
  ]
}
```

## 欄位

| 欄位 | 用在 | 說明 |
|---|---|---|
| `id` | 全部 | 英數、`-`、`_`；也是輸出檔名 |
| `type` | 全部 | `image`／`video`／`tts` |
| `prompt` | 全部 | 見 prompt-guide.md。**素材用 `@圖片N`／`@音訊N`／`@影片N` 點名**，N＝它在 `inputs` 裡同類素材的順序（從 1 開始）；程式會換成 H3 的 `<Picture N>` 並接上 |
| `inputs` | image、video(ref) | 圖片／影片／聲音檔，順序有意義 |
| `aspect` | image、video | `auto`、`9:16`、`16:9`、`1:1`、`4:3`、`3:4`、`21:9` |
| `size` | image | `1K`、`1.3K`、`1.6K`、`2K`（預設）、`2.7K` |
| `mode` | video | `ref`（預設）、`frames`、`text` |
| `first`／`last` | video(frames) | 首格／尾格圖片，至少一張 |
| `extend` | video(ref) | 前面某個 job 的 `id`（同一批），或一支影片檔路徑 |
| `seconds` | video、tts | 2–15 |
| `resolution` | video | `480P`、`720P`、`1080P` |
| `intensity` | video | `off`（預設）、`low`、`mid`、`high`，判準見 SKILL.md |
| `fast` | video | `true`（預設，8 步）／`false`（12 步） |
| `voices` | tts | 參考聲音，≤ 3，對應 `<Audio 1..3>` |
| `seed` | 全部 | 不給就隨機；要重現就固定 |

## 一批的順序與 `@id`
同一批依序執行。任何檔案欄位（`inputs`、`first`、`last`、`voices`、`extend`）都可以寫 `@<id>`，
意思是「**用這一批裡前面那個 job 的成品**」：例如先生 `frame01` 這張圖，再讓 `shot02` 用 `"first": "@frame01"`。
被引用的 job 一定要排在前面而且成功，否則這一段會失敗（其他段照跑）。
這樣「分鏡圖 → 影片 → 配音」整條可以一次開機做完。
