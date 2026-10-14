from __future__ import annotations

import argparse
import getpass
import os

# A child Python process proves cache loading under a token-free offline environment.
import subprocess  # nosec B404
import sys
from pathlib import Path
from typing import Protocol

from transcriptor.model_config import (
    ACCESS_CREDENTIAL_PAGE_URL,
    DIARIZATION_MODEL,
    DIARIZATION_REVISION,
    MODEL_TERMS_URL,
)
from transcriptor.runtime_policy import IMPLICIT_CREDENTIAL_ENV

KEYRING_SERVICE = "Transcriptor Hugging Face setup"
KEYRING_ACCOUNT = "huggingface-token"


class CredentialStore(Protocol):
    def get_password(self, service: str, account: str) -> str | None: ...

    def set_password(self, service: str, account: str, password: str) -> None: ...

    def delete_password(self, service: str, account: str) -> None: ...


def _credential_store() -> CredentialStore:
    try:
        import keyring
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Secure token storage is unavailable. Install the setup dependencies with "
            "`uv sync --locked --extra diarization --extra setup`."
        ) from exc
    return keyring


def cache_root() -> Path:
    hf_home = os.environ.get("HF_HOME")
    if hf_home:
        return Path(hf_home).expanduser()
    xdg_cache = os.environ.get("XDG_CACHE_HOME")
    if xdg_cache:
        return Path(xdg_cache).expanduser() / "huggingface"
    return Path.home() / ".cache" / "huggingface"


def directory_size(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def format_bytes(size: int) -> str:
    value = float(size)
    for unit in ("B", "KiB", "MiB", "GiB", "TiB"):
        if value < 1024 or unit == "TiB":
            return f"{value:.1f} {unit}"
        value /= 1024
    raise AssertionError("unreachable")


def _yes_no(prompt: str, *, default: bool = False) -> bool:
    suffix = " [Y/n] " if default else " [y/N] "
    reply = input(prompt + suffix).strip().lower()
    if not reply:
        return default
    return reply in {"y", "yes"}


def _stored_token(store: CredentialStore) -> str | None:
    try:
        return store.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
    except Exception as exc:
        raise RuntimeError(
            f"Could not read the system credential store: {exc}"
        ) from exc


def _remove_token(store: CredentialStore) -> bool:
    try:
        if store.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT) is None:
            return False
        store.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        return True
    except Exception as exc:
        raise RuntimeError(
            f"Could not update the system credential store: {exc}"
        ) from exc


def _save_token(store: CredentialStore, token: str) -> None:
    try:
        store.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, token)
    except Exception as exc:
        raise RuntimeError(
            f"Could not update the system credential store: {exc}"
        ) from exc


def _get_setup_token(store: CredentialStore, *, allow_prompt: bool) -> tuple[str, str]:
    environment_token = os.environ.get("HUGGINGFACE_TOKEN") or os.environ.get(
        "HF_TOKEN"
    )
    if environment_token:
        return environment_token, "environment"
    stored = _stored_token(store)
    if stored:
        return stored, "system credential store"
    if not allow_prompt:
        raise RuntimeError(
            "No Hugging Face token is available. Run the guided setup in an interactive terminal."
        )
    token = getpass.getpass(
        "Paste a Hugging Face read token (input is hidden): "
    ).strip()
    if not token:
        raise RuntimeError("Setup cancelled: no token was entered.")
    return token, "prompt"


def _verify_access(token: str, model_name: str, revision: str) -> None:
    from huggingface_hub import HfApi, hf_hub_download

    try:
        HfApi().whoami(token=token)
        hf_hub_download(
            repo_id=model_name,
            filename="config.yaml",
            revision=revision,
            token=token,
        )
    except Exception as exc:
        raise RuntimeError(
            "Hugging Face access could not be verified. Check the token and confirm that "
            f"you accepted the conditions at {MODEL_TERMS_URL}, then retry."
        ) from exc


def _download_whisper(model_name: str) -> None:
    from faster_whisper import WhisperModel

    print(f"Downloading or verifying Whisper model: {model_name}")
    WhisperModel(model_name, device="cpu", compute_type="int8")


def _download_diarization(model_name: str, revision: str, token: str) -> None:
    os.environ["PYANNOTE_METRICS_ENABLED"] = "0"
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["DO_NOT_TRACK"] = "1"
    from pyannote.audio import Pipeline

    try:
        pipeline = Pipeline.from_pretrained(
            model_name, revision=revision, token=token
        )
        if pipeline is None:
            raise RuntimeError("Model loader returned no pipeline.")
    except Exception as exc:
        raise RuntimeError(
            "The diarization model download failed. Check network access and available disk "
            "space, then retry the same setup command."
        ) from exc


