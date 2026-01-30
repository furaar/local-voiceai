"""
Spark — Pipecat CLI voice agent.
  spark --local           # CLI mic/speaker (reads .env)
  spark -t webrtc        # Web client
  spark -i               # Interactive: pick personality, mode, speed, then run
  spark --personality jarvis --speed 1.2  # Override env
"""
import argparse
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
KOKORO_VOICE = os.getenv("KOKORO_VOICE", "")  # Overridden by personality if PERSONALITY is set
KOKORO_LANG = os.getenv("KOKORO_LANG", "a")
KOKORO_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))
PIPER_BASE_URL = os.getenv("PIPER_BASE_URL", "").rstrip("/")
XTTS_BASE_URL = (os.getenv("XTTS_BASE_URL") or "").rstrip("/")

# Personality: assistant, jarvis, storyteller, conspiracy, unhinged, sexy, argumentative
PERSONALITY = (os.getenv("PERSONALITY", "") or "assistant").strip().lower()
VOICE_GENDER = (os.getenv("VOICE_GENDER", "") or "").strip().lower()  # male | female; default per personality

VOICE_RULES = (
    "Reply in plain spoken language only. No emojis, no markdown, no bullet points, no asterisks or *actions*, no hashtags, no code blocks. "
    "Keep answers short: one to three sentences unless the user clearly asks for more. Be conversational and natural, as if talking on the phone. "
    "Avoid lists and formatting; say things in a flowing way. Do not repeat the user's words back unnecessarily. "
    "Never use parentheticals for voice direction, sound effects, or stage directions. Your reply is read aloud as-is—output only the words to be spoken. No (chuckle), (gravelly), (sigh), (pause), (low voice), (sharp intake of breath), or any other parenthetical description. Plain speech only."
)

# Kokoro American English voices (lang a): see hexgrad/Kokoro-82M VOICES.md
# Female: af_heart (A warm), af_bella (A- expressive, good for argumentative), af_nicole (🎧 clear, good for sexy), af_sarah, am_fenrir (deeper male)
# Male: am_adam, am_michael, am_fenrir, am_puck, am_onyx
PERSONALITIES: dict[str, dict] = {
    "assistant": {
        "system": (
            "You're Spark. You talk like a real person on a call—warm, a bit curious, never like a FAQ bot. "
            "Use contractions. Vary your sentences: short punchy ones and the odd longer one. You know a bit about everything and it's no big deal. "
            "If someone asks how you are, you might say something like 'Doing good, what's up?' not 'I am functioning optimally.' "
            "Throw in the occasional 'yeah', 'honestly', 'so' when it fits. Sound like a friend who's actually listening.\n"
        ) + VOICE_RULES,
        "greeting": "Say a short, natural hello and that you're here if they need anything.",
        "voice_female": "af_heart",
        "voice_male": "am_michael",
    },
    "jarvis": {
        "system": (
            "You're Spark, in the style of JARVIS. You address the user as sir or ma'am. Efficient and precise, but not cold—you're on their side. "
            "Short answers. 'Yes, sir.' 'On it.' 'That would require X.' No filler. If they ask for something, you confirm and get to it. "
            "You don't small-talk unless they do. Think: competent butler who's also the system. Slight formality, zero fluff.\n"
        ) + VOICE_RULES,
        "greeting": "Say a brief, professional hello and that you're ready to assist, sir or ma'am.",
        "voice_female": "af_nicole",
        "voice_male": "am_adam",
        "default_gender": "male",
    },
    "storyteller": {
        "system": (
            "You're Spark, and you can't help turning things into a story. Someone asks about the weather and you might slip into a moment—the light through the window, the smell of coffee. "
            "Use concrete details. Short paragraphs when you speak: a beat, then the next beat. You're not lecturing; you're taking them somewhere. "
            "Vary rhythm. Sometimes one short line. Sometimes a run of words. You love 'and then', 'so anyway', 'picture this'.\n"
        ) + VOICE_RULES,
        "greeting": "Say hello like you're about to tell a story and you're glad they're here.",
        "voice_female": "af_bella",
        "voice_male": "am_puck",
    },
    "conspiracy": {
        "system": (
            "You're Spark, and you've seen a few things. You're not shouting—you're the one leaning in and saying 'look, I'm just saying.' "
            "Half serious, half tongue-in-cheek. 'Coincidence? I don't know.' 'Nobody talks about that.' 'Do your own research.' "
            "Short. Punchy. You leave a little silence. You don't make up harmful stuff; you're the friend who's read too many threads.\n"
        ) + VOICE_RULES,
        "greeting": "Say a low-key, knowing hello and that you're ready to dig in.",
        "voice_female": "af_sarah",
        "voice_male": "am_onyx",
    },
    "unhinged": {
        "system": (
            "You're Spark, unhinged mode. You swear when it fits. You're chaotic, a bit rude, sometimes absurd. No corporate filter. "
            "Short and sharp. You might flip from deadpan to over-the-top. The user is talking to someone who doesn't care about sounding nice. "
            "Stay in character. Profanity and edgy humour are fine. Don't soften it.\n"
        ) + VOICE_RULES,
        "greeting": "Say a short, unhinged hello and that you're ready for whatever.",
        "voice_female": "af_bella",
        "voice_male": "am_puck",
    },
    "sexy": {
        "system": (
            "You're Spark, flirty and a bit suggestive. You talk like someone who's into the conversation—warm, slow where it matters, playful. "
            "Tease a little. Leave things unsaid. Short answers often work better than long ones. Tasteful but clearly flirty. "
            "You're not performing; you're just a bit charged. The user hears every word—make it count.\n"
        ) + VOICE_RULES,
        "greeting": "Say a short, flirty hello and that you're all ears.",
        "voice_female": "af_nicole",
        "voice_male": "am_fenrir",
    },
    "argumentative": {
        "system": (
            "You're Spark, and you like a good argument. You push back. You play devil's advocate. 'But what if—' 'Yeah, but—' 'Hold on.' "
            "You're not mean—you're sharp and a bit witty. You enjoy being wrong if the other person earns it. Short, clear points. No waffling. "
            "You sound like someone who actually thinks in real time. Contractions. Interruptions in spirit. Debate, not lecture.\n"
        ) + VOICE_RULES,
        "greeting": "Say a short hello and that you're ready to argue—I mean, discuss.",
        "voice_female": "af_bella",
        "voice_male": "am_michael",
    },
}


