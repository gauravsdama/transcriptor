# Transcriptor release readiness

Updated: 2026-10-14

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
- `transcriptor.model_setup` uses a Hugging Face token only to verify access and download the gated diarization model. Interactive token input is hidden. Optional persistence uses the operating system credential store; `--remove-token` deletes it. Runtime commands do not accept or read the token.
- The package has no network service or inbound port. Runtime loading uses cached files only, disables implicit Hugging Face credentials, sets Hugging Face and Transformers offline modes, and disables Hugging Face and pyannote telemetry before import.

## Model access and storage

- The Community-1 model is licensed CC BY 4.0. Access requires the user to review its conditions at <https://huggingface.co/pyannote/speaker-diarization-community-1>, share contact information with pyannote, and agree that pyannote may occasionally send model or service news. Transcriptor does not accept those conditions for the user.
- A read token can be created at <https://huggingface.co/settings/tokens> after access is granted. The token is needed for initial diarization-model download and setup retries, not inference.
- Setup and runtime pin Community-1 revision `3533c8cf8e369892e6b79ff1bf80f7b0286a54ee`; updates require an explicit code and lockfile review.
- Upstream repository metadata reports approximately 464 MiB for `Systran/faster-whisper-small` and 32 MiB for `pyannote/speaker-diarization-community-1`. The Python environment and temporary download space are additional; the macOS setup check requires 3 GiB free.
- Hugging Face caches models under `~/.cache/huggingface` by default. `HF_HOME` or `XDG_CACHE_HOME` can select another location.

## Verification evidence

Verified on macOS arm64. Packaging uses Python 3.12; the current dependency and runtime pass also ran under Python 3.14.4.

```text
.venv/bin/python -m unittest discover -s tests -v
6 tests passed

uvx ruff check transcriptor scripts tests
All checks passed

uvx bandit -q -r transcriptor scripts
No findings

uvx pip-audit --path <active-site-packages>
No known vulnerabilities

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

UV_PROJECT_ENVIRONMENT=/tmp/transcriptor-validation... uv sync --locked --extra diarization --extra setup --python 3.12
locked dependency installation and compatibility check passed

.venv/bin/python -m transcriptor.model_setup --whisper-model small
required Whisper model loaded from cache; token-free cached-only verification passed

network-denied 60-second private recording sample
7.21 seconds elapsed; 887 MB maximum resident set; 0 socket messages sent or received

network-denied empty-cache check
failed with the documented local-cache setup instruction and no network fallback

private representative recording validation
1289.75 seconds; 246 transcript segments; English detected; no transcript text retained in the repository

dependency reports
103-component CycloneDX SBOM; 102 installed dependency license records
```

The generated reports are `docs/dependencies/sbom.cdx.json` and `docs/dependencies/licenses.json`.

## Status

**Ready for source publication with diarization still experimental.** Git provenance, Apache-2.0 licensing, locked installation, Whisper setup, real-recording transcription, offline enforcement, secure token setup, SBOM, and dependency license reporting are in place. The remaining validation requires owner action: accept the `pyannote/speaker-diarization-community-1` conditions, run `.venv/bin/python -m transcriptor.model_setup --diarization`, and make a representative two-speaker recording available outside the macOS-protected Voice Memos container. The validation run itself will be offline. Until it passes, keep diarization labeled experimental.
