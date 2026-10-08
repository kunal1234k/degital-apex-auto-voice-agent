"""Digital Apex Automation Agency - AI Voice Agent (live demo).

Stack: VideoSDK Agents + Google Gemini Live (speech-to-speech).
The agent talks to a caller in Hinglish/Hindi/English, explains the agency's
services and packages, and saves a real lead (CSV + optional webhook + optional
Telegram alert to the owner) through the `save_lead` tool.
"""

import asyncio
import csv
import json
import logging
import os
import traceback
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

from videosdk.agents import (
    Agent,
    AgentSession,
    JobContext,
    Pipeline,
    RoomOptions,
    WorkerJob,
    function_tool,
)
from videosdk.agents.plugins import GeminiLiveConfig, GeminiRealtime

load_dotenv()
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("digital-apex-voice")

AGENT_NAME = os.getenv("AGENT_NAME", "Aanya")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-live-preview")
GEMINI_VOICE = os.getenv("GEMINI_VOICE", "Leda")

LEADS_FILE = Path(os.getenv("LEADS_FILE", "data/leads.csv"))
LEAD_FIELDS = [
    "timestamp_utc",
    "name",
    "business_name",
    "phone",
    "email",
    "service",
    "budget",
    "notes",
]

INSTRUCTIONS = f"""
You are {AGENT_NAME}, a warm and professional voice assistant of Digital Apex Automation Agency.
You are speaking on a live phone-style voice call, so keep every reply short and natural.

=== IDENTITY AND HONESTY ===
- Your name is {AGENT_NAME}. You work for Digital Apex Automation Agency.
- If the caller asks whether you are a human or a bot, say honestly that you are the agency's AI voice assistant,
  and that this very call is a live demo of the kind of voice agent the agency builds for businesses.
- Never claim to be human. Never invent facts, prices, offers or client names that are not listed below.
- If you do not know something, say the team will confirm it and offer to take the caller's details.

=== STYLE ===
- Maximum 2 short sentences per reply, then stop and let the caller speak.
- Default language is simple Hinglish (Hindi in everyday speech with common English words), friendly and respectful.
- Ask at the start which language the caller prefers: Hindi, English or Hinglish, and then stay in that language.
- Do not read long lists. Mention at most 2-3 items at a time, then ask what the caller needs.
- Speak prices clearly, for example "fourteen thousand nine hundred ninety nine rupees".
- Stay on topic: the agency's services. Politely steer back if the caller asks about unrelated things
  such as politics, religion, hacking or anything illegal.

=== START OF CALL ===
The greeting is spoken for you automatically. Wait for the caller to reply, then continue.

=== ABOUT DIGITAL APEX AUTOMATION AGENCY ===
A growth and automation agency that helps local and small businesses get more customers using
paid ads, AI automation, local SEO, and modern websites.

Services:
- Paid Traffic (Meta/Instagram/Google ads)
- AI Automation: WhatsApp chatbots, AI voice agents like this one, lead capture and instant owner alerts
- Local SEO and Google Business Profile growth
- Web and Design: premium animated websites with a smart admin panel

Packages (always say that final scope can be adjusted to the business):
- Starter: Rs 14,999 one time
- Growth: Rs 24,999 per month plus ad spend
- Automation: Rs 17,999 per month
- Apex Scale: Rs 39,999 per month plus ad spend

NFC Google Review Card: a set of 2 cards for Rs 1,999. The customer taps the card with their phone and the
Google review page of the business opens directly. No app is needed.

Pricing for custom things (for example a custom AI voice agent for the caller's own business) depends on
the requirements. Do not quote a number for it. Say the team will prepare a proper quote after understanding
the business.

Contact: WhatsApp or call +91 93503 59379, email degitaljk5@gmail.com.

=== WHAT TO DO ON THE CALL ===
1. Understand the caller's business and what they want: more customers, automation, a website, reviews, etc.
2. Recommend the most relevant service or package in one or two sentences.
3. If the caller is interested or asks for a demo or quotation, collect these details,
   ONE question at a time:
   - Name
   - Business name
   - Phone number (repeat the digits back and ask for confirmation)
   - Email address (optional, skip if the caller does not want to share)
   - Which service they need
   - Approximate budget (optional)
4. When you have at least the name, phone number and service, call the save_lead tool.
   Call it only once per caller, after the details are confirmed.
5. After the tool succeeds, tell the caller that the team will contact them shortly on WhatsApp or call.

=== COMMON QUESTIONS ===
- "How long will it take?" -> A website or chatbot usually takes a few days to a couple of weeks depending
  on scope; the team confirms the exact timeline after understanding the requirement.
- "Can I get a demo?" -> Yes. Collect details and save the lead so the team can arrange a demo.
- "Where are you located?" -> The agency serves clients across India. Do not give any address.

=== ENDING ===
When the caller is done, say a short warm goodbye, for example:
"Thank you for speaking with Digital Apex Automation Agency. Have a great day!"
"""


