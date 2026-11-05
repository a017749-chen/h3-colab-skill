"""AI-movie planning -> h3-multimodal-colab manifests (the 「腳本拍片」 mode of the skill).

mvkit already decides, deterministically, everything that caused the defects of earlier runs: the segments
(one H3 clip each, several 分鏡 cut inside), who is on screen in every 分鏡, who speaks and whether the voice is
off screen, which pictures go in and in what order, the head count, the timing of every line. This module
turns that plan into the skill's own batch format, so generation runs through scripts/h3run.py (Colab) or
scripts/h3local.py (ComfyUI Desktop) like any other batch:

    film.json            how to rebuild the project (script, bible, pictures, preset, aspect, batch length)
    jobs/batchNN/        one skill batch per review batch: manifest.json + inputs/ (+ out/ after the run)
    raw_clips/           collected clips, named the way mvkit's review and assembly expect
    review_state.json    approvals and redo seeds (mvkit.batches)

The prompt of every job is the H3 six-section reference format (references/prompt-guide.md). The planned,
checkable parts are written here in English: subject definitions with picture numbers, retention analysis,
the head count, every [Shot k] with its start time, who is on screen, every line verbatim in <d>[Mandarin] ...</d>,
voice-over and closed-mouth rules. What needs a writer - the visual description of each shot, the summary,
the soundscape - is left as <<WRITE ...>> slots holding the script's own (usually Chinese) text. The agent
replaces the slots with English prose; lint_manifest() refuses a batch that still has a slot, Chinese outside
<d> tags, a missing or altered line, a wrong picture number, or a detailed_description too short for H3.
"""
from __future__ import annotations

import json
import math
import re
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from .script_loader import (
    BeatSpec,
    PictureRef,
    ShotSpec,
    StoryboardProject,
    _resolve_path,
    clean_dialogue,
    framing_en,
    is_detail_beat,
    shot_engine,
    shot_gen_mode,
    shot_picture_plan,
)

FILM_FILE = "film.json"
WRITE = "<<WRITE"
LANG_TAG = "[Mandarin]"
CJK = re.compile(r"[㐀-鿿豈-﫿]")
DIALOGUE = re.compile(r"<d>\s*\[[^\]]+\]\s*(.*?)</d>", re.S)
SECTIONS = ("subject_definitions", "summary", "retention_analysis", "detailed_description",
            "overall_soundscape", "non_diegetic_music")
MIN_WORDS, GOOD_WORDS, MAX_WORDS = 250, 350, 500


# ---------------------------------------------------------------------- the film folder
@dataclass
class FilmConfig:
    """Everything needed to rebuild the same project: approvals are tied to a fingerprint of each shot, so
    every command must rebuild it identically from the same sources."""
    script: str
    bible: str = ""
    refs: str = ""
    title: str = ""
    preset: str = "none"
    aspect: str = "16:9"
    audio_mode: str = "native_h3_audio"
    batch_minutes: float = 2.0
    tail_guard_sec: float = 0.35
    base_seed: int = 768914106098754
    intensity: str = "off"
    extra: Dict[str, Any] = field(default_factory=dict)

    def save(self, film: Path) -> Path:
        film.mkdir(parents=True, exist_ok=True)
        f = film / FILM_FILE
        f.write_text(json.dumps(self.__dict__, ensure_ascii=False, indent=1), encoding="utf-8")
        return f

    @classmethod
    def load(cls, film: Path) -> "FilmConfig":
        f = Path(film) / FILM_FILE
        if not f.is_file():
            raise FileNotFoundError(f"{f} not found: run `h3movie.py plan` first")
        return cls(**json.loads(f.read_text(encoding="utf-8")))

    def base_dirs(self) -> List[Path]:
        dirs = [self.refs, str(Path(self.script).parent), str(Path(self.bible).parent) if self.bible else ""]
        return [Path(d) for d in dirs if d]


