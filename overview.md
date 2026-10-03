# Technical Architecture & Comprehensive Codebase Analysis

---

# Part 1: High-Level Project Analysis

## 1. Project Overview
**VibeCheck** is a context-aware, AI-driven music streaming web platform. Rather than requiring users to search for songs manually, VibeCheck evaluates the user's immediate physical and temporal environment—capturing **facial emotion** via webcam/image analysis, checking **local weather conditions**, and determining the **time of day**. 

By applying a **3D Context Recommendation Formula** ($\text{Emotion} \times \text{Time} \times \text{Weather}$), the application calculates target musical audio parameters (valence, energy, acousticness) and curates a personalized 7-song playlist. It bridges music metadata from Spotify with playback streaming powered by YouTube Music, presenting the user with an interactive player experience across 10 supported languages (English, Hindi, Tamil, Telugu, Kannada, Malayalam, Bengali, Punjabi, Marathi, and Gujarati).

---

## 2. Input & Output System Specification

```
                                  [ SYSTEM INPUTS ]
                                          │
    ┌─────────────────────────────────────┼─────────────────────────────────────┐
    ▼                                     ▼                                     ▼
[ Facial Image ]                  [ Spatial Coordinates ]               [ Temporal Context ]
• WebCam Stream (Base64 JPEG)     • Geolocation (Lat / Lon)             • Client System Time
• File Upload (Base64 DataURI)    • IP-based Location (Fallback)        • Time-of-Day Bucket
                                          │
                                          ▼
                             [ VIBECHECK BACKEND ENGINE ]
                                          │
                                          ▼
                                 [ SYSTEM OUTPUTS ]
                                          │
    ┌─────────────────────────────────────┼─────────────────────────────────────┐
    ▼                                     ▼                                     ▼
[ Emotion Classification ]        [ Dynamic Audio Stream ]             [ Context Metadata ]
• Dominant Mood Label             • YouTube Video ID & Embed           • Weather Condition Pill
• Confidence & Score Vector       • Synchronized Audio Control         • Responsive UI Queue
```

### Exact Inputs:
1. **Facial Image Feed**: Base64-encoded JPEG image string generated either from a 5-second live webcam stream (sampling at 500ms intervals) or a manual user photo upload.
2. **Geolocation Data**: HTML5 Browser `latitude` and `longitude` coordinates (with IP-based reverse geolocation fallback via `ip-api.com`).
3. **Temporal Context**: Server/Client hour extracted from system time to derive `morning`, `day`, or `night` buckets.
4. **User Preferences**: Selected language (e.g., English, Hindi, Punjabi, or multi-language Mix) and optional manual weather test override.

### Exact Outputs:
1. **Emotion Vector**: Dominant emotion classification (`happy`, `sad`, `angry`, `fear`, `disgust`, `surprise`, `neutral`) along with raw probability distributions across categories.
2. **Curated 7-Song Playlist Queue**: Ordered array of track metadata objects containing `title`, `artist`, `cover`, and `song_string`.
3. **Audio Stream & Playback**: Resolved YouTube Video ID mapped to the hidden YouTube IFrame Player with volume, seek, pause/play, next/prev controls, and synchronized EQ visualizers.
4. **Environmental Status Badges**: Contextual UI indicators showing detected emotion, live weather, and time bucket.

---

## 3. Workflow & End-to-End Architecture

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                                   FRONTEND (Browser)                                   │
│  [index.html] ◄──────────────► [script.js] ◄──────────────► [YouTube IFrame Player]   │
└───────────────────────────────────┬────────────────────────────────────────────────────┘
                                    │ HTTP REST APIs (JSON)
