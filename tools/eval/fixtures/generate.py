#!/usr/bin/env python3
"""Generates synthetic audio fixtures for diarization (#2) and VAD/ASR evaluation.

Each case in cases.yaml becomes a .wav, a .rttm ground truth and a .json of
metadata. The ground truth is exact by construction: every turn's start and
duration come from the same timeline this script builds the audio from, not
from a separate detection pass over the finished file.

Speech comes from the ElevenLabs text-to-speech API. --dry-run replaces every
call with an ffmpeg sine tone of the same estimated duration, one frequency
per voice, so the pipeline (overlap placement, effects, RTTM, metadata) can be
exercised for free. Everything else (overlap mixing, noise, the telephone
codec chain) is ffmpeg via subprocess, never a DSP library.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

import calibration

SAMPLE_RATE = 16000
# Rough, language-agnostic speaking rate used only to size dry-run tones and
# to fail fast on cases whose turns are supposed to be short (see
# short-turns in cases.yaml). Real synthesis measures its own PCM length.
CHARS_PER_SECOND = 15.0
MIN_TURN_SECONDS = 0.5

ELEVENLABS_TTS_URL = "https://api.elevenlabs.io/v1/text-to-speech/{voice_id}"
ELEVENLABS_VOICES_URL = "https://api.elevenlabs.io/v1/voices"
ELEVENLABS_KEY_FILE = Path.home() / ".config" / "elevenlabs" / "key"
PLACEHOLDER_VOICE_ID = "REPLACE_WITH_ELEVENLABS_VOICE_ID"

FIXTURES_DIR = Path(__file__).resolve().parent
DEFAULT_CASES_PATH = FIXTURES_DIR / "cases.yaml"
DEFAULT_VOICES_PATH = FIXTURES_DIR / "voices.yaml"
DEFAULT_OUT_DIR = Path.home() / "Voxtrama" / "eval"


class FixtureError(Exception):
    """Raised when a case or voice cannot be turned into audio."""


@dataclass(frozen=True)
class Turn:
    """One line of a case's script, before it has been placed on a timeline."""

    voice: str
    text: str
    overlap_ms: int


@dataclass(frozen=True)
class Case:
    id: str
    language: str
    speakers: int
    turns: list[Turn]
    effects: dict[str, Any]


@dataclass(frozen=True)
class Voice:
    voice_id: str
    language: str
    gender: str
    # Only set for voices used with --piper. Piper is a separate, permissively
    # licensed engine (MIT), kept here because the one fixture that ships
    # inside the repository cannot depend on ElevenLabs' redistribution terms.
    piper_model: str | None = None
    piper_speaker: int | None = None


@dataclass(frozen=True)
class PlannedSegment:
    """A turn placed on the timeline: what the RTTM and the ffmpeg mix are built from."""

    speaker: str
    start: float
    duration: float


def estimate_duration(text: str) -> float:
    """Estimate how long ElevenLabs will take to speak `text`.

    Only used to size a dry-run tone, since there is no PCM to measure yet.
    Once audio exists (real or dry-run), its measured length is used instead.
    """
    return max(MIN_TURN_SECONDS, len(text) / CHARS_PER_SECOND)


def load_cases(path: Path) -> list[Case]:
    """Parse cases.yaml into Case objects."""
    raw = yaml.safe_load(path.read_text())
    return [_parse_case(item) for item in raw["cases"]]


def _calibration_turns(language: str, voice: str) -> list[Turn]:
    """Build turns from a calibration script's `scripted` passage.

    Every non-blank line becomes its own turn on the case's declared voice,
    so a calibration case keeps one RTTM segment per sentence like any other
    case, without its text being duplicated into cases.yaml.
    """
    script = calibration.load_script(language)
    scripted = next(p for p in script.passages if p.id == "scripted")
    lines = [line.strip() for line in scripted.text.splitlines() if line.strip()]
    return [Turn(voice=voice, text=line, overlap_ms=0) for line in lines]


def _parse_case(raw: dict[str, Any]) -> Case:
    if "calibration_script" in raw:
        turns = _calibration_turns(raw["calibration_script"], raw["voice"])
    else:
        turns = [
            Turn(voice=t["voice"], text=t["text"], overlap_ms=int(t.get("overlap_ms", 0)))
            for t in raw["turns"]
        ]
    return Case(
        id=raw["id"],
        language=raw["language"],
        speakers=int(raw["speakers"]),
        turns=turns,
        effects=raw.get("effects") or {},
    )


