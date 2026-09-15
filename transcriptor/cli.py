from __future__ import annotations

import argparse
from pathlib import Path

from transcriptor.pipeline import (
    SUPPORTED_AUDIO_EXTENSIONS,
    InboxTranscriptionPipeline,
    PyannoteDiarizer,
)


def build_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"

    parser = argparse.ArgumentParser(
        prog="transcriptor-inbox",
        description="Transcribe audio files from an inbox folder into markdown or text files.",
    )
    parser.add_argument(
        "--inbox",
        type=Path,
        default=data_dir / "inbox",
        help="Folder containing new audio files.",
    )
    parser.add_argument(
        "--transcripts",
        type=Path,
        default=data_dir / "transcripts",
        help="Folder where transcript files will be written.",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=data_dir / "archive",
        help="Folder where processed audio files will be moved.",
    )
    parser.add_argument(
        "--state-file",
        type=Path,
        default=data_dir / "state" / "processed_files.json",
        help="JSON manifest used to skip files that were already processed.",
    )
    parser.add_argument(
        "--recordings-dir",
        type=Path,
        default=data_dir / "state" / "recordings",
        help="Folder for structured transcript JSON used by Phase 2 speaker naming.",
    )
    parser.add_argument(
        "--speaker-names-file",
        type=Path,
        default=data_dir / "state" / "speaker_names.json",
        help="JSON file that stores per-recording speaker name assignments.",
    )
    parser.add_argument(
        "--model",
        default="small",
        help="Whisper model size or local model path. Example: tiny, base, small, medium.",
    )
    parser.add_argument(
        "--language",
        default=None,
        help="Optional spoken language code such as en or es. Leave unset for auto-detect.",
    )
    parser.add_argument(
        "--task",
        choices=("transcribe", "translate"),
        default="transcribe",
        help="Use translate only if you want English output from non-English audio.",
    )
    parser.add_argument(
        "--output-format",
        choices=("md", "txt"),
        default="md",
        help="Transcript file format.",
    )
    parser.add_argument(
        "--compute-type",
        default="int8",
        help="faster-whisper compute type. int8 is the best default for local CPU use.",
    )
    parser.add_argument(
        "--device",
        default="cpu",
        help="Inference device passed to faster-whisper. cpu is the safest default.",
    )
    parser.add_argument(
        "--beam-size",
        type=int,
        default=5,
        help="Beam size for decoding.",
    )
    parser.add_argument(
        "--diarize",
        action="store_true",
        help="Run a local pyannote diarization pass and label transcript segments by speaker.",
    )
    parser.add_argument(
        "--diarization-model",
        default="pyannote/speaker-diarization-community-1",
        help="pyannote diarization pipeline name or local model path.",
    )
    parser.add_argument(
        "--num-speakers",
        type=int,
        default=None,
        help="Exact speaker count hint for diarization.",
    )
    parser.add_argument(
        "--min-speakers",
        type=int,
        default=None,
        help="Lower bound hint for diarization.",
    )
    parser.add_argument(
        "--max-speakers",
        type=int,
        default=None,
        help="Upper bound hint for diarization.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Process files even if the manifest says they were already handled.",
    )
    parser.add_argument(
        "--keep-audio",
        action="store_true",
        help="Keep original audio files in the inbox instead of archiving them.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="List what would be processed without running transcription.",
    )
    parser.add_argument(
        "--extensions",
        nargs="*",
        default=sorted(SUPPORTED_AUDIO_EXTENSIONS),
        help="Audio extensions to scan for. Defaults cover common voice memo formats.",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    diarizer = None
    if args.diarize:
        diarizer = PyannoteDiarizer(
            model_name=args.diarization_model,
            device=args.device,
            num_speakers=args.num_speakers,
            min_speakers=args.min_speakers,
            max_speakers=args.max_speakers,
        )

    pipeline = InboxTranscriptionPipeline(
        inbox_dir=args.inbox,
        transcripts_dir=args.transcripts,
        archive_dir=args.archive,
        state_file=args.state_file,
        recordings_dir=args.recordings_dir,
        speaker_names_file=args.speaker_names_file,
        model_name=args.model,
        language=args.language,
        task=args.task,
        output_format=args.output_format,
        compute_type=args.compute_type,
        device=args.device,
        beam_size=args.beam_size,
        force=args.force,
        archive_audio=not args.keep_audio,
        dry_run=args.dry_run,
        extensions={suffix.lower() for suffix in args.extensions},
        diarizer=diarizer,
    )
    try:
        return pipeline.run()
    except RuntimeError as exc:
        print(str(exc))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
