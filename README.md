# Cyber Security for All 

[![Python Version](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-Backend-092E20.svg?logo=django)](https://www.djangoproject.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> An accessible, engaging, and educational platform designed to protect vulnerable demographics from evolving cybersecurity threats.

## Table of Contents
- [About the Project](#-about-the-project)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Getting Started](#-getting-started)
- [Team Plato](#-team-plato)

## About the Project

Cybersecurity threats—such as phishing emails, scams, and data breaches—pose significant risks to everyday internet users. **Cyber Security for All** is a web application explicitly targeting two disproportionately affected demographics: older adults (50+) and younger users (under 15). 

Developed as part of the COM2042 module at the University of Surrey, this platform aims to bridge the digital literacy gap by providing an accessible, secure, and gamified learning environment.

## Key Features

- **Email Breach Checker:** Securely validates if an email address has been compromised using the Have I Been Pwned (HIBP) API (processed strictly in-memory).
- **AI Cybersecurity Chatbot:** An intelligent assistant powered by the Groq API (Llama 3.3 70B), with automatic failover to Google Gemini, providing cybersecurity guidance in simple, accessible language.
- **Gamified Quiz System:** Dynamically generated quizzes complete with a real-time leaderboard via WebSockets to encourage continuous learning.
- **Education Module:** Contextual, post-quiz explanations detailing the rationale behind correct answers and highlighting real-world threats like phishing.
- **Privacy First:** Strictly adheres to UK GDPR. Data collection for under-15s is limited to name and email only.

## Tech Stack

**Frontend:**
- HTML5 / CSS3 (Static templates rendered via Django)

**Backend:**
- **Framework:** Django (Python)
- **Real-Time:** Django Channels (WebSocket/SSE support)
- **Database:** MySQL

**External Services:**
- Have I Been Pwned (HIBP) API v3
- Groq API (Primary LLM)
- Google Gemini API (Fallback LLM)
- GitLab CI/CD Pipeline


## Getting Started

### Prerequisites
- Python 3.10+
- MySQL Server
- API Keys for Groq and HIBP

### Installation

1. **Clone the repository**
   ```bash
   git clone [https://gitlab.surrey.ac.uk/csee/com2042/2025-26-groups/team-plato.git](https://gitlab.surrey.ac.uk/csee/com2042/2025-26-groups/team-plato.git)
   cd team-plato
   ```

2. **Create and activate a virtual environment**
    ```bash
    python -m venv venv
    source venv/bin/activate # On windows use  `venv\Scripts\activate` 
    ```

3. **Install dependencies**
    ```bash
    pip install -r requirements.txt
    ```

4. **Configure Environment Variables**
    ```bash
    cp .env.example .env # `copy .env.example .env` if on windows
    ```
    Open the newly created .env file and replace the placeholder values with your actual API keys and database credentials.

    ```bash
    GROQ_API_KEY=your_groq_key
    GEMINI_API_KEY=your_gemini_key
    HIBP_API_KEY=your_hibp_key
    DB_NAME=teamplato_db
    DB_USER=your_db_user
    DB_PASSWORD=your_db_password
    ```

5. **Run Database Migrations**
    ```bash
    python manage.py migrate
    ```

6. **Start the Development Server**
    ```bash
    python manage.py runserver
    ```

## Team Plato

Developed by a dedicated six-person student group for the University of Surrey.

| Role | Team Member |
| :--- | :--- |
| **Project Manager** | Jon Moloney |
| **Vice Project Manager** | Dominykas Vaisiunas |
| **Technical Lead** | Kartik Dharmala |
| **Documentation Lead** | Adit Sharma |
| **Frontend / QA** | Yashovardhan Jain |
| **Backend / QA** | Khaleel Rahman |

**Project Sponsor:** Dany Varghese  
**Module Leader:** Andrew Crossan