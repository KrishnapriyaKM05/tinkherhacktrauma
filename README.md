# 🧠 Cognitive Memory Analytics System

> A hackathon project modeling human memory decay using piecewise exponential forgetting curves, ML-learned parameters, and simulated time progression.

---

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Set your Groq API key (REQUIRED for quiz generation)
export GROQ_API_KEY=your_groq_api_key_here

# 3. Run the app
python app.py
# Visit http://localhost:5000
```

---

## 🔑 Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `GROQ_API_KEY` | **Yes** | Groq LLM API key for quiz generation |
| `SECRET_KEY` | No | Flask session key (default: dev key) |

Get a free Groq key at: https://console.groq.com

---

## 🏗️ Architecture

```
cognitive_memory/
├── app.py                          # Flask entry point (factory)
├── requirements.txt
├── memory.db                       # SQLite database (auto-created)
│
├── database/
│   └── db.py                       # Schema, connection, init
│
├── services/                       # ALL business logic lives here
│   ├── forgetting_curve_service.py # Piecewise R(t) = R₀·exp(-λ·Δt)
│   ├── learning_service.py         # ML: learn λ and R₀ from history
│   ├── time_simulation_service.py  # Simulated time management
│   ├── quiz_service.py             # Groq LLM quiz generation
│   ├── pdf_service.py              # pypdf extraction + storage
│   └── auth_service.py             # Password hashing + auth
│
├── routes/                         # HTTP routes (no logic)
│   ├── auth_routes.py
│   ├── pdf_routes.py
│   ├── quiz_routes.py
│   └── curve_routes.py
│
├── templates/                      # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html / register.html
│   ├── dashboard.html
│   ├── upload.html
│   ├── topic_view.html
│   ├── pre_quiz.html
│   ├── quiz.html
│   ├── result.html
│   └── curve.html
│
└── static/
    ├── css/style.css               # Dark theme UI
    └── js/
        ├── main.js                 # Global JS
        └── curve.js                # Canvas forgetting curve (no libs)
```

---

## 📐 Core Concepts

### Forgetting Curve (Piecewise Exponential)

Each quiz attempt creates a **decay segment**:

```
R(t) = R₀ · exp(-λ · (t - t₀))
```

- `t₀` = time of the quiz attempt (simulated days)
- `R₀` = initial retention = quiz score (min 0.2)
- `λ` = decay rate (baseline: 0.1; ML-learned: personalized)

**Piecewise structure**: Old segments are NEVER modified. Each reattempt closes the previous segment and opens a new one — creating a visible "jump" in the graph.

### Machine Learning (Explainable, Simple)

ML learns λ using **log-linear regression** on consecutive attempt pairs:

```
λ = -log(score_next / score_prev) / Δt
```

Final λ = mean of all valid estimates. Falls back to λ=0.1 with <2 attempts.

R₀ boost is tracked as an **exponential moving average** of score improvements.

### Simulated Time

Time is controlled via a UI slider (0–90 days). No real-time waiting. Each attempt stores its simulated time.

---

## 🧬 Database Schema

| Table | Purpose |
|-------|---------|
| `users` | Auth records (hashed passwords) |
| `pdfs` | Uploaded PDFs (BLOB + extracted text) |
| `quizzes` | One record per quiz generation |
| `quiz_questions` | MCQs per quiz |
| `attempts` | Each attempt = one memory event |
| `attempt_answers` | Per-question answers |
| `decay_segments` | Piecewise curve segments (immutable) |
| `learned_params` | ML-learned λ per user+topic |

---

## 🤖 LLM Dependency

**Provider**: Groq  
**Model**: `llama3-8b-8192`  
**Usage**: Generates 5 MCQ questions per quiz attempt  
**Offline mode**: NOT supported  

Quiz generation is clearly separated in `services/quiz_service.py`. If the API is unavailable, the system fails with a descriptive error rather than silently degrading.

---

## 🔒 Security Notes

- Passwords hashed with `pbkdf2:sha256` via Werkzeug
- Users only see their own data (all queries filter by `user_id`)
- No plain-text passwords stored anywhere
- Session-based auth (Flask cookie sessions)
