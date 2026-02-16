"""Course generation logic — orchestrates Ollama AI + resource enrichment."""

import logging
from ai_providers import call_ollama, parse_json_response
from resource_search import enrich_with_resources
from models import CourseRequest, CoursePlan

logger = logging.getLogger(__name__)

# ─── Phase 1: Generate compact weekly outline ─────────────────
OUTLINE_PROMPT_TEMPLATE = """
Create a structured course outline for:
**Goal**: {goal}

Structure the course week-by-week (4-24 weeks depending on complexity).

Return specific JSON:
{{
  "title": "Course Name",
  "description": "Short overview",
  "prerequisites": ["String 1", "String 2"],
  "weeks": [
    {{
      "week": 1,
      "title": "Week Title",
      "concepts": ["Topic 1", "Topic 2"],
      "focus": "theory"
    }}
  ]
}}

RULES:
1. "prerequisites" MUST be a list of strings, NOT objects.
2. "concepts" MUST be a list of strings.
3. Output VALID JSON ONLY.
"""

# ─── Phase 2: Generate daily breakdown for a single week ──────
WEEK_DETAILS_PROMPT_TEMPLATE = """
Generate a daily breakdown for Week {week_number}: "{week_title}" of a course on "{goal}".
Concepts to cover: {concepts}

Return JSON:
{{
  "days": [
    {{
      "day": 1,
      "title": "Day Topic",
      "task_type": "theory",
      "duration_minutes": 60,
      "concepts": ["Concept A", "Concept B"]
    }},
    {{
      "day": 2,
      "title": "Day Topic",
      "task_type": "practice",
      "duration_minutes": 90,
      "concepts": ["Concept C"]
    }}
  ]
}}

RULES:
1. Generate 5-7 days for this week.
2. Each day has 2-4 concepts.
3. Mix theory, practice, and review.
4. JSON ONLY.
"""

# ─── Phase 3: Generate details for a single day ──────────────
DAY_DETAILS_PROMPT_TEMPLATE = """
Generate learning content for Day {day_number}: "{day_title}".

**Course Goal**: {goal}
**Type**: {task_type} ({duration_minutes} min)

Return JSON:
{{
  "title": "{day_title}",
  "description": "Educational explanation of the topic. Be clear and direct.",
  "table_of_contents": ["Topic 1", "Topic 2", "Topic 3"],
  "resources": [
    {{ "title": "Search Query", "source": "youtube" }},
    {{ "title": "Search Query", "source": "web" }}
  ]
}}

RULES:
1. Description should be helpful but efficient.
2. Provide 3-5 best search queries for resources (focus on YouTube tutorials).
3. JSON ONLY.
"""


async def generate_course_outline(request: CourseRequest) -> dict:
    """Generate the weekly course outline (compact, fast)."""
    prompt = OUTLINE_PROMPT_TEMPLATE.format(goal=request.goal)

    logger.info(f"Generating weekly outline for: {request.goal}")
    raw = await call_ollama(request.model, prompt)
    data = parse_json_response(raw)

    # Ensure required fields
    if "prerequisites" not in data:
        data["prerequisites"] = []
    if "weeks" not in data:
        data["weeks"] = []

    # Ensure each week has defaults
    for w in data["weeks"]:
        if "concepts" not in w:
            w["concepts"] = []
        if "focus" not in w:
            w["focus"] = "theory"

    data["duration_weeks"] = len(data["weeks"])
    return data


async def generate_week_details(request) -> dict:
    """Generate daily breakdown for a specific week."""
    concepts_str = ", ".join(request.concepts) if request.concepts else request.week_title

    prompt = WEEK_DETAILS_PROMPT_TEMPLATE.format(
        goal=request.goal,
        week_number=request.week_number,
        week_title=request.week_title,
        concepts=concepts_str,
    )

    logger.info(f"Generating details for Week {request.week_number}: {request.week_title}")
    raw = await call_ollama(request.model, prompt)
    data = parse_json_response(raw)

    # Ensure days list
    if "days" not in data:
        data["days"] = []

    for day in data["days"]:
        if "concepts" not in day:
            day["concepts"] = []
        day["is_generated"] = True

    return data


async def generate_day_details(request) -> dict:
    """Generate details for a specific day and enrich with resources."""
    prompt = DAY_DETAILS_PROMPT_TEMPLATE.format(
        goal=request.goal,
        day_title=request.day_title,
        day_number=request.day_number,
        task_type=request.task_type,
        duration_minutes=request.duration_minutes,
    )

    logger.info(f"Generating details for Day {request.day_number}: {request.day_title}")
    raw = await call_ollama(request.model, prompt)
    data = parse_json_response(raw)

    # Enrich resources
    if "resources" in data:
        from resource_search import search_youtube, search_web

        final_resources = []
        for r in data["resources"][:4]:
            q = r.get("title", request.day_title)
            if r.get("source") == "youtube":
                res = await search_youtube(q + " tutorial")
                if res: final_resources.append(res[0])
            else:
                res = await search_web(q + " tutorial")
                if res: final_resources.append(res[0])

        data["resources"] = [r.model_dump() for r in final_resources]

    return data
