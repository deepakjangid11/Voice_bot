import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv
from groq import Groq
from voice_bot.service.appointment_db import get_available_doctor_slots, book_doctor_slot
from src.logger import get_logger
from src.exception import CustomException

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
load_dotenv()

SYMPTOM_SPECIALIZATION_MAP = {
    "pet": "Gastroenterologist",
    "acid": "Gastroenterologist",
    "gas": "Gastroenterologist",
    "stomach": "Gastroenterologist",
    "digestion": "Gastroenterologist",
    "kabz": "Gastroenterologist",
    "constipation": "Gastroenterologist",
    "ulti": "Gastroenterologist",
    "vomit": "Gastroenterologist",
    "sar": "Neurologist",
    "sir": "Neurologist",
    "head": "Neurologist",
    "migraine": "Neurologist",
    "chakkar": "Neurologist",
    "dizzy": "Neurologist",
    "nerve": "Neurologist",
    "skin": "Dermatologist",
    "rash": "Dermatologist",
    "khujli": "Dermatologist",
    "itch": "Dermatologist",
    "acne": "Dermatologist",
    "pimple": "Dermatologist",
    "allergy": "Dermatologist",
    "twacha": "Dermatologist",
    "saans": "Pulmonologist",
    "breath": "Pulmonologist",
    "cough": "Pulmonologist",
    "khansi": "Pulmonologist",
    "asthma": "Pulmonologist",
    "chest": "Pulmonologist",
    "lung": "Pulmonologist",
    "bone": "Orthopedist",
    "haddi": "Orthopedist",
    "knee": "Orthopedist",
    "ghutna": "Orthopedist",
    "back": "Orthopedist",
    "kamar": "Orthopedist",
    "joint": "Orthopedist",
    "ear": "ENT Specialist",
    "kaan": "ENT Specialist",
    "nose": "ENT Specialist",
    "naak": "ENT Specialist",
    "throat": "ENT Specialist",
    "gala": "ENT Specialist",
    "tonsil": "ENT Specialist",
    "heart": "Cardiologist",
    "dil": "Cardiologist",
    "bp": "Cardiologist",
    "eye": "Ophthalmologist",
    "aankh": "Ophthalmologist",
    "vision": "Ophthalmologist",
    "teeth": "Dentist",
    "tooth": "Dentist",
    "daant": "Dentist",
    "bukhar": "General Physician",
    "fever": "General Physician",
    "cold": "General Physician",
    "thand": "General Physician",
    "weakness": "General Physician",
    "kamzori": "General Physician",
    "body pain": "General Physician",
    "sardee": "General Physician",
    "dard": "General Physician"
}

AFFIRMATIVE_KEYWORDS = {
    "yes", "yep", "yeah", "sure", "ok", "okay", "certainly", "definitely",
    "comfortable", "i am comfortable", "book it", "please book", "book appointment",
    "confirm", "confirm it", "sounds good", "works for me", "fine",
    "haan", "ha", "haa", "haji", "ha ji", "theek hai", "thik hai",
    "comfortable hu", "book kar do", "kar do", "book karo", "confirm kar do",
    "kar dijiye", "kardo", "book kardo", "bilkul", "chalega"
}

DECLINE_KEYWORDS = {
    "no", "nope", "nah", "not comfortable", "another time", "different time",
    "next slot", "other time", "change time", "any other time", "next",
    "nahi", "na", "dusra", "dusra time", "dusra slot", "agla",
    "agla slot", "dusra time batao", "koi aur time", "koi or time",
    "dusra dekho", "ye nahi chalega", "dusra batao"
}

LANGUAGE_PATTERNS = [
    (["speak in hindi", "talk in hindi", "in hindi", "hindi me", "hindi mein", "hindi please", "can you speak hindi", "can you speak in hindi", "switch to hindi", "hindi me baat", "hindi mein baat", "hindi me bolo", "hindi mein bolo", "hindi"], "Hindi"),
    (["speak in hinglish", "talk in hinglish", "in hinglish", "hinglish me", "hinglish mein", "switch to hinglish", "hinglish"], "Hinglish"),
    (["speak in english", "talk in english", "in english", "english me", "english mein", "english please", "can you speak english", "can you speak in english", "switch to english", "english"], "English")
]

