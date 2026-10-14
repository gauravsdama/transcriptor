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

`faster-whisper` and `pyannote.audio` inference run locally. Their first setup downloads model files; the gated pyannote model requires a Hugging Face token for that download only. Runtime model loading is forced offline, and pyannote telemetry is disabled. Audio and transcripts are never uploaded by Transcriptor.

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

Install the locked environment with Python 3.12 or newer, then run the model setup:

```bash
uv sync --locked --extra diarization --extra setup
.venv/bin/python -m transcriptor.model_setup
```

The default Whisper model is about 464 MiB. The setup command reports the cache location and verifies token-free, cached-only loading before it finishes. Normal transcription is local after that.

Optional speaker diarization uses a pinned revision of [`pyannote/speaker-diarization-community-1`](https://huggingface.co/pyannote/speaker-diarization-community-1), whose files are about 32 MiB and carry a CC BY 4.0 license. Its access form asks you to share contact information with pyannote and agree that pyannote may occasionally email model or service news. Review those conditions yourself, grant access, create a read token, then run:

```bash
.venv/bin/python -m transcriptor.model_setup --diarization
```

The guided flow hides token input, verifies access without printing the token, and can store it in the operating system credential store for setup retries. Transcription and diarization never read the stored token. Remove it at any time with:

```bash
.venv/bin/python -m transcriptor.model_setup --remove-token
```

Model caches normally live at `~/.cache/huggingface`; `HF_HOME` or `XDG_CACHE_HOME` can relocate them. The complete Python environment is substantially larger than the model files, so keep at least 3 GiB free during installation.

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
.venv/bin/python -m transcriptor.cli --diarize
```

If you know the speaker count, pass it as a hint:

```bash
.venv/bin/python -m transcriptor.cli --diarize --num-speakers 2
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
- Model installation requires network access. Runtime inference forces Hugging Face and Transformers offline modes, disables implicit token use, and loads cached files only.
- Hugging Face and pyannote usage telemetry are disabled before their runtime libraries are imported.
- Audio, transcripts, speaker mappings, and recording metadata may contain sensitive information. Keep `data/` out of a public repository.
- The inbox workflow processes local files; it is not a recording, meeting, or cloud-sync service.

See [release readiness](docs/RELEASE_READINESS.md) for verified scope and remaining publication decisions.

## License

Copyright 2026 Gaurav Dama. Licensed under the Apache License 2.0; see [LICENSE](LICENSE).