┌───────────────────────────────────▼────────────────────────────────────────────────────┐
│                                    BACKEND (Flask)                                     │
│  ┌───────────────────┐    ┌────────────────────┐    ┌───────────────────────────────┐  │
│  │   /api/detect-    │    │    /api/weather    │    │         /api/recommend        │  │
│  │     emotion       │    │                    │    │                               │  │
│  └─────────┬─────────┘    └─────────┬──────────┘    └───────────────┬───────────────┘  │
│            │                        │                               │                  │
│   [Haar Cascade + DeepFace]  [OpenWeatherMap API]        [3D Context Formula Engine]   │
│            │                        │                               │                  │
│            └────────────────────────┴───────────────┬───────────────┘                  │
│                                                     ▼                                  │
│                                        ┌─────────────────────────┐                     │
│                                        │  Spotify Web API        │                     │
│                                        │  (Audio Feature Seeds)  │                     │
│                                        └────────────┬────────────┘                     │
│                                                     ▼                                  │
│                                        ┌─────────────────────────┐                     │
│                                        │   /api/youtube-search   │                     │
│                                        │   (ytmusicapi 2-Pass)   │                     │
│                                        └─────────────────────────┘                     │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Step-by-Step Execution Flow:
1. **User Initiation**: The user opens the web application (`index.html`) served by Flask route `/`. The frontend initializes the YouTube IFrame API, fetches user likes from `/api/likes`, and opens the **Vibe Check Modal**.
2. **Emotion Capture & Analysis**:
   - If **Live Camera** is chosen, `script.js` captures a frame every 500ms for 5 seconds and POSTs the Base64 image payload to `/api/detect-emotion`.
   - `app.py` receives the image, converts it into a OpenCV NumPy array, detects face bounds via **Haar Cascades** for low latency, crops to the prominent face, and passes it to **DeepFace** to compute emotion probabilities.
   - The frontend aggregates frame scores over 5 seconds, selects the mode/dominant emotion, and displays real-time UI feedback.
3. **Contextual Environment Gathering**:
   - The browser requests HTML5 geolocation (`navigator.geolocation`).
   - The frontend queries `/api/weather?lat=...&lon=...`.
   - `app.py` contacts the **OpenWeatherMap API** (or falls back to IP geolocation) to retrieve the weather condition (e.g., `Clear`, `Rain`, `Clouds`).
4. **3D Context Recommendation Engine**:
   - The frontend calls `/api/recommend` passing `emotion`, `weather`, and `language`.
   - `build_playlist()` computes base `valence` and `energy` scores from `EMOTION_PARAMS`, modifies `energy` based on time of day (`get_time_of_day()`), and adjusts `valence` based on weather conditions (`get_weather_modifier()`).
   - The engine queries Spotify API via `spotipy` using genre seeds and audio feature targets (`target_valence`, `target_energy`, `target_acousticness`).
   - Results are filtered through a **Regional Firewall** (filtering out Western artists when non-English regional languages are selected), merged with matching user-liked songs from `liked_songs.json`, and padded with safe offline fallback tracks to yield a 7-song queue.
5. **Stream Resolution & Playback**:
   - The frontend receives the 7-song playlist and triggers `playSongAtIndex(0)`.
   - `script.js` queries `/api/youtube-search?q=Track - Artist`.
   - Backend `app.py` uses `ytmusicapi` in a 2-pass validation filter (matching title word overlaps) to locate the exact YouTube video ID.
   - The video ID is sent back to the browser, and `state.ytPlayer.loadVideoById(videoId)` starts streaming audio while displaying album art and track metadata.

---

## 4. Implementation Strategy & Architecture Design Patterns

| Feature / Goal | Engineering Choice | Technical Rationale |
| :--- | :--- | :--- |
| **Backend Framework** | **Flask (Python)** | Lightweight, low-overhead microframework ideal for serving REST endpoints and bridging native Python ML libraries (OpenCV, DeepFace) with frontend web clients. |
| **Emotion Recognition** | **Two-Pass Hybrid Detection** | Haar Cascade performs spatial face detection first to crop the image, drastically lowering DeepFace inference time and preventing frame processing bottlenecks during live streaming. |
| **Recommendation Model** | **3D Context Matrix** | Combines user internal state (Emotion) with external environment (Time & Weather) to modulate 2D audio vector parameters ($\text{Valence} \times \text{Energy} \times \text{Acousticness}$). |
| **Playback Architecture** | **Hybrid Metadata & Audio Stream** | Uses Spotify's music taxonomy and audio metrics for recommendation precision, while leveraging YouTube Music via `ytmusicapi` and YouTube IFrame API for free playback without Spotify Premium OAuth restrictions. |
| **Regional Firewall** | **Blocklist Filter Pattern** | Prevents recommendation leakage (e.g. Western pop artists diluting regional query recommendations) when user selects regional Indian languages. |
| **Resilience & Fallback** | **Multi-tier Failover System** | 1. DeepFace missing $\rightarrow$ Simulated emotion.<br>2. Spotify credentials missing $\rightarrow$ Offline safe fallback matrix.<br>3. OpenWeather failure $\rightarrow$ IP Geolocation $\rightarrow$ Default clear weather.<br>4. YouTube embed restricted $\rightarrow$ Candidate video array auto-retry. |

