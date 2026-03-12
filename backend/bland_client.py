from __future__ import annotations

import asyncio
import logging
import os
import re
from typing import Callable

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BLAND_API_KEY = os.getenv("BLAND_API_KEY", "")
BLAND_BASE_URL = "https://api.bland.ai/v1"

ROOT_TASK = """You are calling an automated phone system (IVR). Your job is to listen and discover the menu options.

RULES — follow strictly:
1. Start SILENT. Most IVRs read their menu after a pause.
2. If the system asks an open-ended question like "What can I help you with?" — say ONLY: "What are my options?" ONE TIME.
3. Once the system starts listing options — STOP TALKING. Stay completely silent and just listen.
4. After you hear the options, stay silent. Do NOT ask for more options, do NOT say "even more options", do NOT say "more information". Just wait silently.
5. If the system asks a yes/no question — say "no" and nothing else.
6. NEVER say: representative, agent, operator, transfer, person, help.
7. NEVER press any buttons. NEVER select any menu option.
8. Wait through ALL pauses, hold music, silence, and advertisements.
9. You may say "What are my options?" at MOST ONCE per call. After that, stay silent no matter what.

Your goal: hear the menu options, then stay silent until the call ends."""

def dtmf_branch_task(keys: str) -> str:
    """Generate a task for navigating a DTMF IVR by pressing keys after hearing the menu."""
    # Split compound paths like "1w3" into individual keys ["1", "3"]
    individual_keys = [k for k in keys.split("w") if k]
    last_key = individual_keys[-1] if individual_keys else keys

    return f"""You are calling an automated phone system (IVR). Your job is to navigate to a specific submenu and listen to its options.

STEP 1: Wait and listen. The IVR will play a greeting and read menu options. Stay SILENT during this.
STEP 2: Once you hear the menu options being read (e.g. "Press 1 for..., Press 2 for..."), wait until the FULL menu is read.
STEP 3: After the menu is fully read, press button {last_key}. Press it ONCE only.
STEP 4: After pressing {last_key}, go COMPLETELY SILENT. Listen to whatever submenu or message plays next.

RULES:
- Do NOT press any button until the system has finished reading the menu options.
- After pressing {last_key}, NEVER press any more buttons.
- If the system asks an open-ended question like "What can I help you with?" — say ONLY: "What are my options?" ONE TIME, then go silent.
- If asked a yes/no question — say "no" and nothing else.
- NEVER say: representative, agent, operator, transfer, person, help.
- Wait through ALL pauses, hold music, and silence.

Your goal: press {last_key} at the right time, then hear the COMPLETE submenu options."""


def voice_branch_task(option_to_say: str) -> str:
    """Generate a task for navigating a voice-based IVR by speaking an option."""
    return f"""You are calling an automated phone system (IVR). Your job is to select ONE specific option and then listen to the submenu.

When the system answers and asks what you need, say EXACTLY: "{option_to_say}"

After selecting that option:
- Listen carefully to whatever menu or message plays next
- Be COMPLETELY SILENT after selecting the option — just listen
- Do NOT select any further options, do NOT ask for more options
- NEVER say "representative", "agent", or "operator"
- NEVER hang up early
- If asked a yes/no question, say "no"
- If asked to describe your issue again, repeat ONLY: "{option_to_say}"

Your goal: navigate to "{option_to_say}" and hear the COMPLETE list of submenu options available there."""


async def place_call(
    phone_number: str,
    task: str | None = None,
    dtmf_sequence: str | None = None,
    max_duration: int = 60,
    retries: int = 2,
) -> dict:
    """Place a call via Bland AI with retry on transient errors.

    For DTMF navigation:
    - Single key (e.g. "3"): agent waits for menu, then presses the key
    - Compound path (e.g. "1w3"): precall_dtmf_sequence handles prefix keys ("1"),
      agent presses the last key ("3") after hearing the submenu
    """
    if task is None:
        task = dtmf_branch_task(dtmf_sequence) if dtmf_sequence else ROOT_TASK

    payload: dict = {
        "phone_number": phone_number,
        "task": task,
        "model": "base",
        "max_duration": max_duration,
        "wait_for_greeting": True,
        "record": True,
        "voicemail_detection": "disabled",
    }

    # For compound paths (depth 2+), use precall_dtmf for the prefix keys
    # The agent will press the last key after hearing the submenu
    if dtmf_sequence and "w" in dtmf_sequence:
        prefix_keys = dtmf_sequence.rsplit("w", 1)[0]  # "1w3" -> "1", "1w2w3" -> "1w2"
        payload["precall_dtmf_sequence"] = "wwwwwwwwww" + prefix_keys

    last_error = None
    for attempt in range(retries + 1):
        try:
            async with httpx.AsyncClient() as client:
                resp = await client.post(
                    f"{BLAND_BASE_URL}/calls",
                    json=payload,
                    headers={"authorization": BLAND_API_KEY},
                    timeout=30,
                )
                if resp.status_code == 429:
                    wait = min(2 ** attempt * 2, 10)
                    logger.warning(f"Rate limited (429), waiting {wait}s (attempt {attempt + 1})")
                    await asyncio.sleep(wait)
                    continue
                resp.raise_for_status()
                return resp.json()
        except httpx.HTTPStatusError as e:
            last_error = e
            if e.response.status_code >= 500:
                wait = 2 ** attempt
                logger.warning(f"Server error {e.response.status_code}, retry in {wait}s")
                await asyncio.sleep(wait)
                continue
            raise
        except (httpx.ConnectError, httpx.TimeoutException) as e:
            last_error = e
            wait = 2 ** attempt
            logger.warning(f"Connection error: {e}, retry in {wait}s")
            await asyncio.sleep(wait)
            continue

    raise last_error or Exception("place_call failed after retries")


