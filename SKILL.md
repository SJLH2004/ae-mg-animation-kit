---
name: ae-mg-animation-kit
description: Build a complete flat-graphics MG (motion graphics) explainer in After Effects by script — storyboard, per-shot comp organization, PIL pre-rendered vector graphics, icon rasterising, TTS voice-over, original score, 50fps render and spec-compliant H.264 delivery. Use when the user asks to 做 MG 动画 / MG 科普片 / 动态影像设计作业 / AE 制作动画 / 用脚本批量建 AE 工程 / 分镜合成 / AE 自动化出片, or wants an AE project organised as master-comp + per-shot comps with a fixed delivery spec (resolution / fps / duration / bitrate).
agent_created: true
---

# AE MG Animation Kit

Script-drive After Effects to produce a whole flat-graphics explainer: AEP built by
JSX, graphics pre-rendered with PIL, voice-over from TTS, music synthesised from
scratch, frames rendered headless, then encoded to an exact delivery spec.

The value of this skill is not "how to animate". It is the **list of things that
silently produce a wrong picture while every API call reports success** — read
`references/ae-extendscript-pitfalls.md` before writing any JSX, and run
`scripts/blank_scan.py` before declaring a cut finished.

## When to use

- User wants an MG / motion-graphics explainer (科普, 宣传, 作业) and expects you to produce the AEP plus the finished MP4.
- User has an existing AE project that needs to be rebuilt script-style, or re-timed to a new duration/spec.
- User has a spec sheet (resolution, fps, ≤N seconds, target bitrate, audio codec) and needs delivery to match exactly.

## The seven steps

1. **Script + storyboard** — write the voice-over as *sentences with time codes*, one shot per sentence. Duration budget comes from the TTS timing, not from guessing. See `references/project-organization.md`.
2. **Assets** — pre-render every graphic with PIL at 2× and downsample (no AE shape layers, see pitfalls #1). Icons via SVG → PDF → raster → tint. Details in `references/asset-pipeline.md`.
3. **Audio bed** — TTS per line, synthesised SFX, original score. Load `video-score-composer` for the score; run `rhythm_scan.py` on a rough render so cues land on real motion.
4. **Build the AEP** — one JSX per shot, injected into a single AE launch. Master comp holds one layer per shot comp.
5. **Render** — `aerender` (no GUI). Output is a frame sequence; AE has no PNG template (pitfall #7).
6. **QA** — `scripts/frames_qa.py` for spot checks, `scripts/blank_scan.py` for empty-window and content-density sweeps. Never eyeball a whole cut frame by frame.
7. **Encode + verify** — `scripts/encode_submit.py` with CBR for the bitrate target, then print the ffprobe table and confirm every row of the spec.

## Non-negotiables

- **Never `app.project.save()` from an inspection or render script.** A script that connects to an untitled project and then saves will overwrite a real AEP with an 8 KB empty one. Check `app.project.file.fsName` first, and copy the AEP before any rebuild.
- **Never rebuild over a file the user has hand-edited.** If the user says "我手动改了工程", render *their* file; only touch `build_*.py` afterwards to keep future rebuilds in sync.
- **Every shot comp must carry its own full-frame background.** A single-comp project survives because a background layer spans several shots; after splitting into shot comps those shots become black.
- **Empty windows are the #1 perceived defect.** Two neighbouring shots each fade their elements out/in, so at the boundary nothing is on screen for 0.15–0.25 s. Scan for it (step 6) and fill it (a transition element or an overlap on a *same-colour* background).
- **Work in an ASCII path** (e.g. `C:/aelink`). Chinese paths break JSX file references and psd-tools parsing.

## Scripts

| Script | Purpose |
|---|---|
| `scripts/inspect_aep.py` | Read-only dump: comps, layer counts, work areas, master timeline, missing footage, item count |
| `scripts/frames_qa.py` | Export specific seconds as PNG via `saveFrameToPng` (with the async wait) |
| `scripts/blank_scan.py` | Per-0.1 s content-density sweep over a finished MP4 — finds empty windows and dead cuts |
| `scripts/psd2png.py` | PSD sequence → PNG sequence (threaded, ~15 s for 2300 frames) |
| `scripts/encode_submit.py` | CBR encode to spec + ffprobe verification table + clipping check |

All scripts take explicit paths; nothing is hard-coded to one project.

## References

- `references/project-organization.md` — master/segment comp layout, time remapping `T(t)`, work areas, naming.
- `references/asset-pipeline.md` — PIL graphics, icon rasterising, TTS, SFX, score hand-off.
- `references/ae-extendscript-pitfalls.md` — the silent-failure list. Read first.
- `references/render-and-delivery.md` — aerender, PSD/PNG frame pipeline, CBR encoding, spec table, loudness.
