import os
import pymysql
from pymysql.cursors import DictCursor
from pathlib import Path
from dotenv import load_dotenv
from src.logger import get_logger

logger = get_logger(__name__)

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(BASE_DIR / ".env")
load_dotenv() 

def get_db_connection():
    return pymysql.connect(
        host=os.getenv("DB_HOST", "localhost"),
        user=os.getenv("DB_USER", "root"),
        password=os.getenv("DB_PASSWORD", "NewPassword123"),
        database=os.getenv("DB_NAME", "health_db"),
        port=int(os.getenv("DB_PORT", "3306")),
        cursorclass=DictCursor,
        autocommit=False
    )

def get_available_doctor_slots(doctor_name=None, specialization=None, slot_date=None, limit=5):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            query = """
                SELECT
                    s.slot_id,
                    s.doctor_id,
                    d.name AS doctor_name,
                    d.specialization,
                    d.clinic,
                    s.slot_date,
                    TIME_FORMAT(s.start_time, '%%h:%%i %%p') AS start_time,
                    TIME_FORMAT(s.end_time, '%%h:%%i %%p') AS end_time
                FROM doctor_slots s
                JOIN doctors d ON s.doctor_id = d.doctor_id
                WHERE s.is_booked = 0 AND s.slot_date >= CURDATE()
            """
            params = []

            if doctor_name:
                query += " AND d.name LIKE %s"
                params.append(f"%{doctor_name}%")

            if specialization:
                query += " AND d.specialization LIKE %s"
                params.append(f"%{specialization}%")

            if slot_date:
                query += " AND s.slot_date = %s"
                params.append(slot_date)

            query += " ORDER BY s.slot_date ASC, s.start_time ASC LIMIT %s"
            params.append(int(limit))

            cur.execute(query, tuple(params))
            slots = cur.fetchall()

            if not slots and not slot_date:
                cur.execute(
                    """
                    SELECT
                        s.slot_id,
                        s.doctor_id,
                        d.name AS doctor_name,
                        d.specialization,
                        d.clinic,
                        s.slot_date,
                        TIME_FORMAT(s.start_time, '%%h:%%i %%p') AS start_time,
                        TIME_FORMAT(s.end_time, '%%h:%%i %%p') AS end_time
                    FROM doctor_slots s
                    JOIN doctors d ON s.doctor_id = d.doctor_id
                    WHERE s.is_booked = 0
                    ORDER BY s.slot_date DESC, s.start_time ASC
                    LIMIT %s
                    """,
                    (int(limit),)
                )
                slots = cur.fetchall()

            for slot in slots:
                if hasattr(slot.get("slot_date"), "strftime"):
                    slot["slot_date"] = slot["slot_date"].strftime("%d %B %Y")

            return slots
    except Exception as e:
        logger.error(f"Error fetching doctor slots: {e}")
        return []
    finally:
        if conn:
            conn.close()

def book_doctor_slot(slot_id, patient_id=1, reason="Voice Bot Booking"):
    conn = None
    try:
        conn = get_db_connection()
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.slot_id,
                    s.doctor_id,
                    s.is_booked,
                    d.name AS doctor_name,
                    d.specialization,
                    d.clinic,
                    s.slot_date,
                    TIME_FORMAT(s.start_time, '%%h:%%i %%p') AS start_time,
                    TIME_FORMAT(s.end_time, '%%h:%%i %%p') AS end_time
                FROM doctor_slots s
                JOIN doctors d ON s.doctor_id = d.doctor_id
                WHERE s.slot_id = %s
                FOR UPDATE
                """,
                (slot_id,)
            )

            slot = cur.fetchone()

            if not slot:
                conn.rollback()
                return {"success": False, "message": "Doctor slot not found"}

            if slot["is_booked"] == 1:
                conn.rollback()
                return {"success": False, "message": "This doctor slot is already booked"}

            cur.execute(
                "UPDATE doctor_slots SET is_booked = 1 WHERE slot_id = %s AND is_booked = 0",
                (slot_id,)
            )

            if cur.rowcount == 0:
                conn.rollback()
                return {"success": False, "message": "Slot is no longer available"}

            cur.execute(
                """
                INSERT INTO appointments (patient_id, doctor_id, slot_id, reason, status)
                VALUES (%s, %s, %s, %s, 'booked')
                """,
                (patient_id, slot["doctor_id"], slot_id, reason)
            )

            appointment_id = cur.lastrowid
            conn.commit()

            date_str = slot["slot_date"].strftime("%d %B %Y") if hasattr(slot["slot_date"], "strftime") else str(slot["slot_date"])

            return {
                "success": True,
                "appointment_id": appointment_id,
                "doctor_name": slot["doctor_name"],
                "specialization": slot["specialization"],
                "clinic": slot["clinic"],
                "slot_id": slot["slot_id"],
                "slot_date": date_str,
                "start_time": slot["start_time"],
                "end_time": slot["end_time"],
                "message": "Doctor appointment booked successfully"
            }

    except Exception as e:
        if conn:
            conn.rollback()
        logger.error(f"Error booking doctor slot: {e}")
        return {"success": False, "message": str(e)}
    finally:
        if conn:
            conn.close()
