from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SUPPORTED_AUDIO_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".flac",
    ".m4a",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".oga",
    ".ogg",
    ".wav",
    ".webm",
}


@dataclass(slots=True)
class TranscriptSegment:
    start_seconds: float
    end_seconds: float
    text: str
    speaker_id: str | None = None


@dataclass(slots=True)
class DiarizationSegment:
    start_seconds: float
    end_seconds: float
    speaker_id: str


@dataclass(slots=True)
class TranscriptDocument:
    recording_id: str
    source_name: str
    source_path: str
    source_sha256: str
    created_at: str
    language: str | None
    language_probability: float | None
    duration_seconds: float | None
    model: str
    task: str
    transcript_path: str
    output_format: str
    diarization_enabled: bool
    diarization_source: str | None
    segment_count: int
    segments: list[TranscriptSegment]
    diarization_segments: list[DiarizationSegment]


class PyannoteDiarizer:
    def __init__(
        self,
        *,
        model_name: str,
        hf_token: str | None,
        device: str,
        num_speakers: int | None,
        min_speakers: int | None,
        max_speakers: int | None,
    ) -> None:
        self.model_name = model_name
        self.hf_token = hf_token
        self.device = device
        self.num_speakers = num_speakers
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers
        self._pipeline: Any | None = None

    def _load_pipeline(self) -> Any:
        if self._pipeline is not None:
            return self._pipeline
        cache_root = Path(tempfile.gettempdir()) / "transcriptor-runtime-cache"
        matplotlib_cache = cache_root / "matplotlib"
        xdg_cache = cache_root / "xdg-cache"
        cache_root.mkdir(parents=True, exist_ok=True)
        matplotlib_cache.mkdir(parents=True, exist_ok=True)
        xdg_cache.mkdir(parents=True, exist_ok=True)
        os.environ.setdefault("MPLCONFIGDIR", str(matplotlib_cache))
        os.environ.setdefault("XDG_CACHE_HOME", str(xdg_cache))
        try:
            from pyannote.audio import Pipeline
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing dependency 'pyannote.audio'. Install with `pip install -e .[diarization]`."
            ) from exc

        if self.model_name.startswith("pyannote/") and not self.hf_token:
            raise RuntimeError(
                "Diarization requires a Hugging Face token for the hosted pyannote model download. "
                "Pass --hf-token or set HUGGINGFACE_TOKEN."
            )

        self._pipeline = Pipeline.from_pretrained(self.model_name, token=self.hf_token)
        if self.device != "cpu":
            try:
                import torch
            except ModuleNotFoundError as exc:
                raise RuntimeError(
                    "Non-CPU diarization requested but torch is not available."
                ) from exc
            self._pipeline.to(torch.device(self.device))
        return self._pipeline

    def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
        pipeline = self._load_pipeline()
        diarization_kwargs: dict[str, int] = {}
        if self.num_speakers is not None:
            diarization_kwargs["num_speakers"] = self.num_speakers
        if self.min_speakers is not None:
            diarization_kwargs["min_speakers"] = self.min_speakers
        if self.max_speakers is not None:
            diarization_kwargs["max_speakers"] = self.max_speakers

        result = pipeline(str(audio_path), **diarization_kwargs)
        annotation = getattr(result, "speaker_diarization", result)
        if hasattr(annotation, "itertracks"):
            iterator = annotation.itertracks(yield_label=True)
        else:
            iterator = annotation

        segments: list[DiarizationSegment] = []
        for item in iterator:
            if len(item) == 3:
                turn, _, speaker = item
            else:
                turn, speaker = item
            segments.append(
                DiarizationSegment(
                    start_seconds=float(turn.start),
                    end_seconds=float(turn.end),
                    speaker_id=normalize_speaker_id(str(speaker)),
                )
            )
        return segments


