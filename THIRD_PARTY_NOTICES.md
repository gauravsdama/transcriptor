# Third-party notices

Transcriptor installs third-party libraries from the versions resolved in `uv.lock`; it does not vendor their source in the wheel.

| Direct dependency | Role | License evidence |
|---|---|---|
| faster-whisper 1.2.1 | Required local transcription runtime | MIT in installed package metadata |
| pyannote.audio 4.0.7 | Optional speaker diarization runtime | MIT for the package; its installed notices also include Apache-2.0 material derived from WeSpeaker |
| keyring 25.7.0 | Optional setup credential storage | MIT in installed package metadata |

The selected pyannote release was raised above 4.0.4 because the upstream project reports unsafe remote configuration instantiation in versions through 4.0.4. The official `pyannote.audio` repository and installed root license identify the package as MIT; its distribution also carries an Apache-2.0 notice for incorporated WeSpeaker material. The optional Community-1 model is not distributed with Transcriptor; its pinned Hugging Face revision is downloaded only after the user accepts the model repository's separate CC-BY-4.0 conditions.

Transitive packages and detected licenses are recorded in `docs/dependencies/licenses.json`, and the CycloneDX inventory is `docs/dependencies/sbom.cdx.json`. Those generated reports complement rather than replace upstream license texts.
