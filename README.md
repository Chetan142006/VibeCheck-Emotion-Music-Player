<div align="center">

```
██╗   ██╗██╗██████╗ ███████╗ ██████╗██╗  ██╗███████╗ ██████╗██╗  ██╗
██║   ██║██║██╔══██╗██╔════╝██╔════╝██║  ██║██╔════╝██╔════╝██║ ██╔╝
██║   ██║██║██████╔╝█████╗  ██║     ███████║█████╗  ██║     █████╔╝ 
╚██╗ ██╔╝██║██╔══██╗██╔══╝  ██║     ██╔══██║██╔══╝  ██║     ██╔═██╗ 
 ╚████╔╝ ██║██████╔╝███████╗╚██████╗██║  ██║███████╗╚██████╗██║  ██╗
  ╚═══╝  ╚═╝╚═════╝ ╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝ ╚═════╝╚═╝  ╚═╝
```

### *Your face sets the vibe. Music does the rest.*

[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-2.x-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![Spotify](https://img.shields.io/badge/Spotify_API-Powered-1DB954?style=for-the-badge&logo=spotify&logoColor=white)](https://developer.spotify.com)
[![YouTube](https://img.shields.io/badge/YouTube_Music-Playback-FF0000?style=for-the-badge&logo=youtube&logoColor=white)](https://music.youtube.com)
[![DeepFace](https://img.shields.io/badge/DeepFace-Emotion_AI-blueviolet?style=for-the-badge)](https://github.com/serengil/deepface)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

</div>

---

## ⚡ What is VibeCheck?

> **VibeCheck** is a **multimodal, context-aware music streaming platform** that reads your **facial emotion**, checks the **weather outside**, and knows **what time of day** it is — then curates a 7-song playlist in real time. No typing. No searching. Just your face.

This project was built as a **Mini Project** for the paper:
> *"A Smart Multimodal Context-Aware Music Streaming Platform Using Facial Emotion Recognition"*

---

## 🧠 How It Actually Works

```
📸 Your Camera
      │
      ▼
┌─────────────────────┐
│   Haar Cascade      │  ← Detects face region fast
│   + DeepFace AI     │  ← Classifies emotion (7 classes)
└─────────┬───────────┘
          │  emotion
          ▼
┌─────────────────────┐     ┌──────────────────────┐
│  3D Context Formula │ ◄───│  🌤 Weather (OWM API) │
│                     │ ◄───│  🕐 Time of Day       │
│  Mood × Time × ☁️   │
└─────────┬───────────┘
          │  audio target params (valence, energy)
          ▼
┌─────────────────────┐
│   Spotify API       │  ← Fetches contextually matched tracks
│   Recommendations   │
└─────────┬───────────┘
          │  song metadata
          ▼
┌─────────────────────┐
│ YouTube Music API   │  ← Finds the real video/song to stream
│ (2-Pass Validation) │
└─────────┬───────────┘
          │
          ▼
       🎵 PLAY
```

---

## 🎭 Detected Emotions

| Emotion | Vibe it creates |
|---|---|
| 😄 **Happy** | High-energy, upbeat dance tracks |
| 😢 **Sad** | Soulful, slow, introspective ballads |
| 😡 **Angry** | Power anthems, high-intensity beats |
| 😨 **Fear** | Ambient, soft, calming compositions |
| 🤢 **Disgust** | Rebellious, indie, alt-energy tracks |
| 😲 **Surprise** | Fresh, trending, eclectic picks |
| 😐 **Neutral** | Chill, balanced, evergreen favorites |

---

## 🌍 Multi-Language Support

VibeCheck speaks **10 languages** — with curated song libraries for each:

`English` · `Hindi` · `Tamil` · `Telugu` · `Malayalam` · `Punjabi`

> 🔒 **Regional Firewall**: When a regional language is selected, Western artists are filtered out to preserve local music integrity.

---

## 🛠 Tech Stack

| Layer | Technology |
|---|---|
| **Backend** | Python · Flask |
| **Emotion AI** | DeepFace (FER+ model) · OpenCV Haar Cascade |
| **Recommendations** | Spotify Web API (`spotipy`) |
| **Music Playback** | YouTube Music API (`ytmusicapi`) |
| **Weather Context** | OpenWeatherMap API |
| **Frontend** | HTML5 · Vanilla CSS · JavaScript |
| **Data Persistence** | JSON (liked songs store) |

---

## 🧮 The 3D Context Formula

```python
valence = emotion_base_valence
         + weather_modifier   # +0.10 (sunny) → -0.10 (rainy)
         
energy  = emotion_base_energy
         + time_modifier      # +0.10 (morning) → -0.10 (night)

→ Spotify target_valence, target_energy, target_acousticness
→ Playlist of 7 songs (Liked → Spotify → Safe Fallback)
```

---

## 🚀 Getting Started

### 1. Clone the repo
```bash
git clone https://github.com/Chetan142006/VibeCheck-Emotion-Music-Player.git
cd VibeCheck-Emotion-Music-Player
```

### 2. Set up the environment
```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS/Linux

pip install -r requirements.txt
```

### 3. Configure API Keys
Create a `.env` file in the root directory:
```env
OPENWEATHER_API_KEY=your_openweathermap_key
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
```

> 🔑 Get your keys from:
> - [OpenWeatherMap](https://openweathermap.org/api) — Free tier works
> - [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)

### 4. Run it
```bash
python app.py
```
Open → **http://localhost:5000**

---

## 📡 API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/api/detect-emotion` | Accepts base64 image → returns emotion + confidence scores |
| `GET` | `/api/weather` | Fetches weather by lat/lon (falls back to IP geolocation) |
| `POST` | `/api/recommend` | Returns a 7-song playlist from the 3D context engine |
| `GET` | `/api/youtube-search` | 2-pass YT Music search with title validation |
| `POST` | `/api/like` | Save a liked song with its emotion context |
| `DELETE` | `/api/like` | Remove a liked song |
| `GET` | `/api/likes` | Fetch all liked song keys |

---

## 📁 Project Structure

```
VibeCheck-Emotion-Music-Player/
│
├── app.py                          # 🧠 Core Flask backend (817 lines)
├── requirements.txt                # 📦 Python dependencies
├── liked_songs.json                # 💾 Persisted user likes
├── architecture.png                # 🗺 System architecture diagram
├── Mini_Project_Technical_Paper.pdf # 📄 IEEE-style research paper
│
├── templates/
│   └── index.html                  # 🖥 Single-page frontend
│
└── static/
    ├── style.css                   # 🎨 UI Styles
    └── script.js                   # ⚡ Frontend logic & player controls
```

---

## 🎵 Smart Playlist Logic

```
Priority 1 → ❤️  Liked songs matching current emotion
Priority 2 → 🎧  Spotify API recommendations (contextual)
Priority 3 → 🛡️  Curated safe fallbacks (always available)
```

- Tracks already played are stored in a **50-song rolling history** to avoid repetition
- Playlist auto-refreshes when the queue ends (**Infinite Queue mode**)

---

## 📊 Emotion → Audio Parameter Mapping

| Emotion | Valence | Energy | Acousticness |
|---|---|---|---|
| Happy | 0.85 | 0.85 | Low |
| Sad | 0.20 | 0.25 | High |
| Angry | 0.30 | 0.90 | Low |
| Fear | 0.25 | 0.40 | Medium |
| Disgust | 0.35 | 0.55 | Medium |
| Surprise | 0.70 | 0.80 | Low |
| Neutral | 0.55 | 0.50 | Medium |

---

## 🔭 Future Scope

- [ ] 🎙 Voice tone-based emotion detection
- [ ] 🧬 Personalized ML model fine-tuning per user
- [ ] 📱 Progressive Web App (PWA) support
- [ ] 🤝 Social listening rooms
- [ ] 📈 Listening mood history & analytics dashboard

---

## 👨‍💻 Author

**Chetan Sai** — Mini Project, 2026  
*B.Tech | Computer Science & Engineering*

---

<div align="center">

*Built with 🎧 + 😄 + ☁️ + 🕐 = the perfect playlist*

**[⭐ Star this repo](https://github.com/Chetan142006/VibeCheck-Emotion-Music-Player)** if VibeCheck matched your vibe!

</div>