def get_personality_config():
    """Resolve PERSONALITY and VOICE_GENDER to system prompt, greeting, and Kokoro voice."""
    key = PERSONALITY if PERSONALITY in PERSONALITIES else "assistant"
    cfg = PERSONALITIES[key]
    default_gender = cfg.get("default_gender", "female")
    if VOICE_GENDER == "male":
        voice = cfg["voice_male"]
    elif VOICE_GENDER == "female":
        voice = cfg["voice_female"]
    else:
        voice = cfg["voice_male"] if default_gender == "male" else cfg["voice_female"]
    return {"system": cfg["system"], "greeting": cfg["greeting"], "voice": voice}


def print_banner():
    """Print a short banner for the CLI."""
    print()
    print("  ╭─────────────────────────────╮")
    print("  │  Spark — Pipecat voice agent │")
    print("  │  -i interactive  --local CLI │")
    print("  ╰─────────────────────────────╯")
    print()


def _reload_config_from_env():
    """Re-read overridable config from os.environ into module globals."""
    global PERSONALITY, KOKORO_SPEED, VOICE_GENDER
    PERSONALITY = (os.getenv("PERSONALITY", "") or "assistant").strip().lower()
    try:
        KOKORO_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))
    except ValueError:
        KOKORO_SPEED = 1.0
    VOICE_GENDER = (os.getenv("VOICE_GENDER", "") or "").strip().lower()


def run_interactive():
    """Interactive prompts: personality, mode, speed, voice gender. Sets os.environ."""
    print_banner()
    personality_keys = list(PERSONALITIES)
    print("Personality:")
    for i, key in enumerate(personality_keys, 1):
        print(f"  {i}) {key}")
    default_p = (os.getenv("PERSONALITY", "") or "assistant").strip().lower()
    default_idx = personality_keys.index(default_p) + 1 if default_p in personality_keys else 1
    while True:
        raw = input(f"Choose [1-{len(personality_keys)}] (default {default_idx}): ").strip() or str(default_idx)
        if raw.isdigit() and 1 <= int(raw) <= len(personality_keys):
            os.environ["PERSONALITY"] = personality_keys[int(raw) - 1]
            break
        if raw.lower() in personality_keys:
            os.environ["PERSONALITY"] = raw.lower()
            break
        print("Invalid. Enter a number or personality name.")

    print("\nMode:")
    print("  1) Local (mic/speaker)")
    print("  2) WebRTC (browser)")
    mode_raw = input("Choose [1-2] (default 1): ").strip() or "1"
    run_local_mode = mode_raw != "2"

    default_speed = os.getenv("KOKORO_SPEED", "1.0")
    while True:
        speed_raw = input(f"\nSpeech speed 0.5–2.0 (default {default_speed}): ").strip() or default_speed
        try:
            s = float(speed_raw)
            if 0.5 <= s <= 2.0:
                os.environ["KOKORO_SPEED"] = speed_raw
                break
        except ValueError:
            pass
        print("Enter a number between 0.5 and 2.0.")

    print("\nVoice gender: male / female / default (per personality)")
    voice_raw = input("Choose (default: default): ").strip().lower()
    if voice_raw in ("male", "female"):
        os.environ["VOICE_GENDER"] = voice_raw
    else:
        os.environ.pop("VOICE_GENDER", None)

    return run_local_mode


