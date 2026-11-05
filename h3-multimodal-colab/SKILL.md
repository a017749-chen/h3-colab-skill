---
name: h3-multimodal-colab
description: Generate pictures, talking videos, video extensions and voice (TTS) with MiniMax H3 on the user's own Google Colab GPU, driven entirely from this computer through google-colab-cli. Use when the user asks to 生圖／改圖／生成影片／延伸影片／配音／TTS／讓角色說話／把分鏡生出來, or wants storyboard frames, clips or voice lines made with H3 — including when you yourself have no image or video tool. Also for a whole film from the user's own script (拍片／腳本拍片／分鏡腳本／教學影片／招生影片／OSCE 示範影片／短劇, consistent characters and scenes, reviewed 2 minutes at a time) through scripts/h3movie.py, and for AI-movie's MV, subtitle and YouTube tools in mvkit/. Runs on Google Colab (needs Google AI Pro; the user's computer needs no GPU) or, if the user prefers, on their own ComfyUI Desktop (local mode, scripts/h3local.py).
---

# H3 多模態生成（Colab GPU）

一顆 MiniMax H3 模型，在使用者自己的 Colab GPU 上生成：

| 種類 | 做什麼 | 底層 |
|---|---|---|
| `image` | 文生圖；或拿最多 8 張圖編輯（換表情、換衣服、換畫風、把人放進場景） | P-H3-Image（掛在同一顆 H3 上的 LoRA） |
| `video` | 參考生成（角色照／場景圖／聲音當參考）、頭尾格、純文字，2–15 秒，有聲音 | H3 Ref2VA／FL2VA |
| `video` + `extend` | 接著上一段影片往下演，成品自動接回原片 | Motion Context |
| `tts` | 配音：設計聲音，或拿一段聲音當音色參考說新台詞 | H3 32×32（只解碼聲音） |
| 整部片 | 使用者自己的腳本＋角色表＋參考圖 → 一段段生成、每 2 分鐘審核、合成全片 | `scripts/h3movie.py`（AI-movie 的規劃器）→ 上面的 `video` |

你（大模型）負責**理解需求、寫提示詞、組工作清單、檢查成果**；生成全部在 Colab 上跑。
所以就算你自己不能生圖，也能照這份 skill 把整套分鏡、影片、配音做完。

---

## 0. 第一次使用：先問在哪裡跑

**第一件事先問使用者**：「要在 Google Colab 上跑，還是用你自己電腦上的 ComfyUI Desktop（本地）？」
- 本地要提醒：**ComfyUI Desktop 要先自己安裝好並打開**（https://comfy.org/download），而且需要 NVIDIA 顯示卡、
  16 GB 以上顯示卡記憶體、約 50 GB 硬碟。沒有就用 Colab。
- 沒回答、或沒有符合條件的顯示卡 → **Colab**。
- 選了就記住，之後每批照用。使用者中途說「改用本地／改回 Colab」就換。

### 本地版（ComfyUI Desktop）
完整說明：https://github.com/dseditor/h3-colab-skill/blob/main/localguide.md 。和 Colab 版同一份 manifest、同一套提示詞規則，差別只有：
沒有 colab-cli、不用登入、不用等 GPU、沒有 15 分鐘保留與關機；影片預設 **480P**。
```
python scripts/h3local.py check            # ComfyUI 開了沒、缺哪些模型與節點
python scripts/h3local.py setup            # 第一次：下載缺的模型（約 50 GB）、節點組、H3 Toybox
python scripts/h3local.py run h3job/manifest.json [--confirmed]
```
- 模型放 `C:\Users\<使用者>\ComfyUI-Shared\models`（ComfyUI Desktop 的預設）；放別處加 `--models-dir`。
- `setup` 裝了新節點時，照它印出的指令裝節點套件，請使用者**重開 ComfyUI Desktop**，再 `check`。
- 可攜版 ComfyUI 回報不出自己的位置：加 `--comfy-dir <ComfyUI 資料夾>`。
- **監看**：`run` 每 10 秒印進度，做好一個就放進 `out/`；你也可以直接看 `http://127.0.0.1:8188/queue`。
- 下面第 1 節的流程照走，只是第 6 步換成 `h3local.py run`，第 8 步不用問保留 GPU。

### Colab 版：先跟使用者說清楚，再安裝

如果 `python scripts/h3run.py check` 找不到 colab 或還沒登入，**先停下來**，用使用者的語言說明這五件事，等對方說「好」才開始：

