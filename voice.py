"""voice.py - SmartShop Voice-to-Order Module.

Downloads Telegram voice / audio messages (.oga, .ogg, .mp3),
converts them to WAV format using ffmpeg/pydub, and transcribes them
to text using SpeechRecognition (Vietnamese & English).
"""

import io
import json
import os
import subprocess
import tempfile
import urllib.request

try:
    import speech_recognition as sr
except ImportError:
    sr = None


def download_telegram_audio(file_id: str) -> bytes | None:
    """Download audio file from Telegram Bot API using file_id."""
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
    if not bot_token:
        return None
    try:
        meta_url = f"https://api.telegram.org/bot{bot_token}/getFile?file_id={file_id}"
        meta = json.loads(urllib.request.urlopen(meta_url, timeout=10).read().decode("utf-8"))
        file_path = meta["result"]["file_path"]
        file_url = f"https://api.telegram.org/file/bot{bot_token}/{file_path}"
        return urllib.request.urlopen(file_url, timeout=30).read()
    except Exception as e:
        print(f"[VOICE] Error downloading audio: {e}")
        return None


def convert_audio_to_wav(audio_bytes: bytes, input_ext: str = "oga") -> str | None:
    """Convert audio bytes into a temporary 16kHz mono WAV file path."""
    temp_dir = tempfile.gettempdir()
    in_path = os.path.join(temp_dir, f"tg_voice_in_{os.getpid()}_{tempfile._get_candidate_names().__next__()}.{input_ext}")
    out_path = os.path.join(temp_dir, f"tg_voice_out_{os.getpid()}_{tempfile._get_candidate_names().__next__()}.wav")

    try:
        with open(in_path, "wb") as f:
            f.write(audio_bytes)

        # Use ffmpeg CLI to convert to 16kHz mono WAV
        cmd = [
            "ffmpeg", "-y",
            "-i", in_path,
            "-ar", "16000",
            "-ac", "1",
            out_path
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=15)
        if res.returncode == 0 and os.path.exists(out_path):
            return out_path
        else:
            print(f"[VOICE] ffmpeg conversion failed: {res.stderr.decode('utf-8', errors='replace')[:200]}")
    except Exception as ex:
        print(f"[VOICE] Audio conversion error: {ex}")
    finally:
        if os.path.exists(in_path):
            try:
                os.remove(in_path)
            except Exception:
                pass
    return None


def transcribe_audio(audio_bytes: bytes, input_ext: str = "oga") -> str:
    """
    Transcribe audio bytes to text.
    Primary language: Vietnamese (vi-VN), fallback to English (en-US).
    """
    if sr is None:
        return ""

    wav_path = convert_audio_to_wav(audio_bytes, input_ext)
    if not wav_path or not os.path.exists(wav_path):
        return ""

    recognizer = sr.Recognizer()
    try:
        with sr.AudioFile(wav_path) as source:
            audio_data = recognizer.record(source)

        # 1. Try Vietnamese
        try:
            text = recognizer.recognize_google(audio_data, language="vi-VN")
            if text and text.strip():
                print(f"[VOICE] Transcribed (vi-VN): {text}")
                return text.strip()
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"[VOICE] vi-VN recognition notice: {e}")

        # 2. Fallback to English
        try:
            text = recognizer.recognize_google(audio_data, language="en-US")
            if text and text.strip():
                print(f"[VOICE] Transcribed (en-US): {text}")
                return text.strip()
        except sr.UnknownValueError:
            pass
        except Exception as e:
            print(f"[VOICE] en-US recognition notice: {e}")

        return ""
    except Exception as e:
        print(f"[VOICE] Transcription general error: {e}")
        return ""
    finally:
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except Exception:
                pass
