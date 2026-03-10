/* ═══════════════════════════════════════════════════════════════════
   VibeCheck — Frontend JavaScript
   ═══════════════════════════════════════════════════════════════════
   Handles:
   • YouTube IFrame API (hidden player, autoplay queue)
   • Webcam capture & emotion detection
   • Image upload & emotion detection
   • Weather + recommendation flow
   • Player UI controls (play/pause, next, volume, progress)
   • Queue management
   ═══════════════════════════════════════════════════════════════════ */

// ── STATE ───────────────────────────────────────────────────────────
const state = {
    queue: [],            // Array of song strings: "Song - Artist"
    currentIndex: -1,     // Currently playing index
    isPlaying: false,
    ytPlayer: null,       // YouTube player instance
    ytReady: false,       // Is YouTube player ready?
    scanTimer: null,      // Webcam scan interval
    scanTimeout: null,    // 5-second scan timeout
    cameraStream: null,   // MediaStream reference
    emotionCounts: {},    // Accumulate detections during scan
    likes: [],            // Array of liked song keys
    songsPlayedSinceVibeCheck: 0, // Counter for vibe check prompt
    currentContext: {     // To fetch more songs for dynamic queue
        emotion: "neutral",
        weather: "Clear",
        language: "mix"
    }
};

// ── DOM REFERENCES ──────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => document.querySelectorAll(sel);

const dom = {
    // Player
    playerCard: $("#playerCard"),
    albumImage: $("#albumImage"),
    albumPlaceholder: $(".album-placeholder"),
    songTitle: $("#songTitle"),
    songArtist: $("#songArtist"),
    progressFill: $("#progressFill"),
    currentTime: $("#currentTime"),
    totalTime: $("#totalTime"),
    playPauseBtn: $("#playPauseBtn"),
    playIcon: $("#playIcon"),
    pauseIcon: $("#pauseIcon"),
    prevBtn: $("#prevBtn"),
    nextBtn: $("#nextBtn"),
    volumeSlider: $("#volumeSlider"),
    vinylDisc: $("#vinylDisc"),
    // Queue
    queueList: $("#queueList"),
    queueCount: $("#queueCount"),
    // Like Button
    likeBtn: $("#likeBtn"),
    heartOutline: $("#heartOutline"),
    heartFilled: $("#heartFilled"),
    // Context pills
    emotionPill: $("#emotionPill"),
    weatherPill: $("#weatherPill"),
    timePill: $("#timePill"),
    // Vibe Check
    vibeCheckBtn: $("#vibeCheckBtn"),
    modalOverlay: $("#modalOverlay"),
    vibeModal: $("#vibeModal"),
    modalClose: $("#modalClose"),
    optCamera: $("#optCamera"),
    optUpload: $("#optUpload"),
    langSelect: $("#langSelect"),
    // Camera
    cameraView: $("#cameraView"),
    cameraFeed: $("#cameraFeed"),
    cameraCanvas: $("#cameraCanvas"),
    emotionOverlay: $("#emotionOverlay"),
    scanBar: $("#scanBar"),
    cancelScan: $("#cancelScan"),
    // Upload
    uploadView: $("#uploadView"),
    dropzone: $("#dropzone"),
    fileInput: $("#fileInput"),
    uploadPreview: $("#uploadPreview"),
    previewImage: $("#previewImage"),
    uploadEmotionOverlay: $("#uploadEmotionOverlay"),
    // Loading
    modalLoading: $("#modalLoading"),
    loadingText: $("#loadingText"),
    // Modal options wrapper
    modalOptions: $(".modal-options"),
    modalSubtitle: $(".modal-subtitle"),
    modalTitle: $(".modal-title"),
    langSelector: $(".language-selector"),
    // Vibe Prompt
    vibePromptBanner: $("#vibePromptBanner"),
    promptContent: $(".prompt-content"),
    promptClose: $("#promptClose"),
    // Toast
    toastContainer: $("#toastContainer"),
};

// ═══════════════════════════════════════════════════════════════════
//  1. YOUTUBE IFRAME API
// ═══════════════════════════════════════════════════════════════════

