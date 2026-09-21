# 🎙️ VoiceLedger

**A voice-first bookkeeping app for shopkeepers.** Speak a transaction, confirm it, and let AI keep your ledger, chase your dues, and flag risky customers, all without typing a single number.

> Built as a 5-day team sprint for the **AI-103** course.

---

## 📖 Table of Contents

- [Overview](#-overview)
- [Problem Statement](#-problem-statement)
- [Key Features](#-key-features)
- [Architecture](#-architecture)
- [Tech Stack](#-tech-stack)
- [Project Structure](#-project-structure)
- [Getting Started](#-getting-started)
- [Environment Variables](#-environment-variables)
- [API Reference](#-api-reference)
- [Usage Walkthrough](#-usage-walkthrough)
- [Roadmap](#-roadmap)
- [License](#-license)

---

## 🌟 Overview

Small shopkeepers often track credit (*udhaar*), sales, and payments in paper notebooks or memory. Typing into a bookkeeping app is slow and unfriendly, especially for people who are more comfortable speaking in their local language.

**VoiceLedger** lets a shopkeeper simply *say* what happened, for example *"Ramesh took 2 kg sugar, 90 rupees on credit"*. The app transcribes it, extracts the structured entry using AI agents, shows a confirmation card, and saves it to the ledger.

## 🎯 Problem Statement

- Manual bookkeeping is error-prone and time-consuming.
- Most bookkeeping apps assume typing fluency and English UI.
- Shopkeepers lose money to forgotten dues and unnoticed risky borrowers.

**VoiceLedger** solves this with voice input, a bilingual UI, and AI-driven reminders and risk insights.

---

## ✨ Key Features

| Feature | Description |
|---|---|
| 🎤 **Voice Recording** | One-tap record screen to capture a transaction by speaking. |
| ✅ **Confirmation Card** | AI-parsed entry (customer, item, amount, credit/paid) is shown for review before saving. |
| 📒 **Ledger List** | Searchable, chronological list of all transactions and customer balances. |
| 💬 **Ask Assistant** | Ask natural-language questions like *"How much does Ramesh owe me?"* |
| 🔔 **Reminder Generator** | Auto-drafts polite payment reminder messages for customers with pending dues. |
| ⚠️ **Risk Dashboard** | Highlights customers with high outstanding balances or late-payment patterns. |
| 🌐 **Two-Language UI** | Toggle between two languages for the interface. |

---

## 🏗️ Architecture

```
┌──────────────────────┐        ┌──────────────────────────────┐
│   React Frontend     │  HTTP  │        FastAPI Backend       │
│  (frontend/)         │◄──────►│          (backend/)          │
│                      │        │                              │
│ • Record screen      │        │ • REST endpoints             │
│ • Confirmation card  │        │ • Agent Framework            │
│ • Ledger list        │        │   ├─ Extraction agent        │
│ • Ask assistant      │        │   ├─ Query agent             │
│ • Reminder generator │        │   └─ Risk / reminder agent   │
│ • Risk dashboard     │        │ • MCP tools (ledger ops)     │
│ • Language toggle    │        │ • Database                   │
└──────────────────────┘        └──────────────────────────────┘
```

**Flow:** Voice → Transcription → Extraction agent → Confirmation card → Ledger write → Query / reminder / risk agents read from the ledger via MCP tools.

---

## 🛠️ Tech Stack

**Frontend**
- React
- Browser audio recording (MediaRecorder API)
- i18n for two-language support

**Backend**
- Python, FastAPI
- Agent Framework (multi-agent orchestration)
- Model Context Protocol (MCP) for exposing ledger tools to agents

**AI / Data**
- LLM for extraction, Q&A, reminders, and risk summaries
- Speech-to-text for voice transcription
- `<your database here>` for ledger storage

---

## 📁 Project Structure

```
voiceledger/
├── frontend/                 # React app
│   ├── src/
│   │   ├── components/
│   │   │   ├── RecordScreen
│   │   │   ├── ConfirmationCard
│   │   │   ├── LedgerList
│   │   │   ├── AskAssistant
│   │   │   ├── ReminderGenerator
│   │   │   ├── RiskDashboard
│   │   │   └── LanguageToggle
│   │   ├── i18n/
│   │   └── App.jsx
│   └── package.json
├── backend/                  # FastAPI + agents + MCP server
│   ├── app/
│   │   ├── main.py
│   │   ├── agents/
│   │   ├── mcp/
│   │   └── models/
│   └── requirements.txt
├── .env.example
└── README.md
```

> Adjust folder and file names to match your actual repo.

---

## 🚀 Getting Started

### Prerequisites

- Node.js 18+
- Python 3.10+
- API keys for your LLM and speech-to-text provider

### 1. Clone the repository

```bash
git clone https://github.com/<your-org>/voiceledger.git
cd voiceledger
```

### 2. Set up the backend

```bash
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

cp ../.env.example .env         # then fill in your keys
uvicorn app.main:app --reload --port 8000
```

Backend runs at `http://localhost:8000`. Interactive API docs are at `http://localhost:8000/docs`.

### 3. Set up the frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173` (or the port shown in your terminal).

---

## 🔐 Environment Variables

Create a `.env` file in `backend/`:

```env
# LLM / Agent
LLM_API_KEY=your_key_here
LLM_MODEL=your_model_name

# Speech-to-text
STT_API_KEY=your_key_here

# Database
DATABASE_URL=your_database_url

# App
FRONTEND_ORIGIN=http://localhost:5173
```

And in `frontend/` (if needed):

```env
VITE_API_BASE_URL=http://localhost:8000
```

> ⚠️ Never commit real keys. Keep `.env` in `.gitignore`.

---

## 📡 API Reference

> Update these to match your actual routes.

| Method | Endpoint                  | Description                                     |
|--------|---------------------------|-------------------------------------------------|
| `POST` | `/transcribe`             | Upload audio, receive transcript                |
| `POST` | `/extract`                | Parse transcript into a structured ledger entry |
| `POST` | `/ledger`                 | Save a confirmed entry                          |
| `GET`  | `/ledger`                 | List transactions (supports filters)            |
| `GET`  | `/customers/{id}/balance` | Get a customer's outstanding balance            |
| `POST` | `/ask`                    | Natural-language question over the ledger       |
| `POST` | `/reminders`              | Generate a payment reminder for a customer      |
| `GET`  | `/risk`                   | Risk summary across customers                   |

**Example: extract**

```http
POST /extract
Content-Type: application/json

{ "transcript": "Ramesh took 2 kg sugar, 90 rupees on credit" }
```

```json
{
  "customer": "Ramesh",
  "item": "Sugar",
  "quantity": "2 kg",
  "amount": 90,
  "type": "credit"
}
```

---

## 🧭 Usage Walkthrough

1. **Record** — Tap the mic and say the transaction.
2. **Confirm** — Review the parsed card; edit if needed, then confirm.
3. **Browse** — Open the ledger to see all entries and balances.
4. **Ask** — Type or speak a question in the assistant tab.
5. **Remind** — Generate a reminder for customers with dues.
6. **Monitor** — Check the risk dashboard for high-exposure customers.
7. **Switch language** — Use the toggle in the header.

<!-- Add screenshots here -->
<!-- ![Record Screen](docs/screenshots/record.png) -->

---
## 🗺️ Roadmap

- [ ] Offline-first mode for low-connectivity shops
- [ ] More regional languages
- [ ] Automated WhatsApp / SMS reminders
- [ ] Inventory tracking from voice entries
- [ ] Daily and weekly summary reports

---

## 📄 License

This project was created for educational purposes as part of the AI-103 course.
