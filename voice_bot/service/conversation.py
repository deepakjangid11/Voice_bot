import sys
from src.logger import get_logger
from src.exception import CustomException
logger = get_logger(__name__)

class ConversationService:

    def __init__(self):
        try:
            self.messages = [
                {
                    "role" : "system",
                    "content" : "You are a helpful and friendly voice assistent. Give clear and concise responses."
                }
            ]

            logger.info("Conversation service initialized successfully.")

        except Exception as e:
            logger.error("Failed to initialize Conversation service")
            raise CustomException(e,sys)

    def add_message(self , role , content):
        try:
            self.messages.append({
                "role" : role,
                "content" : content
            })
            logger.info(f"{role} message adding to conversation.")
        except Exception as e:
            logger.error("Error during adding message to conversation.")
            raise CustomException(e,sys)

    def get_messages(self):
        try:
            return self.messages
        except Exception as e:
            logger.error("Error during getting messages from conversation.")
            raise CustomException(e,sys)