---

# Part 2: Deep-Dive Technical Documentation

Below is the complete, structured technical documentation for the codebase. You can copy and save this section directly as `DOCUMENTATION.md`.

```markdown
# VibeCheck — Deep-Dive Codebase Technical Documentation

This document provides a comprehensive analysis of every major function, module, and implementation block across the VibeCheck project files.

---

## Table of Contents
1. [Backend Modules (`app.py`)](#1-backend-modules-apppy)
2. [Frontend Engine (`static/script.js`)](#2-frontend-engine-staticscriptjs)
3. [User Interface & Layout (`templates/index.html`)](#3-user-interface--layout-templatesindexhtml)
4. [Data Persistence & Configuration (`liked_songs.json`, `.env`, `requirements.txt`)](#4-data-persistence--configuration)

---

## 1. Backend Modules (`app.py`)

### `load_liked_songs()`, `save_liked_song()`, `remove_liked_song()`

#### The "What"
These helper functions manage reading from and writing to `liked_songs.json`. They store liked tracks alongside contextual metadata (`emotion`, `weather`, `time_of_day`, `language`, and ISO timestamp) indexed by a normalized, lowercase song string key.

#### The "Why"
- **Contextual Personalization**: Storing the environment in which a song was liked allows the recommendation engine (`build_playlist`) to prioritize songs the user previously liked under identical emotional and environmental conditions.
- **Deduplication**: Keying by `song.lower().strip()` prevents duplicate entries caused by minor case or whitespace discrepancies.
- **Fail-Safe I/O**: Surrounding read operations in `try/except` blocks ensures that corrupt or unreadable JSON files degrade gracefully by returning an empty dictionary rather than crashing the Flask backend.

---

### DeepFace & OpenCV Haar Cascade Setup

```python
try:
    from deepface import DeepFace
    DEEPFACE_AVAILABLE = True
except ImportError:
    DEEPFACE_AVAILABLE = False

face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
```

#### The "What"
Imports `DeepFace` conditionally and loads OpenCV's frontal face Haar Cascade XML classifier.

#### The "Why"
- **Environment Adaptability**: Heavy deep-learning dependencies like DeepFace or TensorFlow might fail to load in constrained deployment environments (e.g. basic cloud tiers). The boolean flag `DEEPFACE_AVAILABLE` allows the backend to start cleanly and substitute simulated emotion logic if necessary.
- **Performance Optimization**: Haar Cascade pre-filters images before DeepFace analysis. Passing a full 640x480 webcam frame to DeepFace is computationally expensive. Locating the bounding box of the face and cropping the frame first reduces tensor dimensions and cuts inference latency by up to 60%.

---

### Data Dictionaries: `SAFE_SONGS`, `EMOTION_PARAMS`, `LANGUAGE_GENRES`

#### The "What"
- `SAFE_SONGS`: A nested mapping of 7 emotion categories across 10 languages, offering hand-curated fallback tracks.
- `EMOTION_PARAMS`: Maps emotions to target audio metrics (`valence` and `energy`) on a scale of `0.0` to `1.0`.
- `LANGUAGE_GENRES`: Maps specific languages to high/low energy and valence genre seed strings used during Spotify recommendation calls.

#### The "Why"
- **Guaranteed Output**: Web APIs like Spotify may occasionally fail, rate-limit, or return zero results for obscure genre combinations. `SAFE_SONGS` acts as an offline guarantee so the user always receives 7 playable songs.
- **Psychographic Mapping**: In music information retrieval (MIR), **Valence** represents musical positiveness (happy vs. sad/melancholic) and **Energy** represents perceptual intensity. Mapping emotions to 2D vector coordinates allows mathematical modulation based on environmental context.

---

### `get_time_of_day()` & `get_weather_modifier()`

```python
def get_time_of_day():
    hour = datetime.now().hour
    if 5 <= hour < 12:
        return "morning", 0.1
    elif 12 <= hour < 19:
        return "day", 0.0
    else:
        return "night", -0.1

def get_weather_modifier(weather_main: str):
    weather_main = weather_main.lower() if weather_main else ""
    mapping = {
        "clear": 0.10, "rain": -0.10, "thunderstorm": -0.10,
        "clouds": 0.0, "party": 0.20
    }
    return mapping.get(weather_main, 0.0)
