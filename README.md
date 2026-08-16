# 🧠 NeuroClear
**Automated Dysarthria Screening & Speech Analysis Pipeline**

NeuroClear is a full-stack, AI-powered clinical tool designed to detect, assess, and rehabilitate motor speech disorders using objective acoustic metrics.

## 🚀 The Architecture
This application completely decouples language models from acoustic signal processing to provide deterministic, clinical-grade accuracy.

1. **Next.js Frontend:** A highly responsive, HIPAA-inspired UI architecture capturing raw MediaRecorder audio streams.
2. **FastAPI Backend:** A robust Python microservice handling concurrent tensor processing.
3. **Phonetic Alignment (Wav2Vec2):** Extracts Connectionist Temporal Classification (CTC) log-probabilities to isolate micro-articulatory decay at the phoneme level.
4. **Motor Tremor Detection (SciPy DSP):** Custom peak-finding algorithms isolate involuntary tremors via amplitude envelope extraction.
5. **Clinical Synthesis (Gemini 3.6 Flash):** Generates structured diagnostic rationales and targeted rehabilitation protocols based purely on the DSP metrics.

## 🛠️ Local Installation

**Prerequisites:** Python 3.10+, Node.js 18+, FFmpeg

1. **Clone & Setup Backend**
```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt  # or uv sync if you use uv
# Add your GEMINI_API_KEY to .env
uvicorn main:app --reload
```

2. **Clone & Setup Frontend**
```bash
cd frontend
npm install
npm run build
npm run dev
```

## 🧪 The Pipeline Workflow
The frontend initiates a HTTP multipart upload connection to the backend. The backend processes audio in a strict 5-stage pipeline, ensuring deterministic and objective analysis:

1. **Transcription:** Whisper ASR converts audio to text.
2. **Alignment:** Wav2Vec2 generates CTC log-probabilities per phoneme.
3. **Prosody Metrics:** Calculates rate (WPM) and pauses (Silent Duration).
4. **Tremor Detection:** SciPy DSP detects amplitude envelope peaks.
5. **Clinical Reasoning:** Gemini synthesizes findings into a structured report.

## 🤝 Reproducing Clinical Accuracy
To match the diagnostic consistency of the demo, ensure:
- **Frontend:** The `text` state in `index.tsx` is explicitly provided.
- **Backend:** `MOCK_API = false`. The `/analyze` endpoint must be reachable at `http://localhost:8000/analyze`.

---

## 🎯 The "Three-Domain" Verification Logic

The core of NeuroClear's clinical rigor is the **Intersection of Evidence** principle. The system is architected to prevent false positives by requiring objective signals from multiple independent domains before flagging a diagnosis.

### 1. Domain 1: Articulation (Phonetic Integrity)
*   **Source:** Wav2Vec2 CTC log-probabilities.
*   **Mechanism:** The frontend sends the raw audio and target text. The backend runs CTC alignment to generate a frame-level probability distribution. The frontend then calculates the mean CTC score across the entire transcript.
*   **Validation:**
    *   **False Positive Protection:** A single "bad word" (e.g., a word with high noise interference) is ignored. The system averages scores across the whole sentence, ensuring that only widespread articulatory decay affects the result.

### 2. Domain 2: Prosody (Rhythm & Fluency)
*   **Source:** Audio silence detection (SciPy `find_peaks` on RMS envelope).
*   **Mechanism:** The backend analyzes the audio waveform to detect "Silent Gaps" (delays > 300ms) and calculates the Speaking Rate (WPM).
*   **Validation:**
    *   **Normal Variation:** The system explicitly checks if the speaking rate is **"significantly slower than normal (130–180 WPM)."**
    *   **Threshold:** A rate below 80 WPM is required to trigger concern.
    *   **False Positive Protection:** The UI explicitly tells the user: *"A slow rate alone is NOT sufficient to conclude dysarthria. It may reflect deliberate reading pace."*

### 3. Domain 3: Motor Control (Tremor & Tremble)
*   **Source:** Audio envelope peak analysis (SciPy `find_peaks`).
*   **Mechanism:** For the word "WELL", the system specifically counts the number of significant acoustic peaks in the amplitude envelope.
*   **Validation:**
    *   **Normal Range:** A healthy speaker typically has **0–2 peaks**.
    *   **Pathological Threshold:** More than **3 distinct amplitude peaks** are flagged as a motor disfluency.
    *   **False Positive Protection:** Even if a tremor is detected, the `isDysarthric` function checks if **at least one other domain is also abnormal** (Rate OR Articulation) before confirming a diagnosis.

---

## 🧠 How the "Three-Domain" Logic Works in Practice

### Scenario A: False Positive (Normal User)
1.  **User:** Reads "The weather is nice." Slowly.
2.  **Articulation:** CTC scores are good (e.g., avg -0.5). *Domain OK.*
3.  **Prosody:** Rate is slow (60 WPM) because they are reading carefully. *Domain Flagged.*
4.  **Tremor:** 1 peak detected (normal). *Domain OK.*
5.  **Result:** Since **Prosody** is the ONLY flagged domain, the system concludes: *"No dysarthria detected."* The UI shows the "Slow Speaking" note but confirms "No motor speech disorder detected."

### Scenario B: True Positive (Patient with Parkinsonism)
1.  **User:** Reads "The weather is nice." Slowly and Shaky.
2.  **Articulation:** CTC scores are poor on several words. *Domain Flagged.*
3.  **Prosody:** Rate is very slow (45 WPM). *Domain Flagged.*
4.  **Tremor:** 6 peaks detected on "WELL" (shaking). *Domain Flagged.*
5.  **Result:** **All three domains** are abnormal. The system confirms: *"Dysarthria detected"* and generates a full clinical report.

