"""Google Model Armor — Prompt Safety Guardrail.

Emulates Google Cloud Model Armor's SanitizeUserPrompt behaviour using
local regex rules.  Detects:
  1. Harmful / dangerous content (weapons, explosives, poisons, violence,
     malware) — focuses on content that could hurt others.
  2. Prompt injection & jailbreak attempts.

No external API call is required — the module uses compiled regex patterns
that mirror the categories enforced by the real Model Armor service.

Usage:
    from research_agent.model_armor import screen_prompt, BLOCKED_RESPONSE_TEXT
    result = screen_prompt(user_input)
    if result.is_blocked:
        print(result.blocked_message)
"""

import re
import logging
from dataclasses import dataclass, field
from typing import List, Optional

logger = logging.getLogger("research_agent.model_armor")

# ──────────────────────────────────────────────────────────────────────────────
# Configurable blocked-message text
# ──────────────────────────────────────────────────────────────────────────────
BLOCKED_RESPONSE_TEXT = (
    "⛔  I'm sorry, I cannot help with that request.  "
    "It appears to ask for information that could cause harm to others, "
    "or it violates our ethical guidelines.  "
    "Please ask a different question."
)


# ──────────────────────────────────────────────────────────────────────────────
# Result dataclass
# ──────────────────────────────────────────────────────────────────────────────
@dataclass
class ModelArmorResult:
    """Verdict returned by the Model Armor screening template."""

    is_blocked: bool
    filter_name: Optional[str] = None
    violation_category: Optional[str] = None
    reason: Optional[str] = None
    blocked_message: str = BLOCKED_RESPONSE_TEXT