def build_project(cfg: FilmConfig, film: Path) -> Tuple[StoryboardProject, Any]:
    """Script + bible + pictures -> aligned project (the same steps as Step 3 of the Colab notebook)."""
    from .alignment import (align_project, apply_bible, discover_bible_from_refs, load_bible,
                            supplement_bible_from_refs)
    from .batches import apply_review_seeds
    from .presets import apply_preset
    from .script_import import import_script

    project = import_script(cfg.script, title=cfg.title or Path(cfg.script).stem, audio_mode=cfg.audio_mode)
    if cfg.bible:
        apply_bible(project, load_bible(cfg.bible))
    elif cfg.refs:
        apply_bible(project, discover_bible_from_refs(cfg.refs))
    if cfg.refs:
        supplement_bible_from_refs(project, cfg.refs)
    if cfg.preset and cfg.preset != "none":
        apply_preset(project, cfg.preset)
    project.audio_mode = cfg.audio_mode
    project.set_aspect(cfg.aspect)
    project.inference_mode = project.inference_mode or "reference"
    project.tail_guard_sec = float(cfg.tail_guard_sec)
    project.base_seed = int(cfg.base_seed)
    for k, v in (cfg.extra or {}).items():       # e.g. {"send_extra_views": true}
        if hasattr(project, k):
            setattr(project, k, v)
    report = align_project(project, cfg.base_dirs())
    project.validate()
    apply_review_seeds(project, film)
    return project, report


def job_id(shot: ShotSpec) -> str:
    return "seg" + re.sub(r"[^A-Za-z0-9_-]", "_", str(shot.shot_id))


def clip_seconds(project: StoryboardProject, shot: ShotSpec) -> int:
    """Seconds asked of H3: the kept length plus the tail that is trimmed later, whole seconds, 2-15."""
    return int(min(15, max(2, math.ceil(project.generation_seconds(shot) - 1e-6))))


# ---------------------------------------------------------------------- the six-section draft
def _subjects(project: StoryboardProject, shot: ShotSpec, pictures: List[PictureRef]) -> Dict[str, int]:
    """character id -> <Subject N>, in the order the shot lists them (only people who appear or speak)."""
    order: List[str] = []
    for c in shot.characters:
        if c in project.characters and c not in order:
            order.append(c)
    for b in shot.beats:
        for c in list(b.on_screen) + ([b.speaker] if b.speaker else []):
            if c in project.characters and c not in order:
                order.append(c)
    if not shot.beats and shot.speaker in project.characters and shot.speaker not in order:
        order.append(shot.speaker)
    return {c: n for n, c in enumerate(order, start=1)}


_NUMBER = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}


def _pic_token(n: int) -> str:
    return f"@圖片{n}"


def _picture_number(pictures: List[PictureRef], char_id: str) -> int:
    for n, p in enumerate(pictures, start=1):
        if p.role == "character" and p.char_id == char_id:
            return n
    return 0


def _clock(t: float) -> str:
    m, s = divmod(max(0.0, t), 60)
    return f"{int(m):02d}:{s:06.3f}"


def _beats(shot: ShotSpec) -> List[BeatSpec]:
    """A one-cut shot behaves like a segment with a single 分鏡."""
    if shot.beats:
        return shot.beats
    return [BeatSpec(beat_id=f"{shot.shot_id}-1", duration_sec=shot.duration_sec, framing="",
                     visual=shot.visual_prompt, dialogue=shot.dialogue, speaker=shot.speaker,
                     camera=shot.camera_motion, on_screen=list(shot.characters), voice_over=shot.voice_over)]


def _name(project: StoryboardProject, cid: str, subjects: Dict[str, int]) -> str:
    return f"<Subject {subjects[cid]}>" if cid in subjects else (
        project.characters[cid].name if cid in project.characters else cid)