class WhisperTranscriber:
    def __init__(
        self,
        *,
        model_name: str,
        device: str,
        compute_type: str,
        language: str | None,
        task: str,
        beam_size: int,
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.task = task
        self.beam_size = beam_size
        self._model: Any | None = None

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        try:
            from faster_whisper import WhisperModel
        except ModuleNotFoundError as exc:
            raise RuntimeError(
                "Missing dependency 'faster-whisper'. Install the project dependencies first."
            ) from exc

        self._model = WhisperModel(
            self.model_name,
            device=self.device,
            compute_type=self.compute_type,
        )
        return self._model

    def transcribe(
        self,
        audio_path: Path,
        source_sha256: str,
        *,
        transcript_path: Path,
        output_format: str,
    ) -> TranscriptDocument:
        model = self._load_model()
        segments_iter, info = model.transcribe(
            str(audio_path),
            language=self.language,
            task=self.task,
            beam_size=self.beam_size,
            vad_filter=True,
            condition_on_previous_text=False,
        )
        segments = [
            TranscriptSegment(
                start_seconds=float(segment.start),
                end_seconds=float(segment.end),
                text=segment.text.strip(),
            )
            for segment in segments_iter
        ]
        return TranscriptDocument(
            recording_id=source_sha256,
            source_name=audio_path.name,
            source_path=str(audio_path.resolve()),
            source_sha256=source_sha256,
            created_at=datetime.now(UTC).isoformat(),
            language=getattr(info, "language", None),
            language_probability=getattr(info, "language_probability", None),
            duration_seconds=getattr(info, "duration", None),
            model=self.model_name,
            task=self.task,
            transcript_path=str(transcript_path.resolve()),
            output_format=output_format,
            diarization_enabled=False,
            diarization_source=None,
            segment_count=len(segments),
            segments=segments,
            diarization_segments=[],
        )


class InboxTranscriptionPipeline:
    def __init__(
        self,
        *,
        inbox_dir: Path,
        transcripts_dir: Path,
        archive_dir: Path,
        state_file: Path,
        recordings_dir: Path,
        speaker_names_file: Path,
        model_name: str,
        language: str | None,
        task: str,
        output_format: str,
        compute_type: str,
        device: str,
        beam_size: int,
        force: bool,
        archive_audio: bool,
        dry_run: bool,
        extensions: set[str],
        diarizer: Any | None = None,
        transcriber: Any | None = None,
    ) -> None:
        self.inbox_dir = inbox_dir
        self.transcripts_dir = transcripts_dir
        self.archive_dir = archive_dir
        self.state_file = state_file
        self.recordings_dir = recordings_dir
        self.speaker_names_file = speaker_names_file
        self.output_format = output_format
        self.force = force
        self.archive_audio = archive_audio
        self.dry_run = dry_run
        self.extensions = {suffix if suffix.startswith(".") else f".{suffix}" for suffix in extensions}
        self.diarizer = diarizer
        self.transcriber = transcriber or WhisperTranscriber(
            model_name=model_name,
            device=device,
            compute_type=compute_type,
            language=language,
            task=task,
            beam_size=beam_size,
        )

    def run(self) -> int:
        self._ensure_directories()
        manifest = self._load_manifest()
        speaker_names = load_speaker_names(self.speaker_names_file)
        audio_files = self._discover_audio_files()
        if not audio_files:
            print(f"No new audio files found in {self.inbox_dir}")
            return 0

        processed_count = 0
        skipped_count = 0

        for audio_path in audio_files:
            digest = sha256_for_file(audio_path)
            if not self.force and digest in manifest:
                skipped_count += 1
                print(f"Skipping {audio_path.name}: already processed")
                continue

            transcript_path = self._build_output_path(audio_path, digest)
            if self.dry_run:
                print(f"Would process {audio_path.name} -> {transcript_path.name}")
                continue

            print(f"Transcribing {audio_path.name}")
            transcript = self.transcriber.transcribe(
                audio_path,
                digest,
                transcript_path=transcript_path,
                output_format=self.output_format,
            )
            if self.diarizer is not None:
                diarization_segments = self.diarizer.diarize(audio_path)
                transcript = apply_diarization(
                    transcript,
                    diarization_segments,
                    diarization_source=getattr(self.diarizer, "model_name", self.diarizer.__class__.__name__),
                )
            save_recording_document(
                self._recording_document_path(digest),
                transcript,
            )
            write_transcript(
                transcript_path,
                transcript,
                self.output_format,
                speaker_names.get(digest, {}),
            )

            archived_path = None
            if self.archive_audio:
                archived_path = self._archive_audio(audio_path, digest)

            manifest[digest] = {
                "source_name": audio_path.name,
                "source_sha256": digest,
                "processed_at": datetime.now(UTC).isoformat(),
                "transcript_path": str(transcript_path.resolve()),
                "transcript_markdown_path": str(
                    companion_output_path(transcript_path, "md").resolve()
                ),
                "transcript_text_path": str(
                    companion_output_path(transcript_path, "txt").resolve()
                ),
                "archived_audio_path": str(archived_path.resolve()) if archived_path else None,
                "recording_document_path": str(self._recording_document_path(digest).resolve()),
                "language": transcript.language,
                "segment_count": transcript.segment_count,
                "speaker_count": len(list_speaker_ids(transcript)),
                "duration_seconds": transcript.duration_seconds,
            }
            processed_count += 1

        if not self.dry_run:
            self._save_manifest(manifest)

        print(
            f"Finished. processed={processed_count} skipped={skipped_count} dry_run={self.dry_run}"
        )
        return 0

    def _ensure_directories(self) -> None:
        self.inbox_dir.mkdir(parents=True, exist_ok=True)
        self.transcripts_dir.mkdir(parents=True, exist_ok=True)
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        self.recordings_dir.mkdir(parents=True, exist_ok=True)
        self.speaker_names_file.parent.mkdir(parents=True, exist_ok=True)
        if self.archive_audio:
            self.archive_dir.mkdir(parents=True, exist_ok=True)

    def _discover_audio_files(self) -> list[Path]:
        files = [
            path
            for path in sorted(self.inbox_dir.iterdir())
            if path.is_file() and path.suffix.lower() in self.extensions
        ]
        return files

    def _load_manifest(self) -> dict[str, dict[str, Any]]:
        if not self.state_file.exists():
            return {}
        try:
            with self.state_file.open("r", encoding="utf-8") as handle:
                return json.load(handle)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"State file is not valid JSON: {self.state_file}"
            ) from exc

    def _save_manifest(self, manifest: dict[str, dict[str, Any]]) -> None:
        with self.state_file.open("w", encoding="utf-8") as handle:
            json.dump(manifest, handle, indent=2, sort_keys=True)
            handle.write("\n")

    def _build_output_path(self, audio_path: Path, digest: str) -> Path:
        suffix = ".md" if self.output_format == "md" else ".txt"
        filename = f"{audio_path.stem}--{digest[:8]}{suffix}"
        return self.transcripts_dir / filename

    def _archive_audio(self, audio_path: Path, digest: str) -> Path:
        target = self.archive_dir / f"{audio_path.stem}--{digest[:8]}{audio_path.suffix.lower()}"
        counter = 1
        while target.exists():
            target = self.archive_dir / (
                f"{audio_path.stem}--{digest[:8]}--{counter}{audio_path.suffix.lower()}"
            )
            counter += 1
        shutil.move(str(audio_path), str(target))
        return target

    def _recording_document_path(self, digest: str) -> Path:
        return self.recordings_dir / f"{digest}.json"