/**
 * Called automatically by the YouTube IFrame API script once loaded.
 * Creates a hidden player instance.
 */
function onYouTubeIframeAPIReady() {
    state.ytPlayer = new YT.Player("ytPlayer", {
        height: "180",
        width: "280",
        playerVars: {
            autoplay: 0,
            controls: 0,
            disablekb: 1,
            fs: 0,
            modestbranding: 1,
            rel: 0,
        },
        events: {
            onReady: onPlayerReady,
            onStateChange: onPlayerStateChange,
            onError: onPlayerError,
        },
    });
}

function onPlayerReady() {
    state.ytReady = true;
    // Set initial volume
    state.ytPlayer.setVolume(parseInt(dom.volumeSlider.value, 10));
    console.log("[YT] Player ready");
}

function onPlayerStateChange(event) {
    switch (event.data) {
        case YT.PlayerState.PLAYING:
            state.isPlaying = true;
            updatePlayPauseUI();
            dom.playerCard.classList.add("playing");
            startProgressTracker();
            break;
        case YT.PlayerState.PAUSED:
            state.isPlaying = false;
            updatePlayPauseUI();
            dom.playerCard.classList.remove("playing");
            stopProgressTracker();
            break;
        case YT.PlayerState.ENDED:
            // Auto-advance to next song in queue
            stopProgressTracker();

            // Increment songs played counter
            state.songsPlayedSinceVibeCheck++;

            // Show vibe check prompt every 2 songs
            if (state.songsPlayedSinceVibeCheck % 2 === 0) {
                showVibePrompt();
            }

            // Always fetch more songs to keep the queue seamlessly expanding
            fetchMoreForQueue();

            playNext();
            break;
        case YT.PlayerState.BUFFERING:
            // Do nothing special
            break;
    }
}

function onPlayerError(event) {
    console.warn("[YT] Player error:", event.data);
    showToast("Playback error — skipping to next track", "error");
    // Try next song
    setTimeout(playNext, 1000);
}

// ═══════════════════════════════════════════════════════════════════
//  2. PLAYBACK CONTROLS
// ═══════════════════════════════════════════════════════════════════

/** Play or pause the current track. */
function togglePlayPause() {
    if (!state.ytReady || state.queue.length === 0) return;
    if (state.isPlaying) {
        state.ytPlayer.pauseVideo();
    } else {
        state.ytPlayer.playVideo();
    }
}

/** Play next track in queue. */
function playNext() {
    if (state.queue.length === 0) return;
    if (state.currentIndex < state.queue.length - 1) {
        playSongAtIndex(state.currentIndex + 1);
    } else {
        // End of queue — loop back to start
        playSongAtIndex(0);
    }
}

/** Play previous track in queue. */
function playPrev() {
    if (state.queue.length === 0) return;
    if (state.currentIndex > 0) {
        playSongAtIndex(state.currentIndex - 1);
    }
}

/**
 * Play a specific song from the queue by index.
 * Searches YouTube for the video ID, then loads it.
 */
async function playSongAtIndex(index) {
    if (index < 0 || index >= state.queue.length) return;
    state.currentIndex = index;
    const songStr = state.queue[index];

    // Parse "Song - Artist"
    const parts = songStr.split(" - ");
    const title = parts[0] || songStr;
    const artist = parts.slice(1).join(" - ") || "";

    dom.songTitle.textContent = title;
    dom.songArtist.textContent = artist || "Unknown Artist";
    updateQueueHighlight();
    updateNavButtons();
    checkLikeStatus(songStr);

    // Search YouTube for video ID
    try {
        const resp = await fetch(`/api/youtube-search?q=${encodeURIComponent(songStr)}`);
        const data = await resp.json();

        if (data.videoId && state.ytReady) {
            // Update thumbnail as album art
            if (data.thumbnail) {
                dom.albumImage.src = data.thumbnail;
                dom.albumImage.style.display = "block";
                dom.albumPlaceholder.style.display = "none";
            }

            state.ytPlayer.loadVideoById(data.videoId);
            showToast(`🎵 Now playing: ${title}`, "info");
        } else {
            showToast(`Could not find: ${title}`, "error");
            // Skip to next after short delay
            setTimeout(playNext, 1500);
        }
    } catch (err) {
        console.error("[Playback] Error:", err);
        showToast("Search failed — skipping", "error");
        setTimeout(playNext, 1500);
    }
}

