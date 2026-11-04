# 排錯

先跑 `python scripts/h3run.py check`，看三件事：colab 指令在不在、有沒有登入、剩幾點。

## 一定要記得的：沒關的 GPU 會一直扣點
- `h3run.py run` 結束時會自動 `stop`（除非加了 `--keep`），最後還會列出帳號上還開著的 runtime。
- 本機程式被強制中斷、電腦睡著、網路斷掉時，**遠端那台不會自己停**。回來第一件事：
  ```
  python scripts/h3run.py sessions
  python scripts/h3run.py stop --all
  ```
- 對話結束前，確認 `sessions` 是空的。

## 安裝與登入
| 症狀 | 原因與處理 |
|---|---|
| `No module named 'termios'`（Windows） | colab-cli 的互動終端只支援 Linux／macOS。安裝腳本會打補丁；手動處理：重跑 `install/install.ps1` |
| `WebSocketConnectionClosedException: socket is already closed`（Windows） | colab-cli 0.7.5 的問題。安裝腳本固定裝 **0.7.4** |
| `colab` 指令跑起來先去檢查更新、卡住 | `~/.config/colab-cli/settings.json` 寫 `{"enable_update_check": false}`（安裝腳本會寫） |
| 登入後 `redirect_uri_mismatch` | 一定要用 `colab_login.py`（它用 colab-cli 自己的 client 與 redirect），不要自己拼網址 |
| `invalid_grant` | 授權碼只能用一次、幾分鐘內有效：重跑 `colab_login.py url` |
| 換帳號 | 刪掉 `~/.config/colab-cli/token.json` 再登入 |

## 開機
| 症狀 | 處理 |
|---|---|
| 點數夠卻分配不到 GPU | 尖峰時段常見。等幾分鐘再試，或改 L4／G4。**不要改 A100**（貴很多） |
| GPU 名字打錯 | colab-cli 會默默開成 A100。`h3run.py` 只接受 L4、G4、A100、H100 |
| `GPU capability ... cannot run the int8 H3 model` | 拿到 T4（太舊），換 L4 以上 |
| `沒有登入`／`401` | token 過期或被撤銷：重跑登入 |

## 生成
| 症狀 | 處理 |
|---|---|
| 一段影片失敗，其他成功 | 看 `out/results.json` 那一段的 `error`；只重送那一段（可加 `--session` 沿用還開著的機器） |
| 畫面上有燒進去的字幕 | 提示詞太短：照 prompt-guide 寫滿 350–500 字的 `detailed_description` |
| 人不像參考照片 | 提示詞裡的人物描述跟參考圖不一致；照圖寫外觀 |
| 動作很少、像照片在晃 | 動作戲把 `intensity` 調高（low→mid→high） |
| 對話戲表情誇張、人亂動 | `intensity` 改回 `off` |
| 開頭的台詞被吃掉 | 第一句前加短的語氣詞，或那句單獨重錄 |
| 圖片長文字變成亂碼 | P-H3 的已知限制：字放短、用引號 |
| `that job has not produced a file` | `@id` 指向的 job 排在後面或失敗了 |
| 進度一直停在 `models` | 第一次要下載約 50–60 GB，L4 上通常 1–3 分鐘；超過 15 分鐘看 Hugging Face 狀態 |

## 想看遠端的完整紀錄
```
colab exec -s <session> -f <一個只有 print(open('/content/h3job/remote_job.log').read()[-5000:]) 的檔案>
```
ComfyUI 的紀錄在 `/content/comfyui.log`，Toybox 的在 `/content/toybox.log`。

## 檔案回傳
- 預設用 `colab download` 一個一個抓（圖片、短片、配音都很小）。
- **不要**把影片轉成文字印在 log 裡傳回來，會慢幾十分鐘而且一直扣點。
- 檔案很多或很大時：如果你（Agent）本身有連 Google 雲端硬碟，可以讓遠端先把 `out/` 複製到雲端硬碟再用你的連接器取。
  這需要在 Colab 上授權雲端硬碟（`colab drivemount` 會在 VM 上跳出瀏覽器授權，10 分鐘內要完成），所以只在真的需要時才用。

## 參考過的前人經驗
- bockybocky/colab-gpu-runner（MIT）：Windows 上固定 0.7.4＋補丁、短 exec 比長 exec 穩、結束一定檢查殘留 runtime、不要用 log 傳檔。
- Google 的 google-colab-cli（Apache-2.0）：登入流程（client、scope、redirect）照它的 `auth.py`。
