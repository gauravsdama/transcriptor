from __future__ import annotations

import argparse
from pathlib import Path

from transcriptor.pipeline import (
    list_speaker_ids,
    load_recording_document,
    load_speaker_names,
    normalize_speaker_id,
    save_speaker_names,
    speaker_display_name,
    write_transcript,
)


class SpeakerNamingService:
    def __init__(self, *, recordings_dir: Path, speaker_names_file: Path) -> None:
        self.recordings_dir = recordings_dir
        self.speaker_names_file = speaker_names_file

    def list_recordings(self) -> list[str]:
        if not self.recordings_dir.exists():
            return []
        return sorted(path.stem for path in self.recordings_dir.glob("*.json"))

    def show_recording(self, recording_id: str) -> str:
        transcript = load_recording_document(self._recording_path(recording_id))
        speaker_names = load_speaker_names(self.speaker_names_file).get(
            recording_id, {}
        )
        lines = [
            f"Recording ID: {recording_id}",
            f"Transcript path: {transcript.transcript_path}",
            f"Diarization enabled: {transcript.diarization_enabled}",
        ]
        speaker_ids = list_speaker_ids(transcript)
        if not speaker_ids:
            lines.append("Speakers: none")
        else:
            lines.append("Speakers:")
            for speaker_id in speaker_ids:
                lines.append(
                    f"- {speaker_id} -> {speaker_display_name(speaker_id, speaker_names)}"
                )
        return "\n".join(lines)

    def set_speaker_name(self, recording_id: str, speaker_id: str, name: str) -> None:
        all_names = load_speaker_names(self.speaker_names_file)
        normalized = normalize_speaker_id(speaker_id)
        all_names.setdefault(recording_id, {})[normalized] = name.strip()
        save_speaker_names(self.speaker_names_file, all_names)
        self.rerender_recording(recording_id)

    def unset_speaker_name(self, recording_id: str, speaker_id: str) -> None:
        all_names = load_speaker_names(self.speaker_names_file)
        normalized = normalize_speaker_id(speaker_id)
        if recording_id in all_names:
            all_names[recording_id].pop(normalized, None)
            if not all_names[recording_id]:
                all_names.pop(recording_id)
        save_speaker_names(self.speaker_names_file, all_names)
        self.rerender_recording(recording_id)

    def rerender_recording(self, recording_id: str) -> None:
        transcript = load_recording_document(self._recording_path(recording_id))
        speaker_names = load_speaker_names(self.speaker_names_file).get(
            recording_id, {}
        )
        write_transcript(
            Path(transcript.transcript_path),
            transcript,
            transcript.output_format,
            speaker_names,
        )

    def _recording_path(self, recording_id: str) -> Path:
        path = self.recordings_dir / f"{recording_id}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"No structured recording state found for recording ID {recording_id!r}."
            )
        return path


def build_parser() -> argparse.ArgumentParser:
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"

    parser = argparse.ArgumentParser(
        prog="transcriptor-speakers",
        description="Manage speaker names for processed transcripts and rerender outputs.",
    )
    parser.add_argument(
        "--recordings-dir",
        type=Path,
        default=data_dir / "state" / "recordings",
        help="Folder containing structured transcript JSON state.",
    )
    parser.add_argument(
        "--speaker-names-file",
        type=Path,
        default=data_dir / "state" / "speaker_names.json",
        help="JSON file that stores per-recording speaker name assignments.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("list", help="List recording IDs that can be renamed.")

    show_parser = subparsers.add_parser("show", help="Show speakers for one recording.")
    show_parser.add_argument("recording_id")

    set_parser = subparsers.add_parser("set", help="Assign a name to a speaker label.")
    set_parser.add_argument("recording_id")
    set_parser.add_argument("speaker_id")
    set_parser.add_argument("name")

    unset_parser = subparsers.add_parser(
        "unset", help="Remove a speaker name assignment."
    )
    unset_parser.add_argument("recording_id")
    unset_parser.add_argument("speaker_id")

    rerender_parser = subparsers.add_parser(
        "rerender",
        help="Rewrite the transcript file using the current speaker name mappings.",
    )
    rerender_parser.add_argument("recording_id")

    return parser


def main() -> int:
    args = build_parser().parse_args()
    service = SpeakerNamingService(
        recordings_dir=args.recordings_dir,
        speaker_names_file=args.speaker_names_file,
    )

    if args.command == "list":
        for recording_id in service.list_recordings():
            print(recording_id)
        return 0

    try:
        if args.command == "show":
            print(service.show_recording(args.recording_id))
            return 0
        if args.command == "set":
            service.set_speaker_name(args.recording_id, args.speaker_id, args.name)
            print(
                f"Updated {args.recording_id} {normalize_speaker_id(args.speaker_id)} -> {args.name}"
            )
            return 0
        if args.command == "unset":
            service.unset_speaker_name(args.recording_id, args.speaker_id)
            print(
                f"Removed name for {args.recording_id} {normalize_speaker_id(args.speaker_id)}"
            )
            return 0
        if args.command == "rerender":
            service.rerender_recording(args.recording_id)
            print(f"Rerendered transcript for {args.recording_id}")
            return 0
    except FileNotFoundError as exc:
        print(str(exc))
        return 1

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
