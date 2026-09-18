"""tests/test_voice.py - Unit test for voice module."""

import unittest
import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import voice

class TestVoiceModule(unittest.TestCase):
    def test_transcribe_empty_bytes(self):
        result = voice.transcribe_audio(b"")
        self.assertEqual(result, "")

    def test_convert_invalid_bytes(self):
        wav_path = voice.convert_audio_to_wav(b"not_an_audio_stream", "oga")
        self.assertIsNone(wav_path)

    def test_download_no_token(self):
        # Save old token
        old_token = os.environ.get("TELEGRAM_BOT_TOKEN")
        try:
            os.environ["TELEGRAM_BOT_TOKEN"] = ""
            res = voice.download_telegram_audio("fake_file_id")
            self.assertIsNone(res)
        finally:
            if old_token:
                os.environ["TELEGRAM_BOT_TOKEN"] = old_token

if __name__ == "__main__":
    unittest.main()