def sha256_for_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_transcript(
    output_path: Path,
    transcript: TranscriptDocument,
    output_format: str,
    speaker_names: dict[str, str] | None = None,
) -> None:
    resolved_names = speaker_names or {}
    markdown_path = companion_output_path(output_path, "md")
    text_path = companion_output_path(output_path, "txt")
    markdown_path.write_text(render_markdown(transcript, resolved_names), encoding="utf-8")
    text_path.write_text(render_plain_text(transcript, resolved_names), encoding="utf-8")
    if output_format not in {"md", "txt"}:
        raise RuntimeError(f"Unsupported output format: {output_format}")


def render_markdown(
    transcript: TranscriptDocument,
    speaker_names: dict[str, str] | None = None,
) -> str:
    resolved_names = speaker_names or {}
    metadata_lines = [
        f"# Transcript: {transcript.source_name}",
        "",
        f"- Recording ID: `{transcript.recording_id}`",
        f"- Source path: `{transcript.source_path}`",
        f"- SHA256: `{transcript.source_sha256}`",
        f"- Created at: `{transcript.created_at}`",
        f"- Model: `{transcript.model}`",
        f"- Task: `{transcript.task}`",
        f"- Language: `{transcript.language or 'unknown'}`",
    ]
    if transcript.language_probability is not None:
        metadata_lines.append(
            f"- Language confidence: `{transcript.language_probability:.3f}`"
        )
    if transcript.duration_seconds is not None:
        metadata_lines.append(
            f"- Duration: `{format_seconds(transcript.duration_seconds)}`"
        )
    metadata_lines.extend(
        [
            f"- Segments: `{transcript.segment_count}`",
            f"- Speakers: `{len(list_speaker_ids(transcript))}`",
            f"- Diarization: `{'enabled' if transcript.diarization_enabled else 'disabled'}`",
            "",
            "## Speakers",
            "",
        ]
    )
    speaker_ids = list_speaker_ids(transcript)
    if speaker_ids:
        for speaker_id in speaker_ids:
            metadata_lines.append(
                f"- `{speaker_id}`: {speaker_display_name(speaker_id, resolved_names)}"
            )
    else:
        metadata_lines.append("- No speaker labels")
    metadata_lines.extend(
        [
            "",
            "## Transcript",
            "",
        ]
    )
    for segment in transcript.segments:
        prefix = render_speaker_prefix(segment.speaker_id, resolved_names)
        metadata_lines.append(
            f"[{format_seconds(segment.start_seconds)} - {format_seconds(segment.end_seconds)}] "
            f"{prefix}{segment.text}"
        )
    metadata_lines.append("")
    metadata_lines.append("## Plain Text")
    metadata_lines.append("")
    metadata_lines.append(join_plain_text(transcript.segments))
    metadata_lines.append("")
    return "\n".join(metadata_lines)


