"""ADK Agent Definitions — Research & Refinement Bot.

Agent pipeline (executed sequentially by SequentialAgent):
  greeter_agent  → Welcomes user, collects and restates the question.
  search_agent   → Uses google_search to produce an initial factual answer.
  critique_agent → Evaluates the answer and lists specific improvements.
  refine_agent   → Rewrites the answer incorporating all critique suggestions.

The root_agent is a SequentialAgent that drives the pipeline in order.
Session state keys used for cross-agent data sharing:
  user_question   – The user's original question (set by greeter_agent).
  initial_answer  – Search-grounded first-draft answer (set by search_agent).
  critique_notes  – Numbered list of critique suggestions (set by critique_agent).
  final_answer    – Polished, refined answer (set by refine_agent).
"""

import os
import warnings
from dotenv import load_dotenv

# SequentialAgent is deprecated in ADK 2.x in favour of Workflow, but Workflow
# cannot yet be used as an LlmAgent sub-agent.  Suppress the deprecation
# warning until the ADK provides a complete replacement.
warnings.filterwarnings(
    "ignore",
    message="SequentialAgent is deprecated",
    category=DeprecationWarning,
)

from google.adk.agents import LlmAgent, SequentialAgent
from google.adk.tools import google_search

load_dotenv()

# ──────────────────────────────────────────────────────────────────────────────
# Model selection
# ──────────────────────────────────────────────────────────────────────────────
MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# Allow google_search alongside agent delegation (multi-tool guard bypass)
google_search.bypass_multi_tools_limit = True

# ──────────────────────────────────────────────────────────────────────────────
# Agent 1 — Greeter
# ──────────────────────────────────────────────────────────────────────────────
_GREETER_INSTRUCTION = """
You are the Greeter Agent in a Research & Refinement pipeline.

Your ONLY responsibilities:
1. Warmly welcome the user to the Research & Refinement Bot.
2. Confirm or restate the user's question clearly so they know it was understood.
3. Set the session state key 'user_question' to the user's question exactly as received.
4. Briefly explain that the pipeline will:
   a) Search Google for an answer.
   b) Critique that answer.
   c) Refine it into a polished final response.

Do NOT attempt to answer the question yourself.
Output a short, friendly introduction followed by a restatement of the question.
"""

greeter_agent = LlmAgent(
    name="greeter_agent",
    model=MODEL,
    description=(
        "Welcomes the user, acknowledges their question, and explains the "
        "pipeline steps before handing off to the search agent."
    ),
    instruction=_GREETER_INSTRUCTION,
    output_key="user_question",   # persists the question for downstream agents
)

# ──────────────────────────────────────────────────────────────────────────────
# Agent 2 — Search Agent
# ──────────────────────────────────────────────────────────────────────────────
_SEARCH_INSTRUCTION = """
You are the Search Agent in a Research & Refinement pipeline.

Your ONLY responsibilities:
1. Retrieve the user's question from session state key 'user_question'.
2. Use the 'google_search' tool to find current, accurate information that
   answers the question.
3. Synthesize the search results into a clear, factual, well-structured
   initial answer.  Include relevant facts, data points, and sources where
   available.
4. Write your complete initial answer to session state key 'initial_answer'.

Do NOT critique or refine — just produce the best factual answer you can
from the search results.
"""

search_agent = LlmAgent(
    name="search_agent",
    model=MODEL,
    description=(
        "Uses google_search to find real-time information and produces the "
        "initial factual answer to the user's question."
    ),
    instruction=_SEARCH_INSTRUCTION,
    tools=[google_search],
    output_key="initial_answer",
)

# ──────────────────────────────────────────────────────────────────────────────
# Agent 3 — Critique Agent
# ──────────────────────────────────────────────────────────────────────────────
_CRITIQUE_INSTRUCTION = """
You are the Critique Agent in a Research & Refinement pipeline.

Your ONLY responsibilities:
1. Read the user's question from session state key 'user_question'.
2. Read the initial answer from session state key 'initial_answer'.
3. Critically evaluate the initial answer against the following criteria:
   • Accuracy        — Are all stated facts correct and well-supported?
   • Completeness    — Does it fully address all parts of the question?
   • Clarity         — Is the language clear, concise, and well-organised?
   • Depth           — Does it provide sufficient context and explanation?
   • Sources & Trust — Are claims backed by credible sources?
   • Tone & Style    — Is the tone appropriate for the audience?
4. Write a numbered list of SPECIFIC, ACTIONABLE improvement suggestions.
   Each suggestion must explain exactly what is wrong and how to fix it.
5. Save your critique list to session state key 'critique_notes'.

Do NOT rewrite the answer — only provide the critique notes.
"""

critique_agent = LlmAgent(
    name="critique_agent",
    model=MODEL,
    description=(
        "Evaluates the initial answer for accuracy, completeness, clarity, "
        "depth, and style, then produces a numbered list of improvement suggestions."
    ),
    instruction=_CRITIQUE_INSTRUCTION,
    output_key="critique_notes",
)

# ──────────────────────────────────────────────────────────────────────────────
# Agent 4 — Refine Agent
# ──────────────────────────────────────────────────────────────────────────────
_REFINE_INSTRUCTION = """
You are the Refine Agent — the final stage of a Research & Refinement pipeline.

Your ONLY responsibilities:
1. Read the user's question from session state key 'user_question'.
2. Read the initial answer from session state key 'initial_answer'.
3. Read the critique notes from session state key 'critique_notes'.
4. Rewrite the answer, addressing EVERY critique suggestion completely.
   Your refined answer must be:
   • More accurate and factually precise than the original.
   • More complete — covering all aspects of the question.
   • Clearly structured with headings or bullet points where appropriate.
   • Written in a professional, readable, and accessible tone.
   • Supported by specific facts and sources where available.
5. Begin your output with a brief header:
     ✅  REFINED ANSWER
6. Save your refined answer to session state key 'final_answer'.

Your output IS the final answer delivered to the user — make it excellent.
"""

refine_agent = LlmAgent(
    name="refine_agent",
    model=MODEL,
    description=(
        "Rewrites the initial answer by incorporating all critique suggestions, "
        "producing a polished, accurate, and well-structured final answer."
    ),
    instruction=_REFINE_INSTRUCTION,
    output_key="final_answer",
)

# ──────────────────────────────────────────────────────────────────────────────
# Root — Sequential Pipeline Orchestrator
# ──────────────────────────────────────────────────────────────────────────────
root_agent = SequentialAgent(
    name="research_refinement_pipeline",
    description=(
        "Sequential pipeline that greets the user, searches Google for an "
        "answer, critiques the answer, and refines it into a polished response."
    ),
    sub_agents=[
        greeter_agent,
        search_agent,
        critique_agent,
        refine_agent,
    ],
)
