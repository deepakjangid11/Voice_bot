# AI Voice Bot

An AI-powered voice bot designed for natural voice-based conversations and automated doctor appointment booking. The system combines speech processing, AI/LLM capabilities, backend APIs, and database integration to provide an interactive voice-based healthcare experience.

## Features

* Voice-based AI conversation
* Speech-to-Text processing
* AI-powered response generation
* Text-to-Speech voice responses
* Doctor appointment booking
* Database integration
* REST API backend using FastAPI
* Conversation and appointment handling
* Environment-based API key management
* Postman support for API testing
* Logging and exception handling

## Voice Bot Flow

```text
User
  ↓
Voice Input
  ↓
Speech-to-Text
  ↓
AI / LLM Processing
  ↓
Intent & Conversation Handling
  ↓
Database Operations
  ↓
Text-to-Speech
  ↓
Voice Response
  ↓
User
```

For appointment booking:

```text
User
  ↓
Voice Bot
  ↓
Collect Patient Details
  ↓
Select City
  ↓
Select Doctor / Specialty
  ↓
Select Date & Time
  ↓
Check Availability
  ↓
Book Appointment
  ↓
Store Appointment in Database
  ↓
Voice Confirmation
```

## Tech Stack

* Python
* FastAPI
* LLM / Generative AI
* Speech-to-Text
* Text-to-Speech
* REST APIs
* Database
* Uvicorn
* python-dotenv
* Postman

## Project Structure

```text
voice-bot/
│
├── src/
│   ├── voice_bot/
│   ├── __init__.py
│   ├── exception.py
│   └── logger.py
│
├── static/
├── templates/
├── Logs/
│
├── main.py
├── requirements.txt
├── pyproject.toml
├── .python-version
├── .env.example
├── .gitignore
└── README.md
```

## Installation

Clone the repository:

```bash
git clone <your-repository-url>
cd voice-bot
```

Create a virtual environment:

```bash
python -m venv .venv
```

Activate the virtual environment on Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

## Environment Variables

Create a `.env` file in the project root.

```env
GROQ_API_KEY=your_api_key
ELEVENLABS_API_KEY=your_api_key
GEMINI_API_KEY=your_api_key
DATABASE_URL=your_database_url
```

Use the environment variable names required by the project configuration.

**Never commit `.env` or API keys to GitHub.**

A `.env.example` file can be used to show the required variables without exposing secret values.

## Run the Project

Start the FastAPI application:

```bash
uvicorn main:app --reload
```

The API will be available locally at:

```text
http://127.0.0.1:8000
```

## API Testing

The APIs can be tested using Postman.

Typical testing flow:

```text
Start Server
     ↓
Open Postman
     ↓
Send API Request
     ↓
Provide Voice / User Input
     ↓
Process Request
     ↓
Receive AI Response
```

## Security

API keys and sensitive configuration are stored using environment variables.

The following files should not be committed:

```text
.env
.venv/
__pycache__/
Logs/
```

Make sure `.env` is included in `.gitignore` before pushing the project to GitHub.

## Error Handling & Logging

The project includes dedicated exception handling and logging components to help identify runtime errors and monitor application behavior.

```text
src/
├── exception.py
└── logger.py
```

## Future Improvements

* Real-time voice conversation
* Improved response latency
* Multi-language voice support
* Advanced appointment management
* Doctor availability management
* Authentication and authorization
* Conversation history
* Production deployment
* Improved AI agent capabilities

## Author

**Deepak Jangid**

BCA | AI/ML & Data Science | Python | FastAPI | Flutter

## License

This project is for educational and development purposes.