def _verify_cached_only(
    whisper_model: str,
    diarization_model: str | None,
    diarization_revision: str | None,
) -> None:
    script = [
        "from faster_whisper import WhisperModel",
        f"WhisperModel({whisper_model!r}, device='cpu', compute_type='int8', local_files_only=True)",
    ]
    if diarization_model:
        script.extend(
            [
                "from pyannote.audio import Pipeline",
                (
                    "assert Pipeline.from_pretrained("
                    f"{diarization_model!r}, revision={diarization_revision!r}) is not None"
                ),
            ]
        )
    environment = os.environ.copy()
    environment.update(
        {
            "DO_NOT_TRACK": "1",
            IMPLICIT_CREDENTIAL_ENV: "1",
            "HF_HUB_DISABLE_TELEMETRY": "1",
            "HF_HUB_DISABLE_UPDATE_CHECK": "1",
            "HF_HUB_OFFLINE": "1",
            "PYANNOTE_METRICS_ENABLED": "0",
            "TRANSFORMERS_OFFLINE": "1",
        }
    )
    environment.pop("HF_TOKEN", None)
    environment.pop("HUGGINGFACE_TOKEN", None)
    # sys.executable and -c are fixed; user values are repr-escaped and no shell is used.
    result = subprocess.run(  # nosec B603
        [sys.executable, "-c", ";".join(script)],
        env=environment,
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = (
            result.stderr.strip().splitlines()[-1]
            if result.stderr.strip()
            else "unknown error"
        )
        raise RuntimeError(f"Cached-only verification failed: {detail}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transcriptor-setup",
        description="Download Transcriptor models, then verify token-free offline loading.",
    )
    parser.add_argument("--whisper-model", default="small")
    parser.add_argument("--diarization", action="store_true")
    parser.add_argument("--diarization-model", default=DIARIZATION_MODEL)
    parser.add_argument("--diarization-revision", default=DIARIZATION_REVISION)
    parser.add_argument(
        "--accepted-model-terms",
        action="store_true",
        help="Confirm that you personally reviewed and accepted the model conditions.",
    )
    parser.add_argument(
        "--no-store-token",
        action="store_true",
        help="Use the token for this setup run without saving it to the system credential store.",
    )
    parser.add_argument("--remove-token", action="store_true")
    parser.add_argument("--status", action="store_true")
    return parser


def run(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = _credential_store()
    if args.remove_token:
        removed = _remove_token(store)
        print(
            "Stored setup token removed."
            if removed
            else "No stored setup token was found."
        )
        return 0
    if args.status:
        present = _stored_token(store) is not None
        print(
            f"Model cache: {cache_root()} ({format_bytes(directory_size(cache_root()))})"
        )
        print(f"Setup token in system credential store: {'yes' if present else 'no'}")
        return 0

    print(
        "Transcriptor downloads models once, then transcription runs from the local cache."
    )
    print(f"Model cache: {cache_root()}")
    print("Whisper small is about 464 MiB. Community-1 model files are about 32 MiB.")
    print(
        "The Python environment and model caches need additional working space; keep 3 GiB free."
    )
    before = directory_size(cache_root())
    _download_whisper(args.whisper_model)

    downloaded_diarization: str | None = None
    if args.diarization:
        print(
            "\nSpeaker diarization uses a gated model. A Hugging Face account is required once."
        )
        print(f"Review and accept the model conditions yourself: {MODEL_TERMS_URL}")
        print(f"Create a read token after accepting them: {ACCESS_CREDENTIAL_PAGE_URL}")
        accepted = args.accepted_model_terms
        if not accepted and sys.stdin.isatty():
            accepted = _yes_no(
                "Have you reviewed and accepted those conditions on Hugging Face?"
            )
        if not accepted:
            raise RuntimeError(
                "Diarization setup stopped. Transcriptor cannot accept third-party conditions for you."
            )
        token, credential_source = _get_setup_token(
            store, allow_prompt=sys.stdin.isatty()
        )
        print(
            "Verifying model access with token from "
            f"{credential_source}; the token will not be printed."
        )
        _verify_access(token, args.diarization_model, args.diarization_revision)
        _download_diarization(args.diarization_model, args.diarization_revision, token)
        downloaded_diarization = args.diarization_model
        if (
            credential_source == "prompt"
            and not args.no_store_token
            and _yes_no(
                "Save the token in the system credential store for setup retries?"
            )
        ):
            _save_token(store, token)
            print(
                "Token saved in the system credential store. Remove it with --remove-token."
            )

    _verify_cached_only(
        args.whisper_model,
        downloaded_diarization,
        args.diarization_revision if downloaded_diarization else None,
    )
    after = directory_size(cache_root())
    print(
        f"Models are ready. Cache size: {format_bytes(after)} (+{format_bytes(max(0, after - before))})."
    )
    print(
        "Cached-only loading passed with tokens removed from the verification environment."
    )
    return 0


def main(argv: list[str] | None = None) -> int:
    try:
        return run(argv)
    except (EOFError, KeyboardInterrupt):
        print(
            "Setup cancelled. No model terms were accepted on your behalf.",
            file=sys.stderr,
        )
        return 130
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