def load_voices(path: Path) -> dict[str, Voice]:
    """Parse voices.yaml into a name -> Voice map."""
    raw = yaml.safe_load(path.read_text())
    return {
        name: Voice(
            voice_id=v["voice_id"],
            language=v["language"],
            gender=v["gender"],
            piper_model=v.get("piper_model"),
            piper_speaker=v.get("piper_speaker"),
        )
        for name, v in raw["voices"].items()
    }


def ffmpeg_available() -> bool:
    """Whether ffmpeg is on PATH. Callers use this to skip instead of fail."""
    return shutil.which("ffmpeg") is not None


def _run_ffmpeg(args: list[str]) -> None:
    result = subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args],
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise FixtureError(f"ffmpeg failed: {' '.join(args)}\n{result.stderr}")


def _wav_duration(path: Path) -> float:
    with wave.open(str(path), "rb") as wav_file:
        return wav_file.getnframes() / wav_file.getframerate()


def _mean_volume_db(path: Path) -> float:
    """Measure a wav's mean volume in dBFS via ffmpeg's volumedetect filter."""
    result = subprocess.run(
        ["ffmpeg", "-hide_banner", "-i", str(path), "-af", "volumedetect", "-f", "null", "-"],
        capture_output=True,
        text=True,
    )
    match = re.search(r"mean_volume:\s*(-?\d+(?:\.\d+)?)\s*dB", result.stderr)
    if not match:
        raise FixtureError(f"could not read mean_volume from ffmpeg output for {path}")
    return float(match.group(1))


def voice_frequency(voice_name: str) -> int:
    """Deterministic dry-run tone frequency for a voice, distinct enough to tell voices apart."""
    digest = hashlib.sha1(voice_name.encode()).hexdigest()
    return 150 + (int(digest[:4], 16) % 700)


def synth_turn_dry_run(text: str, voice_name: str, out_path: Path) -> None:
    """Render a sine tone standing in for a turn's speech, sized to the text's estimate."""
    duration = estimate_duration(text)
    frequency = voice_frequency(voice_name)
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={frequency}:sample_rate={SAMPLE_RATE}:duration={duration}",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(out_path),
        ]
    )


def _resolve_api_key() -> str:
    key = os.environ.get("ELEVENLABS_API_KEY")
    if key:
        return key
    if ELEVENLABS_KEY_FILE.is_file():
        return ELEVENLABS_KEY_FILE.read_text().strip()
    raise FixtureError(
        f"no ElevenLabs API key found: set ELEVENLABS_API_KEY or write it to {ELEVENLABS_KEY_FILE}"
    )