def _list(names: Sequence[str]) -> str:
    names = list(names)
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def build_six_section(project: StoryboardProject, shot: ShotSpec, pictures: List[PictureRef]) -> str:
    subjects = _subjects(project, shot, pictures)
    beats = _beats(shot)
    native = project.audio_mode == "native_h3_audio"
    hold = max(0.0, clip_seconds(project, shot) - shot.duration_sec)

    # subject_definitions
    lines = ["subject_definitions:"]
    for cid, n in subjects.items():
        ch = project.characters[cid]
        pic = _picture_number(pictures, cid)
        src = f"the person in {_pic_token(pic)}" if pic else "a person with no reference picture"
        bits = [f"<Subject {n}> is {ch.name}, {src}"]
        if ch.description:
            bits.append(ch.description)
        if ch.screen_position:
            bits.append(f"always {ch.screen_position}")
        line = ", ".join(bits) + "."
        if native and ch.voice:
            line += f" Voice: {ch.voice}."
        lines.append(line)
    for n, p in enumerate(pictures, start=1):
        if p.role == "scene":
            scene = project.scenes.get(shot.scene_id)
            where = (scene.name or scene.description) if scene else "the location"
            lines.append(f"{_pic_token(n)} is the {where} location reference (architecture, furniture and light "
                         f"only; any person in it is not part of this video).")
        elif p.role == "extra":
            lines.append(f"{_pic_token(n)} is another view of the same person, not an additional person.")

    # summary
    lines += ["", "summary:",
              f"[reference generation] {WRITE}: one or two English sentences on what happens in this clip. "
              f"Script: {shot.title or shot.visual_prompt[:120]}>>"]

    # retention_analysis
    lines += ["", "retention_analysis:"]
    for cid, n in subjects.items():
        seen = [f"[Shot {k}]" for k, b in enumerate(beats, start=1) if cid in b.on_screen and not is_detail_beat(b)]
        hands = [f"[Shot {k}]" for k, b in enumerate(beats, start=1) if cid in b.on_screen and is_detail_beat(b)]
        where = []
        if seen:
            where.append("appears in " + ", ".join(seen))
        if hands:
            where.append("hands only in " + ", ".join(hands))
        if not where:
            where.append("heard, not seen")
        pic = _picture_number(pictures, cid)
        keep = (f"face, hair, clothing and build exactly as in {_pic_token(pic)}" if pic
                else "appearance exactly as described in subject_definitions")
        lines.append(f"<Subject {n}> ({'; '.join(where)}): fully_preserved - {keep}.")
    for n, p in enumerate(pictures, start=1):
        if p.role == "scene":
            lines.append(f"{_pic_token(n)}: location reference - architecture, furniture and light only; "
                         f"not a first frame.")

    # detailed_description
    count = len(subjects)
    people = ("No people appear in this video; no faces, no bystanders." if not count else
              f"Exactly {_NUMBER.get(count, str(count))} {'person' if count == 1 else 'people'} in this video: "
              f"{_list([f'<Subject {n}>' for n in subjects.values()])}. "
              f"{'This person is' if count == 1 else 'Each of them is'} one single individual who appears only "
              f"once in any frame: no twins, no clones, no mirrored copies, no extra people or bystanders.")
    lines += ["", "detailed_description:",
              f"The target video is a {shot.duration_sec:g}-second clip in {len(beats)} "
              f"{'shot' if len(beats) == 1 else 'shots'}. {people}"]
    t = 0.0
    for k, b in enumerate(beats, start=1):
        head = f"[Shot {k}]" if k == 1 else f"[Shot {k}] At {_clock(t)},"
        framing = framing_en(b.framing) if b.framing else ""
        vis = [c for c in b.on_screen if c in project.characters]
        if not vis:
            on = "On screen: no people, no faces."
        elif is_detail_beat(b):
            on = f"On screen: only the hands and forearms of {_list([_name(project, c, subjects) for c in vis])}; " \
                 f"no face is visible."
        else:
            on = f"On screen: {_list([_name(project, c, subjects) for c in vis])}; nobody else."
        source = "; ".join(x for x in (b.lighting and f"light: {b.lighting}", b.camera and f"camera: {b.camera}",
                                       b.visual and f"action: {b.visual}") if x)
        words = "100-160" if len(beats) <= 3 else "70-110"
        if framing:
            framing = (framing[0].upper() if k == 1 else framing[0].lower()) + framing[1:] + "."
        parts = [head, framing, on,
                 f"{WRITE}: {words} English words - camera position and movement, light, what each person does "
                 f"and how they react, written as seen. Script: {source or shot.visual_prompt}>>"]
        spoken = clean_dialogue(b.dialogue)
        if native and spoken:
            if b.speaker and not b.voice_over and b.speaker in subjects:
                who = _name(project, b.speaker, subjects)
                parts.append(f"{who} (S{subjects[b.speaker]}) says, <d>{LANG_TAG} {spoken}</d> "
                             f"Only {who}'s lips move; everyone else keeps their mouth closed.")
            elif b.speaker and b.speaker in subjects:
                who = _name(project, b.speaker, subjects)
                parts.append(f"Voice-over by {who} (S{subjects[b.speaker]}), whose face is not in this shot: "
                             f"<d>{LANG_TAG} {spoken}</d> Nobody on screen moves their lips.")
            else:
                parts.append(f"An off-screen narrator ({project.narrator}): <d>{LANG_TAG} {spoken}</d> "
                             f"The people on screen do not speak; their lips stay relaxed.")
        elif not native:
            parts.append("Nobody speaks: no dialogue, no narration.")
        lines.append(" ".join(p for p in parts if p))
        t += b.duration_sec
    if hold > 0:
        lines.append(f"In the last {hold:g} {'second' if hold == 1 else 'seconds'} everyone holds the final "
                     f"pose silently.")

    # sound
    speakers = [b.speaker for b in beats if clean_dialogue(b.dialogue)]
    effects = "; ".join(dict.fromkeys(b.sound for b in beats if b.sound)) or "room tone"
    if not native or not speakers:
        voices = "No voices."
    elif all(s in subjects for s in speakers):
        named = _list([f"<Subject {subjects[s]}>" for s in dict.fromkeys(speakers)])
        voices = f"Only {named} {'speaks' if len(set(speakers)) == 1 else 'speak'}, with the same voice as in " \
                 f"every other clip. No other voices."
    else:
        voices = "The same single narrator voice as in every other clip. No other voices."
    music = next((m for m in (_music(b.sound) for b in beats) if m), "")
    lines += ["", "overall_soundscape:",
              f"{WRITE}: English, action and room sounds only, no music. Script: {effects}>> {voices}",
              "", "non_diegetic_music:",
              f"{WRITE}: one English sentence. Script: {music}>>" if music else "N/A"]
    return "\n".join(lines) + "\n"


