import speech_recognition as sr
import pyttsx3
import threading

recognizer = sr.Recognizer()
engine = pyttsx3.init()

# Set voice properties
engine.setProperty('rate', 175)
engine.setProperty('volume', 1.0)

def speak(text: str):
    def _speak():
        engine.say(text)
        engine.runAndWait()
    thread = threading.Thread(target=_speak)
    thread.start()

def listen() -> str:
    with sr.Microphone() as source:
        recognizer.adjust_for_ambient_noise(source, duration=0.5)
        try:
            audio = recognizer.listen(source, timeout=5, phrase_time_limit=10)
            text = recognizer.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            return ""
        except sr.UnknownValueError:
            return ""
        except Exception as e:
            return ""