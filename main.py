import speech_recognition as sr
from support_functions import speak, check_battery
from processor import process_command


recogniser = sr.Recognizer()
speak("Hey There. I'm Sophia. How can I assist you today?")

while True:
    try:
        with sr.Microphone() as source:
            print("Listening...")
            audio = recogniser.listen(source)
        command = recogniser.recognize_google(audio).lower()
        print("Processing:", command)
        if command.lower() == "sofia" or command.lower() == "sophia":
            speak("Yes")
        if command in ["exit", "quit", "stop"]:
            speak("Have a good day!")
            break

        process_command(command)
        check_battery()

    except sr.UnknownValueError:
        print("Could not understand audio.")
    except sr.RequestError as e:
        print("Recognition error:", e)
