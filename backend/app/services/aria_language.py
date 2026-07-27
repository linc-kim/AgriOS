"""
ARIA — language identification for a trilingual farm.

Kenyan poultry farmers do not speak in one language at a time. A single sentence
is routinely English, Swahili and Sheng at once — "Nimepea layers kilo 45 leo",
"Broilers wameanza kukohoa", "Remind me kesho nioshe drinkers". Treating that as
"unknown" or forcing it into one bucket is how an assistant ends up feeling
foreign to the person using it.

This module is a small, deterministic classifier: it counts weighted markers for
each language and reports the primary language, whether the sentence is mixed,
and the evidence behind the call. It is pure — no I/O, no model — so the routing
layer above it can decide, cheaply and repeatably, how to read what the farmer
wrote before any of it reaches Gemini.

It deliberately does not *translate*. The NLU vocabulary already matches Swahili
and Sheng terms directly (that is more reliable than translating a whole sentence
first), so this only needs to *identify* — enough for the router to pick a path
and for ARIA to reply in the farmer's own language.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from enum import Enum


class Language(str, Enum):
    ENGLISH = "en"
    SWAHILI = "sw"
    SHENG = "sheng"


# ── Marker vocabularies ───────────────────────────────────────────────────────
#
# Function words and high-frequency domain terms, not an exhaustive dictionary.
# Markers are the words that *disambiguate* — content nouns shared across
# languages (a proper noun, a number) are deliberately excluded so a farm name
# does not sway the count.

_SWAHILI_MARKERS = {
    # function words
    "na", "ya", "wa", "kwa", "ni", "si", "la", "za", "cha", "vya", "kama",
    "leo", "kesho", "jana", "sasa", "juzi",
    "nini", "lini", "vipi", "wapi", "nani", "ngapi", "gani",
    "niambie", "nataka", "nina", "sina", "kuna", "hakuna",
    # domain
    "kuku", "vifaranga", "mayai", "yai", "chakula", "pumba", "maji", "chanjo",
    "ugonjwa", "magonjwa", "mifugo", "shamba", "lishe", "bei", "gharama",
    "faida", "hasara", "mauzo", "uzito", "kilo",
    "nimepea", "nimewapa", "walikufa", "wamekufa", "amekufa", "wameanza",
    "kukohoa", "nioshe", "nunua", "niliuza",
}

# Sheng is Nairobi's urban creole: Swahili grammar, borrowed and coined slang.
# These are markers that are Sheng specifically — not standard Swahili and not
# English — so their presence lifts the Sheng score above plain Swahili.
_SHENG_MARKERS = {
    "mzae", "buda", "mrembo", "manze", "maze", "sasa za", "niaje", "vibe",
    "poa", "fiti", "sawa sawa", "doo", "ganji", "chapaa", "mkwanja", "mula",
    "dishi", "dishen", "form", "maform", "githeri", "mbogi", "wasee", "msee",
    "beste", "wazi", "ushago", "ndai", "keja", "stori", "gwiti",
    "sema", "mob", "kaa rada", "noma", "kubaya", "fisi",
}

_ENGLISH_MARKERS = {
    "the", "a", "an", "is", "are", "was", "were", "and", "or", "of", "to",
    "for", "in", "on", "how", "what", "when", "why", "which", "who", "many",
    "much", "remind", "record", "explain", "show", "give", "gave", "today",
    "tomorrow", "died", "dead", "feed", "eggs", "birds", "flock",
}


@dataclass
class LanguageResult:
    primary: Language
    #: True when at least two languages have real support in the same text.
    mixed: bool
    #: Per-language marker score, for transparency and tests.
    scores: dict[str, int] = field(default_factory=dict)
    #: The markers that fired, per language.
    evidence: dict[str, list[str]] = field(default_factory=dict)

    @property
    def languages(self) -> list[str]:
        """Every language with any support, primary first."""
        present = [lang for lang, n in self.scores.items() if n > 0]
        present.sort(key=lambda code: (code != self.primary.value, -self.scores[code]))
        return present


def _normalise(text: str) -> str:
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c))
    return text.lower()


def _count(tokens: list[str], joined: str, markers: set[str]) -> tuple[int, list[str]]:
    hits: list[str] = []
    for m in markers:
        if " " in m:
            if m in joined:
                hits.append(m)
        elif m in tokens:
            hits.append(m)
    return len(hits), hits


def detect_language(text: str) -> LanguageResult:
    """
    Identify the primary language of a farmer's message and whether it is mixed.

    Weighted marker counting: Sheng markers also count toward Swahili (Sheng is
    built on Swahili), but a Sheng-specific hit is what tips the primary from
    Swahili to Sheng. English is the fallback primary when nothing else fires —
    the honest default rather than a guess.
    """
    norm = _normalise(text)
    tokens = re.findall(r"[a-z']+", norm)
    token_set = tokens  # membership tests below

    en, en_hits = _count(token_set, norm, _ENGLISH_MARKERS)
    sw, sw_hits = _count(token_set, norm, _SWAHILI_MARKERS)
    sheng, sheng_hits = _count(token_set, norm, _SHENG_MARKERS)

    # Sheng rides on Swahili grammar — its markers reinforce the Swahili family.
    sw_family = sw + sheng

    scores = {"en": en, "sw": sw_family, "sheng": sheng}
    evidence = {"en": en_hits, "sw": sw_hits, "sheng": sheng_hits}

    # Primary: Sheng wins when it has its own marker and the sentence isn't
    # overwhelmingly English; else whichever family scores higher; English breaks
    # ties only when nothing African-language fired.
    if sheng >= 1 and sw_family >= en:
        primary = Language.SHENG
    elif sw_family > en:
        primary = Language.SWAHILI
    elif en > 0:
        primary = Language.ENGLISH
    elif sw_family > 0:
        primary = Language.SWAHILI
    else:
        primary = Language.ENGLISH  # honest default

    # Mixed: English and the Swahili family both have genuine support.
    mixed = en > 0 and sw_family > 0

    return LanguageResult(primary=primary, mixed=mixed, scores=scores, evidence=evidence)


def reply_language_note(result: LanguageResult) -> str:
    """A short instruction for the generative layer to answer in kind."""
    if result.primary is Language.SWAHILI:
        return "Respond in Swahili."
    if result.primary is Language.SHENG:
        return "Respond in simple Swahili/Sheng, matching the farmer's tone."
    if result.mixed:
        return "Respond in the same mix of English and Swahili the farmer used."
    return "Respond in English."