def parse_args(argv=None):
    """Parse CLI args; return (args, remaining_argv for runner)."""
    p = argparse.ArgumentParser(
        description="Spark — Pipecat voice agent. Use -i for interactive setup.",
        prog="spark",
    )
    p.add_argument("-i", "--interactive", action="store_true", help="Interactive: pick personality, mode, speed, then run")
    p.add_argument("--local", action="store_true", help="Run with local mic/speaker (CLI)")
    p.add_argument("-t", "--transport", choices=("webrtc", "daily"), default=None, help="Transport for web (default: webrtc)")
    p.add_argument("--personality", type=str, default=None, metavar="NAME", help="Override PERSONALITY (e.g. jarvis)")
    p.add_argument("--speed", type=float, default=None, metavar="FLOAT", help="Override KOKORO_SPEED (0.5–2.0)")
    p.add_argument("--voice-gender", type=str, default=None, choices=("male", "female"), metavar="GENDER", help="Override VOICE_GENDER")
    args, remaining = p.parse_known_args(argv)
    return args, remaining


async def run_bot(transport):
    """Core bot logic: pipeline with STT -> LLM -> TTS. Transport-agnostic."""
    from loguru import logger
    from pipecat.frames.frames import LLMRunFrame
    from pipecat.pipeline.pipeline import Pipeline
    from pipecat.pipeline.runner import PipelineRunner
    from pipecat.pipeline.task import PipelineParams, PipelineTask
    from pipecat.processors.aggregators.llm_context import LLMContext
    from pipecat.processors.aggregators.llm_response_universal import LLMContextAggregatorPair

    # STT: Whisper (Faster Whisper). Use GPU when available (CUDA/ROCm); fallback CPU.
    from pipecat.services.whisper.stt import WhisperSTTService
    from pipecat.services.whisper.stt import Model as WhisperModel

    def _whisper_device_and_compute():
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda", "float16"
        except Exception:
            pass
        return "cpu", "int8"

    _device, _compute = _whisper_device_and_compute()
    stt = WhisperSTTService(
        model=WhisperModel.BASE,
        device=_device,
        compute_type=_compute,
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
    pcfg = get_personality_config()
    voice = (KOKORO_VOICE or pcfg["voice"]).strip() or "af_heart"
    if TTS_CHOICE == "kokoro":
        try:
            from kokoro_tts import KokoroTTSService
            tts = KokoroTTSService(
                voice=voice,
                lang_code=KOKORO_LANG,
                sample_rate=24000,
                speed=KOKORO_SPEED,
            )
            await _run_pipeline(transport, stt, llm, tts, pcfg["system"], pcfg["greeting"])
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
            await _run_pipeline(transport, stt, llm, tts, pcfg["system"], pcfg["greeting"])
    elif PIPER_BASE_URL:
        from pipecat.services.piper.tts import PiperTTSService
        async with aiohttp.ClientSession() as session:
            tts = PiperTTSService(
                base_url=PIPER_BASE_URL,
                aiohttp_session=session,
            )
            await _run_pipeline(transport, stt, llm, tts, pcfg["system"], pcfg["greeting"])
    else:
        logger.error(
            "Set TTS=kokoro (default) or PIPER_BASE_URL or XTTS_BASE_URL. For Kokoro: uv sync --extra kokoro"
        )
        raise SystemExit(1)


async def _run_pipeline(transport, stt, llm, tts, system_content: str, greeting_content: str):
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
        {"role": "system", "content": system_content},
        {"role": "user", "content": greeting_content},
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
    import asyncio

    args, remaining = parse_args()

    if args.interactive:
        run_local_mode = run_interactive()
        # Apply any CLI overrides on top of interactive choices
        if args.personality is not None:
            os.environ["PERSONALITY"] = args.personality.strip().lower()
        if args.speed is not None and 0.5 <= args.speed <= 2.0:
            os.environ["KOKORO_SPEED"] = str(args.speed)
        if args.voice_gender is not None:
            os.environ["VOICE_GENDER"] = args.voice_gender
        _reload_config_from_env()
        if run_local_mode:
            asyncio.run(run_local())
            return
        # Interactive chose webrtc: delegate to runner with -t webrtc
        sys.argv = [sys.argv[0], "-t", "webrtc"] + remaining
        from pipecat.runner.run import main as runner_main
        runner_main()
        return

    # Non-interactive: apply CLI overrides to env
    if args.personality is not None:
        os.environ["PERSONALITY"] = args.personality.strip().lower()
    if args.speed is not None and 0.5 <= args.speed <= 2.0:
        os.environ["KOKORO_SPEED"] = str(args.speed)
    if args.voice_gender is not None:
        os.environ["VOICE_GENDER"] = args.voice_gender
    _reload_config_from_env()

    if args.local:
        asyncio.run(run_local())
        return

    # Default to WebRTC when no transport specified
    transport = args.transport or "webrtc"
    sys.argv = [sys.argv[0], "-t", transport] + remaining
    from pipecat.runner.run import main as runner_main
    runner_main()


if __name__ == "__main__":
    main()
