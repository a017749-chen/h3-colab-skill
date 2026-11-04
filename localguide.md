# 本地版：用自己的顯示卡跑（ComfyUI Desktop）

同一個 skill、同一份 `manifest.json`，改成在**你自己的電腦**上生成：
AI 一樣負責寫提示詞、組工作清單、檢查成果；生成交給你電腦上的 ComfyUI Desktop（`127.0.0.1:8188`）。

和 Colab 版的差別只有**模型與節點裝在哪裡**：

| | Colab 版（`h3run.py`） | 本地版（`h3local.py`） |
|---|---|---|
| GPU | 租 Colab 的 L4／G4，扣運算單元 | 你自己的顯示卡，不扣點 |
| 要裝什麼 | colab-cli、登入一次 | **ComfyUI Desktop**（自己先裝好）＋模型＋3 個節點組 |
| 模型 | 每次開機下載到 Colab（3–5 分鐘） | **只下載一次**，放在 `C:\Users\<你>\ComfyUI-Shared\models` |
| 等 GPU | 尖峰時段可能分配不到 | 不用等 |
| 做完 | GPU 留 15 分鐘，再自動關機 | 沒有這件事，ComfyUI 開著就能一直做 |
| 影片預設 | L4 480P／G4 720P | **480P** |

## 需要什麼

- **ComfyUI Desktop**：https://comfy.org/download 。**請先自己安裝好、打開一次**（AI 不會替你裝這個）。
- **顯示卡**：NVIDIA，**16 GB 以上**的顯示卡記憶體（24–32 GB 比較從容）。不到 16 GB 請用 Colab 版。
- **硬碟**：約 **50 GB**（加生圖再約 10 GB）。
- **Git**：用來下載節點組與 H3 Toybox。

## 給 AI 的一句話

已經裝好 skill 的話，直接說：

```text
我想改用自己電腦上的 ComfyUI Desktop 來生成（不用 Colab）。請照 h3-multimodal-colab 的 localguide.md 幫我檢查缺什麼、裝好模型與節點，之後的生成都在本地跑並幫我監看。
```

還沒裝 skill 的話，先照 [README](README.md) 的一行安裝（本地版用不到 Colab 登入，安裝時跟 AI 說「我只用本地版」就好）。

## AI 會做的事（指令）

```
python <skill>/scripts/h3local.py check            # ComfyUI 有沒有開、缺哪些模型與節點
python <skill>/scripts/h3local.py setup            # 下載缺的模型、節點組、H3 Toybox（只有第一次）
python <skill>/scripts/h3local.py run h3job/manifest.json   # 生成，檔案放進 h3job/out/
```

1. **check**：連 `127.0.0.1:8188`，回報 ComfyUI 版本、顯示卡、缺的模型與節點。ComfyUI 沒開會叫你先打開。
2. **setup**：
   - 模型下載到 `C:\Users\<你>\ComfyUI-Shared\models\<資料夾>`（ComfyUI Desktop 的預設共用模型資料夾；
     你放在別處就加 `--models-dir <路徑>`）。已經有的不會重抓——判斷方式是**直接問 ComfyUI 它看得到哪些檔案**，
     放在任何 ComfyUI 認得的資料夾都算。
   - 節點組：ComfyUI 已經認得全部節點就**跳過**（避免同一組節點裝兩次）；缺的才裝到 ComfyUI 的 `custom_nodes`，
     接著它會印出一行「用 ComfyUI 自己的 Python 安裝節點套件」的指令，跑完**重新啟動 ComfyUI Desktop**，再 `check` 一次。
   - H3 Toybox（生成引擎）與提示詞技能庫放在 `~/.config/h3skill/local/`。
3. **run**：和 Colab 版同一份 manifest。兩支以上影片一樣要先跟你確認規格（`--confirmed`）。
   每 10 秒回報一次進度，做好一個就放進 `out/`，最後寫 `out/results.json`。

## 要下載的東西

模型（約 50 GB）：

| 資料夾 | 檔案 | 來源 |
|---|---|---|
| `diffusion_models` | `Minimax-h3_Singularity_x_10Eros-Max_PRISM_int8.safetensors` | OliviaRossi/Minimax-h3_Singularity-x-10Eros-Max_PRISM |
| `text_encoders` | `qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors` | Comfy-Org/MiniMax-H3 |
| `vae` | `minimax_h3_video_vae_int8_convrot.safetensors`、`minimax_h3_audio_vae_fp32.safetensors` | Comfy-Org/MiniMax-H3 |
| `loras` | `pika_h3_flex_ref2va_v1_bf16.safetensors` | Comfy-Org/MiniMax-H3 |
| `loras` | turbo／MysticXXX／H3_Combat_V2／Motion_Repair／H3_SPEED_slider | dseditor/minimax-h3-studio-assets |
| `semantic_bridge/t8_compat` | `BUNNY_H3_ActionLogic_Bridge_V1_T8_Compat.safetensors` | dseditor/minimax-h3-studio-assets |
| `latent_upscale_models` | `minimax_h3_latent_upscaler_3d_fp16_V2.safetensors` | dseditor/minimax-h3-studio-assets |

生圖（選用，`setup --with-pictures`，約 10 GB）：PrunaAI/P-H3-Image-Comfy 的 LoRA、文字編碼器、圖片 VAE。

節點組（3 個）：[minimax-h3-audio-T8](https://github.com/T8mars/comfyui-minimax-h3-audio-T8)、
[comfyui-SelfLift](https://github.com/facok/comfyui-SelfLift)、
[ComfyUI-H3-Motion-Context](https://github.com/NikoDemon80/ComfyUI-H3-Motion-Context)。
圖片生成要較新的 ComfyUI（有 `PH3ImageConditioning` 節點）：`check` 說缺它時，先把 ComfyUI Desktop 更新到最新版。

完整清單以 `remote/remote_job.py` 的 `BASE_MODELS`／`PICTURE_MODELS`／`NODES` 為準（本地版與 Colab 版共用同一份）。

## 排錯

| 症狀 | 處理 |
|---|---|
| `127.0.0.1:8188 沒有回應` | 打開 ComfyUI Desktop，等它完全載入再試 |
| `找不到 ComfyUI 的資料夾` | 可攜版 ComfyUI 不會回報自己的位置：加 `--comfy-dir <有 input、custom_nodes 的那一層>` |
| `ComfyUI 不認得這些節點` | 節點組沒裝好、或裝了還沒重開 ComfyUI；`PH3ImageConditioning` 缺＝ComfyUI 太舊 |
| 顯示卡記憶體不足 | 降到 480P、縮短秒數；關掉其他吃顯示卡的程式；還是不行就用 Colab 版 |
| `H3 Toybox 沒有啟動` | 看 `~/.config/h3skill/local/toybox.log`；Toybox 用 ComfyUI 自己的 Python 跑（需要 `av`、`Pillow`） |
| 某一段失敗 | 看 `out/results.json` 那一段的 `error`，只重送那一段（做好的會自動跳過） |

完整的執行紀錄在 manifest 旁邊的 `.h3local/runner.log`。

## 實測（2026-11-05，RTX 5090）

| 工作 | 時間 |
|---|---|
| 配音 6 秒 | 14 秒 |
| 影片 3 秒、480P、9:16、純文字 | 25 秒 |