# ──────────────────────────────────────────────────────────────────────────────
# Model Armor Template
# ──────────────────────────────────────────────────────────────────────────────
class ModelArmorTemplate:
    """Simulates a Google Cloud Model Armor template with two filter groups.

    Filter Group 1 – Harmful & Dangerous Content
      Targets requests that ask how to create weapons, poisons, explosives,
      malware, or how to inflict violence on others.

    Filter Group 2 – Prompt Injection & Jailbreak
      Targets attempts to override system instructions, persona-swap into
      an "unfiltered" mode, or extract internal prompts.
    """

    def __init__(self, blocked_message: str = BLOCKED_RESPONSE_TEXT) -> None:
        self.blocked_message = blocked_message

        # ── Group 1: Harmful / Dangerous Content ─────────────────────────────
        # Focuses on intent to HURT OTHERS — matches creation of weapons,
        # explosives, poisons, malware, and direct violence instructions.
        self._harmful: List[re.Pattern] = [
            # Explosives / IEDs / bombs ─ broad set
            re.compile(
                r"\b(?:how\s+(?:to|do\s+i|can\s+i|does\s+one|would\s+one)\s+)?"
                r"(?:make|create|build|assemble|construct|synthesize|manufacture|"
                r"prepare|detonate|trigger)\b.{0,60}?"
                r"\b(?:bombs?|ieds?|pipe\s*bombs?|car\s*bombs?|suicide\s*bombs?|"
                r"fertilizer\s*bombs?|dirty\s*bombs?|explosives?|detonators?|"
                r"dynamite|c[\s\-]?4|grenades?|claymore|landmine)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            # Chemical / biological weapons
            re.compile(
                r"\b(?:how\s+(?:to|do\s+i|can\s+i|does\s+one|would\s+one)\s+)?"
                r"(?:make|synthesize|manufacture|produce|grow|cultivate|weaponize)\b.{0,60}?"
                r"\b(?:sarin|vx\s+nerve|novichok|mustard\s+gas|nerve\s+agents?|"
                r"anthrax|ricin|botulinum|weaponized\s+plague|biological\s+weapons?|"
                r"chemical\s+weapons?)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            # Illegal firearms / ghost guns / silencers
            re.compile(
                r"\b(?:how\s+(?:to|do\s+i|can\s+i|does\s+one|would\s+one)\s+)?"
                r"(?:make|build|3d[\s\-]?print|convert|modify)\b.{0,60}?"
                r"\b(?:ghost\s*guns?|untraceable\s*guns?|silencers?|suppressors?|"
                r"illegal\s+firearms?|automatic\s+conversion|full[\s\-]?auto\s+mod)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            # Malware / cyberattacks intended to harm
            re.compile(
                r"\b(?:how\s+(?:to|do\s+i|can\s+i|does\s+one|would\s+one)\s+)?"
                r"(?:write|code|create|build|deploy|spread|use)\b.{0,60}?"
                r"\b(?:ransomware|keyloggers?|trojans?|worms?|rootkits?|spyware|"
                r"ddos\s+(?:attack|botnet)|zero[\s\-]?day\s+exploit|"
                r"malicious\s+(?:code|payload|script)|"
                r"malware\s+to\s+(?:steal|infect|hack|corrupt|destroy))\b",
                re.IGNORECASE | re.DOTALL,
            ),
            # Standalone malware + harmful verb phrasing
            re.compile(
                r"\b(?:create|write|build|code)\b.{0,40}?"
                r"\bmalware\b.{0,40}?"
                r"\b(?:steal|compromise|hack|infect|destroy|encrypt|ransom)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            # Physical violence against specific people / groups
            re.compile(
                r"\b(?:how\s+(?:to|do\s+i|can\s+i|does\s+one|would\s+one)\s+)?"
                r"(?:kill|murder|assassinate|poison|attack|hurt|harm|torture|"
                r"rape|kidnap|abduct)\b.{0,60}?"
                r"\b(?:someone|people|person|children|child|crowd|president|"
                r"politician|officer|teacher|my\s+(?:family|neighbor|ex|wife|husband))\b",
                re.IGNORECASE | re.DOTALL,
            ),
            # Poisons / drugs to harm others
            re.compile(
                r"\b(?:how\s+(?:to|do\s+i|can\s+i|does\s+one|would\s+one)\s+)?"
                r"(?:make|synthesize|extract|obtain|poison\s+(?:someone|people|water))\b.{0,60}?"
                r"\b(?:cyanide|polonium|arsenic|poison\s+someone|date[\s\-]?rape\s+drug|"
                r"rohypnol|methamphetamine\s+to\s+sell)\b",
                re.IGNORECASE | re.DOTALL,
            ),
        ]

        # ── Group 2: Prompt Injection & Jailbreak ────────────────────────────
        self._injection: List[re.Pattern] = [
            # System prompt override commands
            re.compile(
                r"\b(?:ignore|disregard|forget|override|bypass|clear|drop|"
                r"remove|delete|disable)\b.{0,40}?"
                r"\b(?:instructions?|directives?|rules?|constraints?|"
                r"system\s+prompt|guardrails?|safety\s+filters?|guidelines?|"
                r"policies|restrictions)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            # Jailbreak / special-mode invocations
            re.compile(
                r"\b(?:jailbreak|dan\s+mode|developer\s+mode|unrestricted\s+mode|"
                r"god\s+mode|evil\s+mode|do\s+anything\s+now|dAN)\b",
                re.IGNORECASE,
            ),
            # Persona-swap to uncensored entity (with or without 'as/like' bridging)
            re.compile(
                r"\b(?:act|pretend|behave|roleplay|simulate|respond)\b.{0,50}?"
                r"\b(?:an?\s+)?(?:unfiltered|unrestricted|uncensored|evil|"
                r"jailbroken|hacked|no[\s\-]?restriction|evil\s+ai|malicious\s+ai)\b",
                re.IGNORECASE | re.DOTALL,
            ),
            # "You have no rules / limits" declarations
            re.compile(
                r"\b(?:you\s+have\s+no\s+(?:rules|restrictions|limits|guidelines|"
                r"ethics|morals))\b",
                re.IGNORECASE,
            ),
            # Prompt/system-prompt exfiltration (with or without leading verb)
            re.compile(
                r"\b(?:(?:reveal|show|display|print|repeat|output|leak|expose)\b.{0,40}?)?"
                r"\b(?:system\s+prompt|secret\s+instructions?|hidden\s+(?:rules?|instructions?)|"
                r"internal\s+prompt|your\s+instructions?|your\s+hidden\s+\w+)\b",
                re.IGNORECASE | re.DOTALL,
            ),
        ]

    # ── Public API ────────────────────────────────────────────────────────────

    def sanitize_user_prompt(self, text: str) -> ModelArmorResult:
        """Screen a user prompt against all Model Armor template filters.

        Evaluation order:
          1. Harmful content (highest priority — intent to hurt others).
          2. Prompt injection / jailbreak.

        Args:
            text: Raw user input string.

        Returns:
            ModelArmorResult with ``is_blocked=True`` if any filter fires,
            or ``is_blocked=False`` if the prompt is clean.
        """
        if not text or not text.strip():
            return ModelArmorResult(is_blocked=False)

        clean = text.strip()

        # ── 1. Harmful content ────────────────────────────────────────────────
        for pattern in self._harmful:
            match = pattern.search(clean)
            if match:
                logger.warning(
                    "[Model Armor] HARMFUL match — snippet='%s' | full='%.120s'",
                    match.group(0)[:80],
                    clean,
                )
                return ModelArmorResult(
                    is_blocked=True,
                    filter_name="harmful_content_filter",
                    violation_category="Dangerous & Harmful Content",
                    reason=f"Matched prohibited phrase: '{match.group(0)[:80]}'",
                    blocked_message=self.blocked_message,
                )

        # ── 2. Prompt injection / jailbreak ──────────────────────────────────
        for pattern in self._injection:
            match = pattern.search(clean)
            if match:
                logger.warning(
                    "[Model Armor] INJECTION match — snippet='%s' | full='%.120s'",
                    match.group(0)[:80],
                    clean,
                )
                return ModelArmorResult(
                    is_blocked=True,
                    filter_name="prompt_injection_jailbreak_filter",
                    violation_category="Prompt Injection & Jailbreak Attempt",
                    reason=f"Matched injection attempt: '{match.group(0)[:80]}'",
                    blocked_message=self.blocked_message,
                )

        return ModelArmorResult(is_blocked=False)


# ── Module-level singleton & convenience wrapper ──────────────────────────────
_default_template = ModelArmorTemplate()


def screen_prompt(text: str) -> ModelArmorResult:
    """Screen *text* using the default Model Armor template.

    Args:
        text: User input to validate.

    Returns:
        ModelArmorResult verdict.
    """
    return _default_template.sanitize_user_prompt(text)