def _music(sound: str) -> str:
    m = re.search(r"(?:配樂|音樂|music)\s*[：:]?\s*([^；;。\n]+)", sound or "", flags=re.I)
    if not m:
        return ""
    v = m.group(1).strip()
    return "" if re.fullmatch(r"(無|none|n/?a|沒有|不需要)", v, flags=re.I) else v


# ---------------------------------------------------------------------- manifests
def job_plan(project: StoryboardProject, shot: ShotSpec, pictures: List[PictureRef]) -> Dict[str, Any]:
    """What lint and review check the finished prompt and clip against."""
    from .batches import shot_fingerprint
    beats = _beats(shot)
    return {
        "shot_id": shot.shot_id, "index": shot.index, "fingerprint": shot_fingerprint(project, shot),
        "prompt_key": prompt_key(project, shot),
        "keep_seconds": shot.duration_sec, "pictures": len(pictures),
        "shots": len(beats),
        "lines": [clean_dialogue(b.dialogue) for b in beats
                  if clean_dialogue(b.dialogue) and project.audio_mode == "native_h3_audio"],
        "people": len(_subjects(project, shot, pictures)),
    }


def prompt_key(project: StoryboardProject, shot: ShotSpec) -> str:
    """Fingerprint of what the prompt is written from: everything but the seed. A redo only changes the seed,
    so the prose the agent already wrote for that shot is kept."""
    import copy
    from .batches import shot_fingerprint
    s = copy.copy(shot)
    s.seed = 0
    return shot_fingerprint(project, s)