1. **會做什麼**：在使用者的 Google 帳號開一台 Colab GPU，裝 ComfyUI＋H3，生成完把檔案下載回這台電腦，然後**關掉那台 GPU**。
2. **要什麼訂閱**：至少 **Google AI Pro**（附 Colab 運算單元）。Plus 不夠。在 Colab 右上角「資源」可以看剩多少點。
3. **花多少點**：L4 約每小時 1.5 點（≈ RTX 4060，練習用），G4 約每小時 11 點（≈ RTX Pro 6000，快）。每次開機要先裝環境＋下載約 50 GB 模型（加生圖約 60 GB），Colab 網路快，大約 3–5 分鐘；之後每段影片 L4 約數分鐘。
4. **會從哪裡抓什麼**：GitHub 的 ComfyUI、3 個節點組、H3 Toybox；Hugging Face 的 H3 模型（Comfy-Org、OliviaRossi PRISM、PrunaAI P-H3-Image、dseditor 鏡像的 LoRA）。**全部下載到 Colab 上，不佔這台電腦的空間。**
5. **何時要登入**：只有第一次。你會給他一個 Google 網址，他用**有 AI Pro 的帳號**登入、按允許，把頁面上的授權碼貼回對話。token 存在 `~/.config/colab-cli/token.json`，之後不用再登入。

說明完、使用者同意安裝後，再問兩個選擇（**沒有回答就用預設**），記住他的答案，之後每批照用：
- **要不要安裝生圖？**（預設：**不裝**。使用者已經有別的生圖工具時就不需要；裝的話每次開機多下載約 10 GB）
  要的話，之後的 `h3run.py run` 都加 `--with-pictures`。沒裝的時候，批次裡有圖片工作仍會自動下載，但先問過使用者。
- **要用更快的 G4 嗎？**（預設：**L4**。G4 約每小時 11 點，L4 約 1.5 點）
  選 G4 時要告訴使用者：**影片預設會是 720P**（L4 預設 480P）。

安裝：照 repo 的 `INSTALL_FOR_AGENTS.md`（裝 uv → google-colab-cli 0.7.4 → Windows 補丁 → 放好這個 skill）。
登入：
```
python scripts/colab_login.py url          # 把網址給使用者
python scripts/colab_login.py code <授權碼>  # 使用者貼回來之後
python scripts/h3run.py check              # 看到剩餘運算單元＝成功
```

---

## 1. 每次生成的流程

1. **問清楚要什麼**（或從使用者給的分鏡、劇本裡讀出來）：幾張圖、幾段影片、哪些台詞、誰的臉、什麼比例。
2. **準備輸入檔**：角色照、場景圖、參考聲音放進一個工作資料夾，例如 `h3job/inputs/`。
3. **寫提示詞**：照 `references/prompt-guide.md`。影片一定要寫完整的英文六段式（短提示詞會讓 H3 在畫面上燒字幕）。
4. **寫 `manifest.json`**：格式見 `references/manifest.md`。整批一次送，不要一個一個開機。
5. **確認規格與花費**：
   - **兩支以上的影片，一定要先跟使用者確認規格**：解析度（480P／720P）、直式或橫式（9:16／16:9）、每段秒數。
     長任務生成時間很長，規格錯了要整批重來。`h3run.py` 在兩支以上影片時**沒有 `--confirmed` 不會開機**，
     它會先印出這批的摘要（數量、總秒數、解析度、比例、L4 的時間估計），把那段摘要給使用者看，確認後再加 `--confirmed`。
   - 沒指定解析度時：L4 用 480P、G4 用 720P。
   - 第一次的批次先用 L4、480P、5 秒試一段。
6. **送出**：
   ```
   python scripts/h3run.py run h3job/manifest.json --gpu L4
   ```
   它會開機 → 上傳 → 背景生成 → 每 30 秒回報 → 每完成一個就下載到 `h3job/out/`。
7. **檢查成果**：圖片打開看；影片至少抽幾格看＋聽聲音；有錯就只重做那一個（改 prompt 或 seed）。
8. **回報，並問使用者要不要保留 GPU**：每個檔案的路徑、花了多久、用了哪個 seed；有失敗的說原因。
   做完之後 GPU **先留著 15 分鐘**（模型都還在上面）。一定要問一句：
   「要繼續生成或修改嗎？要的話 GPU 先留著（L4 一小時約 1.5 點）；不用的話我現在關掉。」
   - 要繼續 → 下一批加 `--session <名字>`，不用重新下載模型（省 3–5 分鐘）
   - 要多留一下 → `python scripts/h3run.py keep --session <名字> --minutes 60`（最多 240）
   - 不用了 → `python scripts/h3run.py stop --session <名字>`
   - **使用者沒回答也沒關係**：本機有一個獨立的計時器，15 分鐘沒有新工作就自動關掉，對話結束了也照樣會關。

