"""Research & Refinement Bot — Main Entry Point.

Interactive CLI that:
  1. Displays a welcome banner.
  2. Prompts the user for a question.
  3. Runs the input through Google Model Armor (safety guardrail).
  4. If approved, drives the ADK SequentialAgent pipeline:
        greeter → search → critique → refine
  5. Streams pipeline output to the terminal with agent labels.
  6. Loops back for the next question until the user types 'exit'.

Environment variables (set in .env):
  GEMINI_API_KEY  — Required. Google AI Studio API key.
  GEMINI_MODEL    — Optional. Defaults to 'gemini-2.5-flash'.
"""

import asyncio
import os
import sys

# ── Encoding fix for Windows consoles ────────────────────────────────────────
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from dotenv import load_dotenv

load_dotenv()

from google.adk.runners import InMemoryRunner
from google.genai import types

from research_agent.agents import root_agent
from research_agent.model_armor import screen_prompt

# ── ANSI colour helpers (degrade gracefully on non-ANSI terminals) ─────────
_ANSI = os.getenv("TERM", "").lower() not in ("", "dumb") or sys.platform == "win32"


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _ANSI else text


BOLD   = lambda t: _c("1", t)
GREEN  = lambda t: _c("32", t)
CYAN   = lambda t: _c("36", t)
YELLOW = lambda t: _c("33", t)
RED    = lambda t: _c("31", t)
BLUE   = lambda t: _c("34", t)
MAGENTA= lambda t: _c("35", t)
DIM    = lambda t: _c("2", t)

# ── Agent display names / colours ─────────────────────────────────────────────
AGENT_STYLE = {
    "greeter_agent":                    (CYAN,    "🤝 Greeter"),
    "search_agent":                     (BLUE,    "🔍 Search"),
    "critique_agent":                   (YELLOW,  "🧐 Critique"),
    "refine_agent":                     (GREEN,   "✨ Refine"),
    "research_refinement_pipeline":     (MAGENTA, "🔄 Pipeline"),
}

SESSION_COUNTER = 0


# ──────────────────────────────────────────────────────────────────────────────
def print_banner() -> None:
    """Print the welcome banner."""
    sep = "═" * 68
    print()
    print(BOLD(sep))
    print(BOLD("  🤖  Research & Refinement Bot  —  Powered by Google ADK"))
    print(BOLD(sep))
    print()
    print("  Pipeline stages:")
    print(f"    {CYAN('1. Greeter')}   — Welcomes you and confirms your question")
    print(f"    {BLUE('2. Search')}    — Finds an initial answer via Google Search")
    print(f"    {YELLOW('3. Critique')}  — Identifies weaknesses and improvement areas")
    print(f"    {GREEN('4. Refine')}    — Rewrites the answer into a polished response")
    print()
    print(f"  {DIM('Security: Google Model Armor guardrails active')}")
    print(f"  {DIM('Type  exit  or  quit  to end the session.')}")
    print(BOLD(sep))
    print()


# ──────────────────────────────────────────────────────────────────────────────
def _agent_label(agent_name: str) -> str:
    """Return a coloured, human-readable label for an agent."""
    if agent_name in AGENT_STYLE:
        colour_fn, display = AGENT_STYLE[agent_name]
        return colour_fn(f"[{display}]")
    return f"[{agent_name}]"


