# 🧠 Cognitive Memory Analytics System

> A hackathon project that models human memory decay using piecewise exponential forgetting curves, ML-learned parameters, and simulated time progression — powered by an LLM quiz engine.

[![Live Demo](https://img.shields.io/badge/demo-live-brightgreen)](https://your-live-link.com)
[![License](https://img.shields.io/badge/license-MIT-blue)](./LICENSE)
[![HTTPS](https://img.shields.io/badge/https-enabled-green)](https://your-live-link.com)

---

## 📖 Project Description

The Cognitive Memory Analytics System is a full-stack web application that simulates and visualizes how human memory decays over time using the **Ebbinghaus forgetting curve**. Users upload PDF study materials, take AI-generated quizzes, and watch their personalized retention curves update in real time.

Unlike static flashcard tools, this system uses log-linear regression to **learn each user's personal decay rate (λ)** from their quiz history — making predictions progressively more accurate the more they study. A built-in time simulator lets users fast-forward days without waiting, enabling rapid experimentation and analysis.

---

## 🛠️ Tech Stack

**Frontend**
- HTML5 / CSS3 
- Jinja2 Templating
- Vanilla JavaScript (Canvas API — no external chart libraries)

**Backend**
- Python 3 / Flask
- SQLite (via `memory.db`, auto-created on first run)
- Werkzeug (password hashing)

**AI / ML**
- Groq API (`llama3-8b-8192`) — LLM quiz generation
- Custom log-linear regression for λ (decay rate) learning
- Piecewise exponential forgetting curve: `R(t) = R₀ · exp(-λ · Δt)`

**DevOps & Tools**
- Git & GitHub
- pip / requirements.txt

---

## ✨ Features

1. **Personalized Forgetting Curves** — Visualizes memory retention over time using a piecewise exponential model `R(t) = R₀ · exp(-λ · Δt)`. Each quiz attempt creates a new decay segment, producing a graph with visible "jumps" on re-study.

2. **ML-Learned Decay Parameters** — Uses log-linear regression on consecutive quiz attempts to learn each user's personal decay rate (λ) and retention boost (R₀). Falls back gracefully to λ=0.1 with fewer than 2 attempts.

3. **AI-Powered Quiz Generation** — Integrates with Groq's LLM API to auto-generate 5 multiple-choice questions directly from uploaded PDF content, with no manual question writing needed.

4. **PDF Upload & Text Extraction** — Users upload study materials as PDFs. The system extracts text via `pypdf` and stores it for on-demand quiz generation tied to each topic.

5. **Simulated Time Progression** — A UI slider (0–90 days) lets users advance simulated time without real waiting, enabling rapid testing of memory decay across different study schedules.

6. **Secure Multi-User Auth** — Session-based authentication with `pbkdf2:sha256` password hashing. All data is strictly scoped per user — no cross-user data leakage.

---

## 📸 Screenshots

**Dashboard — Retention Overview**
<img width="1896" height="992" alt="image" src="https://github.com/user-attachments/assets/f9b9926a-2ef7-42c2-b11a-b672d6c5557f" />


**Forgetting Curve Visualization**
<img width="1872" height="989" alt="image" src="https://github.com/user-attachments/assets/89238825-f513-44ac-89ca-33bf65005c62" />


**Quiz Interface**
<img width="1873" height="995" alt="image" src="https://github.com/user-attachments/assets/55d16f82-87ab-4276-b12d-30e566285fb9" />


---

## 🎥 Demo Video

▶️ [Watch the Demo](https://youtube.com/your-demo-link)

*The demo covers: uploading a PDF, taking a quiz, viewing the live forgetting curve update, and advancing simulated time to observe decay.*

---

## 🏗️ Architecture Diagram

<img width="861" height="620" alt="image" src="https://github.com/user-attachments/assets/e5de7942-0d2c-438c-9166-ad81be4a1317" />


> The system follows a clean service-layer architecture. Routes handle HTTP only; all business logic lives in `services/`. The forgetting curve, ML learning, and LLM quiz generation are fully decoupled into independent services.

---

## 📡 API Documentation

Base URL: `http://localhost:5000`

| Method | Endpoint              | Description                          | Auth Required |
|--------|-----------------------|--------------------------------------|---------------|
| POST   | `/auth/register`      | Register a new user                  | ❌ No          |
| POST   | `/auth/login`         | Log in and create session            | ❌ No          |
| POST   | `/auth/logout`        | End the current session              | ✅ Yes         |
| POST   | `/pdf/upload`         | Upload a PDF and extract text        | ✅ Yes         |
| GET    | `/pdf/<id>`           | View a topic and its quiz history    | ✅ Yes         |
| POST   | `/quiz/generate`      | Generate a quiz from a PDF topic     | ✅ Yes         |
| POST   | `/quiz/submit`        | Submit quiz answers and get score    | ✅ Yes         |
| GET    | `/curve/<topic_id>`   | Get forgetting curve data for topic  | ✅ Yes         |


---

## ⚙️ Installation

**Prerequisites:** Python 3.8+, pip, and a free [Groq API key](https://console.groq.com).

**1. Clone the repository**
```bash
git clone https://github.com/your-username/tinkherhacktrauma.git
cd tinkherhacktrauma
```

**2. Install dependencies**
```bash
pip install -r requirements.txt
```

**3. Set environment variables**
```bash
# Required — get a free key at https://console.groq.com
export GROQ_API_KEY=your_groq_api_key_here

# Optional — Flask session secret (defaults to dev key)
export SECRET_KEY=your_secret_key_here
```

> On Windows, use `set GROQ_API_KEY=...` instead of `export`.

---

## ▶️ Run Commands

**Start the app**
```bash
python app.py
```

Visit `http://localhost:5000` — the SQLite database (`memory.db`) is created automatically on first run.

> ⚠️ **Offline mode is NOT supported.** Quiz generation requires a live Groq API connection. The system will fail with a descriptive error rather than silently degrade if the API is unavailable.

---

## 📁 Project Structure

```
cognitive_memory/
├── app.py                           # Flask entry point (app factory)
├── requirements.txt
├── memory.db                        # SQLite database (auto-created)
│
├── database/
│   └── db.py                        # Schema, connection, init
│
├── services/                        # ALL business logic lives here
│   ├── forgetting_curve_service.py  # Piecewise R(t) = R₀·exp(-λ·Δt)
│   ├── learning_service.py          # ML: learn λ and R₀ from history
│   ├── time_simulation_service.py   # Simulated time management
│   ├── quiz_service.py              # Groq LLM quiz generation
│   ├── pdf_service.py               # pypdf extraction + storage
│   └── auth_service.py              # Password hashing + auth
│   └── profileservices.py
|   └── time_simulation_service.py

├── routes/                          # HTTP routes (no business logic)
│   ├── auth_routes.py
│   ├── pdf_routes.py
│   ├── quiz_routes.py
│   └── curve_routes.py
│   └── profileroutes.py
|
├── templates/                       # Jinja2 HTML templates
│   ├── base.html
│   ├── login.html
│   ├── register.html
│   ├── dashboard.html
│   ├── upload.html
│   ├── topic_view.html
│   ├── pre_quiz.html
│   ├── quiz.html
│   ├── result.html
│   └── curve.html
|   └── profile.html
|   └── start.html
│
├── static/
│   ├── css/style.css                # Dark theme UI
│   └── js/
│       ├── main.js                  # Global JS
│       └── curve.js                 # Canvas forgetting curve (no libs)


---

## 🔑 Environment Variables

| Variable        | Required | Description                                |
|-----------------|----------|--------------------------------------------|
| `GROQ_API_KEY`  | ✅ Yes    | Groq LLM API key for quiz generation       |
| `SECRET_KEY`    | ❌ No     | Flask session secret (defaults to dev key) |

Get a free Groq key at: [https://console.groq.com](https://console.groq.com)

---

## 🧬 Database Schema

| Table              | Purpose                                       |
|--------------------|-----------------------------------------------|
| `users`            | Auth records (hashed passwords)               |
| `pdfs`             | Uploaded PDFs (BLOB + extracted text)         |
| `quizzes`          | One record per quiz generation event          |
| `quiz_questions`   | MCQ questions per quiz                        |
| `attempts`         | Each attempt = one memory event               |
| `attempt_answers`  | Per-question answers per attempt              |
| `decay_segments`   | Piecewise curve segments (immutable)          |
| `learned_params`   | ML-learned λ per user + topic                 |

---

## 📐 Core Concepts

**Forgetting Curve (Piecewise Exponential)**

Each quiz attempt creates a new decay segment. Old segments are never modified — reattempts close the previous segment and open a new one, creating visible "jumps" in the graph:

```
R(t) = R₀ · exp(-λ · (t - t₀))
```

- `t₀` = time of the quiz attempt (simulated days)
- `R₀` = initial retention = quiz score (minimum 0.2)
- `λ` = decay rate (baseline: 0.1; personalized via ML)

**Machine Learning (Explainable, Lightweight)**

λ is learned using log-linear regression on consecutive attempt pairs:

```
λ = -log(score_next / score_prev) / Δt
```

Final λ = mean of all valid estimates. Falls back to λ=0.1 with fewer than 2 attempts. R₀ boost is tracked as an exponential moving average of score improvements.

---

## 🔒 Security

- Passwords hashed with `pbkdf2:sha256` via Werkzeug
- All database queries filter by `user_id` — users only see their own data
- No plain-text passwords stored anywhere
- Session-based auth via Flask cookie sessions

---

## 🤖 AI Tools Used

| Tool                    | Purpose                                           |
|-------------------------|---------------------------------------------------|
| Groq (llama3-8b-8192)   | Runtime quiz generation from uploaded PDF content |
| Claude                  | Documentation drafting and code review            |

> All AI-generated content was reviewed and validated by team members before use.

---

## 👥 Team Members

| Name        | Role                 | GitHub                                       |
|-------------|----------------------|----------------------------------------------|
| Krishnapriya K M   | Full-Stack Developer | https://github.com/KrishnapriyaKM05 |
| Rida Kareem | ML / Backend         | https://github.com/ridakareem         |

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](./LICENSE) file for details.

---

## 🌐 Live Link

🔗 **[https://your-project-url.com](https://your-project-url.com)**

> Hosted with HTTPS enabled. Loads with no console errors.
