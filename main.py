import sys
import base64
import time
import threading
from pathlib import Path
from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from voice_bot.service.voice_service import VoiceService
from voice_bot.service.llm_service import LLMService
from voice_bot.service.conversation import ConversationService
from voice_bot.service.appointment_db import get_available_doctor_slots
from src.logger import get_logger
from src.exception import CustomException

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")
load_dotenv()

app = FastAPI(title="Nova Voice Assistant")

@app.middleware("http")
async def add_no_cache_headers(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/static") or request.url.path == "/":
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    return response

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static"
)

templates = Jinja2Templates(directory=BASE_DIR / "templates")

voice_service = VoiceService()
llm_service = LLMService()
conversation_service = ConversationService()

def warmup_services():
    try:
        get_available_doctor_slots(limit=1)
        llm_service.generate_response([{"role": "user", "content": "hi"}])
        res = voice_service.text_to_speech("Hi")
        _ = b"".join(res)
    except Exception:
        pass

@app.on_event("startup")
def startup_event():
    threading.Thread(target=warmup_services, daemon=True).start()

STOP_COMMANDS = {
    "stop",
    "stop listening",
    "stop now",
    "please stop",
    "okay stop",
    "ok stop",
    "shut up",
    "cancel"
}

NOISE_FILTER_WORDS = {
    "thank you.",
    "thank you",
    "thanks for watching.",
    "thanks for watching",
    "bye.",
    "bye"
}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    try:
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={"cache_buster": int(time.time())}
        )
    except Exception as e:
        logger.error("Error loading home page.")
        raise CustomException(e, sys)

@app.post("/chat")
async def chat(audio_file: UploadFile = File(...)):
    try:
        total_start = time.perf_counter()

        audio_data = await audio_file.read()

        if not audio_data:
            return JSONResponse(
                status_code=400,
                content={
                    "user_text": "",
                    "response_text": "",
                    "audio": None,
                    "stopped": False,
                    "message": "No audio received."
                }
            )

        filename = audio_file.filename or "recording.webm"
        content_type = audio_file.content_type or "audio/webm"

        stt_start = time.perf_counter()

        user_text = voice_service.speech_to_text(
            audio_data,
            filename=filename,
            content_type=content_type
        )

        stt_time = time.perf_counter() - stt_start

        if not user_text:
            return JSONResponse(
                content={
                    "user_text": "",
                    "response_text": "",
                    "audio": None,
                    "stopped": False
                }
            )

        user_text = user_text.strip()
        logger.info(f"User said: {user_text}")

        clean_chars = user_text.strip(". ,?!;:\"'-")
        if not clean_chars or len(clean_chars) < 2 or user_text.lower() in NOISE_FILTER_WORDS:
            logger.info(f"Ignored noise artifact: '{user_text}'")
            return JSONResponse(
                content={
                    "user_text": "",
                    "response_text": "",
                    "audio": None,
                    "stopped": False
                }
            )

        normalized_text = user_text.lower().strip()

        if normalized_text in STOP_COMMANDS:
            logger.info("Stop command received.")

            conversation_service.add_message(
                "user",
                user_text
            )

            return JSONResponse(
                content={
                    "user_text": user_text,
                    "response_text": "",
                    "audio": None,
                    "stopped": True
                }
            )

        conversation_service.add_message(
            "user",
            user_text
        )

        messages = conversation_service.get_messages()
        messages = messages[-12:]

        llm_start = time.perf_counter()

        response_text = llm_service.generate_response(messages)

        llm_time = time.perf_counter() - llm_start

        logger.info(f"AI response: {response_text}")

        conversation_service.add_message(
            "assistant",
            response_text
        )

        tts_start = time.perf_counter()

        audio_response = voice_service.text_to_speech(
            response_text
        )

        if isinstance(audio_response, bytes):
            audio_bytes = audio_response
        else:
            audio_bytes = b"".join(audio_response)

        tts_time = time.perf_counter() - tts_start

        base64_start = time.perf_counter()

        audio_base64 = base64.b64encode(
            audio_bytes
        ).decode("utf-8")

        base64_time = time.perf_counter() - base64_start

        total_time = time.perf_counter() - total_start

        print()
        print("========== LATENCY BREAKDOWN ==========")
        print(f"STT Time       : {stt_time:.3f} sec")
        print(f"LLM Time       : {llm_time:.3f} sec")
        print(f"TTS Time       : {tts_time:.3f} sec")
        print(f"Base64 Time    : {base64_time:.3f} sec")
        print(f"TOTAL BACKEND  : {total_time:.3f} sec")
        print("=======================================")
        print()

        return JSONResponse(
            content={
                "user_text": user_text,
                "response_text": response_text,
                "audio": audio_base64,
                "stopped": False
            }
        )

    except Exception as e:
        logger.error("Error during chat processing.")
        raise CustomException(e, sys)