def synth_turn_real(text: str, voice: Voice, out_path: Path) -> None:
    """Call the ElevenLabs text-to-speech endpoint and write the result as a 16 kHz PCM wav.

    Never exercised by --dry-run or by the test suite: this is the only function
    in this file that talks to the network, and every call spends the caller's
    ElevenLabs credit.
    """
    import httpx  # local import: dry-run and tests must never require this dependency

    if voice.voice_id == PLACEHOLDER_VOICE_ID:
        raise FixtureError(
            "voices.yaml still has a placeholder voice_id: fill it in before running "
            "generate.py without --dry-run"
        )
    api_key = _resolve_api_key()
    url = ELEVENLABS_TTS_URL.format(voice_id=voice.voice_id)
    response = httpx.post(
        url,
        params={"output_format": "pcm_16000"},
        headers={"xi-api-key": api_key, "Content-Type": "application/json"},
        json={"text": text, "model_id": "eleven_multilingual_v2"},
        timeout=60.0,
    )
    response.raise_for_status()
    with wave.open(str(out_path), "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)  # 16-bit PCM, matching output_format=pcm_16000
        wav_file.setframerate(SAMPLE_RATE)
        wav_file.writeframes(response.content)


def synth_turn_piper(text: str, voice: Voice, out_path: Path, data_dir: Path) -> None:
    """Speak `text` with Piper and write it as a 16 kHz mono wav.

    Piper is MIT and its LibriTTS-R voice is CC BY 4.0, which is why this
    path exists: the one clip that ships inside the repository has
    to be redistributable by anyone who clones it, and that rules out the
    ElevenLabs path next to this one. Piper writes 22.05 kHz, so the result is
    resampled to the rate the rest of the pipeline works at.
    """
    if not voice.piper_model or voice.piper_speaker is None:
        raise FixtureError(
            f"voice '{voice.voice_id}' has no piper_model/piper_speaker: "
            "--piper needs both in voices.yaml"
        )
    raw = out_path.with_suffix(".piper.wav")
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "piper",
            "-m",
            voice.piper_model,
            "-s",
            str(voice.piper_speaker),
            "--data-dir",
            str(data_dir),
            # Piper normalizes each utterance to full scale, so asking for a
            # lower volume without also disabling that is a no-op: both flags
            # together are what leaves headroom, and without them a handful of
            # samples clip. Inaudible, but a reference clip that other people
            # measure against should not have any.
            "--no-normalize",
            "--volume",
            "0.8",
            "-f",
            str(raw),
        ],
        input=text.encode(),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0 or not raw.is_file():
        raise FixtureError(f"piper failed for '{text[:40]}...': {result.stderr.decode()[-400:]}")
    _run_ffmpeg(
        ["-i", str(raw), "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(out_path)]
    )
    raw.unlink()


def _mix_turns(turn_paths: list[Path], starts: list[float], out_path: Path) -> None:
    """Layer each turn's audio at its planned start time and mix down to one wav.

    adelay places each turn on the timeline, and amix sums them with
    normalize=0. The default, normalize=1, divides by the number of inputs,
    which here is the number of turns, not the number of voices sounding at
    once, so a ten-turn case would come out roughly ten times too quiet. The
    limiter applied at the end of the chain is what keeps overlapping turns
    from clipping.
    """
    inputs: list[str] = []
    for path in turn_paths:
        inputs += ["-i", str(path)]
    delayed = ";".join(
        f"[{i}:a]adelay={int(start * 1000)}:all=1[a{i}]" for i, start in enumerate(starts)
    )
    joined = "".join(f"[a{i}]" for i in range(len(turn_paths)))
    filter_complex = f"{delayed};{joined}amix=inputs={len(turn_paths)}:normalize=0[mix]"
    _run_ffmpeg(
        [
            *inputs,
            "-filter_complex",
            filter_complex,
            "-map",
            "[mix]",
            "-c:a",
            "pcm_s16le",
            str(out_path),
        ]
    )


def _apply_noise(in_path: Path, out_path: Path, snr_db: float, tmp_dir: Path) -> None:
    """Add pink noise to `in_path` at the given signal-to-noise ratio."""
    duration = _wav_duration(in_path)
    signal_db = _mean_volume_db(in_path)
    noise_raw = tmp_dir / "noise_raw.wav"
    _run_ffmpeg(
        [
            "-f",
            "lavfi",
            "-i",
            f"anoisesrc=color=pink:sample_rate={SAMPLE_RATE}:amplitude=1:duration={duration}",
            "-ac",
            "1",
            "-c:a",
            "pcm_s16le",
            str(noise_raw),
        ]
    )
    noise_raw_db = _mean_volume_db(noise_raw)
    gain_db = (signal_db - snr_db) - noise_raw_db
    noise_final = tmp_dir / "noise_final.wav"
    _run_ffmpeg(
        ["-i", str(noise_raw), "-af", f"volume={gain_db}dB", "-c:a", "pcm_s16le", str(noise_final)]
    )
    _run_ffmpeg(
        [
            "-i",
            str(in_path),
            "-i",
            str(noise_final),
            "-filter_complex",
            "amix=inputs=2:normalize=0[mix]",
            "-map",
            "[mix]",
            "-c:a",
            "pcm_s16le",
            str(out_path),
        ]
    )


def _apply_telephone(in_path: Path, out_path: Path, tmp_dir: Path) -> None:
    """Simulate a phone line: downsample to 8 kHz, mu-law encode, resample back to 16 kHz.

    This is a codec applied after the fact, not a live call: it has no jitter
    and no packet loss (see README's Limitations section).
    """
    narrowband = tmp_dir / "telephone_8k.wav"
    _run_ffmpeg(["-i", str(in_path), "-ar", "8000", "-c:a", "pcm_mulaw", str(narrowband)])
    _run_ffmpeg(
        ["-i", str(narrowband), "-ar", str(SAMPLE_RATE), "-c:a", "pcm_s16le", str(out_path)]
    )


def _apply_limiter(in_path: Path, out_path: Path) -> None:
    """Final safety net: cap peaks so an effects chain can never clip the output."""
    _run_ffmpeg(
        [
            "-i",
            str(in_path),
            "-af",
            "alimiter=limit=0.97:attack=5:release=50",
            "-c:a",
            "pcm_s16le",
            str(out_path),
        ]
    )


def build_rttm(file_id: str, segments: list[PlannedSegment]) -> str:
    """Render segments as standard RTTM lines, one SPEAKER row per turn."""
    lines = [
        f"SPEAKER {file_id} 1 {seg.start:.3f} {seg.duration:.3f} <NA> <NA> {seg.speaker} <NA> <NA>"
        for seg in segments
    ]
    return "\n".join(lines) + "\n"


def generate_case(
    case: Case,
    voices: dict[str, Voice],
    out_dir: Path,
    dry_run: bool,
    piper_data_dir: Path | None = None,
) -> Path:
    """Synthesize `case` and write its .wav, .rttm and .json under `out_dir`.

    Returns the path to the .wav. Raises FixtureError on any missing voice,
    placeholder id (outside --dry-run), or ffmpeg failure.
    """
    for turn in case.turns:
        if turn.voice not in voices:
            raise FixtureError(f"case '{case.id}': unknown voice '{turn.voice}'")

    with tempfile.TemporaryDirectory(prefix=f"voxtrama-eval-{case.id}-") as tmp:
        tmp_dir = Path(tmp)
        turn_paths: list[Path] = []
        turn_durations: list[float] = []
        for i, turn in enumerate(case.turns):
            turn_path = tmp_dir / f"turn-{i:02d}.wav"
            if dry_run:
                synth_turn_dry_run(turn.text, turn.voice, turn_path)
            elif piper_data_dir is not None:
                synth_turn_piper(turn.text, voices[turn.voice], turn_path, piper_data_dir)
            else:
                synth_turn_real(turn.text, voices[turn.voice], turn_path)
            turn_paths.append(turn_path)
            turn_durations.append(_wav_duration(turn_path))

        segments: list[PlannedSegment] = []
        cursor = 0.0
        for turn, duration in zip(case.turns, turn_durations, strict=True):
            start = max(0.0, cursor - turn.overlap_ms / 1000)
            segments.append(PlannedSegment(speaker=turn.voice, start=start, duration=duration))
            cursor = start + duration

        mixed = tmp_dir / "mixed.wav"
        _mix_turns(turn_paths, [seg.start for seg in segments], mixed)

        current = mixed
        if "noise_snr_db" in case.effects:
            noisy = tmp_dir / "noisy.wav"
            _apply_noise(current, noisy, float(case.effects["noise_snr_db"]), tmp_dir)
            current = noisy
        if case.effects.get("telephone"):
            telephone = tmp_dir / "telephone.wav"
            _apply_telephone(current, telephone, tmp_dir)
            current = telephone

        out_dir.mkdir(parents=True, exist_ok=True)
        final_wav = out_dir / f"{case.id}.wav"
        _apply_limiter(current, final_wav)

        rttm_path = out_dir / f"{case.id}.rttm"
        rttm_path.write_text(build_rttm(case.id, segments))

        wav_bytes = final_wav.read_bytes()
        metadata = {
            "case_id": case.id,
            "language": case.language,
            "speakers": case.speakers,
            "duration_seconds": round(_wav_duration(final_wav), 3),
            "effects": case.effects,
            "sha256": hashlib.sha256(wav_bytes).hexdigest(),
            "synthetic": True,
            "note": "Synthetic speech generated for evaluation: no real speaker was recorded.",
        }
        (out_dir / f"{case.id}.json").write_text(json.dumps(metadata, indent=2) + "\n")

        return final_wav


def fetch_account_voices() -> list[dict[str, Any]]:
    """List the voices this ElevenLabs account can use.

    Reading the voice list is free: unlike synthesis, GET /v1/voices spends no
    credit. It exists so nobody has to copy voice ids out of a web page by
    hand.
    """
    import httpx  # local import: dry-run and tests must never require this dependency

    response = httpx.get(
        ELEVENLABS_VOICES_URL, headers={"xi-api-key": _resolve_api_key()}, timeout=30.0
    )
    response.raise_for_status()
    return list(response.json().get("voices", []))


def _voice_gender(voice: dict[str, Any]) -> str | None:
    labels = voice.get("labels") or {}
    gender = labels.get("gender")
    return gender.lower() if isinstance(gender, str) else None


def autofill_voices(path: Path) -> int:
    """Rewrite voices.yaml, giving every logical voice a real id from the account.

    Language is a property of the text, not of the voice: eleven_multilingual_v2
    reads Italian and English with the same voice, so the only thing that has to
    differ between logical voices is the voice itself. Two speakers in one clip
    must never resolve to the same id, or the diarization ground truth would
    describe a conversation that is not there.
    """
    declared = load_voices(path)
    available = fetch_account_voices()
    if len(available) < len(declared):
        raise FixtureError(
            f"the account exposes {len(available)} voices but {len(declared)} are declared "
            f"in {path.name}: add voices to the account, or drop cases"
        )

    by_gender: dict[str, list[dict[str, Any]]] = {}
    for voice in available:
        # The account may label a voice anything at all ("neutral" shows up in
        # the default set), so the buckets come from the data, not from a list
        # of genders we happen to expect.
        by_gender.setdefault(_voice_gender(voice) or "unknown", []).append(voice)

    assigned: dict[str, dict[str, Any]] = {}
    used: set[str] = set()
    for name, declared_voice in declared.items():
        pool = by_gender.get(declared_voice.gender, []) + by_gender.get("unknown", []) + available
        pick = next((v for v in pool if v["voice_id"] not in used), None)
        if pick is None:
            raise FixtureError(f"ran out of distinct voices while assigning '{name}'")
        used.add(pick["voice_id"])
        assigned[name] = pick

    lines = [
        "# Logical voice -> ElevenLabs voice_id, used by generate.py and referenced by",
        "# name from cases.yaml. Written by `generate.py --autofill-voices`, which picks",
        "# distinct voices from the account; edit by hand to pin different ones.",
        "voices:",
    ]
    for name, declared_voice in declared.items():
        pick = assigned[name]
        lines += [
            f"  {name}:",
            f"    voice_id: {pick['voice_id']}  # {pick.get('name', 'unnamed')}",
            f"    language: {declared_voice.language}",
            f"    gender: {declared_voice.gender}",
        ]
    path.write_text("\n".join(lines) + "\n")
    return len(assigned)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--cases", type=Path, default=DEFAULT_CASES_PATH, help="Path to cases.yaml."
    )
    parser.add_argument("--only", default=None, help="Generate only the case with this id.")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT_DIR, help="Output directory.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Replace ElevenLabs synthesis with ffmpeg sine tones.",
    )
    parser.add_argument(
        "--piper",
        type=Path,
        default=None,
        metavar="DATA_DIR",
        help=(
            "Synthesize with Piper instead of ElevenLabs, loading voices from DATA_DIR. "
            "Used for the one fixture that ships inside the repository."
        ),
    )
    parser.add_argument(
        "--list-voices",
        action="store_true",
        help="Print the voices this ElevenLabs account can use, and exit. Spends no credit.",
    )
    parser.add_argument(
        "--autofill-voices",
        action="store_true",
        help="Fill voices.yaml with real ids from the account, and exit. Spends no credit.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    if args.list_voices or args.autofill_voices:
        try:
            if args.list_voices:
                for voice in fetch_account_voices():
                    gender = _voice_gender(voice) or "unknown"
                    print(f"{voice['voice_id']}  {gender:<7} {voice.get('name', 'unnamed')}")
            else:
                count = autofill_voices(DEFAULT_VOICES_PATH)
                print(f"wrote {count} voice ids to {DEFAULT_VOICES_PATH}")
        except FixtureError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 1
        return 0

    if not ffmpeg_available():
        print("error: ffmpeg is required and was not found on PATH", file=sys.stderr)
        return 1

    cases = load_cases(args.cases)
    if args.only:
        cases = [c for c in cases if c.id == args.only]
        if not cases:
            print(f"error: no case with id '{args.only}' in {args.cases}", file=sys.stderr)
            return 1

    voices = load_voices(DEFAULT_VOICES_PATH)
    for case in cases:
        try:
            wav_path = generate_case(
                case, voices, args.out, dry_run=args.dry_run, piper_data_dir=args.piper
            )
        except FixtureError as exc:
            print(f"error: {case.id}: {exc}", file=sys.stderr)
            return 1
        print(f"generated {wav_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