### 要延伸或補拍時
- 使用者常常看完影片才說「接著往下演」「這段重做」。GPU 還留著的時候，下一批加 `--session <名字>` 沿用，模型不用重新下載。
- 確定只做一次（例如使用者說「做完就關」）：第 6 步加 `--stop-after`。
- 中途失敗、被中斷的批次**一律馬上關機**，不會留著。
- `python scripts/h3run.py sessions` 會列出開著的 GPU 和各自還剩幾分鐘自動關閉。

---

### 使用者給的是一整份腳本時：用腳本拍片模式
腳本超過幾段、要一整部片、角色場景要前後一致、要分批審核 → **不要自己拆段寫 manifest**，照 `references/movie-mode.md`：
```
python scripts/h3movie.py plan --script <腳本> --bible <角色表> --refs <參考圖> --film <工作資料夾>
（你）把 manifest 裡的 <<WRITE …>> 寫成英文 → python scripts/h3movie.py lint --film <工作資料夾>
python scripts/h3run.py run <工作資料夾>/jobs/batch01/manifest.json --gpu L4 --confirmed
python scripts/h3movie.py collect / approve / redo --shots 02 / next / assemble --film <工作資料夾>
```
規劃器替你決定每段送哪些圖、每個分鏡誰入鏡、誰說話（畫內或畫外）、人數與台詞時間，這些是之前人物重複、配音對不上的原因，
manifest 裡規劃好的句子不要改。第 2 節的判準照樣適用（對話與示範 `intensity` 一律 `off`）。

## 2. 任務判準（你要替使用者決定的開關）

### 影片模式
| 情況 | 用 |
|---|---|
| 有角色要說話、對戲、要鎖住臉和衣服 | `mode: "ref"`，角色照＋場景圖放 `inputs`，提示詞用 `@圖片N` 點名 |
| 動作必須落在某個姿勢、換場要精準銜接 | `mode: "frames"`，`first`／`last` 放首格、尾格 |
| 空景、氣氛、快速試想法 | `mode: "text"` |
| 「接著往下演」「再長一點」 | `mode: "ref"` ＋ `extend: "<上一段的 id 或影片檔>"` |

對話和衝突場面**用 ref 最穩**：首格會把還沒進場的人也畫進畫面，參考生成不會。

### 動作強度 `intensity`（預設 `off`）
| 內容 | intensity |
|---|---|
| 對話、文戲、情緒、靜態、產品、風景 | `off`（**平常一律關**：動作 LoRA 會讓人亂動、表情變誇張） |
| 走路、跳舞、轉身、日常移動 | `low` |
| 追逐、跑酷、摔倒、明顯肢體動作 | `mid` |
| 武打、格鬥、怪物戰、爆炸、連續攻防 | `high` |

`intensity` 不是 off 時，會掛上戰鬥、動作修復、速度三顆 LoRA（強度 × 0.6／1.0／1.3）。

### 解析度與長度
- 試拍：`480P`、5 秒。定稿：`720P`。直式短片 `9:16`。
- 一段 2–15 秒；更長就切成多段，或用 `extend` 接。
- 台詞字數 ≈ 秒數 × 4（中文）。超過會講太快或吃字；動作戲可以沒有台詞。

### 圖片
- `size`: `2K` 為預設（P-H3 在 2K 以上最好），要快就 `1.6K`。
- 編輯：`inputs` 第 1 張是**要被改的那張**，其餘是參考，最多 8 張。
- 長段文字畫不好：海報、信件、手機訊息只放短字，引號包起來。

### TTS
- 純配音、旁白、角色台詞、廣播劇。一段 ≤ 15 秒、最多 3 個說話的人。
- 要固定某人的聲音：把他的聲音檔放 `voices`（≤ 3 條，對應 `<Audio 1..3>`）。
- 沒有參考聲音就照描述設計，描述**一定要寫性別和年齡**（「A seven-year-old boy」「An adult woman」）。

---

## 3. 失敗時

先看 `references/troubleshooting.md`。最常見：
- `沒有登入`／token 過期 → 重跑 `colab_login.py url`。
- 點數不足、分配不到 GPU → 換 L4 或晚點再試；**不要**改成 A100（很貴）。
- 某一段生成失敗 → 讀 `out/results.json` 的 error，只重送那一段（可以 `--session` 沿用還開著的機器）。
- 中途斷線 → 先 `h3run.py sessions`，有殘留就 `stop`，再重送。
