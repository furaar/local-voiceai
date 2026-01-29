"""
Local Pipecat CLI voice agent.
Run with: python bot.py --local  (CLI, mic/speaker)
Or with runner: python bot.py -t webrtc  (web client)
"""
import os
import sys

from dotenv import load_dotenv

load_dotenv(override=True)

# LM Studio (OpenAI-compatible)
LM_STUDIO_BASE_URL = os.getenv("LM_STUDIO_BASE_URL", "http://localhost:3000/v1")
LM_MODEL = os.getenv("LM_MODEL", "google_gemma-3-1b-it")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "lm-studio")

# TTS: Kokoro (in-process), or Piper/XTTS server URL
TTS_CHOICE = (os.getenv("TTS", "") or "kokoro").strip().lower()
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
KOKORO_LANG = os.getenv("KOKORO_LANG", "a")
KOKORO_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))
PIPER_BASE_URL = os.getenv("PIPER_BASE_URL", "").rstrip("/")
XTTS_BASE_URL = (os.getenv("XTTS_BASE_URL") or "").rstrip("/")


async def run_bot(transport):
    """Core bot logic: pipeline with STT -> LLM -> TTS. Transport-agnostic."""
    from loguru import logger
    from pipecat.frames.frames import LLMRunFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair

    # STT: Standard Whisper (Faster Whisper, CPU on AMD)
    from pipecat.services.whisper.stt import WhisperSTTService
    from pipecat.services.whisper.stt import Model as WhisperModel

    stt = WhisperSTTService(
        model=WhisperModel.BASE,
        device="cpu",
        compute_type="int8",
    )

    # LLM: LM Studio (OpenAI-compatible)
    from pipecat.services.openai.llm import OpenAILLMService

    llm = OpenAILLMService(
        model=LM_MODEL,
        api_key=OPENAI_API_KEY,
        base_url=LM_STUDIO_BASE_URL,
    )

    # TTS: Kokoro (in-process), Piper, or XTTS (server)
    import aiohttp
    if TTS_CHOICE == "kokoro":
        try:
            from kokoro_tts import KokoroTTSService
            tts = KokoroTTSService(
                voice=KOKORO_VOICE,
                lang_code=KOKORO_LANG,
                sample_rate=24000,
                speed=KOKORO_SPEED,
            )
            await _run_pipeline(transport, stt, llm, tts)
        except ImportError:
            logger.error("Kokoro TTS: install with  uv sync --extra kokoro  (or pip install kokoro soundfile)")
            raise SystemExit(1)
    elif XTTS_BASE_URL:
        from pipecat.services.xtts.tts import XTTSService
        async with aiohttp.ClientSession() as session:
            tts = XTTSService(
                base_url=XTTS_BASE_URL,
                voice_id="default",
                aiohttp_session=session,
            )
            await _run_pipeline(transport, stt, llm, tts)
    elif PIPER_BASE_URL:
        from pipecat.services.piper.tts import PiperTTSService
        async with aiohttp.ClientSession() as session:
            tts = PiperTTSService(
                base_url=PIPER_BASE_URL,
                aiohttp_session=session,
            )
            await _run_pipeline(transport, stt, llm, tts)
    else:
        logger.error(
            "Set TTS=kokoro (default) or PIPER_BASE_URL or XTTS_BASE_URL. For Kokoro: uv sync --extra kokoro"
        )
        raise SystemExit(1)