def render_plain_text(
    transcript: TranscriptDocument,
    speaker_names: dict[str, str] | None = None,
) -> str:
    resolved_names = speaker_names or {}
    lines = [
        f"Transcript: {transcript.source_name}",
        f"Recording ID: {transcript.recording_id}",
        f"Created at: {transcript.created_at}",
        f"Model: {transcript.model}",
        "",
    ]
    for segment in transcript.segments:
        prefix = render_speaker_prefix(segment.speaker_id, resolved_names)
        lines.append(
            f"[{format_seconds(segment.start_seconds)} - {format_seconds(segment.end_seconds)}] "
            f"{prefix}{segment.text}"
        )
    lines.append("")
    return "\n".join(lines)


def join_plain_text(segments: list[TranscriptSegment]) -> str:
    return " ".join(segment.text for segment in segments).strip()


def companion_output_path(output_path: Path, output_format: str) -> Path:
    if output_format == "md":
        return output_path.with_suffix(".md")
    if output_format == "txt":
        return output_path.with_suffix(".txt")
    raise RuntimeError(f"Unsupported output format: {output_format}")


def normalize_speaker_id(raw_speaker_id: str) -> str:
    match = re.fullmatch(r"speaker[_\s-]*(\d+)", raw_speaker_id.strip(), re.IGNORECASE)
    if match:
        return f"SPEAKER_{int(match.group(1)):02d}"
    normalized = re.sub(r"[^A-Za-z0-9]+", "_", raw_speaker_id.strip()).strip("_").upper()
    return normalized or "SPEAKER_UNKNOWN"


def apply_diarization(
    transcript: TranscriptDocument,
    diarization_segments: list[DiarizationSegment],
    *,
    diarization_source: str,
) -> TranscriptDocument:
    updated_segments = [
        TranscriptSegment(
            start_seconds=segment.start_seconds,
            end_seconds=segment.end_seconds,
            text=segment.text,
            speaker_id=best_matching_speaker(segment, diarization_segments),
        )
        for segment in transcript.segments
    ]
    return TranscriptDocument(
        recording_id=transcript.recording_id,
        source_name=transcript.source_name,
        source_path=transcript.source_path,
        source_sha256=transcript.source_sha256,
        created_at=transcript.created_at,
        language=transcript.language,
        language_probability=transcript.language_probability,
        duration_seconds=transcript.duration_seconds,
        model=transcript.model,
        task=transcript.task,
        transcript_path=transcript.transcript_path,
        output_format=transcript.output_format,
        diarization_enabled=True,
        diarization_source=diarization_source,
        segment_count=len(updated_segments),
        segments=updated_segments,
        diarization_segments=diarization_segments,
    )


def best_matching_speaker(
    transcript_segment: TranscriptSegment,
    diarization_segments: list[DiarizationSegment],
) -> str | None:
    best_speaker = None
    best_overlap = 0.0
    for diarization_segment in diarization_segments:
        overlap = overlap_seconds(
            transcript_segment.start_seconds,
            transcript_segment.end_seconds,
            diarization_segment.start_seconds,
            diarization_segment.end_seconds,
        )
        if overlap > best_overlap:
            best_overlap = overlap
            best_speaker = diarization_segment.speaker_id
    return best_speaker


def overlap_seconds(
    start_a: float,
    end_a: float,
    start_b: float,
    end_b: float,
) -> float:
    return max(0.0, min(end_a, end_b) - max(start_a, start_b))