/** Update play/pause button icons. */
function updatePlayPauseUI() {
    dom.playIcon.style.display = state.isPlaying ? "none" : "block";
    dom.pauseIcon.style.display = state.isPlaying ? "block" : "none";
}

/** Enable/disable prev/next based on position. */
function updateNavButtons() {
    dom.prevBtn.disabled = state.currentIndex <= 0;
    dom.nextBtn.disabled = state.queue.length === 0;
}

// ── Progress Tracker ────────────────────────────────────────────────
let progressInterval = null;

function startProgressTracker() {
    stopProgressTracker();
    progressInterval = setInterval(() => {
        if (!state.ytReady || !state.isPlaying) return;
        const current = state.ytPlayer.getCurrentTime() || 0;
        const total = state.ytPlayer.getDuration() || 0;
        if (total > 0) {
            const pct = (current / total) * 100;
            dom.progressFill.style.width = pct + "%";
            dom.currentTime.textContent = formatTime(current);
            dom.totalTime.textContent = formatTime(total);
        }
    }, 500);
}

function stopProgressTracker() {
    if (progressInterval) {
        clearInterval(progressInterval);
        progressInterval = null;
    }
}

function formatTime(seconds) {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s < 10 ? "0" : ""}${s}`;
}

// ═══════════════════════════════════════════════════════════════════
//  3. QUEUE MANAGEMENT
// ═══════════════════════════════════════════════════════════════════

/** Render the queue list in the sidebar. */
function renderQueue() {
    if (state.queue.length === 0) {
        dom.queueList.innerHTML = `<li class="queue-empty"><p>Your playlist will appear here after a Vibe Check ✨</p></li>`;
        dom.queueCount.textContent = "0 songs";
        return;
    }

    dom.queueCount.textContent = `${state.queue.length} songs`;
    dom.queueList.innerHTML = state.queue.map((song, i) => {
        const parts = song.split(" - ");
        const title = parts[0] || song;
        const artist = parts.slice(1).join(" - ") || "";
        const isActive = i === state.currentIndex;
        return `
            <li class="queue-item ${isActive ? "active" : ""}" data-index="${i}" onclick="playSongAtIndex(${i})">
                <span class="queue-item-num">${i + 1}</span>
                <div class="queue-item-info">
                    <div class="queue-item-title">${escapeHtml(title)}</div>
                    <div class="queue-item-artist">${escapeHtml(artist)}</div>
                </div>
                <div class="queue-item-playing">
                    <span class="eq-bar"></span>
                    <span class="eq-bar"></span>
                    <span class="eq-bar"></span>
                    <span class="eq-bar"></span>
                </div>
            </li>
        `;
    }).join("");
}

function updateQueueHighlight() {
    const items = $$(".queue-item");
    items.forEach((item, i) => {
        item.classList.toggle("active", i === state.currentIndex);
    });
}

function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
}

// ═══════════════════════════════════════════════════════════════════
//  4. VIBE CHECK MODAL
// ═══════════════════════════════════════════════════════════════════

function openModal() {
    // Reset modal to initial state
    dom.cameraView.style.display = "none";
    dom.uploadView.style.display = "none";
    dom.modalLoading.style.display = "none";
    dom.modalOptions.style.display = "grid";
    dom.modalSubtitle.style.display = "block";
    dom.langSelector.style.display = "block";
    dom.uploadPreview.style.display = "none";
    dom.modalOverlay.classList.add("open");
}

function closeModal() {
    dom.modalOverlay.classList.remove("open");
    stopCameraScan();
}

// ═══════════════════════════════════════════════════════════════════
//  5. WEBCAM SCAN
// ═══════════════════════════════════════════════════════════════════

async function startCameraScan() {
    dom.modalOptions.style.display = "none";
    dom.modalSubtitle.style.display = "none";
    dom.langSelector.style.display = "none";
    dom.uploadView.style.display = "none";
    dom.cameraView.style.display = "block";
    dom.scanBar.style.width = "0%";
    dom.emotionOverlay.textContent = "Starting camera...";
    state.emotionCounts = {};

    try {
        const stream = await navigator.mediaDevices.getUserMedia({
            video: { facingMode: "user", width: 640, height: 480 },
            audio: false,
        });
        state.cameraStream = stream;
        dom.cameraFeed.srcObject = stream;

        // Wait for video to load
        await new Promise((resolve) => {
            dom.cameraFeed.onloadedmetadata = resolve;
        });

        // Set canvas size
        dom.cameraCanvas.width = dom.cameraFeed.videoWidth;
        dom.cameraCanvas.height = dom.cameraFeed.videoHeight;

        // Start scanning: capture a frame every 500ms
        let elapsed = 0;
        const scanDuration = 5000; // 5 seconds
        const scanInterval = 500;

        state.scanTimer = setInterval(async () => {
            elapsed += scanInterval;
            const pct = Math.min((elapsed / scanDuration) * 100, 100);
            dom.scanBar.style.width = pct + "%";

            // Capture frame
            const ctx = dom.cameraCanvas.getContext("2d");
            ctx.drawImage(dom.cameraFeed, 0, 0);
            const dataUrl = dom.cameraCanvas.toDataURL("image/jpeg", 0.92);

            // Send to backend for emotion detection
            try {
                const resp = await fetch("/api/detect-emotion", {
                    method: "POST",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ image: dataUrl }),
                });
                const data = await resp.json();
                console.log("[Scan] Emotion response:", data);
                if (data.emotion) {
                    const em = data.emotion;
                    // Weight high-confidence detections more than low-confidence ones
                    const weight = data.low_confidence ? 1 : 3;
                    state.emotionCounts[em] = (state.emotionCounts[em] || 0) + weight;
                    dom.emotionOverlay.textContent = `${getEmoji(em)} ${capitalize(em)}`;
                }
            } catch (err) {
                console.warn("[Scan] Frame detection error:", err);
            }
        }, scanInterval);

        // Stop after 5 seconds
        state.scanTimeout = setTimeout(() => {
            finishScan();
        }, scanDuration + 200);

    } catch (err) {
        console.error("[Camera] Error:", err);
        showToast("Camera access denied or unavailable", "error");
        dom.cameraView.style.display = "none";
        dom.modalOptions.style.display = "grid";
        dom.modalSubtitle.style.display = "block";
        dom.langSelector.style.display = "block";
    }
}

function stopCameraScan() {
    if (state.scanTimer) { clearInterval(state.scanTimer); state.scanTimer = null; }
    if (state.scanTimeout) { clearTimeout(state.scanTimeout); state.scanTimeout = null; }
    if (state.cameraStream) {
        state.cameraStream.getTracks().forEach((t) => t.stop());
        state.cameraStream = null;
    }
    dom.cameraFeed.srcObject = null;
}

async function finishScan() {
    // Keep the camera running to show live emotion detection during the analysis stage!
    // stopCameraScan(); 

    // Determine dominant emotion
    const dominant = getDominantEmotion(state.emotionCounts);
    showToast(`🎭 Locked in vibe: ${capitalize(dominant)}`, "success");
    await fetchRecommendations(dominant);
}

function getDominantEmotion(counts) {
    let maxEm = "neutral";
    let maxCount = 0;
    for (const [em, count] of Object.entries(counts)) {
        if (count > maxCount) {
            maxCount = count;
            maxEm = em;
        }
    }
    return maxEm;
}

// ═══════════════════════════════════════════════════════════════════
//  6. IMAGE UPLOAD
// ═══════════════════════════════════════════════════════════════════

function startUpload() {
    dom.modalOptions.style.display = "none";
    dom.modalSubtitle.style.display = "none";
    dom.langSelector.style.display = "none";
    dom.cameraView.style.display = "none";
    dom.uploadView.style.display = "block";
    dom.uploadPreview.style.display = "none";
    dom.dropzone.style.display = "flex";
}

async function handleFileUpload(file) {
    if (!file || !file.type.startsWith("image/")) {
        showToast("Please upload a valid image file", "error");
        return;
    }

    const reader = new FileReader();
    reader.onload = async (e) => {
        const dataUrl = e.target.result;

        // Show preview
        dom.previewImage.src = dataUrl;
        dom.uploadPreview.style.display = "block";
        dom.dropzone.style.display = "none";
        dom.uploadEmotionOverlay.textContent = "Analyzing...";

        try {
            const resp = await fetch("/api/detect-emotion", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ image: dataUrl }),
            });
            const data = await resp.json();

            console.log("[Upload] Emotion response:", data);
            if (data.emotion) {
                const em = data.emotion;
                dom.uploadEmotionOverlay.textContent = `${getEmoji(em)} ${capitalize(em)}`;
                if (data.low_confidence) {
                    showToast(`🎭 Detected: ${capitalize(em)} (low confidence — try better lighting)`, "info");
                } else {
                    showToast(`🎭 Detected emotion: ${capitalize(em)}`, "success");
                }

                // Short pause then fetch recommendations
                setTimeout(() => fetchRecommendations(em), 1000);
            } else {
                dom.uploadEmotionOverlay.textContent = "Detection failed";
                showToast(data.error || "Could not detect emotion", "error");
            }
        } catch (err) {
            console.error("[Upload] Error:", err);
            showToast("Emotion detection failed", "error");
        }
    };
    reader.readAsDataURL(file);
}

// ═══════════════════════════════════════════════════════════════════
//  7. RECOMMENDATION FLOW
// ═══════════════════════════════════════════════════════════════════

/**
 * Full recommendation pipeline:
 * 1. Get user geolocation (if allowed)
 * 2. Fetch weather from backend
 * 3. Call /api/recommend with emotion + weather + language
 * 4. Populate queue & start playback
 */
async function fetchRecommendations(emotion) {
    // Show loading state in modal, but keep camera/upload view visible 
    // so user can see live emotion overlay
    dom.modalLoading.style.display = "flex";
    dom.loadingText.textContent = "Reading the vibes...";

    const language = dom.langSelect.value;

    try {
        // Step 1: Get geolocation
        dom.loadingText.textContent = "Getting your location...";
        let lat = "", lon = "";
        try {
            const pos = await getGeolocation();
            lat = pos.coords.latitude;
            lon = pos.coords.longitude;
        } catch {
            console.warn("[Geo] Location unavailable, using defaults");
        }

        // Step 2: Fetch weather
        dom.loadingText.textContent = "Checking the weather...";
        let weatherMain = "Clear";
        try {
            const wResp = await fetch(`/api/weather?lat=${lat}&lon=${lon}`);
            const wData = await wResp.json();
            weatherMain = wData.main || "Clear";
            // Update weather pill
            dom.weatherPill.textContent = `${getWeatherEmoji(weatherMain)} ${weatherMain}`;
            dom.weatherPill.classList.add("active");
        } catch {
            console.warn("[Weather] Failed, using default");
        }

        // Step 3: Fetch recommendations
        dom.loadingText.textContent = "Curating your playlist...";
        const rResp = await fetch("/api/recommend", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ emotion, weather: weatherMain, language }),
        });
        const rData = await rResp.json();

        if (rData.playlist && rData.playlist.length > 0) {
            // Update context
            const ctx = rData.context || {};
            state.currentContext = ctx; // save for auto-refresh
            state.songsPlayedSinceVibeCheck = 0; // reset prompt counter
            hideVibePrompt(); // hide if showing

            dom.emotionPill.textContent = `${getEmoji(ctx.emotion || emotion)} ${capitalize(ctx.emotion || emotion)}`;
            dom.emotionPill.classList.add("active");
            dom.timePill.textContent = `🕐 ${capitalize(ctx.time_of_day || "day")}`;
            dom.timePill.classList.add("active");

            // Populate queue
            state.queue = rData.playlist;
            state.currentIndex = -1;
            renderQueue();

            // Refresh like states
            await fetchLikes();

            // Close modal & start playback
            closeModal();
            showToast(`✅ ${rData.playlist.length} songs queued!`, "success");
            playSongAtIndex(0);
        } else {
            showToast("No songs found — try a different emotion or language", "error");
            stopCameraScan();
            dom.cameraView.style.display = "none";
            dom.uploadView.style.display = "none";
            dom.modalLoading.style.display = "none";
            dom.modalOptions.style.display = "grid";
            dom.langSelector.style.display = "block";
        }

    } catch (err) {
        console.error("[Recommend] Error:", err);
        showToast("Recommendation failed — please try again", "error");
        stopCameraScan();
        dom.cameraView.style.display = "none";
        dom.uploadView.style.display = "none";
        dom.modalLoading.style.display = "none";
        dom.modalOptions.style.display = "grid";
        dom.langSelector.style.display = "block";
    }
}

/** Fetch a few more songs dynamically to append to the queue */
async function fetchMoreForQueue() {
    try {
        let { emotion, weather, language } = state.currentContext;

        // After 2 songs, switch to a mix of languages to introduce variety
        // This fulfills the requirement to prefer Regional first, then recommend other languages!
        if (language !== "mix" && state.songsPlayedSinceVibeCheck >= 2) {
            language = "mix";
        }

        const rResp = await fetch("/api/recommend", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ emotion, weather, language }),
        });
        const rData = await rResp.json();
        if (rData.playlist) {
            // Add songs that aren't already in the queue
            let added = 0;
            for (const song of rData.playlist) {
                if (!state.queue.includes(song)) {
                    state.queue.push(song);
                    added++;
                }
            }
            if (added > 0) {
                renderQueue();
            }
        }
    } catch (err) {
        console.warn("[Queue] Auto-refresh failed", err);
    }
}

function getGeolocation() {
    return new Promise((resolve, reject) => {
        if (!navigator.geolocation) {
            reject(new Error("Geolocation not supported"));
            return;
        }
        navigator.geolocation.getCurrentPosition(resolve, reject, {
            timeout: 5000,
            enableHighAccuracy: false,
        });
    });
}

// ═══════════════════════════════════════════════════════════════════
//  8. UTILITY FUNCTIONS
// ═══════════════════════════════════════════════════════════════════

function capitalize(str) {
    return str ? str.charAt(0).toUpperCase() + str.slice(1).toLowerCase() : "";
}

function getEmoji(emotion) {
    const map = {
        happy: "😄", sad: "😢", angry: "😡", fear: "😨",
        disgust: "🤢", surprise: "😲", neutral: "😐",
    };
    return map[emotion?.toLowerCase()] || "😐";
}

function getWeatherEmoji(main) {
    const map = {
        clear: "☀️", clouds: "☁️", rain: "🌧️", drizzle: "🌦️",
        thunderstorm: "⛈️", snow: "❄️", mist: "🌫️", fog: "🌫️",
        haze: "🌫️", smoke: "💨",
    };
    return map[main?.toLowerCase()] || "☀️";
}

// ── Toast Notifications ─────────────────────────────────────────────
function showToast(message, type = "info") {
    const toast = document.createElement("div");
    toast.className = `toast ${type}`;
    toast.textContent = message;
    dom.toastContainer.appendChild(toast);

    setTimeout(() => {
        toast.classList.add("removing");
        setTimeout(() => toast.remove(), 300);
    }, 3500);
}

// ── Like Button Logic ───────────────────────────────────────────────
async function fetchLikes() {
    try {
        const resp = await fetch("/api/likes");
        const data = await resp.json();
        if (data.likes) {
            state.likes = data.likes;
        }
    } catch (e) { }
}

function checkLikeStatus(song) {
    if (!song) {
        dom.likeBtn.style.display = "none";
        return;
    }
    dom.likeBtn.style.display = "flex";
    const key = song.toLowerCase().trim();
    const isLiked = state.likes.includes(key);

    dom.heartOutline.style.display = isLiked ? "none" : "block";
    dom.heartFilled.style.display = isLiked ? "block" : "none";
}

async function toggleLike() {
    if (state.currentIndex < 0 || state.currentIndex >= state.queue.length) return;

    const song = state.queue[state.currentIndex];
    const key = song.toLowerCase().trim();
    const isLiked = state.likes.includes(key);

    try {
        if (isLiked) {
            // Unlike
            await fetch("/api/like", {
                method: "DELETE",
                body: JSON.stringify({ song })
            });
            state.likes = state.likes.filter(k => k !== key);
            checkLikeStatus(song);
            showToast("Removed from liked songs");
        } else {
            // Like
            await fetch("/api/like", {
                method: "POST",
                body: JSON.stringify({ song, context: state.currentContext })
            });
            state.likes.push(key);
            checkLikeStatus(song);
            showToast("Added to liked songs ✨", "success");
        }
    } catch (e) {
        showToast("Failed to save like", "error");
    }
}

// ── Vibe Prompt Banner ──────────────────────────────────────────────
function showVibePrompt() {
    dom.vibePromptBanner.classList.add("show");
}

function hideVibePrompt() {
    dom.vibePromptBanner.classList.remove("show");
}

// ═══════════════════════════════════════════════════════════════════
//  9. EVENT LISTENERS
// ═══════════════════════════════════════════════════════════════════

// Player controls
dom.playPauseBtn.addEventListener("click", togglePlayPause);
dom.nextBtn.addEventListener("click", playNext);
dom.prevBtn.addEventListener("click", playPrev);
dom.likeBtn.addEventListener("click", toggleLike);
dom.volumeSlider.addEventListener("input", (e) => {
    if (state.ytReady) {
        state.ytPlayer.setVolume(parseInt(e.target.value, 10));
    }
});

// Progress bar click-to-seek
$(".progress-bar").addEventListener("click", (e) => {
    if (!state.ytReady || !state.isPlaying) return;
    const rect = e.target.getBoundingClientRect();
    const pct = (e.clientX - rect.left) / rect.width;
    const duration = state.ytPlayer.getDuration() || 0;
    state.ytPlayer.seekTo(pct * duration, true);
});

// Vibe Check modal
dom.vibeCheckBtn.addEventListener("click", openModal);
dom.modalClose.addEventListener("click", closeModal);
dom.modalOverlay.addEventListener("click", (e) => {
    if (e.target === dom.modalOverlay) closeModal();
});

// Vibe prompt banner
dom.promptContent.addEventListener("click", () => {
    hideVibePrompt();
    openModal();
});
dom.promptClose.addEventListener("click", hideVibePrompt);

// Camera & Upload options
dom.optCamera.addEventListener("click", startCameraScan);
dom.optUpload.addEventListener("click", startUpload);
dom.cancelScan.addEventListener("click", () => {
    stopCameraScan();
    dom.cameraView.style.display = "none";
    dom.modalOptions.style.display = "grid";
    dom.modalSubtitle.style.display = "block";
    dom.langSelector.style.display = "block";
});

// File input
dom.fileInput.addEventListener("change", (e) => {
    if (e.target.files[0]) handleFileUpload(e.target.files[0]);
});

// Drag and drop
dom.dropzone.addEventListener("dragover", (e) => {
    e.preventDefault();
    dom.dropzone.classList.add("drag-over");
});
dom.dropzone.addEventListener("dragleave", () => {
    dom.dropzone.classList.remove("drag-over");
});
dom.dropzone.addEventListener("drop", (e) => {
    e.preventDefault();
    dom.dropzone.classList.remove("drag-over");
    if (e.dataTransfer.files[0]) handleFileUpload(e.dataTransfer.files[0]);
});

// Keyboard shortcuts
document.addEventListener("keydown", (e) => {
    // Space = play/pause (only when not in modal)
    if (e.code === "Space" && !dom.modalOverlay.classList.contains("open")) {
        e.preventDefault();
        togglePlayPause();
    }
    // Escape = close modal
    if (e.code === "Escape") {
        closeModal();
    }
});

// ═══════════════════════════════════════════════════════════════════
//  10. INITIALIZATION
// ═══════════════════════════════════════════════════════════════════

function init() {
    fetchLikes();
    renderQueue();
    updateNavButtons();
    console.log("[VibeCheck] App initialized — waiting for vibe check...");
}

// Run on DOM ready
if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
} else {
    init();
}
