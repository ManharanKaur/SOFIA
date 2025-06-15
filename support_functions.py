import pyttsx3
import psutil
import time
import requests
import os
from dotenv import load_dotenv

tts = pyttsx3.init()

def speak(text):
    tts.say(text)
    tts.runAndWait()

def check_battery():
    battery = psutil.sensors_battery()
    if battery and battery.percent <= 20 and not battery.power_plugged:
        speak(f"Battery is low. Only {battery.percent} percent left.")

load_dotenv()
news_api = os.getenv("NEWS_API_KEY")

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


