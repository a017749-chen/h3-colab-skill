# 腳本拍片模式（長片、每 2 分鐘審核）

使用者有**自己寫好的腳本**（教學影片、招生影片、OSCE 示範、短劇），要一整部片，角色和場景要從頭到尾一致。
規劃、審核、合片在這台電腦（CPU）；生成照常用 `h3run.py`（Colab）或 `h3local.py`（ComfyUI Desktop）。
規劃器是 AI-movie 的 `mvkit`（在 skill 的 `mvkit/`），指令是 `scripts/h3movie.py`。

## 為什麼不直接手寫 manifest

前人跑了三次都出現的兩個問題，規劃器用固定規則擋掉，不靠每次寫提示詞時記得：

| 問題 | 規劃器怎麼擋 |
|---|---|
| 人物重複出現（雙胞胎、多一個人） | 每個分鏡判斷**誰入鏡**，只送入鏡者的角色圖；寫明「畫面上剛好 N 人、每人只出現一次」；場景圖只當地點參考；三視圖預設不送 |
| 配音對不上、嘴型跑到別人臉上 | 特寫手部時台詞自動改**畫外音**、說話者以外的人閉嘴、每句台詞一字不改放進 `<d>`；接片時每段精準裁到影格與取樣點，聲音不會越接越早 |

## 流程

```
python scripts/h3movie.py plan --script <腳本> --bible <角色表> --refs <參考圖資料夾> --film <工作資料夾> [--preset osce_demo|teaching|recruitment] [--aspect 16:9|9:16]
```
1. **先讀 `<film>/plan.md` 給使用者看**：腳本規格、角色／場景對齊、參考圖檢查、每段送哪些圖、每個分鏡誰入鏡、誰說話（畫內／畫外）。
   入鏡或說話者不對 → 在腳本那個分鏡加 `出場：考生、病人`，或把台詞標成 `（考生畫外）`，重跑 `plan`。
   參考圖檢查有警告（三視圖、合照、場景圖有人、圖太小）→ 先請使用者換圖，這是人物重複最常見的原因。
2. **寫提示詞**：打開 `<film>/jobs/batchNN/manifest.json`，把每個 `<<WRITE …>>` 換成英文（規則見下一節）。其他句子是規劃出來的，**不要改**。
3. **檢查**：`python scripts/h3movie.py lint --film <film>`，有 ❌ 就改到沒有。
4. **送出**：照 SKILL.md 第 1 節（兩支以上影片先跟使用者確認規格，再加 `--confirmed`）：
   `python scripts/h3run.py run <film>/jobs/batchNN/manifest.json --gpu L4 --confirmed`
5. **收片與自動檢查**：`python scripts/h3movie.py collect --film <film>` → 這一批的預覽影片、抽幀檢視圖、審核表（自動檢查結果在最上面）。
   把三個檔案給使用者看。自動檢查要 `ffmpeg`；台詞比對要 `faster-whisper`，人臉數要 `opencv-python`，沒裝就略過該項。
6. **審核**：使用者說可以 → `approve`；某幾段不行 → `redo --shots 02,03`（換新 seed，舊片段保留比較）。
   要改畫面或台詞就改腳本，重跑 `next`，被改到的段落自動重拍，沒改的提示詞會保留。
7. **下一批**：`python scripts/h3movie.py next --film <film>`，回到第 2 步。前一批沒確認，下一批不會產生。
8. **全片**：全部確認後 `python scripts/h3movie.py assemble --film <film>` → `final/` 裡的乾淨版、燒字幕版、`.srt`、`.ass`、檢視圖。
   成品只有一條視訊軌和一條音訊軌（程式會驗證）。

`status --film <film>` 隨時看每批狀態。GPU 還留著時，下一批加 `--session <名字>` 沿用。

## `<<WRITE …>>` 怎麼寫

每個欄位後面附了腳本原文（多半是中文），照它寫成英文：

- **summary**：一兩句英文，這段在演什麼。
- **每個 `[Shot k]` 的描述**：照欄位寫的字數。寫鏡位與運鏡、光線、每個人做什麼、怎麼反應；只寫看得見、聽得見的。
  人的外觀不要重寫（已在 `subject_definitions`），用 `<Subject N>` 稱呼。特寫手部的分鏡**不要寫臉**。
- **overall_soundscape**：環境音、動作聲，不寫音樂。後面那句「Only … speaks」保留。
- **non_diegetic_music**：一句配樂描述；腳本沒有配樂就保留 `N/A`。

`lint` 會擋：沒寫完的 `<<WRITE`、`<d>` 以外還有中文（H3 會燒字幕）、台詞不見或被改、提到不存在的第 N 張圖、
`[Shot]` 數量不對、`detailed_description` 少於 250 個英文字（建議 350–500）。台詞每秒超過約 4.5 字會提醒。

