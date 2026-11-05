# -*- coding: utf-8 -*-
"""腳本拍片：your own script + character/scene bible + reference pictures -> a film, 2 minutes at a time.

Planning, review and assembly run on this computer (CPU); generation is an ordinary skill batch run by
h3run.py (Colab) or h3local.py (ComfyUI Desktop). The planner is AI-movie's mvkit (in ../mvkit).

    python scripts/h3movie.py plan --script script.txt --bible bible.md --refs refs/ --film film/ [--preset osce_demo]
        -> film/plan.md (alignment, picture check, generation plan) + film/jobs/batch01/manifest.json (draft prompts)
    (you)  replace every <<WRITE ...>> in that manifest with English prose
    python scripts/h3movie.py lint --film film/              must pass before any GPU time is spent
    python scripts/h3run.py run film/jobs/batch01/manifest.json --gpu L4 [--confirmed]     (or h3local.py run)
    python scripts/h3movie.py collect --film film/           clips -> preview + automatic checks + review checklist
    python scripts/h3movie.py approve --film film/           or: redo --film film/ --shots 02,03
    python scripts/h3movie.py next --film film/              manifest for the next batch (or for the redo shots)
    python scripts/h3movie.py assemble --film film/          final film: one audio track, zh-TW subtitles
    python scripts/h3movie.py status --film film/
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
SKILL = HERE.parent
sys.path.insert(0, str(SKILL))

from mvkit import batches as B                                   # noqa: E402
from mvkit import skill_bridge as SB                              # noqa: E402


def load(film):
    film = Path(film).resolve()
    cfg = SB.FilmConfig.load(film)
    project, report = SB.build_project(cfg, film)
    plan = B.plan_batches(project, float(cfg.batch_minutes) * 60)
    return film, cfg, project, report, plan


def write_plan_md(film, cfg, project, report, plan, batch, notes):
    from mvkit.alignment import format_alignment_report
    from mvkit.qc_review import check_reference_images
    from mvkit.segment_script import check_segments
    from mvkit.presets import PRESETS
    rule = PRESETS.get(project.preset, {}).get("segment_rule", "free")
    spec = check_segments(project, rule) if any(s.beats for s in project.shots) else []
    try:
        pics = check_reference_images(project, cfg.base_dirs())
    except ImportError:          # Pillow is the only extra the planner uses; everything else is stdlib
        pics = ["（沒有安裝 Pillow，略過參考圖檢查；要檢查請 pip install pillow）"]
    total = sum(s.duration_sec for s in project.shots)
    out = [f"# {project.title}：生成計畫", "",
           f"{len(project.shots)} 段、約 {total / 60:.1f} 分鐘、{project.aspect_ratio}、聲音 {project.audio_mode}、"
           f"每批 ≤ {cfg.batch_minutes:g} 分鐘", "",
           "## 腳本規格", *(f"- {x}" for x in spec or ["✅ 段落秒數、分鏡數、4 大模塊與景別都符合"]), "",
           "## 角色／場景對齊", "```", format_alignment_report(project, report), "```", "",
           "## 參考圖檢查（人物重複最常見的原因）", *(f"- {x}" for x in pics or ["✅ 角色圖都是單人單一角度、場景圖沒有人"]), "",
           "## 批次", "```", B.batch_overview(project, film, plan), "```", ""]
    if batch:
        problems = B.preflight_batch(project, batch, cfg.base_dirs())
        out += [f"## {batch.label()}：每段送哪些圖、每個分鏡誰入鏡、誰說話", "```",
                B.format_plan_report(project, batch, cfg.base_dirs()), "```", ""]
        if problems or notes:
            out += ["## 生成前要處理", *(f"- {x}" for x in problems + notes), ""]
        out += ["入鏡或說話者不對 → 在腳本該分鏡加「出場：考生、病人」或把台詞標成（考生畫外），重跑 plan。"]
    (film / "plan.md").write_text("\n".join(out) + "\n", encoding="utf-8")
    return film / "plan.md"


def make_manifest(film, cfg, project, report, plan):
    batch = B.next_batch(project, film, plan)
    if batch is None:
        write_plan_md(film, cfg, project, report, plan, None, [])
        print("🎉 所有批次都已確認：執行 assemble 合成全片。")
        return None
    B.check_gate(project, film, plan, batch)
    if B.batch_status(project, film, batch) == "generated":
        write_plan_md(film, cfg, project, report, plan, batch, [])
        print(f"👀 {batch.label()} 已經生成，等你審核：collect 看結果，再 approve 或 redo。")
        return None
    path, notes = SB.write_batch_manifest(project, film, batch, cfg.base_dirs(), intensity=cfg.intensity)
    md = write_plan_md(film, cfg, project, report, plan, batch, notes)
    errors, _ = SB.lint_manifest(path)
    todo = sum(j["prompt"].count(SB.WRITE) for j in json.loads(path.read_text(encoding="utf-8"))["jobs"])
    print(f"▶ {batch.label()}：{', '.join(batch.shot_ids)}")
    print(f"   計畫：{md}")
    print(f"   manifest：{path}")
    for n in notes + B.preflight_batch(project, batch, cfg.base_dirs()):
        print(f"   ⚠️ {n}")
    if todo:
        print(f"   ✍️ 還有 {todo} 個 <<WRITE …>> 要寫成英文（規則見 references/movie-mode.md），寫完跑 lint。")
    elif errors:
        print(f"   ❌ lint 還有 {len(errors)} 個問題：跑 lint 看細節。")
    else:
        print("   ✅ 提示詞都寫好了：可以送出。")
    return path


def cmd_plan(a):
    film = Path(a.film).resolve()
    cfg = SB.FilmConfig(script=str(Path(a.script).resolve()),
                        bible=str(Path(a.bible).resolve()) if a.bible else "",
                        refs=str(Path(a.refs).resolve()) if a.refs else "",
                        title=a.title or Path(a.script).stem, preset=a.preset, aspect=a.aspect,
                        audio_mode=a.audio_mode, batch_minutes=a.batch_minutes, intensity=a.intensity)
    if (film / SB.FILM_FILE).is_file() and not a.replace:
        old = SB.FilmConfig.load(film)
        if old.__dict__ != cfg.__dict__:
            sys.exit(f"{film} 已經有另一部片的設定（{SB.FILM_FILE}）。換資料夾，或加 --replace 覆蓋設定"
                     f"（已生成的片段仍會依指紋判斷能不能沿用）。")
    cfg.save(film)
    film, cfg, project, report, plan = load(film)
    make_manifest(film, cfg, project, report, plan)


def cmd_next(a):
    make_manifest(*load(a.film))


def manifests(film, batch_no=None):
    root = Path(film).resolve() / "jobs"
    found = sorted(root.glob("batch*/manifest.json"))
    if batch_no:
        found = [p for p in found if p.parent.name == f"batch{int(batch_no):02d}"]
    return found


def cmd_lint(a):
    paths = [Path(a.manifest)] if a.manifest else manifests(a.film, a.batch)[-1:]
    if not paths:
        sys.exit("沒有 manifest：先跑 plan 或 next")
    bad = 0
    for p in paths:
        errors, warnings = SB.lint_manifest(p)
        print(f"== {p}")
        for e in errors:
            print(f"   ❌ {e}")
        for w in warnings:
            print(f"   ⚠️ {w}")
        if not errors:
            print("   ✅ 可以送出：python scripts/h3run.py run " + str(p) + " --gpu L4"
                  + ("（兩支以上影片要先跟使用者確認規格再加 --confirmed）"
                     if sum(1 for j in json.loads(p.read_text(encoding='utf-8'))["jobs"]) >= 2 else ""))
        bad += len(errors)
    sys.exit(1 if bad else 0)


def cmd_collect(a):
    film, cfg, project, report, plan = load(a.film)
    batch = B.next_batch(project, film, plan)
    if batch is None:
        sys.exit("所有批次都已確認。")
    got = SB.collect_batch(project, film, batch)
    missing = [s for s in batch.shot_ids if s not in got and not B.shot_is_generated(
        project, film, next(x for x in project.shots if x.shot_id == s))]
    print(f"▶ {batch.label()}：收到 {len(got)} 段" + (f"；還缺 {', '.join(missing)}" if missing else ""))
    if missing:
        print("   還缺的段落：看 jobs/batchNN/out/results.json 的 error，修好後只重送那幾段（h3run.py 會跳過已完成的）。")
        return
    if not shutil.which("ffmpeg"):
        print("   ⚠️ 沒有 ffmpeg：跳過預覽與自動檢查；請直接看 raw_clips/ 的片段後 approve 或 redo。")
        return
    preview = B.assemble_batch_preview(project, batch, film, base_dir=Path(cfg.refs) if cfg.refs else None,
                                       burn_subtitles=not a.no_subtitles, qc=not a.no_qc)
    print(f"   預覽：{preview.get('subtitled_mp4') or preview.get('clean_mp4')}")
    print(f"   抽幀檢視圖：{preview.get('review_sheet')}")
    print(f"   審核表：{preview.get('checklist')}")
    for sid, issues in (preview.get("qc") or {}).items():
        for x in issues:
            print(f"   🔎 {x}")
    print("   ➜ 看完預覽：approve，或 redo --shots <鏡號>。")


def cmd_approve(a):
    film, cfg, project, report, plan = load(a.film)
    batch = B.next_batch(project, film, plan)
    if batch is None:
        sys.exit("所有批次都已確認。")
    B.approve_batch(project, film, batch, note=a.note or "")
    print(f"✅ 已確認 {batch.label()}")
    nb = B.next_batch(project, film, plan)
    print(f"➜ 下一步：next 產生 {nb.label()} 的 manifest" if nb else "➜ 全部確認：assemble 合成全片")


def cmd_redo(a):
    film, cfg, project, report, plan = load(a.film)
    ids = [x.strip() for x in a.shots.replace("，", ",").split(",") if x.strip()]
    chained = B.request_redo(project, film, ids, note=a.note or "")
    print(f"🔁 將重拍：{', '.join(ids)}（已換新 seed，舊片段在 raw_clips/_rejected/）")
    if chained:
        print(f"   提醒：{', '.join(chained)} 從這幾段接續，接點可能不順；要一起重拍就把它們也列進 --shots。")
    print("➜ 下一步：next（只會產生被標記重拍的段落；腳本有改的話也一併重拍）")


def cmd_status(a):
    film, cfg, project, report, plan = load(a.film)
    print(B.batch_overview(project, film, plan))


def cmd_assemble(a):
    from mvkit.colab_pipeline import assemble_movie
    film, cfg, project, report, plan = load(a.film)
    if not B.all_approved(project, film, plan) and not a.allow_unapproved:
        print(B.batch_overview(project, film, plan))
        sys.exit("還有批次沒確認。全部 approve 後再合成，或加 --allow-unapproved。")
    clips = [film / "raw_clips" / f"{s.index:02d}_{s.shot_id}.mp4" for s in project.shots]
    missing = [p.name for p in clips if not p.is_file()]
    if missing:
        sys.exit(f"缺少片段：{missing}")
    m = assemble_movie(project, clips, film / "final", base_dir=Path(cfg.refs) if cfg.refs else None,
                       use_asr_alignment=a.asr, burn_subtitles=not a.no_subtitles)
    print("✅ 全片完成（單一視訊軌＋單一音訊軌已驗證）")
    for k in ("clean_mp4", "subtitled_mp4", "srt_path", "ass_path", "review_sheet"):
        if m.get(k):
            print(f"   {k}: {m[k]}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("plan", help="腳本＋角色表＋參考圖 → 生成計畫與第一批 manifest")
    p.add_argument("--script", required=True, help=".txt / .md / .docx / .json / AI Studio 匯出檔 / project.py")
    p.add_argument("--bible", help="角色／場景設定表（.md / .json）；不給就從 --refs 的 char_*／scene_* 檔名建立")
    p.add_argument("--refs", help="參考圖資料夾（char_*.png 人物、scene_*.png 空景、kf_* 關鍵幀）")
    p.add_argument("--film", required=True, help="這部片的工作資料夾")
    p.add_argument("--title")
    p.add_argument("--preset", default="none", choices=["none", "osce_demo", "teaching", "recruitment"])
    p.add_argument("--aspect", default="16:9", choices=["16:9", "9:16", "1:1"])
    p.add_argument("--audio-mode", default="native_h3_audio",
                   choices=["native_h3_audio", "clip_voiceover", "master_audio"])
    p.add_argument("--batch-minutes", type=float, default=2.0)
    p.add_argument("--intensity", default="off", choices=["off", "low", "mid", "high"],
                   help="動作強度（對話、示範一律 off）")
    p.add_argument("--replace", action="store_true", help="覆蓋這個資料夾原本的設定")
    p.set_defaults(fn=cmd_plan)
    for name, fn, hlp in (("next", cmd_next, "下一批（或重拍段落）的 manifest"),
                          ("status", cmd_status, "各批狀態")):
        q = sub.add_parser(name, help=hlp)
        q.add_argument("--film", required=True)
        q.set_defaults(fn=fn)
    q = sub.add_parser("lint", help="送出前檢查提示詞")
    q.add_argument("--film")
    q.add_argument("--batch", type=int)
    q.add_argument("--manifest")
    q.set_defaults(fn=cmd_lint)
    q = sub.add_parser("collect", help="收片段 → 預覽、自動檢查、審核表")
    q.add_argument("--film", required=True)
    q.add_argument("--no-qc", action="store_true")
    q.add_argument("--no-subtitles", action="store_true")
    q.set_defaults(fn=cmd_collect)
    q = sub.add_parser("approve", help="確認這一批")
    q.add_argument("--film", required=True)
    q.add_argument("--note")
    q.set_defaults(fn=cmd_approve)
    q = sub.add_parser("redo", help="只重拍指定段落")
    q.add_argument("--film", required=True)
    q.add_argument("--shots", required=True, help="鏡號，逗號分隔，例如 02,03")
    q.add_argument("--note")
    q.set_defaults(fn=cmd_redo)
    q = sub.add_parser("assemble", help="全片合成")
    q.add_argument("--film", required=True)
    q.add_argument("--asr", action="store_true", help="用 faster-whisper 對齊字幕時間（CPU）")
    q.add_argument("--no-subtitles", action="store_true")
    q.add_argument("--allow-unapproved", action="store_true")
    q.set_defaults(fn=cmd_assemble)
    a = ap.parse_args()
    if a.cmd == "lint" and not (a.film or a.manifest):
        ap.error("lint 需要 --film 或 --manifest")
    a.fn(a)


if __name__ == "__main__":
    main()
