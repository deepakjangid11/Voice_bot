import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from elevenlabs.client import ElevenLabs
from groq import Groq
from src.logger import get_logger
from src.exception import CustomException

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
load_dotenv()

class VoiceService:
    def __init__(self):
        try:
            eleven_api_key = os.getenv("ELEVENLABS_API_KEY")
            if not eleven_api_key:
                raise ValueError("ELEVENLABS_API_KEY is not set in the environment variables.")

            self.client = ElevenLabs(api_key=eleven_api_key)
            self.voice_id = os.getenv("ELEVENLABS_VOICE_ID")

            if not self.voice_id:
                raise ValueError("ELEVENLABS_VOICE_ID is not set in the environment variables.")

            groq_api_key = os.getenv("GROQ_API_KEY")
            if not groq_api_key:
                raise ValueError("GROQ_API_KEY is not set in the environment variables.")

            self.groq_client = Groq(api_key=groq_api_key)

            logger.info("VoiceService initialized with Groq Whisper and ElevenLabs successfully.")
        except Exception as e:
            logger.error("Failed to initialize VoiceService")
            raise CustomException(e, sys)

    def speech_to_text(self, audio_file, filename="recording.webm", content_type="audio/webm"):
        try:
            file_data = (filename, audio_file, content_type)

            result = self.groq_client.audio.transcriptions.create(
                file=file_data,
                model="whisper-large-v3-turbo",
                response_format="json",
                temperature=0.0
            )

            text = result.text.strip() if result and result.text else ""
            return text
        except Exception as e:
            logger.warning(f"STT warning: {e}")
            return ""

    def text_to_speech(self, text):
        try:
            audio = self.client.text_to_speech.convert(
                voice_id=self.voice_id,
                model_id="eleven_flash_v2_5",
                text=text,
                output_format="mp3_22050_32",
                optimize_streaming_latency=4
            )
            return audio
        except Exception as e:
            logger.error("Error during text-to-speech conversion.")
            raise CustomException(e, sys)