def speaker_display_name(speaker_id: str, speaker_names: dict[str, str]) -> str:
    if speaker_id in speaker_names and speaker_names[speaker_id].strip():
        return speaker_names[speaker_id].strip()
    match = re.fullmatch(r"SPEAKER_(\d+)", speaker_id)
    if match:
        return f"Speaker {int(match.group(1)) + 1}"
    return speaker_id.replace("_", " ").title()


def render_speaker_prefix(
    speaker_id: str | None,
    speaker_names: dict[str, str],
) -> str:
    if not speaker_id:
        return ""
    return f"{speaker_display_name(speaker_id, speaker_names)}: "


def list_speaker_ids(transcript: TranscriptDocument) -> list[str]:
    ordered: list[str] = []
    seen: set[str] = set()
    for segment in transcript.segments:
        if segment.speaker_id and segment.speaker_id not in seen:
            seen.add(segment.speaker_id)
            ordered.append(segment.speaker_id)
    for segment in transcript.diarization_segments:
        if segment.speaker_id not in seen:
            seen.add(segment.speaker_id)
            ordered.append(segment.speaker_id)
    return ordered


def transcript_document_to_dict(transcript: TranscriptDocument) -> dict[str, Any]:
    return {
        "recording_id": transcript.recording_id,
        "source_name": transcript.source_name,
        "source_path": transcript.source_path,
        "source_sha256": transcript.source_sha256,
        "created_at": transcript.created_at,
        "language": transcript.language,
        "language_probability": transcript.language_probability,
        "duration_seconds": transcript.duration_seconds,
        "model": transcript.model,
        "task": transcript.task,
        "transcript_path": transcript.transcript_path,
        "output_format": transcript.output_format,
        "diarization_enabled": transcript.diarization_enabled,
        "diarization_source": transcript.diarization_source,
        "segment_count": transcript.segment_count,
        "segments": [
            {
                "start_seconds": segment.start_seconds,
                "end_seconds": segment.end_seconds,
                "text": segment.text,
                "speaker_id": segment.speaker_id,
            }
            for segment in transcript.segments
        ],
        "diarization_segments": [
            {
                "start_seconds": segment.start_seconds,
                "end_seconds": segment.end_seconds,
                "speaker_id": segment.speaker_id,
            }
            for segment in transcript.diarization_segments
        ],
    }


def transcript_document_from_dict(payload: dict[str, Any]) -> TranscriptDocument:
    return TranscriptDocument(
        recording_id=payload["recording_id"],
        source_name=payload["source_name"],
        source_path=payload["source_path"],
        source_sha256=payload["source_sha256"],
        created_at=payload["created_at"],
        language=payload.get("language"),
        language_probability=payload.get("language_probability"),
        duration_seconds=payload.get("duration_seconds"),
        model=payload["model"],
        task=payload["task"],
        transcript_path=payload["transcript_path"],
        output_format=payload["output_format"],
        diarization_enabled=payload.get("diarization_enabled", False),
        diarization_source=payload.get("diarization_source"),
        segment_count=payload["segment_count"],
        segments=[
            TranscriptSegment(
                start_seconds=item["start_seconds"],
                end_seconds=item["end_seconds"],
                text=item["text"],
                speaker_id=item.get("speaker_id"),
            )
            for item in payload["segments"]
        ],
        diarization_segments=[
            DiarizationSegment(
                start_seconds=item["start_seconds"],
                end_seconds=item["end_seconds"],
                speaker_id=item["speaker_id"],
            )
            for item in payload.get("diarization_segments", [])
        ],
    )


def save_recording_document(path: Path, transcript: TranscriptDocument) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(transcript_document_to_dict(transcript), handle, indent=2, sort_keys=True)
        handle.write("\n")


def load_recording_document(path: Path) -> TranscriptDocument:
    with path.open("r", encoding="utf-8") as handle:
        return transcript_document_from_dict(json.load(handle))


def load_speaker_names(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    return {
        recording_id: {
            normalize_speaker_id(speaker_id): name
            for speaker_id, name in speaker_map.items()
        }
        for recording_id, speaker_map in payload.items()
    }


def save_speaker_names(path: Path, payload: dict[str, dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")


def format_seconds(seconds: float) -> str:
    rounded = max(0, int(seconds))
    hours, remainder = divmod(rounded, 3600)
    minutes, secs = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"