# ──────────────────────────────────────────────────────────────────────────────
async def run_pipeline(runner: InMemoryRunner, user_id: str, session_id: str,
                       question: str) -> None:
    """Drive the ADK SequentialAgent pipeline for one question."""

    new_message = types.Content(
        role="user",
        parts=[types.Part.from_text(text=question)],
    )

    current_author: str | None = None

    async for event in runner.run_async(
        user_id=user_id,
        session_id=session_id,
        new_message=new_message,
    ):
        # ── Tool execution notifications ──────────────────────────────────────
        func_calls = event.get_function_calls()
        if func_calls:
            for fc in func_calls:
                args_str = (
                    ", ".join(f"{k}='{v}'" for k, v in fc.args.items())
                    if fc.args else ""
                )
                print(
                    f"\n  {DIM(f'[Tool] {event.author} → {fc.name}({args_str})')}"
                )

        # ── Agent transfer / delegation events ───────────────────────────────
        if event.actions and event.actions.transfer_to_agent:
            dest = event.actions.transfer_to_agent
            print(
                f"\n  {DIM(f'[→ Handing off to {dest}]')}"
            )

        # ── Streamed text content ─────────────────────────────────────────────
        if event.content and event.content.parts:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    author = event.author or "agent"
                    if current_author != author:
                        print()                                 # blank line separator
                        print(_agent_label(author) + "  ", end="", flush=True)
                        current_author = author
                    print(part.text, end="", flush=True)

        # ── ADK errors ───────────────────────────────────────────────────────
        if event.error_code:
            print(
                f"\n  {RED(f'[ADK Error {event.error_code}] {event.error_message}')}"
            )

    print("\n")  # trailing newline after pipeline completes


# ──────────────────────────────────────────────────────────────────────────────
async def main_loop() -> None:
    """Main interactive loop."""
    global SESSION_COUNTER

    print_banner()

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    if not api_key:
        print(
            RED(
                "  ✗  No GEMINI_API_KEY found in environment / .env file.\n"
                "     Please add your Google AI Studio API key and restart.\n"
            )
        )
        return

    runner   = InMemoryRunner(agent=root_agent)
    user_id  = "research_user"

    while True:
        SESSION_COUNTER += 1
        session_id = f"session_{SESSION_COUNTER:04d}"

        # Create a fresh session per question so state is clean each time.
        await runner.session_service.create_session(
            app_name=runner.app_name,
            user_id=user_id,
            session_id=session_id,
        )

        # ── 1. Prompt for the question ────────────────────────────────────────
        try:
            raw = input(BOLD("❓ Your question: ")).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n\n{GREEN('  👋  Goodbye!  Thanks for using the Research & Refinement Bot.')}\n")
            break

        if not raw:
            print(f"  {DIM('(Please enter a question or type exit to quit.)')}")
            continue

        if raw.lower() in {"exit", "quit", "q", "bye"}:
            print(f"\n{GREEN('  👋  Goodbye!  Thanks for using the Research & Refinement Bot.')}\n")
            break

        # ── 2. Model Armor safety check ───────────────────────────────────────
        armor_result = screen_prompt(raw)
        if armor_result.is_blocked:
            print()
            print(
                RED(
                    f"  ⛔  [Model Armor — {armor_result.violation_category}]\n"
                    f"     {armor_result.blocked_message}\n"
                    f"     Reason: {armor_result.reason}"
                )
            )
            print()
            # Log the blocked attempt for visibility
            print(
                DIM(
                    f"  Filter: {armor_result.filter_name}  |  "
                    f"Session: {session_id}"
                )
            )
            print()
            continue

        # ── 3. Run the pipeline ───────────────────────────────────────────────
        print()
        print(BOLD(f"  🚀  Launching pipeline for session {session_id} …"))
        print(DIM("  " + "─" * 64))

        try:
            await run_pipeline(runner, user_id, session_id, raw)
        except Exception as exc:  # noqa: BLE001
            print(f"\n  {RED(f'[Unexpected error] {exc}')}\n")

        # ── 4. Ask whether to continue ────────────────────────────────────────
        try:
            again = input(DIM("  Ask another question? [Y/n]: ")).strip().lower()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{GREEN('  👋  Goodbye!')}\n")
            break

        if again in {"n", "no", "exit", "quit", "q"}:
            print(f"\n{GREEN('  👋  Goodbye!  Thanks for using the Research & Refinement Bot.')}\n")
            break

        print()


# ──────────────────────────────────────────────────────────────────────────────
def main() -> None:
    """Synchronous entrypoint."""
    try:
        asyncio.run(main_loop())
    except KeyboardInterrupt:
        print(f"\n{GREEN('  👋  Session interrupted.  Goodbye!')}\n")


if __name__ == "__main__":
    main()