class LLMService:

    def __init__(self):
        try:
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                raise ValueError("GROQ_API_KEY is not set in the environment variables.")

            self.client = Groq(api_key=api_key)
            self.model = os.getenv("GROQ_LLM_MODEL", "qwen/qwen3.8-27b")
            self.current_language = "English"
            self.reset_booking()
            logger.info(f"Groq client initialized successfully with model: {self.model}")
        except Exception as e:
            logger.error("Failed to initialize Groq client")
            raise CustomException(e, sys)

    def reset_booking(self):
        self.booking_state = {
            "stage": "IDLE",
            "reason": "",
            "specialization": None,
            "doctor_name": None,
            "clinic": None,
            "slots": [],
            "slot_index": 0
        }

    def detect_requested_language(self, text):
        clean = (text or "").lower().strip().strip(". ,?!;:\"'-")
        for patterns, lang in LANGUAGE_PATTERNS:
            if clean in patterns or any(p in clean for p in patterns):
                return lang
        return None

    def map_symptoms_to_specialization(self, symptoms_text):
        text = (symptoms_text or "").lower()
        for kw, spec in SYMPTOM_SPECIALIZATION_MAP.items():
            if kw in text:
                return spec
        return "General Physician"

    def get_tools_definition(self):
        return [
            {
                "type": "function",
                "function": {
                    "name": "recommend_doctor_and_slots",
                    "description": "Call when patient mentions their illness, symptoms, or requested doctor. Finds the specialist doctor and their earliest available appointment slot.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "symptoms": {
                                "type": "string",
                                "description": "Patient illness, symptoms or reason for visit"
                            },
                            "specialization": {
                                "type": "string",
                                "description": "Medical specialization e.g. Gastroenterologist, Neurologist, Dermatologist, Pulmonologist, General Physician"
                            },
                            "doctor_name": {
                                "type": "string",
                                "description": "Specific doctor name if requested"
                            }
                        }
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "propose_next_slot",
                    "description": "Call when patient declines the offered time, says no, asks for another time, or is not comfortable with the slot.",
                    "parameters": {
                        "type": "object",
                        "properties": {}
                    }
                }
            },
            {
                "type": "function",
                "function": {
                    "name": "confirm_and_book_appointment",
                    "description": "Call when patient agrees, says yes, comfortable, confirms, or agrees to book the appointment.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "reason": {
                                "type": "string",
                                "description": "Optional illness reason for appointment"
                            }
                        }
                    }
                }
            }
        ]

    def execute_tool_call(self, tool_name, tool_args):
        try:
            if tool_name == "recommend_doctor_and_slots":
                symptoms = tool_args.get("symptoms") or ""
                specialization = tool_args.get("specialization")
                doctor_name = tool_args.get("doctor_name")

                if not specialization and symptoms:
                    specialization = self.map_symptoms_to_specialization(symptoms)

                slots = get_available_doctor_slots(doctor_name=doctor_name, specialization=specialization, limit=20)
                if not slots and doctor_name:
                    slots = get_available_doctor_slots(specialization=specialization, limit=20)
                if not slots:
                    slots = get_available_doctor_slots(limit=20)

                if not slots:
                    return json.dumps({
                        "status": "no_slots",
                        "message": "No doctor appointment slots are currently available."
                    })

                chosen_doctor = slots[0]["doctor_name"]
                doctor_slots = get_available_doctor_slots(doctor_name=chosen_doctor, limit=10)
                if not doctor_slots:
                    doctor_slots = [s for s in slots if s["doctor_name"] == chosen_doctor]

                self.booking_state["stage"] = "OFFERING_SLOT"
                self.booking_state["reason"] = symptoms or "Patient Consultation"
                self.booking_state["doctor_name"] = chosen_doctor
                self.booking_state["specialization"] = doctor_slots[0]["specialization"]
                self.booking_state["clinic"] = doctor_slots[0]["clinic"]
                self.booking_state["slots"] = doctor_slots
                self.booking_state["slot_index"] = 0

                first_slot = doctor_slots[0]
                return json.dumps({
                    "status": "success",
                    "doctor_name": chosen_doctor,
                    "specialization": doctor_slots[0]["specialization"],
                    "clinic": doctor_slots[0]["clinic"],
                    "slot_date": first_slot["slot_date"],
                    "start_time": first_slot["start_time"],
                    "instruction": f"Recommend {chosen_doctor} ({doctor_slots[0]['specialization']}) for the patient's illness, state slot date {first_slot['slot_date']} at {first_slot['start_time']}, and ask if they are comfortable with this time in {self.current_language}."
                })

            elif tool_name == "propose_next_slot":
                if not self.booking_state["slots"]:
                    return json.dumps({
                        "status": "no_session",
                        "message": "Please mention your symptoms or doctor preference first."
                    })

                self.booking_state["slot_index"] += 1
                idx = self.booking_state["slot_index"]

                if idx < len(self.booking_state["slots"]):
                    next_slot = self.booking_state["slots"][idx]
                    return json.dumps({
                        "status": "success",
                        "doctor_name": self.booking_state["doctor_name"],
                        "slot_date": next_slot["slot_date"],
                        "start_time": next_slot["start_time"],
                        "instruction": f"State that the next available slot for {self.booking_state['doctor_name']} is on {next_slot['slot_date']} at {next_slot['start_time']}, and ask if they are comfortable with this time in {self.current_language}."
                    })
                else:
                    return json.dumps({
                        "status": "no_more_slots",
                        "message": f"No further appointment slots are available for {self.booking_state['doctor_name']}. Would you like to check with another doctor?"
                    })

            elif tool_name == "confirm_and_book_appointment":
                if not self.booking_state["slots"]:
                    return json.dumps({
                        "status": "no_session",
                        "message": "No slot has been selected yet. Please describe your symptoms first."
                    })

                idx = self.booking_state["slot_index"]
                if idx >= len(self.booking_state["slots"]):
                    idx = len(self.booking_state["slots"]) - 1

                slot = self.booking_state["slots"][idx]
                reason = tool_args.get("reason") or self.booking_state.get("reason") or "Patient Consultation"
                result = book_doctor_slot(slot_id=slot["slot_id"], reason=reason)

                if result.get("success"):
                    self.booking_state["stage"] = "BOOKED"
                    return json.dumps({
                        "status": "success",
                        "doctor_name": slot["doctor_name"],
                        "specialization": slot["specialization"],
                        "clinic": slot["clinic"],
                        "slot_date": slot["slot_date"],
                        "start_time": slot["start_time"],
                        "instruction": f"Cheerfully confirm that appointment with {slot['doctor_name']} on {slot['slot_date']} at {slot['start_time']} is confirmed and booked successfully in {self.current_language}."
                    })
                else:
                    return json.dumps({
                        "status": "failed",
                        "message": result.get("message", "Could not book slot.")
                    })

            return json.dumps({"error": "Unknown tool"})
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return json.dumps({"error": str(e)})

    def generate_response(self, messages):
        try:
            last_user_text = ""
            for msg in reversed(messages):
                if msg.get("role") == "user":
                    last_user_text = msg.get("content", "").strip()
                    break

            clean_user_input = last_user_text.lower().strip(". ,?!;:\"'-")

            detected_lang = self.detect_requested_language(clean_user_input)
            if detected_lang:
                self.current_language = detected_lang

            system_message = {
                "role": "system",
                "content": (
                    "You are Nova, Sanjeevani Clinic's friendly and intelligent voice consultation assistant. "
                    f"CURRENT ACTIVE LANGUAGE: {self.current_language}. You MUST speak strictly in {self.current_language}. "
                    "DEFAULT LANGUAGE IS ENGLISH. Do NOT switch to Hindi, Hinglish, or any other language unless the user explicitly requests you to speak in that language (e.g. 'speak in Hindi', 'Hindi me bolo'). "
                    "Always speak naturally in 1 to 2 clear, warm sentences. Never use bullet points, asterisks, tables, or markdown formatting. "
                    "Follow this exact appointment booking protocol: "
                    "1. When a user asks to book an appointment or see a doctor without naming their illness or symptoms, ask them what health issue or symptoms they are experiencing in the active language. "
                    "2. When the user tells you their illness, symptoms, or requested doctor, you MUST call recommend_doctor_and_slots. Then recommend that specialist doctor, announce the slot date and time, and ask: 'Are you comfortable with this time?' (or in the active language if switched). "
                    "3. If the user declines, says no, asks for another time, or says they are not comfortable ('no', 'another time', 'not comfortable', 'nahi', 'dusra time'), you MUST call propose_next_slot. Announce the next slot date and time, and ask if they are comfortable with this time. "
                    "4. When the user agrees or confirms ('yes', 'sure', 'comfortable', 'book it', 'confirm', 'haan', 'theek hai'), you MUST call confirm_and_book_appointment. Cheerfully confirm that their appointment is booked with the doctor name, date, and time in the active language."
                )
            }

            if self.booking_state["stage"] == "OFFERING_SLOT":
                is_affirmative = clean_user_input in AFFIRMATIVE_KEYWORDS or any(kw in clean_user_input for kw in ["book it", "confirm", "comfortable", "works for me", "sounds good", "book kar", "haan", "theek hai"])
                is_decline = clean_user_input in DECLINE_KEYWORDS or any(kw in clean_user_input for kw in ["another time", "different time", "next slot", "not comfortable", "dusra", "agla", "nahi", "koi aur"])

                if is_affirmative and not is_decline:
                    tool_result = self.execute_tool_call("confirm_and_book_appointment", {})
                    follow_up = [
                        system_message,
                        {"role": "user", "content": clean_user_input},
                        {"role": "assistant", "content": "Confirming appointment booking."},
                        {"role": "system", "content": f"Booking execution result: {tool_result}. Now cheerfully confirm to the patient in 1 warm sentence with doctor name, date, and time strictly in {self.current_language}."}
                    ]
                    final_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=follow_up,
                        temperature=0.2,
                        max_tokens=90
                    )
                    return final_response.choices[0].message.content.strip()

                elif is_decline and not is_affirmative:
                    tool_result = self.execute_tool_call("propose_next_slot", {})
                    follow_up = [
                        system_message,
                        {"role": "user", "content": clean_user_input},
                        {"role": "assistant", "content": "Checking next available slot."},
                        {"role": "system", "content": f"Next slot result: {tool_result}. Now announce this next slot to patient in 1 warm sentence strictly in {self.current_language} and ask if they are comfortable with this time."}
                    ]
                    final_response = self.client.chat.completions.create(
                        model=self.model,
                        messages=follow_up,
                        temperature=0.2,
                        max_tokens=90
                    )
                    return final_response.choices[0].message.content.strip()

            conversation = [system_message] + messages

            response = self.client.chat.completions.create(
                model=self.model,
                messages=conversation,
                tools=self.get_tools_definition(),
                tool_choice="auto",
                temperature=0.2,
                max_tokens=110
            )

            choice = response.choices[0]

            if choice.message.tool_calls:
                tool_call = choice.message.tool_calls[0]
                function_name = tool_call.function.name
                try:
                    function_args = json.loads(tool_call.function.arguments) if tool_call.function.arguments else {}
                except Exception:
                    function_args = {}

                tool_result = self.execute_tool_call(function_name, function_args)

                follow_up_messages = conversation + [
                    choice.message,
                    {
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": tool_result
                    }
                ]

                final_response = self.client.chat.completions.create(
                    model=self.model,
                    messages=follow_up_messages,
                    temperature=0.2,
                    max_tokens=110
                )

                return final_response.choices[0].message.content.strip()

            result = choice.message.content.strip() if choice.message.content else "How can I help you today?"
            return result

        except Exception as e:
            logger.error("Error during response generation from Groq LLM.")
            raise CustomException(e, sys)