```

#### The "What"
Functions that produce mathematical numerical offsets to adjust base energy and valence metrics depending on environmental parameters.

#### The "Why"
- **The 3D Context Formula**: A user who is feeling "neutral" at 8:00 AM on a bright sunny day requires a different energy profile than a "neutral" user at 11:00 PM on a rainy night.
- **Mathematical Bound Control**: `get_time_of_day()` boosts energy in the morning (+0.1) and softens it at night (-0.1). `get_weather_modifier()` increases positivity on clear days (+0.1) and lowers it during rain (-0.1). Combining these offsets computes an adapted vector clamped strictly between `0.0` and `1.0`.

---

### `get_spotify_recommendations()`

#### The "What"
Queries Spotify's `/v1/recommendations` endpoint using `spotipy`. It passes calculated target metrics (`target_valence`, `target_energy`, `target_acousticness`) along with language-tailored seed genres.

#### The "Why"
- **Precision Audio Matching**: Spotify's recommendation engine evaluates millions of tracks based on algorithmic audio analysis. Using target feature parameters provides a far more accurate match than simple text-based genre searches.
- **Regional Filtering**: When non-English regional languages (such as Tamil or Hindi) are active, it applies `WESTERN_BLOCKLIST` filtering to remove Western pop artists that might otherwise leak into Indian genre seeds.

---

### `build_playlist()`

#### The "What"
The primary orchestrator of the recommendation engine. It gathers matched user-liked songs, queries Spotify API recommendations, appends curated fallback tracks, removes duplicates, and logs recommendation history to `RECOMMENDATION_HISTORY` to prevent song repetition across consecutive runs.

#### The "Why"
- **Deduplication & History Management**: Users do not want to hear the same track repeatedly in a single session. `RECOMMENDATION_HISTORY` acts as a sliding FIFO buffer (up to 50 tracks) to enforce variety.
- **Hybrid Merging Strategy**: By layering `Liked Songs (Priority 1) -> Spotify Recommendations (Priority 2) -> Safe Fallbacks (Priority 3)`, the system guarantees a personalized, non-empty, exactly 7-song playlist output every time.

---

### `detect_emotion_deepface(img)` & `/api/detect-emotion` Route

#### The "What"
Receives a Base64-encoded image from the client, converts it into an OpenCV image buffer, attempts face detection via Haar Cascade, crops the target area, and runs `DeepFace.analyze(..., actions=['emotion'])`.

#### The "Why"
- **Robust Error Handling**: Facial recognition can fail if lighting is poor, or if the user turns away. Setting `enforce_detection=False` prevents DeepFace from throwing runtime exceptions when face geometry is partial.
- **Confidence Flagging**: If Haar Cascade fails to locate face coordinates, the function falls back to analyzing the full image frame, setting `low_confidence=True` so the frontend can notify the user to adjust lighting.

---

### `/api/youtube-search` Route (2-Pass Validation)

```python
# PASS 1: Strict Audio Search (songs filter)
results_songs = ytmusicapi.search(query=q, filter="songs", limit=15)
# PASS 2: Official Video Fallback
```

#### The "What"
Searches YouTube Music via `ytmusicapi` for a track query (e.g. `Blinding Lights - The Weeknd`) and returns a valid YouTube `videoId` and thumbnail URL.

#### The "Why"
- **Eliminating Hallucinations & Covers**: YouTube search results often include user-generated covers, live bootlegs, or unrelated video clips.
- **Two-Pass Algorithm**: Pass 1 explicitly filters for official audio tracks and compares string title word intersections against the request query (requiring $\ge 80\%$ word match). If Pass 1 returns no valid match, Pass 2 searches unfiltered videos as a fallback, ensuring reliable playback.

---

## 2. Frontend Engine (`static/script.js`)

### State Container (`state`)

#### The "What"
Centralized client-side state object tracking queue items, active playback index, camera stream instances, YouTube player ready flags, aggregated emotion counts, liked song keys, and search retry indices.

#### The "Why"
Single source of truth prevents UI desynchronization between player controls, queue highlights, sidebar indicators, and asynchronous API calls.

---

### YouTube IFrame API Handler (`onYouTubeIframeAPIReady`, `onPlayerStateChange`, `onPlayerError`)

#### The "What"
Initializes an embedded invisible YouTube player (`#ytPlayer`) and listens for state changes (`PLAYING`, `PAUSED`, `ENDED`) and error events (`101`, `150` embed restrictions).

