# MeetFlow AI

> AI-powered meeting intelligence that transforms conversations into clear, accountable and trackable actions.

## 🚀 Overview

MeetFlow AI is an AI-powered meeting assistant that analyzes meeting transcripts and automatically extracts actionable tasks, decisions and important meeting information.

Instead of simply recording what was discussed, MeetFlow AI identifies unclear or incomplete responsibilities and uses an automated n8n clarification workflow to obtain missing information such as the task owner or deadline.

### Core Flow

Meeting Conversation
↓
AI Extraction
↓
Action Items & Decisions
↓
Confidence / Ambiguity Detection
↓
n8n Clarification
↓
Confirmed Owner & Deadline
↓
Trackable Action

## 🎯 Problem

Important responsibilities discussed during meetings are often unclear:

- Who is responsible?
- When should it be completed?
- Was the task actually confirmed?
- What decisions were made?
- What happens when information is missing?

MeetFlow AI addresses this gap by turning unstructured meeting conversations into structured and accountable actions.

## 💡 Key Features

- 📝 Meeting transcript and document input
- 🎙️ Audio meeting transcription
- 🤖 AI-powered action-item extraction
- 📌 Decision extraction
- 📊 Confidence scoring
- 🔍 Ambiguity and missing-information detection
- 👤 Owner and deadline tracking
- 🔄 Duplicate action-item detection
- 💬 Human-in-the-loop clarification
- ⚡ n8n automation integration
- 🔔 Real-time WebSocket updates
- 📅 Calendar integration
- 📄 CSV/PDF export
- 📈 Meeting and action-item statistics
- 🔐 JWT-based authentication

## 🔥 n8n Automation

n8n acts as the automation layer for ambiguous action items.

When MeetFlow AI detects an incomplete task:

```text
MeetFlow AI
     ↓
Ambiguous Action Item
     ↓
n8n Workflow
     ↓
Clarification Request
     ↓
Team Member Response
     ↓
Owner + Deadline
     ↓
MeetFlow AI
     ↓
Confirmed Action Item

🏗️ Architecture
                 ┌─────────────────────┐
                 │   Meeting / User    │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │   React Frontend    │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │   FastAPI Backend   │
                 └──────────┬──────────┘
                            ↓
                 ┌─────────────────────┐
                 │    AI Extraction    │
                 └──────────┬──────────┘
                            ↓
              ┌─────────────┴─────────────┐
              ↓                           ↓
      Action Items                    Decisions
              ↓
      Ambiguity Check
              ↓
       ┌──────┴──────┐
       │             │
    Complete      Ambiguous
       │             │
       ↓             ↓
    Database        n8n
                     ↓
              Clarification
                     ↓
               Database
                     ↓
              WebSocket Update
                     ↓
                React UI
🛠️ Tech Stack
Frontend
1.React 18

2.Vite

3.React Router

4.Lucide React

5.WebSocket

Backend
1.Python

2.FastAPI

3.SQLAlchemy

4.Pydantic

5.SQLite

6.JWT Authentication

7.APScheduler

8.WebSockets

AI
1.OpenAI API

2.Structured meeting extraction

3.Confidence-based ambiguity detection

4.Fallback extraction logic

Automation
1.n8n

2.Webhooks

3.Human-in-the-loop clarification

📂 Project Structure
MeetFlow-AI/
│
├── backend/
│   ├── app/
│   │   ├── routes/
│   │   ├── auth.py
│   │   ├── extraction.py
│   │   ├── llm.py
│   │   ├── models.py
│   │   ├── schemas.py
│   │   ├── scheduler.py
│   │   ├── transcription.py
│   │   └── websocket_manager.py
│   │
│   ├── main.py
│   ├── requirements.txt
│   └── tests/
│
├── frontend/
│   ├── src/
│   │   ├── components/
│   │   ├── context/
│   │   └── pages/
│   ├── package.json
│   └── vite.config.js
│
├── .env.example
├── .gitignore
└── README.md