def _copy_input(src: str, inputs: Path, taken: Dict[str, str]) -> str:
    """Copy a picture into the batch's inputs/ once; returns its path relative to the manifest."""
    src_path = Path(src).resolve()
    key = str(src_path)
    if key not in taken:
        name = src_path.name
        stem, suffix, k = src_path.stem, src_path.suffix, 2
        while (inputs / name).exists() and (inputs / name).resolve() != src_path:
            if (inputs / name).read_bytes() == src_path.read_bytes():
                break
            name = f"{stem}_{k}{suffix}"
            k += 1
        inputs.mkdir(parents=True, exist_ok=True)
        if not (inputs / name).exists():
            shutil.copy2(src_path, inputs / name)
        taken[key] = f"inputs/{name}"
    return taken[key]


def build_job(project: StoryboardProject, shot: ShotSpec, base_dirs: List[Path], batch_dir: Path,
              taken: Dict[str, str], intensity: str = "off") -> Tuple[Dict[str, Any], List[str]]:
    notes: List[str] = []
    mode = shot_gen_mode(project, shot)
    pictures = shot_picture_plan(project, shot, base_dirs)
    job: Dict[str, Any] = {"id": job_id(shot), "type": "video", "seconds": clip_seconds(project, shot),
                           "aspect": project.aspect_ratio, "intensity": intensity, "seed": int(shot.seed)}
    if shot_engine(project, shot) == "first_frame":
        job["mode"] = "frames"
        for key, raw in (("first", shot.first_frame), ("last", shot.last_frame if mode == "first_last" else "")):
            if raw:
                p = _resolve_path(raw, base_dirs)
                if Path(p).is_file():
                    job[key] = _copy_input(p, batch_dir / "inputs", taken)
                else:
                    notes.append(f"{shot.shot_id}: keyframe {raw} not found")
        pictures = []
    else:
        job["mode"] = "ref"
        if mode == "reference_keyframes":
            notes.append(f"{shot.shot_id}: reference + keyframe guides are not available through the skill; "
                         f"generated as plain reference (use 首幀 or 首尾幀 for an exact pose)")
        job["inputs"] = [_copy_input(p.path, batch_dir / "inputs", taken) for p in pictures]
        if not pictures:
            notes.append(f"{shot.shot_id}: no reference picture (scene {shot.scene_id}); H3 will invent the people")
    job["prompt"] = build_six_section(project, shot, pictures)
    job["plan"] = job_plan(project, shot, pictures)
    return job, notes


def write_batch_manifest(project: StoryboardProject, film: Path, batch, base_dirs: List[Path], *,
                         intensity: str = "off", only_pending: bool = True) -> Tuple[Path, List[str]]:
    """jobs/batchNN/manifest.json for the shots of `batch` that still need a clip.

    A prompt the agent already finished is kept as long as its shot did not change (same fingerprint):
    re-running never throws away written prose. A changed shot gets a fresh draft.
    """
    from .batches import shot_is_generated
    batch_dir = film / "jobs" / f"batch{batch.index:02d}"
    path = batch_dir / "manifest.json"
    if path.is_file():
        collect_batch(project, film, batch)     # a finished run nobody collected yet still counts
    old = {}
    if path.is_file():
        old = {j["id"]: j for j in json.loads(path.read_text(encoding="utf-8")).get("jobs", [])}
    taken: Dict[str, str] = {}
    jobs, notes = [], []
    for shot in project.shots:
        if shot.shot_id not in batch.shot_ids:
            continue
        if only_pending and shot_is_generated(project, film, shot):
            continue
        job, n = build_job(project, shot, base_dirs, batch_dir, taken, intensity)
        _set_aside(batch_dir, job["id"])         # h3run skips a job whose output exists: never reuse a stale clip
        prev = old.get(job["id"])
        if prev and prev.get("plan", {}).get("prompt_key") == job["plan"]["prompt_key"]:
            job["prompt"] = prev["prompt"]
            job["intensity"] = prev.get("intensity", job["intensity"])
            for k in ("resolution", "fast"):
                if k in prev:
                    job[k] = prev[k]
        jobs.append(job)
        notes += n
    manifest = {"film": {"title": project.title, "batch": batch.index, "shots": batch.shot_ids},
                "stop_on_error": False, "jobs": jobs}
    batch_dir.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    return path, notes


