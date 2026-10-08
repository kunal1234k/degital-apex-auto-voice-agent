# Digital Apex Voice Agent (Live Demo)

Real-time AI voice agent for Digital Apex Automation Agency, built with VideoSDK Agents and Google Gemini Live.
It talks in Hinglish/Hindi/English, explains services and packages, and saves leads through a real `save_lead` tool.

## Setup (Python 3.12+)

```bash
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env             # then fill GOOGLE_API_KEY and VIDEOSDK_AUTH_TOKEN
python main.py
```

When it starts, the terminal prints a **playground link**. Open it in the browser, allow the microphone and talk to the agent.
You can also try `python main.py console` to talk through your computer's own mic and speaker.

## Where do the leads go?

- Always: `data/leads.csv`
- Optional: Telegram alert to the owner (`TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`)
- Optional: JSON POST to a webhook (`LEAD_WEBHOOK_URL`)

## Easy customisations

| What | Where |
|---|---|
| Name, voice, model | `AGENT_NAME`, `GEMINI_VOICE`, `GEMINI_MODEL` in `.env` |
| Services, prices, contact, tone | `INSTRUCTIONS` in `main.py` |
| Opening and closing lines | `on_enter` and `on_exit` in `main.py` |
| Extra tools (booking, WhatsApp, CRM) | add another `@function_tool` method in `DigitalApexVoiceAgent` |
