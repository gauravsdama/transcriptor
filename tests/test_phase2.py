from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from transcriptor.pipeline import (
    DiarizationSegment,
    InboxTranscriptionPipeline,
    TranscriptDocument,
    TranscriptSegment,
    apply_diarization,
    load_recording_document,
    sha256_for_file,
)
from transcriptor.speakers import SpeakerNamingService


class FakeTranscriber:
    def transcribe(
        self,
        audio_path: Path,
        source_sha256: str,
        *,
        transcript_path: Path,
        output_format: str,
    ) -> TranscriptDocument:
        return TranscriptDocument(
            recording_id=source_sha256,
            source_name=audio_path.name,
            source_path=str(audio_path.resolve()),
            source_sha256=source_sha256,
            created_at="2026-05-19T00:00:00+00:00",
            language="en",
            language_probability=0.99,
            duration_seconds=8.0,
            model="fake-small",
            task="transcribe",
            transcript_path=str(transcript_path.resolve()),
            output_format=output_format,
            diarization_enabled=False,
            diarization_source=None,
            segment_count=2,
            segments=[
                TranscriptSegment(0.0, 4.0, "hello there"),
                TranscriptSegment(4.0, 8.0, "how are you"),
            ],
            diarization_segments=[],
        )


class FakeDiarizer:
    model_name = "fake-diarizer"

    def diarize(self, audio_path: Path) -> list[DiarizationSegment]:
        return [
            DiarizationSegment(0.0, 3.0, "SPEAKER_00"),
            DiarizationSegment(3.0, 8.0, "SPEAKER_01"),
        ]


class Phase2Tests(unittest.TestCase):
    def test_apply_diarization_assigns_best_overlap(self) -> None:
        transcript = TranscriptDocument(
            recording_id="abc123",
            source_name="memo.m4a",
            source_path="/tmp/memo.m4a",
            source_sha256="abc123",
            created_at="2026-05-19T00:00:00+00:00",
            language="en",
            language_probability=0.99,
            duration_seconds=8.0,
            model="fake",
            task="transcribe",
            transcript_path="/tmp/memo.md",
            output_format="md",
            diarization_enabled=False,
            diarization_source=None,
            segment_count=2,
            segments=[
                TranscriptSegment(0.0, 4.0, "hello there"),
                TranscriptSegment(4.0, 8.0, "how are you"),
            ],
            diarization_segments=[],
        )
        updated = apply_diarization(
            transcript,
            [
                DiarizationSegment(0.0, 3.0, "SPEAKER_00"),
                DiarizationSegment(3.0, 8.0, "SPEAKER_01"),
            ],
            diarization_source="fake",
        )
        self.assertEqual(updated.segments[0].speaker_id, "SPEAKER_00")
        self.assertEqual(updated.segments[1].speaker_id, "SPEAKER_01")
        self.assertTrue(updated.diarization_enabled)

    def test_pipeline_and_speaker_rerender_flow(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            inbox = root / "inbox"
            transcripts = root / "transcripts"
            archive = root / "archive"
            state_dir = root / "state"
            recordings_dir = state_dir / "recordings"
            state_file = state_dir / "processed_files.json"
            speaker_names_file = state_dir / "speaker_names.json"

            inbox.mkdir(parents=True)
            sample_audio = inbox / "meeting.m4a"
            sample_audio.write_bytes(b"fake-audio-bytes")
            expected_digest = sha256_for_file(sample_audio)

            pipeline = InboxTranscriptionPipeline(
                inbox_dir=inbox,
                transcripts_dir=transcripts,
                archive_dir=archive,
                state_file=state_file,
                recordings_dir=recordings_dir,
                speaker_names_file=speaker_names_file,
                model_name="small",
                language=None,
                task="transcribe",
                output_format="md",
                compute_type="int8",
                device="cpu",
                beam_size=5,
                force=False,
                archive_audio=True,
                dry_run=False,
                extensions={".m4a"},
                diarizer=FakeDiarizer(),
                transcriber=FakeTranscriber(),
            )

            result = pipeline.run()
            self.assertEqual(result, 0)

            manifest = json.loads(state_file.read_text(encoding="utf-8"))
            self.assertIn(expected_digest, manifest)
            self.assertEqual(manifest[expected_digest]["speaker_count"], 2)

            transcript_path = Path(manifest[expected_digest]["transcript_path"])
            self.assertTrue(transcript_path.exists())
            txt_path = Path(manifest[expected_digest]["transcript_text_path"])
            self.assertTrue(txt_path.exists())
            initial_text = transcript_path.read_text(encoding="utf-8")
            self.assertIn("Speaker 1: hello there", initial_text)
            self.assertIn("Speaker 2: how are you", initial_text)
            initial_txt = txt_path.read_text(encoding="utf-8")
            self.assertIn("Speaker 1: hello there", initial_txt)
            self.assertIn("Speaker 2: how are you", initial_txt)

            recording_doc = load_recording_document(
                Path(manifest[expected_digest]["recording_document_path"])
            )
            self.assertTrue(recording_doc.diarization_enabled)
            self.assertEqual(recording_doc.recording_id, expected_digest)

            archived_audio_path = Path(manifest[expected_digest]["archived_audio_path"])
            self.assertTrue(archived_audio_path.exists())
            self.assertFalse(sample_audio.exists())

            service = SpeakerNamingService(
                recordings_dir=recordings_dir,
                speaker_names_file=speaker_names_file,
            )
            service.set_speaker_name(expected_digest, "speaker_00", "Gaurav")
            service.set_speaker_name(expected_digest, "SPEAKER_01", "Alex")

            updated_text = transcript_path.read_text(encoding="utf-8")
            self.assertIn("Gaurav: hello there", updated_text)
            self.assertIn("Alex: how are you", updated_text)
            updated_txt = txt_path.read_text(encoding="utf-8")
            self.assertIn("Gaurav: hello there", updated_txt)
            self.assertIn("Alex: how are you", updated_txt)

            mapping = json.loads(speaker_names_file.read_text(encoding="utf-8"))
            self.assertEqual(mapping[expected_digest]["SPEAKER_00"], "Gaurav")
            self.assertEqual(mapping[expected_digest]["SPEAKER_01"], "Alex")

            details = service.show_recording(expected_digest)
            self.assertIn("Gaurav", details)
            self.assertIn("Alex", details)


if __name__ == "__main__":
    unittest.main()