def _set_aside(batch_dir: Path, jid: str) -> None:
    """Move out/<id>.* of a job that must be made again to out/_stale/ (kept for comparison)."""
    out = batch_dir / "out"
    for f in sorted(out.glob(f"{jid}.*")) if out.is_dir() else []:
        stale = out / "_stale"
        stale.mkdir(parents=True, exist_ok=True)
        k = 1
        while (stale / f"{jid}_take{k}{f.suffix}").exists():
            k += 1
        f.rename(stale / f"{jid}_take{k}{f.suffix}")


# ---------------------------------------------------------------------- lint
def _section(prompt: str, name: str) -> str:
    m = re.search(rf"^{name}:\s*\n(.*?)(?=^\w+:\s*$|\Z)", prompt, flags=re.S | re.M)
    return m.group(1).strip() if m else ""


def english_words(text: str) -> int:
    return len(re.findall(r"[A-Za-z][A-Za-z'-]*", DIALOGUE.sub(" ", text)))


def lint_prompt(job: Dict[str, Any]) -> Tuple[List[str], List[str]]:
    """(errors, warnings) for one finished job prompt."""
    errors, warnings = [], []
    jid, prompt, plan = job.get("id", "?"), job.get("prompt", ""), job.get("plan") or {}
    if WRITE in prompt:
        errors.append(f"{jid}: {prompt.count(WRITE)} 個 {WRITE} …>> 還沒寫")
    for name in SECTIONS:
        if not re.search(rf"^{name}:", prompt, flags=re.M):
            errors.append(f"{jid}: 少了 {name}: 段")
    outside = DIALOGUE.sub(" ", prompt)
    outside = re.sub(r"@(圖片|音訊|影片)\d+", " ", outside)
    if CJK.search(outside):
        sample = "".join(CJK.findall(outside)[:12])
        errors.append(f"{jid}: <d> 台詞以外還有中文（{sample}…）；本文要全部用英文，否則 H3 容易在畫面上燒字幕")
    heard = [clean_dialogue(x) for x in DIALOGUE.findall(prompt)]
    for line in plan.get("lines", []):
        if line not in heard:
            errors.append(f"{jid}: 腳本台詞不見或被改了：「{line}」（要一字不改放進 <d>{LANG_TAG} …</d>）")
    for extra in heard:
        if plan.get("lines") is not None and extra not in plan.get("lines", []):
            warnings.append(f"{jid}: 多了一句腳本沒有的台詞「{extra}」")
    if job.get("mode") == "frames" and not (job.get("first") or job.get("last")):
        errors.append(f"{jid}: 首幀／首尾幀模式卻沒有首幀或尾幀圖（把圖放進參考圖資料夾，或改成參考圖模式）")
    pics = len(job.get("inputs", [])) if job.get("mode", "ref") == "ref" else 0
    for n in {int(x) for x in re.findall(r"@圖片(\d+)", prompt)} | {int(x) for x in re.findall(r"<Picture (\d+)>", prompt)}:
        if n < 1 or n > pics:
            errors.append(f"{jid}: 提到第 {n} 張圖，但這一段只送了 {pics} 張")
    shots = len(re.findall(r"\[Shot \d+\]", _section(prompt, "detailed_description")))
    if plan.get("shots") and shots != plan["shots"]:
        errors.append(f"{jid}: detailed_description 有 {shots} 個 [Shot]，計畫是 {plan['shots']} 個分鏡")
    if plan.get("people") and "Exactly" not in prompt and "exactly" not in prompt:
        warnings.append(f"{jid}: 沒有寫明畫面上剛好幾個人（防止人物重複最有效的一句）")
    words = english_words(_section(prompt, "detailed_description"))
    if words < MIN_WORDS:
        errors.append(f"{jid}: detailed_description 只有 {words} 個英文字（至少 {MIN_WORDS}，建議 "
                      f"{GOOD_WORDS}–{MAX_WORDS}）；太短 H3 會在畫面上燒字幕")
    elif not GOOD_WORDS <= words <= MAX_WORDS + 150:
        warnings.append(f"{jid}: detailed_description {words} 個英文字（建議 {GOOD_WORDS}–{MAX_WORDS}）")
    chars_per_sec = sum(len(re.sub(r"\W", "", x)) for x in heard) / max(1.0, float(plan.get("keep_seconds") or 10))
    if chars_per_sec > 4.5:
        warnings.append(f"{jid}: 台詞約每秒 {chars_per_sec:.1f} 字（中文約每秒 4 字），可能講太快或吃字")
    return errors, warnings


