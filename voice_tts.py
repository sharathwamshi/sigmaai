"""
voice_tts.py — Text-to-Speech for Sigma Voice Bot
===================================================
PRIMARY: Twilio's built-in <Say voice="Polly.Joanna"> — zero setup,
         professional quality, included in call cost.

This module is used ONLY if you want to pre-generate MP3 files
and serve them via <Play> instead of <Say>.  For most deployments
you can ignore this file entirely — the bot uses <Say> throughout.

Free TTS cascade (if needed):
  1. Google Cloud TTS WaveNet  — 1M chars/month free
  2. gTTS (googletrans)        — unlimited, needs internet
  3. pyttsx3                   — fully offline
"""

import os
import logging
from pathlib import Path
from twilio.twiml.voice_response import VoiceResponse, Say

log = logging.getLogger("SigmaVoice.TTS")

VOICE = "Polly.Joanna"
LANG  = "en-US"


def speak_or_say(response: VoiceResponse, text: str,
                 audio_dir: Path = None, base_url: str = None) -> None:
    """
    Add speech to a TwiML response.
    If audio_dir + base_url are provided, tries to generate an MP3
    and use <Play>. Otherwise falls back to <Say> (recommended).
    """
    if audio_dir and base_url:
        try:
            mp3_url = _generate_mp3(text, audio_dir, base_url)
            response.play(mp3_url)
            return
        except Exception as exc:
            log.warning("MP3 generation failed, using <Say>: %s", exc)

    response.say(text, voice=VOICE, language=LANG)


def _generate_mp3(text: str, audio_dir: Path, base_url: str) -> str:
    """Generate an MP3 and return its public URL."""
    import uuid
    filename = f"{uuid.uuid4().hex}.mp3"
    filepath = audio_dir / filename

    # Try Google Cloud TTS
    if os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"):
        try:
            _google_tts(text, str(filepath))
            return f"{base_url}/static/audio/{filename}"
        except Exception as e:
            log.warning("Google TTS failed: %s", e)

    # Try gTTS
    try:
        _gtts(text, str(filepath))
        return f"{base_url}/static/audio/{filename}"
    except Exception as e:
        log.warning("gTTS failed: %s", e)

    raise RuntimeError("All TTS engines failed")


def _google_tts(text: str, path: str) -> None:
    from google.cloud import texttospeech
    client = texttospeech.TextToSpeechClient()
    inp    = texttospeech.SynthesisInput(text=text)
    voice  = texttospeech.VoiceSelectionParams(
        language_code="en-US", name="en-US-Wavenet-F",
        ssml_gender=texttospeech.SsmlVoiceGender.FEMALE,
    )
    cfg = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3,
        speaking_rate=0.95,
        effects_profile_id=["telephony-class-application"],
    )
    resp = client.synthesize_speech(input=inp, voice=voice, audio_config=cfg)
    Path(path).write_bytes(resp.audio_content)


def _gtts(text: str, path: str) -> None:
    from gtts import gTTS
    gTTS(text=text, lang="en", slow=False).save(path)
