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
from flask import Flask, render_template, request, jsonify
from dotenv import load_dotenv

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

# ── Load environment variables ───────────────────────────────────────────────
load_dotenv()
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY", "")


app = Flask(__name__)

# ==============================================================================
#  SAFE FALLBACK SONGS — per emotion × language (≥ 2 each)
# ==============================================================================

SAFE_SONGS = {
    "happy": {
        "english":   ["Happy - Pharrell Williams", "Walking on Sunshine - Katrina and the Waves", "Uptown Funk - Bruno Mars"],
        "hindi":     ["Badtameez Dil - Benny Dayal", "Gallan Goodiyaan - Shankar Mahadevan", "London Thumakda - Labh Janjua"],
        "tamil":     ["Vaathi Coming - Anirudh Ravichander", "Why This Kolaveri Di - Dhanush", "Aaluma Doluma - Anirudh"],
        "telugu":    ["Butta Bomma - Armaan Malik", "Ramuloo Ramulaa - Anurag Kulkarni", "Saami Saami - Mounika Yadav"],
        "kannada":   ["Belageddu - Kishan", "Bombe Helutaithe - Shankar Mahadevan", "Rangitaranga Title Track"],
        "malayalam": ["Jimikki Kammal - Vineeth Sreenivasan", "Entammede Jimikki Kammal", "Appangal Embadum - Vineeth"],
        "bengali":   ["Ami Je Tomar - Arijit Singh", "Bolte Bolte Cholte Cholte - Imran", "Mon Majhi Re - Arijit Singh"],
        "punjabi":   ["Amplifier - Imran Khan", "Proper Patola - Diljit Dosanjh", "Lahore - Guru Randhawa"],
        "marathi":   ["Zingaat - Ajay Atul", "Apsara Aali - Bela Shende", "Wajle Ki Bara - Ajay Atul"],
        "gujarati":  ["Sajan Sajan - Sachin Jigar", "Ruda Ne Gamo - Sachin Jigar", "Love Ni Bhavai Title Track"],
    },
    "sad": {
        "english":   ["Someone Like You - Adele", "Fix You - Coldplay", "Let Her Go - Passenger"],
        "hindi":     ["Tujhe Kitna Chahne Lage - Arijit Singh", "Channa Mereya - Arijit Singh", "Agar Tum Saath Ho - Arijit Singh"],
        "tamil":     ["Ennai Konjam Matri - Sid Sriram", "Kannazhaga - Dhanush", "Idhazhin Oram - Ajesh Ashok"],
        "telugu":    ["Nee Kannu Neeli Samudram - Sid Sriram", "Ye Maaya Chesave Title Song", "Emai Poyave - Sid Sriram"],
        "kannada":   ["Baarisu Kannada Dindimava", "Mamaraviye - Sonu Nigam", "Onde Ondu Sari - Sonu Nigam"],
        "malayalam": ["Aaromale - Alphons Joseph", "Munbe Vaa - Shreya Ghoshal", "Kannum Kannum Kollaiyadithaal"],
        "bengali":   ["Bojhena Shey Bojhena - Arijit Singh", "Tumi Jakhan - Arijit Singh", "Ei Raat Tomar Amar"],
        "punjabi":   ["Tu Jaane Na - Atif Aslam", "Kiven Mukhre - Nusrat Fateh Ali Khan", "Heer - Javed Ali"],
        "marathi":   ["Tula Pahate Re - Atul Gogavale", "Dev Manus - Ajay Atul", "Meerajya Title Track"],
        "gujarati":  ["Radhey Krishna - Jignesh Kaviraj", "Tari Aankh No Afini - Jignesh Kaviraj", "Tu Heer Meri"],
    },
    "angry": {
        "english":   ["In the End - Linkin Park", "Killing in the Name - Rage Against the Machine", "Numb - Linkin Park"],
        "hindi":     ["Kar Har Maidaan Fateh - Sukhwinder Singh", "Sultan Title Track - Sukhwinder Singh", "Dangal Title Track - Daler Mehndi"],
        "tamil":     ["Aalaporan Tamizhan - AR Rahman", "Verithanam - AR Rahman", "Mersal Arasan - AR Rahman"],
        "telugu":    ["Jai Lava Kusa Title Song - Bobby", "Saahore Bahubali - MM Keeravani", "RRR Naatu Naatu - Rahul Sipligunj"],
        "kannada":   ["Hebbuli Title Track - Supriya Lohith", "Tagaru Title Track", "Roberrt Mass Title Song"],
        "malayalam": ["Pulimurugan Title Song", "Maari Mass Theme", "Lucifer Title Track"],
        "bengali":   ["Pagla Hawar Tore - James", "Tor Premete - James", "Shono - Artcell"],
        "punjabi":   ["Jatt Da Muqabla - Sidhu Moose Wala", "Legend - Sidhu Moose Wala", "So High - Sidhu Moose Wala"],
        "marathi":   ["Aala Re Aala Simmba - Adarsh Shinde", "Mi Hai Koli - Adarsh Shinde", "Zhakaas - Ajay Atul"],
        "gujarati":  ["Gujju Rocks - Jignesh Kaviraj", "Power Star - Jignesh Kaviraj", "Thakar Nu Gaam"],
    },
    "fear": {
        "english":   ["Creep - Radiohead", "Everybody Hurts - R.E.M.", "Mad World - Gary Jules"],
        "hindi":     ["Phir Bhi Tumko Chaahungi - Asha Bhosle", "Ilahi - Arijit Singh", "Ae Dil Hai Mushkil - Arijit Singh"],
        "tamil":     ["Nee Partha Vizhigal - Shreya Ghoshal", "Thalli Pogathey - Sid Sriram", "Oru Naal Koothu"],
        "telugu":    ["Emo Emo - Sid Sriram", "Yemaindo Teliyadu Naaku", "Nuvvostanante Nenoddantana Song"],
        "kannada":   ["Preethse Antha - Shankar Nag", "Devru Kotta Thangi", "Neenirade - Rachita Ram"],
        "malayalam": ["Mizhiyil Ninnum - KJ Yesudas", "Hridayathin Niramayi", "Ormayundo Ee Mugham"],
        "bengali":   ["Tumi Robe Nirobe - Rabindranath", "Ektarare Tuning - Anupam Roy", "Tomake Chai - Anupam Roy"],
        "punjabi":   ["Tera Ban Jaunga - Akhil Sachdeva", "Kalli Kalli - Jass Manak", "Filhall - B Praak"],
        "marathi":   ["Yad Lagla - Ajay Atul", "Ek Aslyane - Ajay Atul", "Deva Shree Ganesha"],
        "gujarati":  ["Dil No Dukh - Jignesh Kaviraj", "Jiv Thi Valayi - Jignesh Kaviraj", "Vaali - Sachin Jigar"],
    },
    "disgust": {
        "english":   ["Smells Like Teen Spirit - Nirvana", "Basket Case - Green Day", "Boulevard of Broken Dreams - Green Day"],
        "hindi":     ["Apna Time Aayega - Ranveer Singh", "Swag Se Swagat - Vishal Dadlani", "Aunty Ji - Yo Yo Honey Singh"],
        "tamil":     ["Surviva - Anirudh Ravichander", "Kutti Story - Anirudh Ravichander", "Vaadi Pulla Vaadi"],
        "telugu":    ["Mind Block - Blaaze", "Buttabomma Remix", "Vachaadayyo Saami"],
        "kannada":   ["Tagaru Banthu Tagaru", "KGF Salaam Rocky Bhai", "Avane Srimannarayana Theme"],
        "malayalam": ["Premam Theme - Rajesh Murugesan", "Ayyappanum Koshiyum Theme", "Jallikattu Theme"],
        "bengali":   ["Lift Karade - Pritam", "Ekla Chalo Re - Amitabh", "Boshonto Eshe Gechhe"],
        "punjabi":   ["No Love - Shubh", "We Rollin - Shubh", "Elevated - Shubh"],
        "marathi":   ["Aika Dajiba - Ajay Atul", "Kombdi Palali - Ajay Atul", "Sairat Zaala Ji"],
        "gujarati":  ["Chhel Chhabili - Geeta Rabari", "Rasiya Tari Radha", "Mogal Taro Aarti"],
    },
    "surprise": {
        "english":   ["Don't Stop Me Now - Queen", "Mr. Brightside - The Killers", "Bohemian Rhapsody - Queen"],
        "hindi":     ["Chaiyya Chaiyya - Sukhwinder Singh", "Malhari - Vishal Dadlani", "Dil Se Re - AR Rahman"],
        "tamil":     ["Rowdy Baby - Dhanush", "Arabic Kuthu - Anirudh", "Jolly O Gymkhana - Anirudh"],
        "telugu":    ["Oo Antava - Indravathi Chauhan", "Ramulo Ramula - Anurag Kulkarni", "Seeti Maar - Devi Sri Prasad"],
        "kannada":   ["Navagraha - Kichcha Sudeep", "KGF Mother Theme", "Yuvarathnaa Title Track"],
        "malayalam": ["Kalakkatha - Rahul Raj", "Lailakame - Ezra", "Karimizhi Kuruvikal"],
        "bengali":   ["Subha Hone Na De - Pritam", "Balam Pichkari Bengali Version", "Tujhe Dekha Toh"],
        "punjabi":   ["Obsessed - Riar Saab", "Brown Munde - AP Dhillon", "Excuses - AP Dhillon"],
        "marathi":   ["Bring It On - Ajay Atul", "Pinga - Ajay Atul", "Malhari Marathi Version"],
        "gujarati":  ["Dholida - Sachin Jigar", "Shubh Aarambh - Sachin Jigar", "Nagada Sang Dhol Baje"],
    },
    "neutral": {
        "english":   ["Blinding Lights - The Weeknd", "Levitating - Dua Lipa", "Shape of You - Ed Sheeran"],
        "hindi":     ["Tum Hi Ho - Arijit Singh", "Raabta Title Song - Arijit Singh", "Khairiyat - Arijit Singh"],
        "tamil":     ["Nenjame - Anirudh Ravichander", "Kanave Kanave - Anirudh", "Ilamai Thirumbi - Sid Sriram"],
        "telugu":    ["Samajavaragamana - Sid Sriram", "Inkem Inkem - Sid Sriram", "Choosi Chudangane - Sid Sriram"],
        "kannada":   ["Hrudayat Vaje Something - Sonu Nigam", "Manasaare - Shankar Mahadevan", "Baare Baare - Armaan Malik"],
        "malayalam": ["Manikya Malaraya Poovi - Vineeth", "Minungum - KS Harisankar", "Chundari Penne - KJ Yesudas"],
        "bengali":   ["Tumi Amar Prothom - Arijit Singh", "Poran Jaye Joliya Re", "Aamar Mon Bhore - Somlata"],
        "punjabi":   ["Excuses - AP Dhillon", "Lover - Diljit Dosanjh", "Softly - Karan Aujla"],
        "marathi":   ["Ved Lavlay - Avadhoot Gupte", "Tula Pahate Re - Ajay Atul", "Mala Ved Lagale"],
        "gujarati":  ["Udne Sapne - Sachin Jigar", "Khelaiya Nonstop Garba", "Sanedo Sanedo - Sachin Jigar"],
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

# Genre tags for Last.fm — language-specific
LANGUAGE_GENRES = {
    "english":   {"high_energy": ["pop", "dance", "electronic", "edm"],
                  "low_energy":  ["acoustic", "lo-fi", "indie", "chill"],
                  "high_valence": ["pop", "funk", "soul"],
                  "low_valence":  ["blues", "sad", "melancholy"]},
    "hindi":     {"high_energy": ["bollywood", "bollywood dance", "indian pop", "hindi remix"],
                  "low_energy":  ["bollywood sad", "ghazal", "sufi", "bollywood unplugged"],
                  "high_valence": ["bollywood", "indian pop", "filmi"],
                  "low_valence":  ["ghazal", "bollywood sad", "sufi"]},
    "tamil":     {"high_energy": ["kollywood", "tamil", "tamil pop", "kuthu"],
                  "low_energy":  ["tamil melody", "carnatic", "tamil unplugged"],
                  "high_valence": ["kollywood", "tamil pop"],
                  "low_valence":  ["tamil melody", "carnatic"]},
    "telugu":    {"high_energy": ["tollywood", "telugu", "telugu pop", "telugu mass"],
                  "low_energy":  ["telugu melody", "telugu unplugged"],
                  "high_valence": ["tollywood", "telugu pop"],
                  "low_valence":  ["telugu melody", "telugu sad"]},
    "kannada":   {"high_energy": ["kannada", "sandalwood", "kannada pop"],
                  "low_energy":  ["kannada melody", "kannada unplugged"],
                  "high_valence": ["kannada", "sandalwood"],
                  "low_valence":  ["kannada melody"]},
    "malayalam": {"high_energy": ["malayalam", "mollywood", "malayalam pop"],
                  "low_energy":  ["malayalam melody", "malayalam unplugged"],
                  "high_valence": ["mollywood", "malayalam pop"],
                  "low_valence":  ["malayalam melody"]},
    "bengali":   {"high_energy": ["bengali", "tollywood bengali", "bangla pop"],
                  "low_energy":  ["rabindra sangeet", "bengali melody", "baul"],
                  "high_valence": ["bengali pop", "bangla rock"],
                  "low_valence":  ["rabindra sangeet", "bengali sad"]},
    "punjabi":   {"high_energy": ["punjabi", "bhangra", "punjabi pop", "punjabi hip hop"],
                  "low_energy":  ["punjabi sad", "punjabi melody", "sufi punjabi"],
                  "high_valence": ["bhangra", "punjabi pop"],
                  "low_valence":  ["punjabi sad", "sufi punjabi"]},
    "marathi":   {"high_energy": ["marathi", "marathi pop", "lavani"],
                  "low_energy":  ["marathi melody", "marathi natya sangeet", "marathi unplugged"],
                  "high_valence": ["marathi pop", "lavani"],
                  "low_valence":  ["marathi natya sangeet", "marathi sad"]},
    "gujarati":  {"high_energy": ["gujarati", "garba", "gujarati pop", "dandiya"],
                  "low_energy":  ["gujarati melody", "gujarati unplugged"],
                  "high_valence": ["garba", "dandiya", "gujarati pop"],
                  "low_valence":  ["gujarati melody"]},
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
    }
    return mapping.get(weather_main, 0.0)


def clamp(val, lo=0.0, hi=1.0):
    return max(lo, min(hi, val))

# ==============================================================================
#  LAST.FM FETCHER
# ==============================================================================

def fetch_lastfm_tracks(tags: list, limit: int = 10) -> list:
    """
    Fetch top tracks from Last.fm for given genre tags.
    Returns list of "Song - Artist" strings.
    """
    if not LASTFM_API_KEY or LASTFM_API_KEY.startswith("your_"):
        return []

    tracks = []
    for tag in tags:
        try:
            resp = http_requests.get("http://ws.audioscrobbler.com/2.0/", params={
                "method": "tag.getTopTracks",
                "tag": tag,
                "api_key": LASTFM_API_KEY,
                "format": "json",
                "limit": limit,
            }, timeout=5)
            data = resp.json()
            for t in data.get("tracks", {}).get("track", []):
                name = t.get("name", "")
                artist = t.get("artist", {}).get("name", "")
                if name and artist:
                    tracks.append(f"{name} - {artist}")
        except Exception as e:
            print(f"[WARN] Last.fm fetch failed for tag '{tag}': {e}")
    return tracks

# ==============================================================================
#  RECOMMENDATION ENGINE
# ==============================================================================

def build_playlist(emotion: str, weather_main: str, language: str = "mix") -> list:
    """
    Build a 7-song playlist using the 3D Context Formula.
    1. Start with safe fallback songs for the emotion + language.
    2. Fetch from Last.fm using mood-mapped genre tags.
    3. Merge, deduplicate, and return exactly 7.
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
            liked_matching.append(data["song"])
            
    # Shuffle and pick up to 3 liked songs
    random.shuffle(liked_matching)
    liked_matching = liked_matching[:3]
    
    # ── Gather safe songs ────────────────────────────────────────────────
    safe = []
    for lang in chosen_langs:
        safe.extend(SAFE_SONGS.get(emotion, {}).get(lang, []))
    random.shuffle(safe)

    # ── Pick genre tags for Last.fm ──────────────────────────────────────
    tags = set()
    for lang in chosen_langs:
        lg = LANGUAGE_GENRES.get(lang, LANGUAGE_GENRES["english"])
        if energy >= 0.6:
            tags.update(lg["high_energy"][:2])
        else:
            tags.update(lg["low_energy"][:2])
        if valence >= 0.5:
            tags.update(lg["high_valence"][:1])
        else:
            tags.update(lg["low_valence"][:1])

    # ── Fetch from Last.fm ───────────────────────────────────────────────
    api_songs = fetch_lastfm_tracks(list(tags), limit=5)
    random.shuffle(api_songs)

    # ── Merge: liked first, safe next, API last, deduplicate, cap at 7 ──
    seen = set()
    final = []
    
    # helper to add song
    def add_song(s):
        key = s.lower().strip()
        if key not in seen:
            seen.add(key)
            final.append(s)

    for s in liked_matching: add_song(s)
    for s in safe: add_song(s)
    for s in api_songs: add_song(s)

    # If still < 7, pad with more safe songs from any language
    if len(final) < 7:
        for em_songs in SAFE_SONGS.get(emotion, {}).values():
            for s in em_songs:
                add_song(s)
                if len(final) >= 7:
                    break
            if len(final) >= 7:
                break

    return final[:7]

# ==============================================================================
#  FLASK ROUTES
# ==============================================================================

@app.route("/")
def index():
    """Serve the main player UI."""
    return render_template("index.html")


def preprocess_image(img):
    """
    Preprocess the image for better face/emotion detection:
    1. Ensure minimum size (scale up small images)
    2. Apply CLAHE (Contrast Limited Adaptive Histogram Equalization)
       for better performance in low-light / uneven lighting
    """
    h, w = img.shape[:2]

    # Scale up if image is too small — DeepFace works best at ≥ 480px height
    if h < 480:
        scale = 480 / h
        img = cv2.resize(img, (int(w * scale), 480), interpolation=cv2.INTER_CUBIC)

    # Convert to LAB colour space and apply CLAHE on the L (lightness) channel
    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l_channel, a_channel, b_channel = cv2.split(lab)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    l_channel = clahe.apply(l_channel)
    lab = cv2.merge([l_channel, a_channel, b_channel])
    img = cv2.cvtColor(lab, cv2.COLOR_LAB2BGR)

    return img


def detect_emotion_deepface(img):
    """
    Two-pass emotion detection strategy:
      Pass 1 — Use 'retinaface' backend with enforce_detection=True (most accurate)
      Pass 2 — Fallback to 'opencv' backend with enforce_detection=True
      Pass 3 — Last resort: 'opencv' with enforce_detection=False (may return neutral)
    Returns (dominant_emotion, scores_dict, confidence_flag)
    """
    backends_to_try = [
        {"detector_backend": "retinaface", "enforce_detection": True},
        {"detector_backend": "opencv",     "enforce_detection": True},
        {"detector_backend": "opencv",     "enforce_detection": False},
    ]

    for i, cfg in enumerate(backends_to_try):
        try:
            result = DeepFace.analyze(
                img,
                actions=["emotion"],
                enforce_detection=cfg["enforce_detection"],
                detector_backend=cfg["detector_backend"],
            )
            if isinstance(result, list):
                result = result[0]

            dominant = result.get("dominant_emotion", "neutral")
            scores = result.get("emotion", {})

            is_low_confidence = (not cfg["enforce_detection"])  # Pass 3 = low confidence

            print(f"[EmotionDetect] Pass {i+1} ({cfg['detector_backend']}, "
                  f"enforce={cfg['enforce_detection']}): "
                  f"dominant={dominant}, scores={scores}")

            return dominant, scores, is_low_confidence

        except Exception as e:
            print(f"[EmotionDetect] Pass {i+1} ({cfg['detector_backend']}) failed: {e}")
            continue

    # All passes failed — return neutral with low confidence
    print("[EmotionDetect] All passes failed, returning neutral (low confidence)")
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

        # Preprocess image for better detection
        img = preprocess_image(img)
        print(f"[EmotionDetect] Preprocessed image size: {img.shape}")

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
    Search YouTube for a video ID matching the query string.
    Uses direct HTTP request to YouTube search (no library dependency).
    Returns: { "videoId": "dQw4w9WgXcQ", "title": "..." }
    """
    q = request.args.get("q", "")
    if not q:
        return jsonify({"error": "No query provided"}), 400

    try:
        # Search YouTube via the HTML search page
        search_url = "https://www.youtube.com/results"
        params = {"search_query": q + " official audio"}
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        resp = http_requests.get(search_url, params=params, headers=headers, timeout=8)
        html = resp.text

        # Extract video IDs from the page using regex
        # YouTube embeds video data as JSON in the HTML — video IDs are 11 chars
        video_ids = re.findall(r'"videoId":"([a-zA-Z0-9_-]{11})"', html)

        if not video_ids:
            # Fallback: try watch?v= pattern
            video_ids = re.findall(r'watch\?v=([a-zA-Z0-9_-]{11})', html)

        if video_ids:
            video_id = video_ids[0]
            # Try to extract video title
            title = q
            try:
                title_match = re.search(r'"title":\{"runs":\[\{"text":"(.*?)"\}\]', html)
                if title_match:
                    title = title_match.group(1)
            except:
                pass
            
            # Build thumbnail URL
            thumbnail = f"https://i.ytimg.com/vi/{video_id}/hqdefault.jpg"

            return jsonify({
                "videoId": video_id,
                "title": title,
                "thumbnail": thumbnail,
                "duration": "",
            })
        else:
            return jsonify({"error": "No results found"}), 404

    except Exception as e:
        print(f"[WARN] YouTube search failed: {e}")
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
