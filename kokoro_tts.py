"""
Kokoro TTS service for Pipecat (in-process, no server).
Uses the kokoro package: pip install kokoro soundfile
Voice names: e.g. af_heart, af_bella, am_adam; see Kokoro VOICES.md.
Voice emotes: (excited), (calm), (whisper), (sad), (serious), (warm) at phrase start
affect speech speed only; they are stripped before synthesis.
"""
import asyncio
import re
from typing import AsyncGenerator, Optional, Tuple

from loguru import logger

from pipecat.frames.frames import ErrorFrame, Frame, TTSAudioRawFrame, TTSStartedFrame, TTSStoppedFrame
from pipecat.services.tts_service import TTSService

KOKORO_SAMPLE_RATE = 24000

# Voice-only emotes: (tag) at start of text -> speed multiplier. Stripped before TTS.
VOICE_EMOTE_SPEED: dict[str, float] = {
    "excited": 1.08,
    "calm": 0.92,
    "whisper": 0.95,
    "sad": 0.90,
    "serious": 0.95,
    "warm": 0.98,
    "quick": 1.06,
    "slow": 0.92,
}
VOICE_EMOTE_PATTERN = re.compile(
    r"^\s*\(\s*(" + "|".join(re.escape(k) for k in VOICE_EMOTE_SPEED) + r")\s*\)\s*",
    re.IGNORECASE,
)


def _strip_voice_emote(text: str) -> Tuple[str, float]:
    """Strip optional (emote) at start of text; return (cleaned_text, speed_multiplier)."""
    text = text.strip()
    speed = 1.0
    m = VOICE_EMOTE_PATTERN.match(text)
    if m:
        key = m.group(1).lower()
        speed = VOICE_EMOTE_SPEED.get(key, 1.0)
        text = text[m.end() :].strip()
    return text, speed


class KokoroTTSService(TTSService):
    """In-process TTS using Kokoro (no HTTP server). Supports voice emotes (excited)/(calm) etc."""

    def __init__(
        self,
        *,
        voice: str = "af_heart",
        lang_code: str = "a",
        sample_rate: int = KOKORO_SAMPLE_RATE,
        speed: float = 1.0,
        **kwargs,
    ):
        super().__init__(sample_rate=sample_rate, **kwargs)
        self._voice = voice
        self._lang_code = lang_code
        self._base_speed = max(0.5, min(2.0, float(speed)))
        self._pipeline = None

    def _ensure_pipeline(self):
        if self._pipeline is None:
            try:
                from kokoro import KPipeline
                self._pipeline = KPipeline(lang_code=self._lang_code)
            except ImportError as e:
                logger.error(f"Kokoro not installed: {e}. Install with: pip install kokoro soundfile")
                raise

    async def run_tts(self, text: str) -> AsyncGenerator[Frame, None]:
        """Generate speech from text using Kokoro. Strips (excited)/(calm) etc. and applies speed."""
        clean_text, emote_speed = _strip_voice_emote(text)
        if not clean_text:
            return
        segment_speed = self._base_speed * emote_speed
        logger.debug(
            f"{self}: Generating TTS [{clean_text[:80]}...] (speed={segment_speed:.2f})"
            if len(clean_text) > 80
            else f"{self}: Generating TTS [{clean_text}] (speed={segment_speed:.2f})"
        )
        self._ensure_pipeline()
        try:
            await self.start_ttfb_metrics()
            yield TTSStartedFrame()
            await self.stop_ttfb_metrics()

            # Run Kokoro in a thread (it's synchronous)
            def _synthesize():
                import numpy as np
                chunks = []
                for _gs, _ps, audio in self._pipeline(clean_text, voice=self._voice, speed=segment_speed):
                    # Kokoro may return a PyTorch tensor; convert to numpy for int16
                    if hasattr(audio, "cpu"):
                        audio = audio.cpu().numpy()
                    audio = np.asarray(audio, dtype=np.float32)
                    audio_int16 = (np.clip(audio, -1.0, 1.0) * 32767).astype(np.int16)
                    chunks.append(audio_int16.tobytes())
                return b"".join(chunks)

            loop = asyncio.get_event_loop()
            audio_bytes = await loop.run_in_executor(None, _synthesize)

            if audio_bytes:
                chunk_size = self.chunk_size
                for i in range(0, len(audio_bytes), chunk_size):
                    chunk = audio_bytes[i : i + chunk_size]
                    if len(chunk) % 2:
                        chunk += b"\x00"
                    if chunk:
                        rate = self.sample_rate or self._init_sample_rate or KOKORO_SAMPLE_RATE
                        yield TTSAudioRawFrame(chunk, rate, 1)
        except Exception as e:
            logger.exception(f"Kokoro TTS error: {e}")
            yield ErrorFrame(error=str(e))
        finally:
            yield TTSStoppedFrame()