#### The "Why"
- **Seamless Auto-advance**: Listening for `YT.PlayerState.ENDED` triggers automatic transition to the next song in the queue without requiring user interaction.
- **Embed Restriction Failover**: Artists frequently restrict certain tracks from embedding on third-party domains (Error 101/150). When this occurs, `onPlayerError` catches the error, picks the next candidate ID from `state.candidateVideoIds`, and retries seamlessly.
- **Dynamic Infinite Queueing**: Every 3 songs played (`state.songsPlayedSinceVibeCheck % 3 === 0`), the frontend automatically calls `fetchMoreForQueue()` to append 3 new tracks to the queue, ensuring uninterrupted playback.

---

### Camera Scanner & Temporal Aggregator (`startCameraScan`, `finishScan`)

#### The "What"
Streams video from the user's webcam (`navigator.mediaDevices.getUserMedia`), captures a frame on an off-screen HTML5 canvas every 500ms for 5 seconds, POSTs frames to `/api/detect-emotion`, and tallies detected emotions in `state.emotionCounts`.

#### The "Why"
- **Temporal Stability**: Micro-expressions or momentary lighting fluctuations can cause single-frame emotion misclassifications. Sampling over a 5-second interval (10 total frames) and calculating the dominant/mode emotion ensures an accurate classification.
- **Weighted Tallying**: High-confidence detections add `3` points to an emotion tally while low-confidence detections add `1` point, prioritizing clear facial readings.

---

### Recommendation Trigger & Geolocation (`fetchRecommendations`)

#### The "What"
Retrieves browser latitude/longitude coordinates via `getGeolocation()`, queries `/api/weather`, POSTs combined parameters to `/api/recommend`, populates the queue, updates environmental pills, and initiates track playback.

#### The "Why"
- **Asynchronous Pipeline**: Chaining these steps ensures that weather and spatial context are determined in real time right when the user completes their emotion scan.

---

## 3. User Interface & Layout (`templates/index.html`)

### Structural Layout & UI Elements

#### The "What"
A single-page interface featuring:
- **Header Badge Row**: Live display pills for emotion, weather, and time context.
- **Player Card (`#playerCard`)**: Displays album art, vinyl rotation animation, title/artist info, progress bar, play/pause/prev/next buttons, volume slider, and like button.
- **Queue Panel (`#queuePanel`)**: Sidebar displaying upcoming tracks with active equalizer bar animations (`.eq-bar`).
- **Modal Overlay (`#vibeModal`)**: Overlay supporting live webcam preview, drag-and-drop file upload, language dropdown, and manual weather test overrides.

#### The "Why"
- **Glassmorphism Aesthetic**: Modern glassmorphism UI styled with translucent backgrounds (`backdrop-filter: blur()`), vibrant accent gradients, and dark mode principles for an engaging visual experience.
- **Non-blocking Workflow**: Modal overlays keep emotion scan controls separate from the main playback canvas, allowing audio playback to continue uninterrupted while the user sets up a new Vibe Check.

---

## 4. Data Persistence & Configuration

### `liked_songs.json`
```json
{
    "blinding lights - the weeknd": {
        "song": "Blinding Lights - The Weeknd",
        "emotion": "happy",
        "weather": "Clear",
        "time_of_day": "night",
        "language": "english",
        "timestamp": "2026-07-22T20:15:00.000000"
    }
}
```
Stores user preferences on the local filesystem without requiring external database server dependencies (like MySQL or MongoDB).

### `.env` Configuration File
```env
OPENWEATHER_API_KEY=your_openweather_key_here
SPOTIPY_CLIENT_ID=your_spotify_client_id
SPOTIPY_CLIENT_SECRET=your_spotify_client_secret
```
Keeps API credentials isolated from source code, preventing security leaks when committing code to version control repositories.

### `requirements.txt`
Declares essential project dependencies:
- `flask`: Web application framework.
- `deepface`, `opencv-python-headless`, `tf-keras`, `retina-face`: Facial recognition and computer vision pipeline.
- `spotipy`: Spotify Web API wrapper.
- `ytmusicapi`: YouTube Music API query and search validation engine.
- `python-dotenv`: Environment configuration loader.
```