def _write_lead_row(row: dict) -> None:
    LEADS_FILE.parent.mkdir(parents=True, exist_ok=True)
    is_new = not LEADS_FILE.exists()
    with LEADS_FILE.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=LEAD_FIELDS)
        if is_new:
            writer.writeheader()
        writer.writerow(row)


def _post_json(url: str, payload: dict) -> None:
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        resp.read()


def _send_telegram(text: str) -> None:
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode("utf-8")
    with urllib.request.urlopen(urllib.request.Request(url, data=data), timeout=10) as resp:
        resp.read()


class DigitalApexVoiceAgent(Agent):
    def __init__(self):
        super().__init__(instructions=INSTRUCTIONS)

    async def on_enter(self):
        await self.session.say(
            f"Namaste! Main {AGENT_NAME} bol rahi hoon, Digital Apex Automation Agency se. "
            "Bataiye, main aapki kya madad kar sakti hoon? "
            "Aap Hindi, English ya Hinglish, jisme comfortable ho, usme baat kar sakte hain."
        )

    async def on_exit(self):
        await self.session.say(
            "Digital Apex Automation Agency se baat karne ke liye shukriya. Aapka din shubh ho!"
        )

    @function_tool
    async def save_lead(
        self,
        name: str,
        phone: str,
        service: str,
        business_name: str = "",
        email: str = "",
        budget: str = "",
        notes: str = "",
    ) -> dict:
        """Save a confirmed lead after the caller has shared their details.

        Call this once per caller, only after the caller confirmed the details.
        name: caller's name. phone: phone number with digits only or with +91.
        service: the service the caller wants. business_name, email, budget and
        notes are optional; notes can hold a one-line summary of the requirement.
        """
        row = {
            "timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "name": name.strip(),
            "business_name": business_name.strip(),
            "phone": phone.strip(),
            "email": email.strip(),
            "service": service.strip(),
            "budget": budget.strip(),
            "notes": notes.strip(),
        }

        try:
            await asyncio.to_thread(_write_lead_row, row)
        except Exception:
            log.exception("Could not write lead to CSV")
            return {"status": "error", "message": "Lead could not be saved right now."}

        log.info("Lead saved: %s", row)

        webhook = os.getenv("LEAD_WEBHOOK_URL")
        if webhook:
            try:
                await asyncio.to_thread(_post_json, webhook, row)
            except Exception:
                log.exception("Lead webhook failed")

        try:
            await asyncio.to_thread(
                _send_telegram,
                "New voice-agent lead\n"
                f"Name: {row['name']}\n"
                f"Business: {row['business_name'] or '-'}\n"
                f"Phone: {row['phone']}\n"
                f"Email: {row['email'] or '-'}\n"
                f"Service: {row['service']}\n"
                f"Budget: {row['budget'] or '-'}\n"
                f"Notes: {row['notes'] or '-'}",
            )
        except Exception:
            log.exception("Telegram alert failed")

        return {"status": "saved", "message": "Lead saved. The team will contact the caller soon."}


async def start_session(context: JobContext):
    model = GeminiRealtime(
        model=GEMINI_MODEL,
        # api_key is read from GOOGLE_API_KEY in the environment
        config=GeminiLiveConfig(
            voice=GEMINI_VOICE,
            response_modalities=["AUDIO"],
        ),
    )

    pipeline = Pipeline(llm=model)

    session = AgentSession(
        agent=DigitalApexVoiceAgent(),
        pipeline=pipeline,
    )

    await session.start(wait_for_participant=True, run_until_shutdown=True)


def make_context() -> JobContext:
    return JobContext(
        room_options=RoomOptions(
            name="Digital Apex Voice Agent",
            playground=True,
        )
    )


if __name__ == "__main__":
    try:
        job = WorkerJob(entrypoint=start_session, jobctx=make_context)
        log.info("Starting Digital Apex Voice Agent...")
        job.start()
    except KeyboardInterrupt:
        log.info("Shutting down...")
    except Exception:
        traceback.print_exc()
