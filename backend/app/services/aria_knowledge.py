"""
ARIA — the poultry knowledge base.

Deterministic answers to husbandry questions, with no model in the loop. A
farmer in a coop with no signal can still ask "what are the signs of
coccidiosis?" and get a real, sourced answer. Gemini and Claude are optional
elaboration on top of this, never a prerequisite for it.

Two hard boundaries shape the content.

*Educational, never diagnostic.* Every disease entry explains what the disease
is, how it presents and how it is prevented — general knowledge a farmer could
read in a manual. None of it looks at the farmer's specific birds and concludes
what they have. That line is frozen in §4.4: an unreliable diagnosis makes a
farmer cull a healthy flock or fail to treat a sick one, so ARIA describes and
defers to a vet rather than deciding. The `vet_now` flag marks entries whose
subject is urgent enough that the answer must end by pointing at a
veterinarian.

*Honest about its edges.* The matcher returns nothing rather than a weak match,
and the caller says "I don't have that" and offers the model if one is
configured. A knowledge base that pads gaps with confident guesses is the same
failure as inventing farm data.

The corpus is a curated starter set covering the questions a Kenyan layer/broiler
keeper asks most. It is meant to grow; entries are plain data so adding one is a
dict literal, not code.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum


class KnowledgeCategory(str, Enum):
    DISEASE = "disease"
    NUTRITION = "nutrition"
    HOUSING = "housing"
    MANAGEMENT = "management"
    PRODUCTION = "production"


@dataclass(frozen=True)
class KnowledgeEntry:
    """One answerable topic. `body` is already farmer-readable prose."""

    key: str
    category: KnowledgeCategory
    title: str
    body: str
    #: Best practices — concrete, actionable lines.
    best_practices: tuple[str, ...] = ()
    #: Warnings / red flags.
    warnings: tuple[str, ...] = ()
    #: Where this knowledge comes from, for the source line.
    source: str = "Greena agronomy reference"
    #: Terms that should match this entry, beyond words in the title.
    keywords: tuple[str, ...] = ()
    #: True when the topic is urgent enough that the answer must send the
    #: farmer to a vet rather than leave them to act alone.
    vet_now: bool = False


# ── The corpus ───────────────────────────────────────────────────────────────
#
# Ordered by nothing in particular; the matcher scores across all of them. Kept
# deliberately tight — every entry is something a farmer actually asks and
# something we can state responsibly without diagnosing.

_ENTRIES: tuple[KnowledgeEntry, ...] = (
    KnowledgeEntry(
        key="newcastle",
        category=KnowledgeCategory.DISEASE,
        title="Newcastle Disease (ND)",
        body=(
            "Newcastle is a highly contagious viral disease of poultry, and one of the "
            "biggest killers of village and commercial flocks in Kenya. It spreads through "
            "droppings, respiratory discharge, contaminated equipment and wild birds. There "
            "is no treatment once birds are infected — control is entirely about vaccination "
            "and biosecurity."
        ),
        best_practices=(
            "Vaccinate: a common Kenyan layer schedule is ND at day 1 (or 7), repeat at "
            "2–3 weeks, then every 2–3 months for layers.",
            "Use the I-2 thermotolerant vaccine where cold chain is unreliable.",
            "Isolate new or returning birds for at least two weeks before mixing.",
        ),
        warnings=(
            "Sudden deaths with twisted necks, paralysis, greenish diarrhoea or a sharp drop "
            "in egg production are classic signs — treat any such outbreak as a reportable emergency.",
        ),
        keywords=("nd", "newcastle", "kideri", "twisted neck", "nervous signs"),
        vet_now=True,
    ),
    KnowledgeEntry(
        key="gumboro",
        category=KnowledgeCategory.DISEASE,
        title="Infectious Bursal Disease (Gumboro)",
        body=(
            "Gumboro is a viral disease that attacks the bursa of Fabricius — the organ that "
            "builds a young bird's immune system. It mostly strikes chicks between 3 and 6 "
            "weeks. Birds that survive are left immunosuppressed, so they respond poorly to "
            "other vaccines and pick up secondary infections easily."
        ),
        best_practices=(
            "Vaccinate around days 10–14 and again at 18–21, timed to the maternal-antibody "
            "decline for your source flock.",
            "Keep brooding hygiene high; the virus is hardy and survives a long time in a dirty house.",
        ),
        warnings=(
            "Watch for whitish, watery diarrhoea, birds pecking at their own vents, and a spike "
            "in deaths in the 3–6 week window.",
        ),
        keywords=("gumboro", "ibd", "bursal", "bursa"),
        vet_now=True,
    ),
    KnowledgeEntry(
        key="mareks",
        category=KnowledgeCategory.DISEASE,
        title="Marek's Disease",
        body=(
            "Marek's is a herpesvirus that causes tumours and paralysis, usually in birds "
            "older than 6 weeks. It spreads through feather dander in the air and is almost "
            "impossible to clear from a contaminated house. The only real defence is "
            "vaccination at the hatchery on day 1."
        ),
        best_practices=(
            "Buy day-old chicks already vaccinated for Marek's — it must be given at hatch, "
            "before exposure.",
            "Once vaccinated, keep chicks away from older birds and dander for the first weeks.",
        ),
        warnings=(
            "Progressive paralysis — often one leg forward, one back — and grey eyes with "
            "irregular pupils point to Marek's.",
        ),
        keywords=("mareks", "marek", "fowl paralysis", "range paralysis"),
        vet_now=True,
    ),
    KnowledgeEntry(
        key="coccidiosis",
        category=KnowledgeCategory.DISEASE,
        title="Coccidiosis",
        body=(
            "Coccidiosis is caused by Eimeria parasites that damage the gut lining. It thrives "
            "in warm, damp litter and hits chicks hardest at 3–6 weeks. Unlike the viral "
            "diseases, it is treatable if caught early — but it wastes feed and stunts growth "
            "long before it kills."
        ),
        best_practices=(
            "Keep litter dry — wet patches under drinkers are where outbreaks start.",
            "Use a coccidiostat in feed or an anticoccidial vaccine for chicks.",
            "Treat confirmed cases promptly with an amprolium- or sulfa-based product and a vet's guidance.",
        ),
        warnings=(
            "Blood or orange, mucoid droppings, huddling, ruffled feathers and pale combs are "
            "the signs to act on.",
        ),
        keywords=("coccidiosis", "coccidia", "eimeria", "bloody droppings", "bloody diarrhea"),
        vet_now=True,
    ),
    KnowledgeEntry(
        key="water_intake",
        category=KnowledgeCategory.MANAGEMENT,
        title="How much water birds drink",
        body=(
            "As a rule of thumb, poultry drink about twice as much water as they eat by weight, "
            "and more in heat. A laying hen drinks roughly 200–300 ml per day in Kenyan "
            "conditions; a broiler climbs from a few ml a day at hatch to 250 ml or more near "
            "market weight. Water is the first thing to check when intake or production drops."
        ),
        best_practices=(
            "Provide clean, cool water at all times — a hen that stops drinking stops eating "
            "and stops laying within a day.",
            "In hot weather, raise water availability and check drinkers more often; heat can "
            "double demand.",
            "Allow about 1 drinker space per 8–10 layers.",
        ),
        keywords=("water", "drink", "drinker", "hydration", "thirst"),
    ),
    KnowledgeEntry(
        key="brooding_temperature",
        category=KnowledgeCategory.HOUSING,
        title="Brooding temperature",
        body=(
            "Chicks cannot regulate their own temperature for the first two to three weeks, so "
            "the brooder does it for them. Start at about 33–35°C at day one and lower it "
            "roughly 2–3°C each week until you reach ambient temperature around week five."
        ),
        best_practices=(
            "Read the chicks, not just the thermometer: evenly spread means comfortable, "
            "huddling under the heat means cold, and spread to the edges means too hot.",
            "Week 1: 33–35°C. Week 2: 31–32°C. Week 3: 28–29°C. Then step down to ambient by week 5.",
        ),
        warnings=(
            "Chilling in the first week is a leading cause of early death and lifelong poor "
            "performance — get brooding right and week six takes care of itself.",
        ),
        keywords=("brooding", "brooder", "chick temperature", "heat lamp", "warmth"),
    ),
    KnowledgeEntry(
        key="lighting",
        category=KnowledgeCategory.PRODUCTION,
        title="Lighting schedules for layers",
        body=(
            "Day length drives laying. Growing pullets are kept on a steady or reducing "
            "schedule so they do not come into lay too early; once they reach point of lay "
            "(around 18 weeks) light is increased gradually to about 16 hours a day and held "
            "there to sustain production."
        ),
        best_practices=(
            "Never reduce light for a laying flock — cutting hours knocks production down and "
            "it is slow to recover.",
            "Add light in the morning rather than late at night so birds are not caught off the "
            "perch when it goes dark.",
            "Target ~16 hours total (natural plus artificial) for peak lay.",
        ),
        keywords=("lighting", "light schedule", "day length", "photoperiod", "bulb", "hours of light"),
    ),
    KnowledgeEntry(
        key="feed_basics",
        category=KnowledgeCategory.NUTRITION,
        title="Feed formulation basics",
        body=(
            "Poultry feed is balanced around energy, protein and calcium, and the balance "
            "changes with age. Chicks need high protein to grow frame; layers need high calcium "
            "for shells. Feeding the wrong ration for the stage wastes money and hurts "
            "performance."
        ),
        best_practices=(
            "Chick/starter: ~20–22% protein. Grower: ~16–18%. Layer: ~16–17% protein with "
            "3.5–4% calcium for shell quality.",
            "Change rations at the transitions — starter to grower around 8 weeks, grower to "
            "layer at point of lay — rather than all at once.",
            "Store feed dry and use it within about 4 weeks; mouldy feed causes drops and "
            "disease.",
        ),
        keywords=("feed formulation", "protein", "ration", "layers mash", "growers mash", "starter", "calcium"),
    ),
    KnowledgeEntry(
        key="egg_grading",
        category=KnowledgeCategory.PRODUCTION,
        title="Egg grading",
        body=(
            "Eggs are graded by weight and by shell and internal quality. Grading lets you "
            "price fairly and spot problems: a rise in small or thin-shelled eggs is usually a "
            "nutrition or age signal, not bad luck."
        ),
        best_practices=(
            "Typical weight bands: small under 53g, medium 53–63g, large 63–73g, extra-large "
            "above 73g.",
            "Candle for cracks and blood spots before sale; collect often to reduce breakages.",
            "Thin or soft shells point to low calcium or heat stress — review the ration and water.",
        ),
        keywords=("egg grading", "egg size", "egg weight", "candling", "shell quality", "grade"),
    ),
    KnowledgeEntry(
        key="biosecurity",
        category=KnowledgeCategory.MANAGEMENT,
        title="Biosecurity basics",
        body=(
            "Biosecurity is everything you do to keep disease out. Most Kenyan flock disasters "
            "walk in on boots, crates, wild birds or new stock. It is cheaper and far more "
            "effective than treating an outbreak after it starts."
        ),
        best_practices=(
            "Quarantine every new or returning bird for at least two weeks before mixing.",
            "Control who and what enters the house — foot dips, dedicated boots, no shared crates.",
            "Keep wild birds and rodents out of feed stores; they carry Newcastle and more.",
            "Dispose of dead birds by burying or burning, never by leaving them near the flock.",
        ),
        keywords=("biosecurity", "quarantine", "disease prevention", "foot dip", "hygiene"),
    ),
    KnowledgeEntry(
        key="vaccination_general",
        category=KnowledgeCategory.MANAGEMENT,
        title="How to vaccinate poultry",
        body=(
            "Most poultry vaccines in Kenya are given by drinking water, eye/nostril drop, or "
            "injection. The method depends on the vaccine — Newcastle and Gumboro are often "
            "given in water or by eye drop, Marek's by injection at the hatchery. The vaccine "
            "only works if it is handled and given correctly."
        ),
        best_practices=(
            "Keep vaccines cold until use; heat and sunlight destroy them.",
            "For water vaccination, withhold water for 1–2 hours first so birds drink the dose "
            "quickly, and use clean, chlorine-free water.",
            "Vaccinate healthy birds only — vaccinating sick birds can make things worse.",
            "Use the whole dose within the time stated after mixing; discard leftovers.",
        ),
        keywords=("vaccinate", "vaccination", "how to vaccinate", "drinking water vaccine", "eye drop", "dose"),
    ),
    KnowledgeEntry(
        key="fcr",
        category=KnowledgeCategory.PRODUCTION,
        title="Feed conversion ratio (FCR)",
        body=(
            "FCR is how much feed it takes to produce a unit of output — kilograms of feed per "
            "kilogram of body-weight gain for broilers, or per dozen eggs for layers. A lower "
            "FCR means you are turning feed into product more efficiently, and since feed is "
            "usually 60–70% of cost, small improvements matter a lot."
        ),
        best_practices=(
            "Broiler target FCR is roughly 1.6–1.9 by market age; layers, around 2 kg feed per "
            "dozen eggs.",
            "Improve FCR by cutting feed waste, matching ration to stage, keeping water flowing, "
            "and controlling disease that quietly steals gains.",
        ),
        keywords=("fcr", "feed conversion", "feed efficiency", "improve fcr", "kilograms of feed"),
    ),
)

_BY_KEY = {e.key: e for e in _ENTRIES}


# ── Matching ─────────────────────────────────────────────────────────────────


@dataclass
class KnowledgeMatch:
    entry: KnowledgeEntry
    score: float
    fields: dict[str, object] = field(default_factory=dict)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z]+", (text or "").lower()))


#: Below this, a match is too weak to trust; the caller says it doesn't know.
MIN_SCORE = 2.0


def search(question: str, limit: int = 1) -> list[KnowledgeMatch]:
    """
    Score the question against every entry and return the best matches above the
    confidence floor. Empty list means "I don't know" — which the caller must
    say honestly rather than paper over.
    """
    q = (question or "").lower()
    q_tokens = _tokens(q)
    if not q_tokens:
        return []

    scored: list[KnowledgeMatch] = []
    for entry in _ENTRIES:
        score = 0.0

        # A keyword phrase appearing verbatim is the strongest signal.
        for kw in entry.keywords:
            if kw in q:
                score += 3.0 if " " in kw else 2.0

        # Title-word overlap.
        title_tokens = _tokens(entry.title)
        score += 1.5 * len(q_tokens & title_tokens)

        # The key itself (e.g. "coccidiosis") mentioned directly.
        if entry.key.replace("_", " ") in q:
            score += 2.5

        if score >= MIN_SCORE:
            scored.append(KnowledgeMatch(entry=entry, score=score))

    scored.sort(key=lambda m: m.score, reverse=True)
    return scored[:limit]


def get(key: str) -> KnowledgeEntry | None:
    return _BY_KEY.get(key)


def all_topics() -> list[dict[str, str]]:
    """For a 'what can I ask?' listing in the UI."""
    return [
        {"key": e.key, "title": e.title, "category": e.category.value}
        for e in _ENTRIES
    ]


def answer(question: str) -> dict | None:
    """
    A structured, farmer-ready answer, or None when nothing matches confidently.

    The shape mirrors the spec's requirement — explanation, best practices,
    warnings, references — so the UI renders every knowledge answer identically.
    `vet_now` tells the caller to append the see-a-vet boundary.
    """
    matches = search(question, limit=1)
    if not matches:
        return None
    e = matches[0].entry
    return {
        "key": e.key,
        "title": e.title,
        "category": e.category.value,
        "explanation": e.body,
        "best_practices": list(e.best_practices),
        "warnings": list(e.warnings),
        "source": e.source,
        "vet_now": e.vet_now,
        "confidence": "high" if matches[0].score >= 4 else "medium",
    }
