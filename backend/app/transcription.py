import io
import os
import logging
from typing import Optional
from openai import OpenAI
from app.config import settings

logger = logging.getLogger("audio_transcriber")

def transcribe_audio(file_bytes: bytes, filename: str) -> str:
    """
    Transcribes audio bytes to text using either OpenAI Whisper API or local Whisper.
    Encapsulated behind this clean interface.
    """
    whisper_mode = getattr(settings, "WHISPER_MODE", "api")
    if settings.WHISPER_USE_LOCAL:
        whisper_mode = "local"

    if whisper_mode == "local":
        try:
            import whisper
            import tempfile
            
            ext = os.path.splitext(filename)[1] or ".mp3"
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as temp_file:
                temp_file.write(file_bytes)
                temp_path = temp_file.name
            
            try:
                model = whisper.load_model("base")
                result = model.transcribe(temp_path)
                return result.get("text", "").strip()
            finally:
                if os.path.exists(temp_path):
                    os.remove(temp_path)
        except ImportError:
            logger.warning("Local whisper module not found; falling back to OpenAI Whisper API")
        except Exception as e:
            logger.error(f"Local Whisper transcription failed: {e}")
            raise ValueError(f"Local audio transcription failed: {e}")

    # Default to OpenAI Whisper API
    api_key = settings.OPENAI_API_KEY or os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not configured for audio transcription")

    client = OpenAI(api_key=api_key)
    
    # Wrap bytes in a BytesIO buffer with name attribute for OpenAI SDK
    buffer = io.BytesIO(file_bytes)
    buffer.name = filename if filename else "audio.mp3"

    transcript_obj = client.audio.transcriptions.create(
        model="whisper-1",
        file=buffer
    )
    return transcript_obj.text.strip()