## 腳本格式（條列，不用表格）

```
段落 2（10–20 秒｜參考圖）：綁壓脈帶
場景：病床旁
分鏡 2-1｜中景｜3 秒
- 色調打光：冷白日光燈，均勻柔和
- 畫面描述：考生協助病人把右上臂衣袖捲起
- 旁白對白：（對病人）「我先幫您把袖子捲起來。」
- 音效配樂：衣物摩擦聲
分鏡 2-2｜特寫｜4 秒
- 出場：考生
- 畫面描述：壓脈帶下緣置於肘窩上方約兩到三公分
- 旁白對白：（考生畫外）「壓脈帶下緣在肘窩上兩到三公分。」
```
- 一個**段落**＝一支 H3 影片（10 秒至少 3 個分鏡，或 15 秒至少 6 個），段內切鏡；段落最長 14.65 秒（尾端留 0.35 秒裁掉）。
- 生成模式寫在段落標題：`參考圖`（預設）、`首幀`、`首尾幀`（另寫 `首幀圖：kf_03_first.png`、`尾幀圖：…`）。
- `出場：` 指定入鏡的人（`無`＝空景、`同上`＝沿用上一個分鏡）；沒寫就從畫面描述與說話者推斷。
- `（對病人）` 決定說給誰聽；`（考生畫外）`、`（考生OS）` 是畫外音。
- `.md` 分鏡表格、`.json`、`.docx`、AI Studio 匯出檔、舊的「分鏡 1：場景／畫面／對話」寫法也讀得懂。

## 角色／場景設定表（bible.md）

```
## 角色
| 代號 | 名稱 | 等級 | 別名 | 外觀 | 參考圖 | 其他參考圖 | 位置 | 聲音 | 主講 |
| examinee | examinee doctor | 主要 | 考生, 醫師 | Taiwanese man in his mid twenties, short black hair, white short coat | char_examinee.png | | left of the bed | a calm young male voice in Taiwan Mandarin | 是 |

## 場景
| 代號 | 名稱 | 別名 | 描述 | 參考圖 | 角色 |
| bedside | OSCE skills room bedside | 病床旁, 床邊 | Bright skills room, hospital bed on the right | scene_bedside.png | examinee, patient |
```
- **外觀、位置、聲音用英文**（它們會原樣進提示詞）；別名用腳本裡的稱呼。
- `聲音` 每段都一樣，聲音才不會換人；`主講` 的人說 `（口述）`、`（對病人）` 的台詞。
- 沒有設定表時，`--refs` 裡的 `char_<名字>.png`、`scene_<名字>.png` 會自動建立角色和場景（外觀要靠圖）。

## 參考圖規則（plan 會自動檢查）

- **角色圖**：一個人、正面、單一角度、直幅半身、素色背景、短邊 ≥ 768 px。**不要三視圖、不要合照。**
- **場景圖**：**沒有人**的空景（實際教室照片最穩）。
- 不同角色不要共用同一張圖。
- 沒有圖時可以先用 skill 的 `image` 工作生成角色定裝照與空景（SKILL.md），挑好再放進 `--refs`。

## AI-movie 的其他工具（同一個 `mvkit`）

這些跟 H3 生成無關，從 AI-movie 一起搬進來，需要時從 skill 資料夾執行（`python -m mvkit.<模組>`，或照 repo 的 `movie/docs`）：

| 模組 | 做什麼 |
|---|---|
| `render_mv`、`epic`、`audio/*`、`qc/mouth`、`qc/zoom`、`qc/align`、`bokeh_still`、`matte_video`、`group_still` | MV：歌曲節拍與情緒剪輯、動態字幕、對嘴片段檢查與合成 |
| `aip_runner`、`make_jobs`、`feature_jobs`、`credits` | AutoIP 雲端生成（另一個服務，需要它的帳號與額度） |
| `youtube_upload`、`youtube_playlists`、`youtube_api`、`thumbkit` | YouTube 上傳、播放清單整理、縮圖 |
| `subtitles`、`colab_pipeline` | 字幕對齊與燒錄、接片（拍片模式的 `assemble` 用的就是它） |
| `h3_colab_runner` | 舊的 Colab Notebook 直接驅動 ComfyUI 的版本（repo 的 `movie/AI_Movie_Maker_Colab.ipynb` 用）；skill 流程不用它 |

完整說明在 repo 的 `movie/docs/zh-TW/`（`EDU_VIDEO_WORKFLOW.md`、`ARCHITECTURE_REVIEW.md`、`WORKFLOW.md`、`PUBLISHING.md`…）。