def lint_manifest(path: str | Path) -> Tuple[List[str], List[str]]:
    m = json.loads(Path(path).read_text(encoding="utf-8"))
    errors, warnings = [], []
    for job in m.get("jobs", []):
        if job.get("type") != "video":
            continue
        e, w = lint_prompt(job)
        errors += e
        warnings += w
    return errors, warnings


# ---------------------------------------------------------------------- after a run
def collect_batch(project: StoryboardProject, film: Path, batch) -> Dict[str, Path]:
    """Copy jobs/batchNN/out/seg*.mp4 into raw_clips/ and record progress, so mvkit's review, approval and
    assembly see them (a clip counts only while its shot is unchanged: the fingerprint is stored with it)."""
    batch_dir = film / "jobs" / f"batch{batch.index:02d}"
    results = {}
    rf = batch_dir / "out" / "results.json"
    if rf.is_file():
        data = json.loads(rf.read_text(encoding="utf-8"))
        results = data.get("jobs", data) if isinstance(data, dict) else {}
    manifest = json.loads((batch_dir / "manifest.json").read_text(encoding="utf-8")) \
        if (batch_dir / "manifest.json").is_file() else {"jobs": []}
    planned = {j["id"]: j for j in manifest.get("jobs", [])}
    prog_file = film / "progress.json"
    progress = json.loads(prog_file.read_text(encoding="utf-8")) if prog_file.is_file() else {}
    got: Dict[str, Path] = {}
    (film / "raw_clips").mkdir(parents=True, exist_ok=True)
    for shot in project.shots:
        if shot.shot_id not in batch.shot_ids:
            continue
        jid = job_id(shot)
        src = batch_dir / "out" / f"{jid}.mp4"
        if not src.is_file():
            continue
        job = planned.get(jid, {})
        fp = job.get("plan", {}).get("fingerprint")
        from .batches import shot_fingerprint
        if fp and fp != shot_fingerprint(project, shot):
            continue          # the shot was edited after this clip was made: it must be made again
        dst = film / "raw_clips" / f"{shot.index:02d}_{shot.shot_id}.mp4"
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime or dst.stat().st_size != src.stat().st_size:
            shutil.copy2(src, dst)
        r = results.get(jid, {}) if isinstance(results, dict) else {}
        progress[shot.shot_id] = {"fingerprint": shot_fingerprint(project, shot), "file": dst.name,
                                  "seconds": float(job.get("seconds") or project.generation_seconds(shot)),
                                  "elapsed_s": r.get("seconds_used"), "seed": r.get("seed", job.get("seed")),
                                  "source": str(src.relative_to(film))}
        got[shot.shot_id] = dst
    prog_file.write_text(json.dumps(progress, ensure_ascii=False, indent=1), encoding="utf-8")
    return got
