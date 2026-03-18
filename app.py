"""
==============================================================================
VibeCheck — Emotion-Based Music Streaming Player (Backend)
==============================================================================
Flask backend that:
  1. Detects facial emotions via DeepFace
  2. Fetches weather context via OpenWeatherMap
  3. Recommends songs using the 3D Context Formula (Emotion × Time × Weather)
  4. Searches YouTube for playback video IDs
  5. Supports 10 languages: English, Hindi, Tamil, Telugu, Kannada,
     Malayalam, Bengali, Punjabi, Marathi, Gujarati
==============================================================================
"""

import os
import re
import base64
import random
import traceback
from io import BytesIO
from datetime import datetime

import json
import cv2
import numpy as np
import requests as http_requests
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

# --- Recommendation History (to avoid repetition) ---
RECOMMENDATION_HISTORY = []
MAX_HISTORY = 50

LIKED_SONGS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "liked_songs.json")

def load_liked_songs():
    if os.path.exists(LIKED_SONGS_FILE):
        try:
            with open(LIKED_SONGS_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def save_liked_song(song, context):
    likes = load_liked_songs()
    # Key by lowercase song name to avoid duplicates
    key = song.lower().strip()
    likes[key] = {
        "song": song,
        "emotion": context.get("emotion", "neutral"),
        "weather": context.get("weather", "Clear"),
        "time_of_day": context.get("time_of_day", "day"),
        "language": context.get("language", "mix"),
        "timestamp": datetime.now().isoformat()
    }
    with open(LIKED_SONGS_FILE, "w", encoding="utf-8") as f:
        json.dump(likes, f, indent=4)
        
def remove_liked_song(song):
    likes = load_liked_songs()
    key = song.lower().strip()
    if key in likes:
        del likes[key]
        with open(LIKED_SONGS_FILE, "w", encoding="utf-8") as f:
            json.dump(likes, f, indent=4)


# ── Conditional DeepFace import (heavy) ──────────────────────────────────────
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False
    print("[WARN] DeepFace not installed — emotion detection will be simulated.")

# Load Haar Cascade from cv2 for faster face detection
face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

# ── Load environment variables ───────────────────────────────────────────────
load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
SPOTIPY_CLIENT_ID = os.getenv("SPOTIPY_CLIENT_ID", "")
SPOTIPY_CLIENT_SECRET = os.getenv("SPOTIPY_CLIENT_SECRET", "")

# --- Spotify Initialization ---
sp = None
if SPOTIPY_CLIENT_ID and SPOTIPY_CLIENT_SECRET:
    try:
        auth_manager = SpotifyClientCredentials(client_id=SPOTIPY_CLIENT_ID, client_secret=SPOTIPY_CLIENT_SECRET)
        sp = spotipy.Spotify(auth_manager=auth_manager)
    except Exception as e:
        print(f"[WARN] Spotify initialization failed: {e}")

# --- Western Blocklist (Regional Firewall) ---
# WESTERN_BLOCKLIST = [
#     "Justin Bieber", "Coldplay", "Taylor Swift", "Ed Sheeran", "Dua Lipa",
#     "Ariana Grande", "The Weeknd", "Post Malone", "Katy Perry", "Drake",
#     "Beyoncé", "Billie Eilish", "Shawn Mendes", "Maroon 5", "Imagine Dragons"
# ]


app = Flask(__name__)

# ==============================================================================
#  SAFE FALLBACK SONGS — per emotion × language (≥ 2 each)
# ==============================================================================

SAFE_SONGS = {
    "happy": {
        "english":   ["Happy - Pharrell Williams", "Can't Stop The Feeling - Justin Timberlake", "24K Magic - Bruno Mars"],
        "hindi":     ["Badtameez Dil - Benny Dayal", "Gallan Goodiyaan - Shankar Mahadevan", "Kala Chashma - Badshah"],
        "tamil":     ["Vaathi Coming - Anirudh Ravichander", "Enjoy Enjaami - Dhee", "Aaluma Doluma - Anirudh"],
        "telugu":    ["Butta Bomma - Armaan Malik", "Ramuloo Ramulaa - Anurag Kulkarni", "Saami Saami - Mounika Yadav"],
        "kannada":   ["Belageddu - Kishan", "Bombe Helutaithe - Shankar Mahadevan", "Karabuu - Dhruva Sarja"],
        "malayalam": ["Jimikki Kammal - Vineeth Sreenivasan", "Kudukku - Vineeth Sreenivasan", "Appangal Embadum - Vineeth"],
        "bengali":   ["Mon Majhi Re - Arijit Singh", "Bolte Bolte Cholte Cholte - Imran", "O My Love - Amanush"],
        "punjabi":   ["Proper Patola - Diljit Dosanjh", "Lahore - Guru Randhawa", "High Rated Gabru - Guru Randhawa"],
        "marathi":   ["Zingaat - Ajay Atul", "Apsara Aali - Bela Shende", "Wajle Ki Bara - Ajay Atul"],
        "gujarati":  ["Sajan Sajan - Sachin Jigar", "Ruda Ne Gamo - Sachin Jigar", "Love Ni Bhavai Title Track"],
    },
    "sad": {
        "english":   ["Someone Like You - Adele", "Someone You Loved - Lewis Capaldi", "Let Her Go - Passenger"],
        "hindi":     ["Tujhe Kitna Chahne Lage - Arijit Singh", "Channa Mereya - Arijit Singh", "Agar Tum Saath Ho - Arijit Singh"],
        "tamil":     ["Ennai Konjam Matri - Sid Sriram", "Kannazhaga - Dhanush", "Idhazhin Oram - Ajesh Ashok"],
        "telugu":    ["Nee Kannu Neeli Samudram - Sid Sriram", "Emai Poyave - Sid Sriram", "Undiporaadhey - Sid Sriram"],
        "kannada":   ["Mamaraviye - Sonu Nigam", "Onde Ondu Sari - Sonu Nigam", "Neene Bari Neene - Sonu Nigam"],
        "malayalam": ["Aaromale - Alphons Joseph", "Munbe Vaa - Shreya Ghoshal", "Kannum Kannum Kollaiyadithaal"],
        "bengali":   ["Bojhena Shey Bojhena - Arijit Singh", "Tumi Jakhan - Arijit Singh", "Ei Raat Tomar Amar"],
        "punjabi":   ["Tu Jaane Na - Atif Aslam", "Kallar - G Khan", "Heer - Javed Ali"],
        "marathi":   ["Tula Pahate Re - Atul Gogavale", "Dev Manus - Ajay Atul", "Meerajya Title Track"],
        "gujarati":  ["Radhey Krishna - Jignesh Kaviraj", "Tari Aankh No Afini - Jignesh Kaviraj", "Tu Heer Meri"],
    },
    "angry": {
        "english":   ["Believer - Imagine Dragons", "Numb - Linkin Park", "Monster - Skillet"],
        "hindi":     ["Kar Har Maidaan Fateh - सुखविंदर सिंह", "Sultan Title Track - सुखविंदर सिंह", "Dangal Title Track - दलेर मेहंदी"],
        "tamil":     ["Aalaporan Tamizhan - AR Rahman", "Verithanam - AR Rahman", "Mersal Arasan - AR Rahman"],
        "telugu":    ["Jai Lava Kusa Title Song - Bobby", "Saahore Bahubali - MM Keeravani", "RRR Naatu Naatu - Rahul Sipligunj"],
        "kannada":   ["Hebbuli Title Track - Supriya Lohith", "Tagaru Title Track", "Roberrt Mass Title Song"],
        "malayalam": ["Maari Mass Theme", "Lucifer Title Track", "Aavesham Theme"],
        "bengali":   ["Tor Premete - James", "Shono - Artcell", "Oniket Prantor - Artcell"],
        "punjabi":   ["Jatt Da Muqabla - Sidhu Moose Wala", "Legend - Sidhu Moose Wala", "So High - Sidhu Moose Wala"],
        "marathi":   ["Aala Re Aala Simmba - Adarsh Shinde", "Mi Hai Koli - Adarsh Shinde", "Zhakaas - Ajay Atul"],
        "gujarati":  ["Gujju Rocks - Jignesh Kaviraj", "Power Star - Jignesh Kaviraj", "Thakar Nu Gaam"],
    },
    "fear": {
        "english":   ["Mad World - Gary Jules", "Burn - Ellie Goulding", "Nightmare - Halsey"],
        "hindi":     ["Phir Bhi Tumko Chaahungi - आशा भोसले", "Ilahi - अरिजीत सिंह", "Ae Dil Hai Mushkil - अरिजीत सिंह"],
        "tamil":     ["Nee Partha Vizhigal - Shreya Ghoshal", "Thalli Pogathey - Sid Sriram", "Oru Naal Koothu"],
        "telugu":    ["Emo Emo - Sid Sriram", "Yemaindo Teliyadu Naaku", "Nuvvostanante Nenoddantana Song"],
        "kannada":   ["Neenirade - Rachita Ram", "Hrudayat Vaje Something", "Nooru Neenu"],
        "malayalam": ["Mizhiyil Ninnum - KJ Yesudas", "Hridayathin Niramayi", "Ormayundo Ee Mugham"],
        "bengali":   ["Ektarare Tuning - Anupam Roy", "Tomake Chai - Anupam Roy", "Amake Amar Moto Thakte Dao"],
        "punjabi":   ["Tera Ban Jaunga - अख़िल सचदेवा", "Kalli Kalli - जस्स मानक", "Filhall - बी प्राक"],
        "marathi":   ["Yad Lagla - अजय अतुल", "Ek Aslyane - अजय अतुल", "Deva Shree Ganesha"],
        "gujarati":  ["Dil No Dukh - जिग्नेश कविराज", "Jiv Thi Valayi - जिग्नेश कविराज", "Vaali - सचिन जिगर"],
    },
    "disgust": {
        "english":   ["Boulevard of Broken Dreams - Green Day", "Holiday - Green Day", "Teenagers - My Chemical Romance"],
        "hindi":     ["Apna Time Aayega - Ranveer Singh", "Swag Se Swagat - विशाल ददलानी", "Aunty Ji - यो यो हनी सिंह"],
        "tamil":     ["Surviva - Anirudh Ravichander", "Kutti Story - Anirudh Ravichander", "Vaadi Pulla Vaadi"],
        "telugu":    ["Mind Block - Blaaze", "Buttabomma Remix", "Vachaadayyo Saami"],
        "kannada":   ["Tagaru Banthu Tagaru", "KGF Salaam Rocky Bhai", "Avane Srimannarayana Theme"],
        "malayalam": ["Premam Theme - Rajesh Murugesan", "Ayyappanum Koshiyum Theme", "Jallikattu Theme"],
        "bengali":   ["Boshonto Eshe Gechhe", "Ekla Chalo Re - एमिताब", "Lungi Dance - Bengali"],
        "punjabi":   ["No Love - Shubh", "We Rollin - Shubh", "Elevated - Shubh"],
        "marathi":   ["Aika Dajiba - अजय अतुल", "Kombdi Palali - अजय अतुल", "Sairat Zaala Ji"],
        "gujarati":  ["Chhel Chhabili - गीता रबारी", "Rasiya Tari Radha", "Mogal Taro Aarti"],
    },
    "surprise": {
        "english":   ["Blinding Lights - The Weeknd", "Starboy - The Weeknd", "Flowers - Miley Cyrus"],
        "hindi":     ["Dil Se Re - AR Rahman (2000 Remake)", "Malhari - विशाल ददलानी", "Chaiyya Chaiyya - Remix"],
        "tamil":     ["Rowdy Baby - Dhanush", "Arabic Kuthu - Anirudh", "Jolly O Gymkhana - Anirudh"],
        "telugu":    ["Oo Antava - Indravathi Chauhan", "Ramulo Ramula - Anurag Kulkarni", "Seeti Maar - Devi Sri Prasad"],
        "kannada":   ["Yuvarathnaa Title Track", "Tagaru Title Track", "James Title Song"],
        "malayalam": ["Karimizhi Kuruvikal", "Lailakame - Ezra", "Kalakkatha - राहुल राज"],
        "bengali":   ["Subha Hone Na De - प्रीतम", "Tujhe Dekha Toh - Bengali", "Beshore - Anupam Roy"],
        "punjabi":   ["Obsessed - Riar Saab", "Brown Munde - AP Dhillon", "Excuses - AP Dhillon"],
        "marathi":   ["Bring It On - अजय अतुल", "Pinga - अजय अतुल", "Zingaat"],
        "gujarati":  ["Dholida - सचिन जिगर", "Shubh Aarambh - सचिन जिगर", "Nagada Sang Dhol Baje"],
    },
    "neutral": {
        "english":   ["Blinding Lights - The Weeknd", "Levitating - Dua Lipa", "Shape of You - Ed Sheeran"],
        "hindi":     ["Tum Hi Ho - अरिजीत सिंह", "Raabta Title Song - अरिजीत सिंह", "Khairiyat - अरिजीत सिंह"],
        "tamil":     ["Nenjame - Anirudh Ravichander", "Kanave Kanave - Anirudh", "Ilamai Thirumbi - Sid Sriram"],
        "telugu":    ["Samajavaragamana - Sid Sriram", "Inkem Inkem - Sid Sriram", "Choosi Chudangane - Sid Sriram"],
        "kannada":   ["Manasaare - शंकर महादेवन", "Baare Baare - अरमान मलिक", "Hrudayat Vaje Something"],
        "malayalam": ["Manikya Malaraya Poovi - विनीत", "Minungum - KS हरिशंकर", "Chundari Penne - KJ येसुदास"],
        "bengali":   ["Tumi Amar Prothom - अरिजीत सिंह", "Poran Jaye Joliya Re", "Aamar Mon Bhore - सोमलता"],
        "punjabi":   ["Excuses - AP Dhillon", "Lover - दिलजीत दोसांझ", "Softly - करण औजला"],
        "marathi":   ["Ved Lavlay - अवधूत गुप्ते", "Tula Pahate Re - अजय अतुल", "Mala Ved Lagale"],
        "gujarati":  ["Udne Sapne - सचिन जिगर", "Sanedo Sanedo - सचिन जिगर", "Valam Aavo Ne"],
    },
}

# ==============================================================================
#  EMOTION → BASE MOOD PARAMETERS (valence, energy, genres per language)
# ==============================================================================

EMOTION_PARAMS = {
    "happy":    {"valence": 0.85, "energy": 0.85},
    "sad":      {"valence": 0.20, "energy": 0.25},
    "angry":    {"valence": 0.30, "energy": 0.90},
    "fear":     {"valence": 0.25, "energy": 0.40},
    "disgust":  {"valence": 0.35, "energy": 0.55},
    "surprise": {"valence": 0.70, "energy": 0.80},
    "neutral":  {"valence": 0.55, "energy": 0.50},
}

# Genre seeds for Spotify — language-specific
# Note: Spotify has a strict list of seed genres.
LANGUAGE_GENRES = {
    "english":   {"high_energy": ["pop", "dance", "rock"],
                  "low_energy":  ["acoustic", "chill", "indie"],
                  "high_valence": ["pop", "happy"],
                  "low_valence":  ["blues", "sad"]},
    "hindi":     {"high_energy": ["bollywood", "indian", "dance"],
                  "low_energy":  ["bollywood", "indian", "acoustic"],
                  "high_valence": ["bollywood", "indian"],
                  "low_valence":  ["bollywood", "indian", "soul"]},
    "tamil":     {"high_energy": ["indian", "dance", "tamil"],
                  "low_energy":  ["indian", "acoustic", "tamil"],
                  "high_valence": ["indian", "tamil"],
                  "low_valence":  ["indian", "tamil"]},
    "telugu":    {"high_energy": ["indian", "dance", "telugu"],
                  "low_energy":  ["indian", "acoustic", "telugu"],
                  "high_valence": ["indian", "telugu"],
                  "low_valence":  ["indian", "telugu"]},
    "kannada":   {"high_energy": ["indian", "dance"],
                  "low_energy":  ["indian", "acoustic"],
                  "high_valence": ["indian"],
                  "low_valence":  ["indian"]},
    "malayalam": {"high_energy": ["indian", "dance"],
                  "low_energy":  ["indian", "acoustic"],
                  "high_valence": ["indian"],
                  "low_valence":  ["indian"]},
    "bengali":   {"high_energy": ["indian", "dance"],
                  "low_energy":  ["indian", "acoustic"],
                  "high_valence": ["indian"],
                  "low_valence":  ["indian"]},
    "punjabi":   {"high_energy": ["indian", "hip-hop", "dance"],
                  "low_energy":  ["indian", "acoustic"],
                  "high_valence": ["indian", "pop"],
                  "low_valence":  ["indian", "soul"]},
    "marathi":   {"high_energy": ["indian", "dance"],
                  "low_energy":  ["indian", "acoustic"],
                  "high_valence": ["indian"],
                  "low_valence":  ["indian"]},
    "gujarati":  {"high_energy": ["indian", "dance"],
                  "low_energy":  ["indian", "acoustic"],
                  "high_valence": ["indian"],
                  "low_valence":  ["indian"]},
}

# ==============================================================================
#  TIME-OF-DAY & WEATHER MODIFIERS
# ==============================================================================

def get_time_of_day():
    """Return time-of-day bucket and energy modifier."""
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning", 0.1
    elif 12 <= hour < 19:
        return "day", 0.0
    else:
        return "night", -0.1


def get_weather_modifier(weather_main: str):
    """Map OpenWeatherMap 'main' field to valence modifier."""
    weather_main = weather_main.lower() if weather_main else ""
    mapping = {
        "clear": 0.10,
        "clouds": 0.0,
        "rain": -0.10,
        "drizzle": -0.05,
        "thunderstorm": -0.10,
        "snow": -0.05,
        "mist": -0.03,
        "fog": -0.03,
        "haze": -0.03,
        "smoke": -0.05,
        "dust": -0.05,
        "party": 0.20, # Manual override for high energy/valence
    }
    return mapping.get(weather_main, 0.0)


def clamp(val, lo=0.0, hi=1.0):
    return max(lo, min(hi, val))

# ==============================================================================
#  SPOTIFY FETCHER
# ==============================================================================

def get_spotify_recommendations(em_params, language, genres, limit=20):
    """
    Fetch track recommendations from Spotify using 3D context.
    Maps emotional parameters to target audio features.
    """
    if not sp:
        return []

    # Map energy/valence to Spotify parameters
    # em_params has {"valence": ..., "energy": ...}
    target_valence = em_params["valence"]
    target_energy = em_params["energy"]
    
    # Advanced 3D Context mapping
    target_acousticness = 0.5
    if target_energy < 0.4: target_acousticness = 0.7  # Sad/Chill
    if target_energy > 0.7: target_acousticness = 0.1  # Happy/Angry/Dance
    
    # Determine search query for language if not English
    query = ""
    if language != "english":
        query = f"language:{language}" # or just name like "hindi"

    try:
        # Get available seed genres to filter our request
        # seeds = sp.recommendation_genre_seeds()['genres']
        # Validating genres against Spotify's set is safer but expensive
        
        recs = sp.recommendations(
            seed_genres=genres[:5], # Spotify limit is 5
            target_valence=target_valence,
            target_energy=target_energy,
            target_acousticness=target_acousticness,
            limit=limit,
            market="IN" if language != "english" else "US"
        )
        
        final_tracks = []
        for t in recs.get('tracks', []):
            artist = t['artists'][0]['name']
            track_name = t['name']
            album_art = t['album']['images'][0]['url'] if t['album']['images'] else ""
            
            # --- Regional Firewall: Filter out Western artists in regional mode ---
            if language != "english":
                is_blocked = False
                for b_artist in WESTERN_BLOCKLIST:
                    if b_artist.lower() in artist.lower():
                        is_blocked = True
                        break
                if is_blocked: continue

            final_tracks.append({
                "title": track_name,
                "artist": artist,
                "cover": album_art,
                "song_string": f"{track_name} - {artist}"
            })
            
        return final_tracks
    except Exception as e:
        print(f"[WARN] Spotify recommendation failed: {e}")
        return []

# ==============================================================================
#  RECOMMENDATION ENGINE
# ==============================================================================

def build_playlist(emotion: str, weather_main: str, language: str = "mix") -> list:
    """
    Build a 7-song playlist using the 3D Context Formula with Spotify recommendations.
    1. Start with safe fallback songs (mapped to objects).
    2. Fetch from Spotify using 3D context (mood × time × weather).
    3. Merge, deduplicate (by song string), and return exactly 7 objects.
    """
    emotion = emotion.lower()
    language = language.lower()
    if emotion not in EMOTION_PARAMS:
        emotion = "happy"

    # ── Get base parameters ──────────────────────────────────────────────
    base = EMOTION_PARAMS[emotion]
    valence = base["valence"]
    energy = base["energy"]

    # ── Apply time-of-day modifier ───────────────────────────────────────
    _, time_mod = get_time_of_day()
    energy = clamp(energy + time_mod)

    # ── Apply weather modifier ───────────────────────────────────────────
    weather_mod = get_weather_modifier(weather_main)
    valence = clamp(valence + weather_mod)

    # ── Determine languages to pull from ─────────────────────────────────
    if language == "mix":
        # Pick English + 2 random Indian languages
        indian_langs = [l for l in SAFE_SONGS[emotion].keys() if l != "english"]
        chosen_langs = ["english"] + random.sample(indian_langs, min(2, len(indian_langs)))
    else:
        chosen_langs = [language] if language in SAFE_SONGS.get(emotion, {}) else ["english"]

    # ── Gather liked songs first ─────────────────────────────────────────
    likes = load_liked_songs()
    liked_matching = []
    
    for key, data in likes.items():
        if data.get("emotion") == emotion:
            if language == "mix" or data.get("language") == language:
                # Convert to object format
                song_str = data["song"]
                parts = song_str.split(" - ")
                liked_matching.append({
                    "title": parts[0] if len(parts) > 0 else song_str,
                    "artist": parts[1] if len(parts) > 1 else "Unknown Artist",
                    "cover": "", # Will get from YT search thumbnail on play if needed
                    "song_string": song_str
                })
            
    random.shuffle(liked_matching)
    liked_matching = liked_matching[:3]
    
    # ── Gather safe fallback songs ───────────────────────────────────────
    safe = []
    for lang in chosen_langs:
        for s in SAFE_SONGS.get(emotion, {}).get(lang, []):
            parts = s.split(" - ")
            safe.append({
                "title": parts[0] if len(parts) > 0 else s,
                "artist": parts[1] if len(parts) > 1 else "Unknown Artist",
                "cover": "",
                "song_string": s
            })
    random.shuffle(safe)

    # ── Pick genre seeds for Spotify ─────────────────────────────────────
    genres = set()
    for lang in chosen_langs:
        lg = LANGUAGE_GENRES.get(lang, LANGUAGE_GENRES["english"])
        if energy >= 0.6:
            genres.update(lg["high_energy"][:2])
        else:
            genres.update(lg["low_energy"][:2])
        if valence >= 0.5:
            genres.update(lg["high_valence"][:1])
        else:
            genres.update(lg["low_valence"][:1])

    # ── Fetch from Spotify ───────────────────────────────────────────────
    api_songs = get_spotify_recommendations(
        {"valence": valence, "energy": energy},
        language,
        list(genres),
        limit=30
    )
    random.shuffle(api_songs)

    # ── Merge and deduplicate ─────────────────────────────────────────────
    seen = set()
    final = []
    
    global RECOMMENDATION_HISTORY
    
    def add_song(song_obj, prioritize_history=False):
        key = song_obj["song_string"].lower().strip()
        if key not in seen:
            if not prioritize_history and key in RECOMMENDATION_HISTORY:
                if len(final) >= 7: return

            seen.add(key)
            final.append(song_obj)
            
            if key not in RECOMMENDATION_HISTORY:
                RECOMMENDATION_HISTORY.append(key)
                if len(RECOMMENDATION_HISTORY) > MAX_HISTORY:
                    RECOMMENDATION_HISTORY.pop(0)

    # 1. Liked songs
    for s in liked_matching: add_song(s, prioritize_history=True)
    
    # 2. Spotify API Songs
    for s in api_songs: 
        if len(final) >= 7: break
        add_song(s)
        
    # 3. Safe fallback
    for s in safe: 
        if len(final) >= 7: break
        add_song(s)

    # Pad if < 7
    if len(final) < 7:
        for s in safe:
            add_song(s, prioritize_history=True)
            if len(final) >= 7: break

    return final[:7]

# ==============================================================================
#  FLASK ROUTES
# ==============================================================================

@app.route("/")
def index():
    """Serve the main player UI."""
    return render_template("index.html")





def detect_emotion_deepface(img):
    """
    Emotion detection strategy mimicking the custom 'emotion_detector.py':
    1. Grayscale the image and use Haar Cascade to find the face bounds.
    2. Crop the image to the face bounds.
    3. Run DeepFace analysis on the cropped face with enforce_detection=False.
    If no face is explicitly found by the cascade, fallback to passing the full 
    image to DeepFace with enforce_detection=False.
    Returns (dominant_emotion, scores_dict, confidence_flag)
    """
    try:
        # Step 1: Detect Face via Haar Cascades
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        faces = face_cascade.detectMultiScale(gray, 1.1, 4)
        
        target_img = img # Default to full image if no cascade face is found
        is_low_confidence = True

        if len(faces) > 0:
            # Step 2: Crop to largest face found
            (x, y, w, h) = faces[0]  # Take the first prominent face
            target_img = img[y:y+h, x:x+w]
            is_low_confidence = False # Haar found a face, higher confidence
            print(f"[EmotionDetect] Face found via Haar Cascade at x:{x} y:{y} w:{w} h:{h}")

        # Step 3: DeepFace Pass on cropped/full image
        result = DeepFace.analyze(
            target_img, 
            actions=['emotion'], 
            enforce_detection=False, 
            silent=True
        )

        if isinstance(result, list):
            result = result[0]

        dominant = result.get("dominant_emotion", "neutral")
        raw_scores = result.get("emotion", {})
        
        # Convert numpy float32 to standard float for JSON serialization
        scores = {k: float(v) for k, v in raw_scores.items()}

        print(f"[EmotionDetect] Dominant: {dominant}, Scores: {scores}")
        return dominant, scores, is_low_confidence

    except Exception as e:
        print(f"[EmotionDetect] Failed: {e}")
        return "neutral", {"neutral": 100.0}, True


@app.route("/api/detect-emotion", methods=["POST"])
def detect_emotion():
    """
    Accept a base64-encoded image, run DeepFace emotion detection.
    Returns: { "emotion": "happy", "scores": {...}, "low_confidence": false }
    """
    try:
        data = request.get_json(force=True)
        image_b64 = data.get("image", "")
        if not image_b64:
            return jsonify({"error": "No image provided"}), 400

        # Strip data URI prefix if present
        if "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]

        # Decode base64 to numpy array
        img_bytes = base64.b64decode(image_b64)
        np_arr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)

        if img is None:
            return jsonify({"error": "Could not decode image"}), 400

        if not DEEPFACE_AVAILABLE:
            # Simulate emotion for environments without DeepFace
            emotions = ["happy", "sad", "angry", "fear", "disgust", "surprise", "neutral"]
            sim_emotion = random.choice(emotions)
            return jsonify({"emotion": sim_emotion, "scores": {sim_emotion: 95.0}, "low_confidence": False})


        # Run two-pass DeepFace analysis
        dominant, scores, low_confidence = detect_emotion_deepface(img)

        return jsonify({
            "emotion": dominant,
            "scores": scores,
            "low_confidence": low_confidence,
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/weather", methods=["GET"])
def weather():
    """
    Fetch weather for given lat/lon from OpenWeatherMap.
    Returns: { "main": "Clear", "description": "clear sky", "temp": 28.5, "city": "Mumbai" }
    """
    lat = request.args.get("lat", "")
    lon = request.args.get("lon", "")

    if not lat or not lon:
        try:
            # Fallback to IP geolocation if client location is missing
            ip_resp = http_requests.get("http://ip-api.com/json/", timeout=5)
            ip_data = ip_resp.json()
            if ip_data.get("status") == "success":
                lat = ip_data.get("lat")
                lon = ip_data.get("lon")
        except Exception as e:
            print(f"[WARN] IP-based location failed: {e}")

    if not lat or not lon:
        return jsonify({"main": "Clear", "description": "unknown", "temp": 25.0, "city": "Unknown"})

    if not OPENWEATHER_API_KEY or OPENWEATHER_API_KEY.startswith("your_"):
        return jsonify({"main": "Clear", "description": "API key not set", "temp": 25.0, "city": "Unknown"})

    try:
        resp = http_requests.get("https://api.openweathermap.org/data/2.5/weather", params={
            "lat": lat,
            "lon": lon,
            "appid": OPENWEATHER_API_KEY,
            "units": "metric",
        }, timeout=5)
        data = resp.json()
        w = data.get("weather", [{}])[0]
        return jsonify({
            "main": w.get("main", "Clear"),
            "description": w.get("description", ""),
            "temp": data.get("main", {}).get("temp", 25),
            "city": data.get("name", "Unknown"),
        })
    except Exception as e:
        print(f"[WARN] Weather API failed: {e}")
        return jsonify({"main": "Clear", "description": "fallback", "temp": 25.0, "city": "Unknown"})


@app.route("/api/recommend", methods=["POST"])
def recommend():
    """
    Build a 7-song playlist from the 3D Context Formula.
    Expects JSON: { "emotion": "happy", "weather": "Clear", "language": "hindi" }
    Returns: { "playlist": [...], "context": {...} }
    """
    try:
        data = request.get_json(force=True)
        emotion = data.get("emotion", "neutral")
        weather_main = data.get("weather", "Clear")
        language = data.get("language", "mix")

        time_label, _ = get_time_of_day()
        playlist = build_playlist(emotion, weather_main, language)

        return jsonify({
            "playlist": playlist,
            "context": {
                "emotion": emotion,
                "weather": weather_main,
                "time_of_day": time_label,
                "language": language,
            }
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/like", methods=["POST"])
def like_song():
    try:
        data = request.get_json(force=True)
        song = data.get("song")
        context = data.get("context", {})
        if not song:
            return jsonify({"error": "No song provided"}), 400
        
        save_liked_song(song, context)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/like", methods=["DELETE"])
def unlike_song():
    try:
        data = request.get_json(force=True)
        song = data.get("song")
        if not song:
            return jsonify({"error": "No song provided"}), 400
        
        remove_liked_song(song)
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/likes", methods=["GET"])
def get_likes():
    try:
        likes = load_liked_songs()
        return jsonify({"likes": list(likes.keys())})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/youtube-search", methods=["GET"])
def youtube_search():
    """
    Search YouTube Music for a track matching the query string.
    Uses ytmusicapi to guarantee fetching exact original songs.
    """
    q = request.args.get("q", "")
    if not q:
        return jsonify({"error": "No query provided"}), 400

    try:
        try:
            from ytmusicapi import YTMusic
        except ImportError:
            return jsonify({"error": "ytmusicapi library not installed"}), 500
            
        ytmusic = YTMusic()
        # We explicitly search for 'songs' to only get official audio
        results = ytmusic.search(query=q, filter="songs", limit=5)
        
        if not results:
             return jsonify({"error": "No suitable song videos found"}), 404

        top_ids = []
        for r in results:
            vid = r.get("videoId")
            if vid and vid not in top_ids:
                top_ids.append(vid)

        if not top_ids:
            return jsonify({"error": "No suitable song videos found"}), 404

        first_res = results[0]
        title = first_res.get("title", "Unknown Track")

        return jsonify({
            "videoId": top_ids[0],
            "videoIds": top_ids,
            "title": title,
            "thumbnail": f"https://i.ytimg.com/vi/{top_ids[0]}/hqdefault.jpg",
            "duration": first_res.get("duration", "")
        })

    except Exception as e:
        print(f"[WARN] YouTube Music search failed: {e}")
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


# ==============================================================================
#  MAIN
# ==============================================================================
    
if __name__ == "__main__":
    print("=" * 60)
    print("  VibeCheck — Emotion-Based Music Player")
    print("  Starting on http://localhost:5000")
    print("=" * 60)
    app.run(debug=False, host="0.0.0.0", port=5000)
