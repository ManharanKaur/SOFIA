import speech_recognition as sr
import webbrowser as wb
import pyttsx3
import Music_library as music
import Webpage_library as page
import requests
from dotenv import load_dotenv
import os

load_dotenv()
news_api = os.getenv("NEWS_API_KEY")



# create a recogniser object
recogniser = sr.Recognizer()
tts = pyttsx3.init() # text to speech we initialized the library

def speak(text): # function to speak the provided text
    tts.say(text)
    tts.runAndWait()

def get_news():
    url = f"http://api.mediastack.com/v1/news?access_key={news_api}&countries=in&languages=pb&limit=5"

    response = requests.get(url)
    data = response.json()

    if "data" in data and len(data["data"]) > 0:
        for i, article in enumerate(data["data"], 1):
            title = article.get("title", "No title available")
            print(f"{i}. {title}")
            speak(f"Headline {i}: {title}")
    else:
        print("Failed to fetch news.")
        speak("Sorry, I couldn't find any news articles.")



def process_command(c):
    # open a link
    if c.startswith("open"):
        page_to_open = c[5:]
        try:
            p = page.page[page_to_open.lower()]
            speak("opening" + page_to_open)
            wb.open(p)
        except Exception as e:
            return
    # play a song
    elif c.startswith("play"):
        song = c[5:]
        try:
            link = music.music[song]
            wb.open(link)
        except Exception as e:
            return
    # give news
    elif "news" in c.lower():
        get_news()
    

    

# obtain audio from the microphone
speak("Hello, I'm Sofia. How can I assist you today?")
while True:
    try:
        with sr.Microphone() as source:
            print ("Sofia's here...")
            audio = recogniser.listen(source)
        command = recogniser.recognize_google(audio)
        if command == "Sofia" or command == "Sophia":
            speak("Yes")
            with sr.Microphone() as source:
                print ("Listening...")
                audio = recogniser.listen(source)
            command = recogniser.recognize_google(audio)
            print("Processing...")
            process_command(command)
        elif command == "exit":
            speak("Have a Good Day!")
            break
    except sr.UnknownValueError:
        text = "Sofia could not understand audio"
        print(text)
    except sr. RequestError as e:
        print ("Sofia error; {0}". format (e))