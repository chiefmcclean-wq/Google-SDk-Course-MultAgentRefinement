"""Research & Refinement Bot — Google ADK Multi-Agent Package.

Exports:
  root_agent      – The top-level ADK agent (registered as 'agent.py' by ADK).
  greeter_agent   – Welcomes the user and collects their question.
  search_agent    – Finds information via google_search tool.
  critique_agent  – Critiques the initial answer and suggests improvements.
  refine_agent    – Rewrites the answer based on critique suggestions.
"""

from research_agent.agents import (
    root_agent,
    greeter_agent,
    search_agent,
    critique_agent,
    refine_agent,
)

__all__ = [
    "root_agent",
    "greeter_agent",
    "search_agent",
    "critique_agent",
    "refine_agent",
]