async def _run_pipeline(transport, stt, llm, tts):
    from loguru import logger
    import time
    from pipecat.frames.frames import (
        LLMFullResponseEndFrame,
        LLMRunFrame,
        LLMTextFrame,
        TranscriptionFrame,
        TTSAudioRawFrame,
        TTSStoppedFrame,
    )
    from pipecat.observers.base_observer import BaseObserver, FramePushed
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair

    class DevLogObserver(BaseObserver):
        """Log Whisper transcriptions, LLM generations, and per-request latency (no pipeline change)."""
        def __init__(self):
            super().__init__()
            self._llm_buffer = []
            self._request_start: float | None = None
            self._first_audio_time: float | None = None
            self._first_audio_seen = False

        async def on_push_frame(self, data: FramePushed):
            frame = data.frame
            now = time.monotonic()
            if isinstance(frame, TranscriptionFrame):
                self._request_start = now
                self._first_audio_time = None
                self._first_audio_seen = False
                logger.info(f"dev | Whisper: {frame.text!r}")
            elif isinstance(frame, LLMTextFrame):
                self._llm_buffer.append(frame.text)
            elif isinstance(frame, LLMFullResponseEndFrame):
                full = "".join(self._llm_buffer).strip()
                if full:
                    logger.info(f"dev | LLM: {full!r}")
                self._llm_buffer.clear()
            elif isinstance(frame, TTSAudioRawFrame) and self._request_start is not None and not self._first_audio_seen:
                self._first_audio_time = now
                self._first_audio_seen = True
            elif isinstance(frame, TTSStoppedFrame) and self._request_start is not None:
                total_ms = (now - self._request_start) * 1000
                first_ms = (self._first_audio_time - self._request_start) * 1000 if self._first_audio_time is not None else None
                if first_ms is not None:
                    logger.info(f"dev | latency: first_audio={first_ms:.0f}ms total={total_ms:.0f}ms")
                else:
                    logger.info(f"dev | latency: total={total_ms:.0f}ms (no audio)")
                self._request_start = None
                self._first_audio_time = None
                self._first_audio_seen = False

    # System + initial user so roles alternate (user/assistant). Stops "Conversation roles must alternate" after first reply.
    messages = [
        {
            "role": "system",
            "content": (
                "You are a friendly local voice assistant. The user hears your replies as speech (TTS), not text.\n"
                "Rules for voice: Reply in plain spoken language only. No emojis, no markdown, no bullet points, no asterisks or *actions*, no hashtags, no code blocks. "
                "Keep answers short: one to three sentences unless the user clearly asks for more. Be conversational and natural, as if talking on the phone. "
                "Avoid lists and formatting; say things in a flowing way. Do not repeat the user's words back unnecessarily.\n"
                "Voice-only emotes: You may start a phrase with a single tag in parentheses to affect how it is spoken (speed/tone). These are stripped before speech and only affect the TTS. Use sparingly. Examples: (excited) for slightly faster, (calm) or (warm) for slightly slower, (whisper) for a bit softer pace. Allowed tags: excited, calm, whisper, sad, serious, warm, quick, slow."
            ),
        },
        {
            "role": "user",
            "content": "Say a short hello and that you're ready.",
        },
    ]
    context = LLMContext(messages)
    # Use smart-turn in user aggregator (new API); avoid deprecated turn_analyzer on transport
    from pipecat.processors.aggregators.llm_response_universal import LLMUserAggregatorParams
    user_params = LLMUserAggregatorParams()
    try:
        from pipecat.audio.turn.smart_turn.base_smart_turn import SmartTurnParams
        from pipecat.audio.turn.smart_turn.local_smart_turn_v3 import LocalSmartTurnAnalyzerV3
        from pipecat.turns.user_stop import TurnAnalyzerUserTurnStopStrategy
        from pipecat.turns.user_turn_strategies import UserTurnStrategies
        user_params = LLMUserAggregatorParams(
            user_turn_strategies=UserTurnStrategies(
                stop=[TurnAnalyzerUserTurnStopStrategy(turn_analyzer=LocalSmartTurnAnalyzerV3(params=SmartTurnParams()))],
            ),
        )
    except Exception:
        pass
    pair = LLMContextAggregatorPair(context, user_params=user_params)
    user_aggregator = pair.user()
    assistant_aggregator = pair.assistant()

    pipeline = Pipeline(
        [
            transport.input(),
            stt,
            user_aggregator,
            llm,
            tts,
            transport.output(),
            assistant_aggregator,
        ]
    )

    task = PipelineTask(
        pipeline,
        params=PipelineParams(enable_metrics=True),
        observers=[DevLogObserver()],
    )

    # Greeting: trigger first LLM response
    await task.queue_frames([LLMRunFrame()])

    runner = PipelineRunner(handle_sigint=True)
    await runner.run(task)


async def run_local():
    """Run with LocalAudioTransport (CLI: mic and speaker)."""
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.transports.local.audio import (
        LocalAudioTransport,
        LocalAudioTransportParams,
    )
    params = LocalAudioTransportParams(
        audio_in_enabled=True,
        audio_out_enabled=True,
        vad_analyzer=SileroVADAnalyzer(),
    )
    transport = LocalAudioTransport(params=params)
    await run_bot(transport)


async def bot(runner_args):
    """Entry point for Pipecat development runner (webrtc, daily, telephony)."""
    from pipecat.runner.utils import create_transport
    from pipecat.audio.vad.silero import SileroVADAnalyzer
    from pipecat.transports.base_transport import TransportParams

    def webrtc_params():
        return TransportParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        )

    def daily_params():
        from pipecat.transports.daily.transport import DailyParams
        return DailyParams(
            audio_in_enabled=True,
            audio_out_enabled=True,
            vad_analyzer=SileroVADAnalyzer(),
        )

    transport_params = {"webrtc": webrtc_params, "daily": daily_params}
    transport = await create_transport(runner_args, transport_params)
    await run_bot(transport)


def main():
    if "--local" in sys.argv:
        import asyncio
        asyncio.run(run_local())
        return

    # Use Pipecat development runner for webrtc/daily/telephony
    from pipecat.runner.run import main as runner_main
    runner_main()


if __name__ == "__main__":
    main()
