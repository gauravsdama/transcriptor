# Transcriptor

Transcriptor is a command-line pipeline for turning a local audio inbox into timestamped transcripts. The source folder is named `aiSECRETary`; the package and installed commands use `transcriptor`.

Current scope:

- transcribe local audio files into Markdown and plain text
- optionally add experimental speaker diarization and saved speaker names
- local folders only
- no paid API required

## Stack

- Python 3.12+
- [`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) for local transcription
- optional [`pyannote.audio`](https://github.com/pyannote/pyannote-audio) for local speaker diarization

`faster-whisper` runs locally. `pyannote.audio` also performs inference locally, but its first setup downloads gated model files and requires a Hugging Face token. Model downloads are a setup requirement; audio and transcript inference remain local.

## Folder layout

```text
data/
├── inbox/
├── transcripts/
├── archive/
└── state/
    ├── processed_files.json
    ├── speaker_names.json
    └── recordings/
```

## Setup

Install the locked full environment with Python 3.12 or newer, then download the required local Whisper model:

```bash
uv sync --locked --extra diarization
.venv/bin/python scripts/download_models.py --whisper-model small
```

The model download is required first-run setup. Normal transcription is local after the model is cached. For optional speaker diarization, accept the model terms on Hugging Face and download its files with a token:

```bash
HUGGINGFACE_TOKEN="your-token" .venv/bin/python scripts/download_models.py --diarization
```

## Usage

1. Put audio files into `data/inbox/`
2. Run:

```bash
.venv/bin/python -m transcriptor.cli
```

3. Read the generated files in `data/transcripts/`

Supported audio extensions:

- `.aac`
- `.aiff`
- `.flac`
- `.m4a`
- `.mp3`
- `.mp4`
- `.mpeg`
- `.oga`
- `.ogg`
- `.wav`
- `.webm`

## Speaker diarization

Run diarization while transcribing:

```bash
HUGGINGFACE_TOKEN="your-token" .venv/bin/python -m transcriptor.cli --diarize
```

If you know the speaker count, pass it as a hint:

```bash
HUGGINGFACE_TOKEN="your-token" .venv/bin/python -m transcriptor.cli --diarize --num-speakers 2
```

What Phase 2 adds:

- transcript segments can be labeled as `Speaker 1`, `Speaker 2`, and so on
- structured transcript JSON is written into `data/state/recordings/`
- a local mapping file in `data/state/speaker_names.json` stores renamed speakers

List processed recordings that can be renamed:

```bash
.venv/bin/python -m transcriptor.speakers list
```

Show the speakers for one recording:

```bash
.venv/bin/python -m transcriptor.speakers show RECORDING_ID
```

Assign a human name to a speaker and rerender the transcript:

```bash
.venv/bin/python -m transcriptor.speakers set RECORDING_ID SPEAKER_00 Gaurav
```

Remove a stored speaker name:

```bash
.venv/bin/python -m transcriptor.speakers unset RECORDING_ID SPEAKER_00
```

Force a rerender of the transcript using current speaker mappings:

```bash
.venv/bin/python -m transcriptor.speakers rerender RECORDING_ID
```

## Common transcription options

Use a different model:

```bash
.venv/bin/python -m transcriptor.cli --model medium
```

Keep original files in the inbox:

```bash
.venv/bin/python -m transcriptor.cli --keep-audio
```

Write plain text instead of Markdown:

```bash
.venv/bin/python -m transcriptor.cli --output-format txt
```

See what would be processed without running transcription:

```bash
.venv/bin/python -m transcriptor.cli --dry-run
```

Reprocess everything even if it was already seen:

```bash
.venv/bin/python -m transcriptor.cli --force
```

## Output format

Markdown transcripts include:

- recording metadata
- model and language details
- a speaker summary section when diarization is enabled
- timestamped transcript segments
- a plain-text section at the bottom for easy copy/paste

Example transcript filename:

```text
meeting-note--1a2b3c4d.md
```

## Tests

Run the local automated test suite with:

```bash
python -m unittest discover -s tests -v
```

These tests cover:

- diarization-to-segment assignment
- transcript persistence and rerendering
- speaker-name mapping updates
- archive and manifest behavior

## Automation

The CLI is the product interface: it works interactively, from `launchd`, or from another local scheduler without a separate desktop app. To schedule it with Codex, adapt [the local automation prompt](docs/codex-automation-prompt.md) to the path of your checkout.

## Limitations and privacy

- Transcription and diarization quality depend on the selected models, recording quality, language, and available hardware.
- Model installation may require network access even though inference and transcript storage are local.
- Audio, transcripts, speaker mappings, and recording metadata may contain sensitive information. Keep `data/` out of a public repository.
- The inbox workflow processes local files; it is not a recording, meeting, or cloud-sync service.

See [release readiness](docs/RELEASE_READINESS.md) for verified scope and remaining publication decisions.

## License

Copyright 2026 Gaurav Dama. Licensed under the Apache License 2.0; see [LICENSE](LICENSE).
