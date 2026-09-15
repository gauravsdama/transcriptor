# Transcriptor release readiness

Updated: 2026-09-15

## Product and audience

Transcriptor is a local CLI for people who want a repeatable audio-inbox workflow without sending recordings to a hosted transcription API. The employer-facing story is the pipeline itself: deterministic file discovery, local Whisper inference, optional diarization, durable manifests, speaker-name rerendering, and privacy-conscious local storage.

CLI-only is the release decision. Scheduling and batch processing are the primary workflows; a native UI would add installation and privacy surface without making either workflow clearer.

## Provenance and ownership

- Canonical source inspected: `/Users/gauravsdama/git/aiSECRETary`.
- The owner confirmed that Transcriptor is original first-party work on 2026-09-15. The directory is now an independent Git repository connected to `https://github.com/gauravsdama/transcriptor`.
- Runtime libraries are installed dependencies, not vendored source. `faster-whisper` is required and `pyannote.audio` is optional.
- The owner selected Apache License 2.0. `LICENSE` and the README copyright notice record that decision.
- `pyannote.audio` 4.0.7 is MIT-licensed, with an Apache-2.0 component notice included upstream. The lockfile no longer selects 4.0.4, which upstream reports as affected by unsafe remote configuration instantiation.

## Privacy and release controls

- `data/` and `tmp/` are ignored in full because they contain audio, transcripts, absolute source paths, speaker mappings, and hashes.
- The current local `data/` folder contains real recordings and transcripts. They were not modified or inspected for editorial content and must not be added to source control or a release archive.
- Tokens may be supplied through `HUGGINGFACE_TOKEN` or `HF_TOKEN`; documentation prefers the environment so secrets do not enter shell history.
- The package has no network service or inbound port. The required `small` Whisper model is downloaded during first-run setup with `scripts/download_models.py`; cached inference is local.

## Verification evidence

Verified on macOS arm64 with Python 3.12.14:

```text
.venv/bin/python -m unittest discover -s tests -v
2 tests passed

.venv/bin/python -m pip check
No broken requirements found.

uv lock
Lockfile generated from pyproject.toml.

uv build
Source distribution and wheel built successfully.

uv venv --python 3.12 /tmp/transcriptor-wheel-check.../venv
uv pip install --no-deps dist/transcriptor-0.1.0-py3-none-any.whl
transcriptor-inbox --help && transcriptor-speakers --help
clean wheel entry-point check passed

UV_PROJECT_ENVIRONMENT=/tmp/transcriptor-validation... uv sync --locked --extra diarization --python 3.12
98 packages installed in a clean environment; dependency compatibility check passed

.venv/bin/python scripts/download_models.py --whisper-model small
required Whisper model downloaded and loaded successfully

private representative recording validation
1289.75 seconds; 246 transcript segments; English detected; no transcript text retained in the repository

dependency reports
97-component CycloneDX SBOM; 97 license records; 0 unresolved license identifiers after installed license-text review
```

The generated reports are `docs/dependencies/sbom.cdx.json` and `docs/dependencies/licenses.json`.

## Status

**Ready for source publication with diarization still experimental.** Git provenance, Apache-2.0 licensing, full locked installation, Whisper model setup, real-recording transcription, SBOM, and dependency license reporting are in place. One validation remains blocked by owner credentials: accept the `pyannote/speaker-diarization-community-1` terms, provide `HUGGINGFACE_TOKEN`, and rerun a representative two-speaker recording with `--diarize --num-speakers 2`. Until then, keep diarization labeled experimental.
