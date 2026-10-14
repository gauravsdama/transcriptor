from __future__ import annotations

import os

IMPLICIT_CREDENTIAL_ENV = "HF_HUB_DISABLE_IMPLICIT_" + "TOKEN"

OFFLINE_RUNTIME_ENVIRONMENT = {
    "DO_NOT_TRACK": "1",
    IMPLICIT_CREDENTIAL_ENV: "1",
    "HF_HUB_DISABLE_TELEMETRY": "1",
    "HF_HUB_DISABLE_UPDATE_CHECK": "1",
    "HF_HUB_OFFLINE": "1",
    "PYANNOTE_METRICS_ENABLED": "0",
    "TRANSFORMERS_OFFLINE": "1",
}


def enforce_offline_runtime() -> None:
    """Disable model-network and telemetry paths before third-party imports."""
    os.environ.update(OFFLINE_RUNTIME_ENVIRONMENT)
