import datetime
import webbrowser as wb
import wikipedia
from support_functions import speak, get_news
import Music_library as music
import Webpage_library as page



def process_command(c):
    # give time 
    if "time" in c.lower():
        speak("Itss " + str(datetime.datetime.now().strftime("%I:%M %p")))
    
    # open a link
    elif c.startswith("open"):
        page_to_open = c[5:]
        try:
            p = page.page[page_to_open.lower()]
            speak("opening" + page_to_open)
            wb.open(p)
        except Exception as e:
            speak("Sorry! Can't open this page")

    # Google search
    elif c.lower() in ["google", "search", "find", "look"]:
        query = c[6:].strip()
        if query:
            speak(f"Searching for {query}")
            wb.open(f"https://www.google.com/search?q={query.replace(' ', '+')}")
        else:
            speak("Please say something to search for.")

    # Wikipedia summary
    elif c.startswith("who is") or c.startswith("what is") or c.startswith("tell me about"):
        try:
            query = c.replace("who is", "").replace("what is", "").replace("tell me about", "").strip()
            summary = wikipedia.summary(query, sentences=2)
            speak(summary)
        except:
            speak("Sorry, I couldn't find anything on Wikipedia.")
            
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
    

    return