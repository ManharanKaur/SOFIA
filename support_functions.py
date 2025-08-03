import pyttsx3 # for text to speech
from langdetect import detect # for auto detection of language spoken
from gtts import gTTS # google text to speech
import tempfile
import psutil # for system monitoring
import requests # for web scraping
import os # for file operations
from dotenv import load_dotenv # for environment variables
from google import generativeai as genai


tts = pyttsx3.init()


def speak(text):
    try:
        lang = detect(text)
        if lang != 'en':  # Use gTTS for non-English
            tts_audio = gTTS(text=text, lang=lang)
            with tempfile.NamedTemporaryFile(delete=True, suffix=".mp3") as fp:
                tts_audio.save(fp.name)
                os.system(f"afplay {fp.name}")  # system player
        else:
            tts.say(text)
            tts.runAndWait()
    except Exception as e:
        print("Fallback to English TTS due to error:", e)
        tts.say(text)
        tts.runAndWait()


# Track last battery percentage announced
last_battery_alert = {"percent": 100}  # Default to full battery

def check_battery():
    battery = psutil.sensors_battery()
    if battery:
        percent = battery.percent
        plugged = battery.power_plugged

        # If not charging and battery below 20%
        if percent <= 20 and not plugged:
            # Only alert if this % hasn't been alerted yet
            if percent < last_battery_alert["percent"]:
                speak(f"Battery is at {percent} percent. Plug me in!")
        last_battery_alert["percent"] = percent





# to get apis for news
load_dotenv()
news_api = os.getenv("NEWS_API_KEY")

#  function to speak news using API
def get_news():
    url = f"http://api.mediastack.com/v1/news?access_key={news_api}&countries=in&languages=en&limit=5"
    
    response = requests.get(url)
    data = response.json()
    
    if "data" in data:
        for i, article in enumerate(data["data"], 1):
            title = article.get("title", "No title available")
            print(f"{i}. {title}")
            speak(f"Headline {i}: {title}")
    else:
        print("Failed to fetch news.")
        speak("Sorry, I couldn't find any news articles.")



genai.configure(api_key=os.environ.get("GEMINI_API_KEY"))
model = genai.GenerativeModel("gemini-2.0-flash")
# function to integrate GEMINI
def ask_gemini(prompt):
    try:
        short_prompt = f"{prompt}\nPlease answer briefly (3-4 lines only)."
        response = model.generate_content([short_prompt])
        answer = response.text
        return answer
    except Exception as e:
        print(f"Error: {e}")
        return "Sorry, I couldn't contact the server right now."

