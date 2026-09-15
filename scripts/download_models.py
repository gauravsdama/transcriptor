#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Download the local inference models required by Transcriptor."
    )
    parser.add_argument("--whisper-model", default="small")
    parser.add_argument("--diarization", action="store_true")
    parser.add_argument(
        "--diarization-model",
        default="pyannote/speaker-diarization-community-1",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()

    from faster_whisper import WhisperModel

    print(f"Downloading or verifying Whisper model: {args.whisper_model}")
    WhisperModel(args.whisper_model, device="cpu", compute_type="int8")
    print("Whisper model is ready.")

    if args.diarization:
        token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get("HF_TOKEN")
        if not token:
            raise SystemExit(
                "Diarization model download requires HUGGINGFACE_TOKEN or HF_TOKEN."
            )
        from pyannote.audio import Pipeline

        print(f"Downloading or verifying diarization model: {args.diarization_model}")
        Pipeline.from_pretrained(args.diarization_model, token=token)
        print("Diarization model is ready.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
