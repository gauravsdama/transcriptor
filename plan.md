# Transcriptor Plan

## Goal

Build a personal, local-first transcription app that runs on your computer for free after setup.

Core requirements:

- input is a voice memo or other audio recording
- output is a transcript file written into a local folder
- the workflow should be automatable with Codex
- Stage 1 should avoid paid APIs and external hosted AI services
- Phase 2 should add multi-speaker separation and speaker naming

Non-goals for now:

- multi-user accounts
- cloud sync
- live transcription
- polished GUI before the local workflow is reliable

## Product shape

The project is a local pipeline, not a hosted SaaS app.

High-level flow:

1. Put audio files into a local inbox folder.
2. Run the transcription pipeline manually or through Codex automation.
3. Generate transcript documents into an output folder.
4. Archive processed audio and track what has already been handled.
5. In Phase 2, attach speaker labels like `Speaker 1` and `Speaker 2`.
6. Let the user rename those labels after transcription.

## Constraints

- personal use only
- runs on one machine
- free to run locally after dependencies and model downloads
- must produce local docs/text files
- should tolerate reruns without duplicating work

## Chosen approach

### Why not use Codex as the transcription engine

Codex is useful for orchestration, scheduling, and file handling, but it should not be the speech-to-text engine.

Reasons:

- speech-to-text is better handled by a dedicated local model runner
- local ASR tools are cheaper and more reliable for repeated use
- automation becomes simpler if Codex only runs a deterministic CLI command

### Local transcription engine

Stage 1 uses `faster-whisper`.

Reasons:

- free to run locally
- good accuracy for an offline workflow
- simple Python integration
- flexible model sizes for speed vs quality tradeoffs

Default assumptions:

- device: `cpu`
- compute type: `int8`
- model: `small`

These defaults favor reliability on a local machine over maximum speed.

## Current implementation

### What exists now

The current repository includes:

- a Python package for the transcription pipeline
- a transcription CLI entrypoint
- a speaker naming CLI entrypoint
- default data folders
- transcript output in Markdown or plain text
- a processed-file manifest to avoid duplicate work
- structured recording JSON for rerendering transcripts
- a local speaker-name registry
- a Codex automation prompt for scheduled runs later

Key files:

- [pyproject.toml](/Users/gauravsdama/git/aiSECRETary/pyproject.toml)
- [transcriptor/cli.py](/Users/gauravsdama/git/aiSECRETary/transcriptor/cli.py)
- [transcriptor/pipeline.py](/Users/gauravsdama/git/aiSECRETary/transcriptor/pipeline.py)
- [transcriptor/speakers.py](/Users/gauravsdama/git/aiSECRETary/transcriptor/speakers.py)
- [README.md](/Users/gauravsdama/git/aiSECRETary/README.md)
- [docs/codex-automation-prompt.md](/Users/gauravsdama/git/aiSECRETary/docs/codex-automation-prompt.md)

### Folder layout

```text
aiSECRETary/
├── data/
│   ├── inbox/
│   ├── transcripts/
│   ├── archive/
│   └── state/
│       ├── recordings/
│       └── speaker_names.json
├── docs/
├── transcriptor/
├── README.md
├── plan.md
└── pyproject.toml
```

### Stage 1 workflow

1. User drops supported audio files into `data/inbox/`.
2. CLI scans the folder for supported extensions.
3. Each file is hashed with SHA-256.
4. If the hash already exists in the manifest, the file is skipped unless `--force` is used.
5. If new, the file is transcribed locally with `faster-whisper`.
6. A transcript file is written to `data/transcripts/`.
7. The source audio is moved to `data/archive/` unless `--keep-audio` is set.
8. The manifest is updated in `data/state/processed_files.json`.

### Phase 2 workflow

1. Run the transcription pipeline with `--diarize`.
2. `faster-whisper` produces timestamped transcript segments.
3. `pyannote.audio` produces speaker diarization segments.
4. The pipeline assigns the best-overlap speaker label to each transcript segment.
5. Structured transcript JSON is stored under `data/state/recordings/`.
6. Markdown or text output is written with generic speaker labels.
7. The speaker naming CLI updates `data/state/speaker_names.json`.
8. The transcript is rerendered using the assigned human names.

### Transcript output format

Current outputs support:

- Markdown: metadata, timestamped segments, plain-text section
- Plain text: minimal timestamped transcript

Example transcript filename:

```text
voice-memo--1a2b3c4d.md
```

Why include the hash suffix:

- avoids collisions between recordings with the same filename
- keeps transcript identity stable
- makes it easier to trace a transcript back to the original audio file

### Supported input formats

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

### Stage 1 CLI surface

Important options already implemented:

- `--model`
- `--language`
- `--task`
- `--output-format`
- `--compute-type`
- `--device`
- `--beam-size`
- `--force`
- `--keep-audio`
- `--dry-run`

### Phase 2 CLI surface

Transcription flags:

- `--diarize`
- `--diarization-model`
- `--hf-token`
- `--num-speakers`
- `--min-speakers`
- `--max-speakers`
- `--recordings-dir`
- `--speaker-names-file`

Speaker naming commands:

- `transcriptor.speakers list`
- `transcriptor.speakers show RECORDING_ID`
- `transcriptor.speakers set RECORDING_ID SPEAKER_ID NAME`
- `transcriptor.speakers unset RECORDING_ID SPEAKER_ID`
- `transcriptor.speakers rerender RECORDING_ID`

### Stage 1 success criteria

Stage 1 is considered complete when:

- audio files can be dropped into the inbox and processed locally
- transcripts are produced consistently as files
- reruns do not duplicate prior work
- the system can be triggered by a single command
- no paid API is required

## Setup and run model

### Local setup

Typical setup:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e .
```

Typical run:

```bash
.venv/bin/python -m transcriptor.cli
```

### Operational assumptions

- first dependency install requires internet
- first model download requires internet
- after setup, transcription runs locally on the machine

## Codex automation plan

Codex should act as a scheduler and reporter, not as the speech model.

### Automation role

Codex automation should:

1. enter the repo working directory
2. run the local CLI
3. summarize which files were processed
4. report failures clearly

### Automation prompt

The initial prompt is already stored in:

- [docs/codex-automation-prompt.md](/Users/gauravsdama/git/aiSECRETary/docs/codex-automation-prompt.md)

### When to automate

Recommended options:

- hourly if you drop files in throughout the day
- daily if this is more like a batch workflow
- manual runs while the pipeline is still being tuned

### Automation risks

- missing dependencies in the virtual environment
- model download not completed yet
- malformed state file
- unsupported audio files dropped into the inbox

## Phase 2: Speaker separation and naming

### Objective

Extend the pipeline so multi-person recordings are transcribed with generic speaker labels first, then renamed by the user.

Target output shape:

```text
[00:00:02 - 00:00:08] Speaker 1: ...
[00:00:09 - 00:00:14] Speaker 2: ...
```

Then later:

```text
[00:00:02 - 00:00:08] Gaurav: ...
[00:00:09 - 00:00:14] Alex: ...
```

### Phase 2 implementation status

Phase 2 is now implemented in the repo as:

1. `faster-whisper` for transcript segments
2. optional `pyannote.audio` diarization
3. overlap-based assignment of speakers onto transcript segments
4. speaker-tagged transcript rendering
5. a local speaker-name mapping file
6. a rerender flow so names can be applied after transcription

### Current Phase 2 tooling

Implemented stack:

- `faster-whisper` for transcript segments
- `pyannote.audio` for diarization

This keeps the system local, but setup is heavier than Stage 1 because diarization dependencies and model access are more involved.

### Expected Phase 2 data additions

New local artifacts now include:

- `data/state/speaker_names.json`
- `data/state/recordings/<recording-id>.json`

Possible speaker mapping shape:

```json
{
  "recording-abc123": {
    "SPEAKER_00": "Gaurav",
    "SPEAKER_01": "Alex"
  }
}
```

### Phase 2 transcript format

Markdown output now includes:

- speaker labels per segment
- a speaker summary section
- recording ID metadata for use with the naming CLI

Example:

```text
## Speakers

- Speaker 1: Gaurav
- Speaker 2: Unknown
```

### Phase 2 user interaction

The implemented UX level is a local rename helper CLI.

- diarization outputs generic labels
- the speaker naming CLI lists or shows discovered speaker IDs
- the user assigns names with a command
- the transcript is rerendered automatically

This is a good midpoint between manual JSON editing and building a full UI.

### Phase 2 technical risks

- overlapping speech reduces quality
- diarization models are more complex to install
- short speaker turns are harder to label well
- label consistency across separate recordings is non-trivial
- local CPU-only diarization may be slow on long recordings

### Phase 2 success criteria

Phase 2 is successful when:

- the pipeline identifies at least two speakers in a multi-person memo
- output segments include stable speaker IDs
- the user can rename those IDs locally
- rerunning the rename step updates final transcript labels cleanly

## Future phases beyond Phase 2

Possible later improvements:

- searchable transcript index
- transcript export formats like `.docx`
- transcript post-processing and summarization
- per-folder automation rules
- automatic language-specific model selection
- basic local review UI

These are deliberately out of scope until Stage 1 and Phase 2 are stable.

## Milestone plan

### Milestone 1: local transcription foundation

Status: complete

- create CLI package
- implement inbox scan
- implement transcript writing
- implement archive flow
- implement processed manifest
- document setup and usage

### Milestone 2: operational hardening

Status: next practical polish pass

- verify transcription end-to-end with real audio
- tune default model choice for your machine
- improve error messages for unsupported or broken files
- optionally add structured logs

### Milestone 3: Codex automation

Status: ready when desired

- create recurring Codex job
- run the CLI on a schedule
- summarize outcomes in the automation result

### Milestone 4: speaker diarization

Status: implemented in code, still needs live-model validation on your machine

- add speaker-labeled segments
- store speaker mappings
- render renamed labels into transcripts
- validate the real pyannote model setup locally

### Milestone 5: usability layer

Status: optional

- add rename helper CLI or small UI
- add transcript browsing and filtering
- add improved export workflows

## Recommended next steps

1. Install dependencies in `.venv`.
2. If you want diarization, install the optional diarization dependencies.
3. Run the pipeline on one real voice memo.
4. Validate transcript quality, speed, and diarization quality on your machine.
5. Decide whether the default model should stay `small` or move to `medium`.
6. Add Codex automation after one successful manual run.
