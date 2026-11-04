# 提示詞寫法

**先讀官方指南**（H3 的作者寫的，這份 skill 不轉載，請直接讀固定版本）：
- 參考生成（`mode: ref`、TTS）：`https://raw.githubusercontent.com/MiniMax-AI/MiniMax-H3/d21241f0a4b3acbb34c97dae47fa417b7065e438/.claude/skills/h3-prompt-writing/references/ref-en.txt`
- 頭尾格／純文字（`mode: frames`、`text`）：同一個資料夾的 `base-en.txt`

讀不到的話，下面是最低限度的規則。

## 影片（最重要：寫太短，H3 會在畫面上燒字幕）

- **本文用英文**，`detailed_description` 寫 **350–500 個英文字**：鏡位、光線、背景、每個人的動作和反應要寫滿整段秒數。
- **台詞**照原文放進 `<d>[Mandarin] 台詞。</d>`（台語、英文就換語言標籤），每句結尾要有 `。？！`。
- 素材用 `@圖片1`、`@圖片2`、`@音訊1` 點名（程式會換成 `<Picture N>`／`<Audio N>`），N＝在 `inputs` 裡同類素材的順序。
- 多鏡頭：`[Shot 1]` 不寫時間，之後 `[Shot 2] At 00:04.000, ...`，全部要落在秒數之內。
- **人物要照參考圖描述**（髮型、衣服、年紀）。提示詞跟參考圖對不上時，H3 會不理參考圖。
- 只描述會被看見、聽見的東西；情緒用表情和身體寫出來（「嘴角一邊上揚、眼睛瞇起」），不要只寫「她很生氣」。
- 有空間的動作戲：先想好**誰從哪裡進場、軸線（誰在左誰在右）、從哪裡離開**，再寫。

參考生成（`ref`）的六段：
```
subject_definitions:
<Subject 1> is the girl from <Picture 1>, long black hair in a low ponytail, black blazer ...
<Picture 2> is the library location reference (architecture and light only).
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).        ← 有參考聲音時

summary:
[reference generation] ...一兩句講這段在演什麼...

retention_analysis:
<Subject 1> (appears in [Shot 1]): fully_preserved - ...
<Picture 2>: location reference - ...

detailed_description:
The target video is ...
[Shot 1] ... <Subject 1> (S1) whispers, <d>[Mandarin] 有人在那裡嗎？</d> ...
[Shot 2] At 00:05.000, ...

overall_soundscape:
...環境音、動作聲（不寫音樂）...

non_diegetic_music:
...一句配樂描述，或 N/A...
```
在 manifest 裡，`subject_definitions` 那行的 `<Picture 1>` 寫成 `@圖片1` 也可以，兩種都會被接上。

### 延伸（`extend`）
- 程式會自動把上一段的**最後一格**當成新的參考圖，並告訴 H3「從這裡接著演」。
- 提示詞只寫**接下來發生什麼**，開頭的姿勢和位置要跟上一段結尾一致。
- 延伸的那一段 `inputs` 還是要放角色照（臉才不會跑掉）。

## 圖片（P-H3-Image）
- 寫成**一段 60–140 個英文字的畫面描述**：圖片種類與構圖 → 主體（外觀、衣服、姿勢、看得見的表情）→ 地點與光線 → 必要的風格細節。
- 不要寫 `masterpiece`、`8k`、`best quality` 這種詞，會變差；也不要寫超長。
- 編輯：第 1 張是被改的圖，用 `@圖片1`、`@圖片2` 點名；先說**改什麼**，再說**什麼不能變**（臉、髮型、衣服、背景）。
  例：`Make the person in @圖片1 burst out laughing: eyes squeezed shut, mouth wide open, head tilted back. Keep the face, hair, outfit and background.`
- 用字要精準：寫「浮起青筋」它可能畫成傷口；寫「太陽穴的血管微微突起」比較安全。
- 畫面裡的字只放短的，用引號包起來。

## TTS（32×32，只要聲音）
TTS 用的也是參考生成的六段，只是畫面會被丟掉，**結構還是要完整**。範例：
```
subject_definitions:
<Subject 1> is a seven-year-old boy with short black hair.
<Subject 2> is an adult woman with long dark hair.
<Audio 1> is the voice-timbre reference for <Subject 1> (S1).

summary:
[reference generation + audio reference] A field of red spider lilies at night. A frightened boy meets a calm woman.

retention_analysis:
<Subject 1> (appears in [Shot 1], [Shot 2]): fully_preserved - ...
<Audio 1>: reference - its vocal timbre guides the dialogue delivery of <Subject 1> without copying the original signal.

detailed_description:
The target video is a quiet, misty night scene.
[Shot 1] <Subject 1> (S1), his voice high-pitched and trembling, asks, <d>[Mandarin] 嗯……你、你是什麼人？</d>
[Shot 2] At 00:04.000, <Subject 2> (S2) answers gently and slowly, <d>[Mandarin] 別怕，我不會傷害你。</d>

overall_soundscape:
Low wind, faint rustling of dry plants.

non_diegetic_music:
N/A
```
規則：
- 說話的人寫成 `<Subject N>`，**一定要寫出性別和年紀**（boy／girl／woman／man／elderly），不然聲音會亂猜。
- 每句都寫語氣（音量、速度、情緒）；台詞一字不改放進 `<d>`。
- 中文約**每秒 4 個字**；`seconds` 要留一點呼吸空間。一段最多 3 個說話的人。
- H3 偶爾會**吃掉一段開頭的前幾個字**：第一句前面加一個短的語氣詞（「嗯……」「唉……」），之後剪掉就好。
- 要固定某個角色的聲音：第一次先不用參考聲音、照描述生成一句，挑一條滿意的，之後都把它放 `voices` 當 `<Audio 1>`。
