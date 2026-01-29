"""
Dev-log frame processors: log Whisper transcriptions and LLM generation to the dev logs.
Insert these in the pipeline to see "dev | Whisper: ..." and "dev | LLM: ..." in the console.
"""
from loguru import logger

from pipecat.frames.frames import (
    Frame,
    FrameDirection,
    InterimTranscriptionFrame,
    LLMFullResponseEndFrame,
    LLMTextFrame,
    TranscriptionFrame,
)
from pipecat.processors.frame_processor import FrameProcessor


class DevLogTranscriptionProcessor(FrameProcessor):
    """Logs Whisper (STT) transcriptions: final and optional interim."""

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, TranscriptionFrame):
            logger.info(f"dev | Whisper: {frame.text!r}")
        elif isinstance(frame, InterimTranscriptionFrame):
            logger.debug(f"dev | Whisper (interim): {frame.text!r}")
        await self.push_frame(frame, direction)


class DevLogLLMProcessor(FrameProcessor):
    """Buffers LLM text and logs the full generation on LLMFullResponseEndFrame."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._buffer: list[str] = []

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)
        if isinstance(frame, LLMTextFrame):
            self._buffer.append(frame.text)
        elif isinstance(frame, LLMFullResponseEndFrame):
            full = "".join(self._buffer).strip()
            if full:
                logger.info(f"dev | LLM: {full!r}")
            self._buffer.clear()
        await self.push_frame(frame, direction)