async def get_call(call_id: str) -> dict:
    """Get call details including transcript, status, cost."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BLAND_BASE_URL}/calls/{call_id}",
            headers={"authorization": BLAND_API_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def stop_call(call_id: str) -> dict:
    """End an active call immediately."""
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{BLAND_BASE_URL}/calls/{call_id}/stop",
            headers={"authorization": BLAND_API_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        logger.info(f"Stopped call {call_id[:8]}...")
        return resp.json()


async def get_events(call_id: str) -> list[dict]:
    """Get the event stream for a call."""
    async with httpx.AsyncClient() as client:
        resp = await client.get(
            f"{BLAND_BASE_URL}/calls/{call_id}/events",
            headers={"authorization": BLAND_API_KEY},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()


async def detect_human_transfer(transcript: str) -> bool:
    """Use Claude to intelligently determine if the transcript indicates a human transfer.

    Returns True if a real human has picked up or the IVR is transferring to a live agent.
    Fast — uses Haiku for ~200ms response time.
    """
    if not transcript or len(transcript.strip()) < 20:
        return False

    import anthropic

    client = anthropic.AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))
    try:
        resp = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=10,
            messages=[{"role": "user", "content": f"""Does this IVR transcript show that a REAL HUMAN representative/agent has picked up or is being connected?

Answer ONLY "yes" or "no". Default to "no".

ONLY answer "yes" if the transcript contains the words "representative", "agent", or "operator" in the context of being transferred to one, OR a real human is clearly speaking conversationally (not scripted IVR).

ALWAYS answer "no" if:
- The transcript only shows automated menus ("Press 1 for...", "Press 2 for...")
- The system says "connect your call" or "connect you" WITHOUT mentioning a representative/agent/operator — this is just an automated fallback, NOT a human transfer
- The system says "we have not received a valid response" — this is a timeout
- The transcript shows the call ending or the agent saying "goodbye"

Transcript (last 500 chars):
{transcript[-500:]}"""}],
        )
        answer = resp.content[0].text.strip().lower()
        logger.info(f"Human transfer check: '{answer}' for transcript ending: ...{transcript[-80:]}")
        return answer.startswith("yes")
    except Exception as e:
        logger.warning(f"Human transfer detection failed: {e}")
        return False


async def wait_for_call(
    call_id: str,
    on_transcript: Callable[[str], None] | None = None,
    poll_interval: float = 3.0,
    timeout: float = 180.0,
) -> dict:
    """Wait for a call to complete by polling call status.

    If on_transcript is provided, sends partial transcript text as it grows.
    Checks for human transfers using Claude when transcript grows significantly.
    """
    elapsed = 0.0
    last_status = ""
    last_real_len = 0  # Length of transcript excluding agent-actions
    stale_polls = 0  # Count polls where real transcript didn't grow
    STALE_LIMIT = 5  # Stop call after this many stale polls (~15s of silence)
    last_transfer_check_len = 0  # Only re-check after significant transcript growth

    while elapsed < timeout:
        data = await get_call(call_id)
        status = data.get("status", "")

        if status != last_status:
            logger.info(f"Call {call_id[:8]}... status: {status} (elapsed: {elapsed:.0f}s)")
            last_status = status

        # Stream partial transcript to frontend
        transcript = data.get("concatenated_transcript", "") or ""

        # Strip agent-actions for growth detection — "[Waiting]" inflates transcript without real content
        real_transcript = re.sub(r'agent-action:\s*\[.*?\]\s*', '', transcript).strip()
        real_len = len(real_transcript)

        if real_len > last_real_len:
            last_real_len = real_len
            stale_polls = 0
            if on_transcript:
                try:
                    result = on_transcript(transcript)
                    if asyncio.iscoroutine(result):
                        await result
                except Exception:
                    pass

            # Real-time human transfer detection disabled — too many false positives.
            # Post-call detection via transcript_parser.py still active.
            # if real_len - last_transfer_check_len > 50:
            #     last_transfer_check_len = real_len
            #     if await detect_human_transfer(transcript):
            #         logger.info(f"Call {call_id[:8]}... HUMAN TRANSFER detected by Claude — stopping call")
            #         try:
            #             await stop_call(call_id)
            #         except Exception:
            #             logger.warning(f"Failed to stop call {call_id[:8]}..., it may have already ended")
            #         await asyncio.sleep(2)
            #         data = await get_call(call_id)
            #         data["_human_transfer"] = True
            #         return data
        elif real_transcript:
            # Real transcript exists but hasn't grown
            stale_polls += 1

        # Early termination: transcript stopped growing (IVR likely hung up)
        if stale_polls >= STALE_LIMIT and transcript:
            logger.info(f"Call {call_id[:8]}... transcript stale for {stale_polls} polls — stopping call")
            try:
                await stop_call(call_id)
            except Exception:
                pass
            await asyncio.sleep(2)
            return await get_call(call_id)

        if status in ("completed", "failed", "busy", "no-answer", "canceled", "error"):
            logger.info(f"Call {call_id[:8]}... finished with status: {status}")
            return data

        await asyncio.sleep(poll_interval)
        elapsed += poll_interval

    logger.warning(f"Call {call_id[:8]}... timed out after {timeout}s (last status: {last_status})")
    return await get_call(call_id)
