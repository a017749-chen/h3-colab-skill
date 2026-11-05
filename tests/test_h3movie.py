"""腳本拍片 mode: AI-movie planning -> skill manifests -> review -> assembly, through scripts/h3movie.py.

Generation itself is faked with ffmpeg test clips; everything around it (planning, prompt drafts, lint, the
skill's own manifest validation, collection, approval, redo, assembly) runs for real. Synthetic data only.
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "h3-multimodal-colab"
MOVIE_DIR = REPO_ROOT / "movie"
EXAMPLE = MOVIE_DIR / "examples" / "osce_demo"
for p in (SKILL_DIR, SKILL_DIR / "scripts"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from mvkit import skill_bridge as SB  # noqa: E402

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
FILLER = ("The camera holds a steady eye-level view while soft even light falls across the bed and the curtain "
          "behind it. The doctor moves slowly and deliberately with his hands clearly visible, and the patient "
          "watches calmly, breathing evenly, his shoulders relaxed against the raised backrest. Every movement is "
          "unhurried and correct, with small natural pauses between steps so that each action can be followed. ") * 2


def h3movie(*args, check=True):
    r = subprocess.run([sys.executable, str(SKILL_DIR / "scripts" / "h3movie.py"), *map(str, args)],
                       capture_output=True, text=True, encoding="utf-8")
    if check and r.returncode:
        raise AssertionError(r.stdout + r.stderr)
    return r


@pytest.fixture
def refs(tmp_path):
    from PIL import Image
    d = tmp_path / "refs"
    d.mkdir()
    Image.new("RGB", (768, 1024), (200, 180, 160)).save(d / "char_examinee.png")
    Image.new("RGB", (768, 1024), (160, 180, 200)).save(d / "char_patient.png")
    Image.new("RGB", (1344, 768), (220, 220, 210)).save(d / "scene_bedside.png")
    Image.new("RGB", (1344, 768), (90, 90, 90)).save(d / "kf_03_first.png")
    Image.new("RGB", (1344, 768), (95, 95, 95)).save(d / "kf_03_last.png")
    return d


def plan(tmp_path, refs):
    film = tmp_path / "film"
    h3movie("plan", "--script", EXAMPLE / "segments.txt", "--bible", EXAMPLE / "bible.md", "--refs", refs,
            "--film", film, "--preset", "osce_demo", "--title", "OSCE_Test")
    return film, film / "jobs" / "batch01" / "manifest.json"


def write_prose(manifest):
    """What the agent does: every <<WRITE ...>> slot becomes English prose."""
    m = json.loads(manifest.read_text(encoding="utf-8"))
    for j in m["jobs"]:
        j["prompt"] = re.sub(r"<<WRITE:.*?>>", lambda x: FILLER.strip() if "English words" in x.group(0)
                             else "A calm clinical demonstration in a bright skills room.", j["prompt"], flags=re.S)
    manifest.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    return m


def fake_run(manifest):
    """Stand-in for h3run.py: one clip per job, the requested length, picture and sound."""
    out = manifest.parent / "out"
    out.mkdir(exist_ok=True)
    m = json.loads(manifest.read_text(encoding="utf-8"))
    for j in m["jobs"]:
        subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i",
                        f"testsrc=size=1344x768:rate=24:duration={j['seconds']}", "-f", "lavfi", "-i",
                        f"sine=frequency=440:sample_rate=48000:duration={j['seconds']}", "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(out / f"{j['id']}.mp4")], check=True)
    (out / "results.json").write_text(json.dumps({"jobs": {j["id"]: {"status": "done", "seconds_used": 90.0}
                                                           for j in m["jobs"]}}), encoding="utf-8")


def test_plan_writes_a_six_section_draft_the_skill_accepts(tmp_path, refs):
    from h3run import load_manifest
    film, manifest = plan(tmp_path, refs)
    assert (film / "plan.md").is_file()
    m = json.loads(manifest.read_text(encoding="utf-8"))
    assert [j["id"] for j in m["jobs"]] == ["seg01", "seg02", "seg03"]
    seg02 = m["jobs"][1]
    assert seg02["mode"] == "ref" and seg02["inputs"] == [
        "inputs/scene_bedside.png", "inputs/char_examinee.png", "inputs/char_patient.png"]
    prompt = seg02["prompt"]
    for section in SB.SECTIONS:
        assert re.search(rf"^{section}:", prompt, flags=re.M), section
    # the planned, anti-duplicate parts are already there, in English
    assert "<Subject 1> is examinee doctor, the person in @圖片2" in prompt
    assert "Exactly two people in this video" in prompt
    assert "On screen: only the hands and forearms of <Subject 1>; no face is visible." in prompt
    assert "Voice-over by <Subject 1> (S1), whose face is not in this shot: <d>[Mandarin] 壓脈帶下緣在肘窩上兩到三公分。</d>" in prompt
    assert "[Shot 2] At 00:03.000, close-up." in prompt
    assert m["jobs"][2]["mode"] == "frames" and m["jobs"][2]["first"].endswith("kf_03_first.png")
    assert seg02["seconds"] == 11                          # 10 s kept + the trimmed tail, whole seconds
    load_manifest(manifest)                                # h3run's own validation (paths, ids, seconds)
    errors, _ = SB.lint_manifest(manifest)
    assert any("<<WRITE" in e for e in errors)              # drafts are not sendable yet
    assert h3movie("lint", "--film", film, check=False).returncode == 1


def test_lint_rules():
    base = {"id": "seg01", "type": "video", "mode": "ref", "inputs": ["inputs/a.png", "inputs/b.png"],
            "plan": {"lines": ["你好。"], "shots": 1, "people": 1, "keep_seconds": 10}}
    good = ("subject_definitions:\n<Subject 1> is a doctor, the person in @圖片2.\n\nsummary:\nA greeting.\n\n"
            "retention_analysis:\n<Subject 1>: fully_preserved.\n\ndetailed_description:\nExactly one person. "
            f"[Shot 1] {FILLER * 2} <Subject 1> (S1) says, <d>[Mandarin] 你好。</d>\n\n"
            "overall_soundscape:\nRoom tone.\n\nnon_diegetic_music:\nN/A\n")
    assert SB.lint_prompt(dict(base, prompt=good))[0] == []
    cases = {
        "還沒寫": good.replace("A greeting.", "<<WRITE: summary>>"),
        "中文": good.replace("A greeting.", "醫師打招呼。"),
        "台詞不見或被改了": good.replace("你好。", "您好。"),
        "只送了 2 張": good.replace("@圖片2", "@圖片3"),
        "個英文字": good.replace(FILLER * 2, "He waves."),
        "少了 overall_soundscape": good.replace("overall_soundscape:", "soundscape:"),
        "[Shot]": good.replace("[Shot 1]", "[Shot 1] [Shot 2]"),
    }
    for expect, prompt in cases.items():
        errors, _ = SB.lint_prompt(dict(base, prompt=prompt))
        assert any(expect in e for e in errors), (expect, errors)
    errors, _ = SB.lint_prompt(dict(base, mode="frames", inputs=[], prompt=good.replace("@圖片2", "a photo")))
    assert any("首幀" in e for e in errors)


@needs_ffmpeg
def test_whole_loop_plan_lint_collect_approve_redo_assemble(tmp_path, refs):
    film, manifest = plan(tmp_path, refs)
    write_prose(manifest)
    assert h3movie("lint", "--film", film, check=False).returncode == 0
    fake_run(manifest)
    out = h3movie("collect", "--film", film, "--no-qc").stdout
    assert "收到 3 段" in out
    assert len(list((film / "raw_clips").glob("*.mp4"))) == 3
    assert "待審核" in h3movie("status", "--film", film).stdout
    h3movie("approve", "--film", film)
    assert "已確認" in h3movie("status", "--film", film).stdout

    # redo one segment: new seed, the written prose is kept, the old clip can neither be skipped nor reused
    written = {j["id"]: j["prompt"] for j in json.loads(manifest.read_text(encoding="utf-8"))["jobs"]}
    h3movie("redo", "--film", film, "--shots", "02")
    h3movie("next", "--film", film)
    m = json.loads(manifest.read_text(encoding="utf-8"))
    assert [j["id"] for j in m["jobs"]] == ["seg02"]
    assert m["jobs"][0]["prompt"] == written["seg02"]
    assert not (manifest.parent / "out" / "seg02.mp4").exists()
    assert (manifest.parent / "out" / "_stale" / "seg02_take1.mp4").exists()
    assert (film / "raw_clips" / "_rejected" / "02_02_take1.mp4").exists()
    assert h3movie("assemble", "--film", film, check=False).returncode != 0      # not approved again yet

    fake_run(manifest)
    h3movie("collect", "--film", film, "--no-qc")
    h3movie("approve", "--film", film)
    out = h3movie("assemble", "--film", film).stdout
    assert "全片完成" in out
    final = film / "final"
    clean = next(final.glob("*_clean.mp4"))
    streams = json.loads(subprocess.run(["ffprobe", "-v", "error", "-show_streams", "-of", "json", str(clean)],
                                        capture_output=True, text=True).stdout)["streams"]
    assert sorted(s["codec_type"] for s in streams) == ["audio", "video"]
    assert next(final.glob("*.zh-TW.srt")).read_text(encoding="utf-8").count("-->") >= 3


def test_editing_the_script_reopens_only_that_segment(tmp_path, refs):
    film, manifest = plan(tmp_path, refs)
    write_prose(manifest)
    script = tmp_path / "script.txt"
    text = (EXAMPLE / "segments.txt").read_text(encoding="utf-8")
    script.write_text(text, encoding="utf-8")
    cfg = SB.FilmConfig.load(film)
    cfg.script = str(script)
    cfg.save(film)
    h3movie("next", "--film", film)
    kept = json.loads(manifest.read_text(encoding="utf-8"))["jobs"]
    assert all("<<WRITE" not in j["prompt"] for j in kept)      # same text: the prose survives
    script.write_text(text.replace("手臂放輕鬆就好。", "手臂放鬆。"), encoding="utf-8")
    h3movie("next", "--film", film)
    jobs = {j["id"]: j for j in json.loads(manifest.read_text(encoding="utf-8"))["jobs"]}
    assert "<<WRITE" in jobs["seg02"]["prompt"] and "手臂放鬆。" in jobs["seg02"]["prompt"]
    assert "<<WRITE" not in jobs["seg01"]["prompt"]
