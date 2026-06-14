import os
import json
import logging
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from dotenv import load_dotenv
import google.generativeai as genai
from prompts import SYSTEM_INSTRUCTIONS

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AuraBackend")

# Load environment variables
load_dotenv()

# Initialize Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("GEMINI_API_KEY is not set in environment or .env file. Running in Demo Mode with fallback responses.")
else:
    logger.info("Configuring Gemini API key...")
    genai.configure(api_key=GEMINI_API_KEY)

app = FastAPI(title="Aura - Mental Health Companion Chatbot")

# Enable CORS for development flexibility
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request schema
class ChatRequest(BaseModel):
    message: str = Field(..., description="Message from the student")
    history: list = Field(default=[], description="Chat history containing past messages")

# API route for chatbot conversation
@app.post("/api/chat")
async def chat_endpoint(request: ChatRequest):
    # Fallback response if Gemini API key is missing (keeps app functional for local tests)
    if not GEMINI_API_KEY:
        logger.info("Demo Mode: Generating fallback response.")
        # Detect simple words to make demo mode feel interactive
        msg_lower = request.message.lower()
        sentiment = "Calm"
        tips = ["Take a slow, deep breath in, hold it, and let it go."]
        quote = "You are stronger than you know."
        
        if any(w in msg_lower for w in ["stress", "exam", "study", "pressure", "tired"]):
            sentiment = "Stressed"
            response_text = "It sounds like school and exams are putting a lot of weight on your shoulders. Remember, your grades do not define your worth. Please take a small break today, even if it is just for five minutes."
            tips = ["Try the shoulder release: pull your shoulders up to your ears, hold for 3 seconds, then drop them completely.", "Step away from your screen for 2 minutes."]
            quote = "One step at a time. You can do this, but you don't have to do it all at once."
        elif any(w in msg_lower for w in ["anxious", "panic", "worry", "scared", "fear"]):
            sentiment = "Anxious"
            response_text = "I hear how much worry you are carrying right now. It can feel really overwhelming when thoughts start racing. I'm right here with you. Let's focus on this present moment and ground ourselves."
            tips = ["Look around and name 3 things you can see, and 2 things you can touch (5-4-3-2-1 Grounding).", "Follow the breathing bubble on the screen for 3 cycles."]
            quote = "Feelings come and go like clouds in a windy sky. Conscious breathing is my anchor. - Thich Nhat Hanh"
        elif any(w in msg_lower for w in ["alone", "lonely", "loneliness", "isolate", "no one"]):
            sentiment = "Lonely"
            response_text = "Loneliness is a heavy feeling, and it is more common in college than people admit. You might feel isolated, but you are not alone in feeling this way. I am here to chat, and I value your presence."
            tips = ["Send a simple text message to a classmate, family member, or friend, even just a funny meme.", "Consider joining a campus club or taking a walk in a public space to feel connected to the environment."]
            quote = "Connection is why we're here; it gives purpose and meaning to our lives. - Brené Brown"
        elif any(w in msg_lower for w in ["sad", "depressed", "cry", "hurt", "gloom"]):
            sentiment = "Sad"
            response_text = "I'm so sorry things feel heavy and sad right now. It is okay to cry and feel down. You don't have to put on a brave face. I am listening, and I want to support you through this."
            tips = ["Wrap yourself in a warm blanket or take a hot shower to feel comforted.", "Write down one small thing you can control today, no matter how tiny."]
            quote = "It's okay to not be okay, as long as you don't give up. - Unknown"
        elif any(w in msg_lower for w in ["happy", "good", "great", "excited", "fine"]):
            sentiment = "Happy"
            response_text = "I am so glad to hear you are feeling good! It's wonderful to celebrate these positive moments in college. Keep riding this wave, and share this positive energy around you!"
            tips = ["Write down what made you happy today so you can remember it on tougher days.", "Take a moment to express gratitude for this feeling."]
            quote = "Joy is not standard; it is a choice we make in the moments we live."
        else:
            response_text = "I am here to listen. You can tell me about your day, your studies, or whatever is on your mind. How are you holding up?"
            tips = ["Take a moment to stretch your neck and back."]
            quote = "Be gentle with yourself. You are doing the best you can."

        return {
            "sentiment": sentiment,
            "intensity": 3,
            "response": response_text,
            "relaxation_tips": tips,
            "quote": quote,
            "demo": True
        }

    try:
        # Initialize Gemini 1.5 Flash model
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash",
            generation_config={"response_mime_type": "application/json"},
            system_instruction=SYSTEM_INSTRUCTIONS
        )
        
        # Build prompt context out of chat history
        prompt_text = "Here is the conversation history:\n"
        for msg in request.history[-6:]: # Fetch up to 6 history rounds to conserve context length
            role = "Student" if msg.get("role") == "user" else "Aura"
            prompt_text += f"{role}: {msg.get('text')}\n"
            
        prompt_text += f"Student: {request.message}\n"
        prompt_text += "\nRespond as Aura in JSON format with keys: sentiment, intensity, response, relaxation_tips, quote."

        logger.info(f"Sending message to Gemini API: {request.message[:40]}...")
        response = model.generate_content(prompt_text)
        
        # Parse the JSON response
        response_json = json.loads(response.text)
        return response_json

    except Exception as e:
        logger.error(f"Error calling Gemini API: {str(e)}")
        raise HTTPException(
            status_code=500, 
            detail=f"An error occurred while connecting to the AI services: {str(e)}"
        )

# Mount static files to serve the front-end SPA
# Note: StaticFiles must be mounted after API paths
static_dir = os.path.join(os.path.dirname(__file__), "static")
if not os.path.exists(static_dir):
    os.makedirs(static_dir)

app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
