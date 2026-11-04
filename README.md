# H3 多模態生成 Skill（Colab GPU）

讓 Claude、Codex（ChatGPT 桌面版）、Hermes 這類 AI，**在你自己的 Google Colab GPU 上**用 MiniMax H3 生成：

- 🖼 **圖片**：文生圖；或拿最多 8 張圖編輯（換表情、換衣服、換畫風、把人放進場景）
- 🎬 **影片**：角色照＋場景圖＋聲音當參考，生成會說話的影片；頭尾格；純文字
- 🧵 **延伸**：接著上一段往下演，自動接回原片
- 🎙 **配音（TTS）**：照描述設計聲音，或拿一段聲音當音色參考說新台詞

AI 負責理解需求、寫提示詞、整理工作清單、檢查成果；生成全部在 Colab 上跑。
**你的電腦不需要顯示卡**，AI 本身不會畫圖也沒關係（例如 Claude 也能把整套分鏡畫完）。

和 [minimax-h3-colab](https://github.com/dseditor/minimax-h3-colab) 的差別：那邊的 H3 Toybox 是**打開 Colab 網頁自己按**；這個是**裝在 AI 底下、完全自動**，AI 自己開機、送工作、收檔案、關機。

---

## 一行安裝（貼給你的 AI）

```text
請照 https://github.com/dseditor/h3-colab-skill/blob/main/INSTALL_FOR_AGENTS.md 幫我安裝 h3-multimodal-colab 這個 skill：開始之前先跟我說明它會做什麼、要什麼訂閱、何時要登入，我同意後再安裝。
```

AI 會先跟你說明，你同意才安裝。安裝完只需要**登入一次**：AI 給你一個 Google 網址，用有 AI Pro 的帳號登入、按允許，把畫面上的授權碼貼回對話。

## 需要什麼

| | |
|---|---|
| 訂閱 | **Google AI Pro**（附 Colab 運算單元，約 400 點／月）。只有 Plus 不夠 |
| 這台電腦 | Windows／macOS／Linux 都可以；會裝 `uv`、Python 3.12 與 Google 的 `google-colab-cli`（獨立環境） |
| AI | 能在你電腦上執行指令的桌面版 AI：Claude Code／Claude 桌面版、Codex（ChatGPT 桌面版）、Hermes… |

| GPU | 相當於 | 每小時 | 400 點約可用 |
|---|---|---|---|
| **L4** | RTX 4060 | 約 1.5 點 | 將近 300 小時 |
| **G4** | RTX Pro 6000 | 約 11 點 | 約 30 小時 |

每次開機要在 Colab 上裝環境＋下載約 50–60 GB 模型。**L4 實測（2026-11-04）**：

| 步驟 | 時間 |
|---|---|
| 開機＋上傳素材 | 約 1 分鐘 |
| 安裝 ComfyUI、節點與 Toybox | 39 秒 |
| 下載模型（含生圖約 60 GB）＋啟動 | 約 3.5 分鐘 |
| 圖片：2 張參考圖編輯、2K（含第一次載入模型） | 112 秒 |
| 影片：參考生成 5 秒 480P | 160 秒 |
| 配音：6 秒，參考聲音的音色 | 17 秒 |
| **整批合計（開機到關機）** | **10.1 分鐘，約 0.5 點** |
所以**一批工作一次送**：分鏡圖、影片、配音可以在同一次開機裡做完（後面的工作可以用 `@id` 接前面的成品）。

## 它怎麼保護你的點數

- 開機前先查剩餘運算單元，不到 5 點不開。
- GPU 只接受 L4／G4／A100／H100（Colab CLI 打錯字會默默開成 A100）。
- 每批有時間上限（預設 120 分鐘）。
- 做完**一定釋放 GPU**，最後再檢查帳號上有沒有殘留的機器。
- 要接著延伸時才保留機器（`--keep`），用完 `h3run.py stop`。

## 檔案

```
h3-multimodal-colab/          ← 裝進 AI 的 skill
  SKILL.md                    流程與判準（影片模式、動作強度、TTS…）
  scripts/h3run.py            本機：檢查、開機、上傳、監看、下載、關機
  scripts/colab_login.py      兩段式登入（AI 給網址 → 你貼授權碼）
  remote/                     在 Colab 上跑：裝環境、下載模型、逐一生成
  workflows/h3_tts32_api.json H3 32×32 配音工作流（只解碼聲音）
  references/                 manifest 格式、提示詞寫法、排錯
install/                      install.ps1（Windows）、install.sh（macOS／Linux）
INSTALL_FOR_AGENTS.md         給 AI 看的安裝步驟
```

## 授權與來源

- 本 repo：MIT。
- 生成引擎是 [H3 Toybox](https://github.com/dseditor/minimax-h3-colab)（同作者）。
- [google-colab-cli](https://pypi.org/project/google-colab-cli/)（Google，Apache-2.0）；登入流程照它的 `auth.py`。
- 模型依各自授權：MiniMax H3（MiniMax H3 Community License，**請先讀**，部分地區另有限制，衍生作品需標示 "Powered by MiniMax H3"）、P-H3-Image（PrunaAI，同上＋Apache-2.0 部分）、各 LoRA 見 [dseditor/minimax-h3-studio-assets](https://huggingface.co/dseditor/minimax-h3-studio-assets)。
- 前人經驗：[bockybocky/colab-gpu-runner](https://github.com/bockybocky/colab-gpu-runner)（MIT）的 Windows 補丁與排錯原則。
- H3 官方提示詞指南不轉載，skill 會請 AI 直接讀官方固定版本。

DSLab 夢想空間實驗室 · 松音
