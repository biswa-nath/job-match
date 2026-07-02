import json
import re

import litellm
from rich.console import Console
from rich.panel import Panel

import config

console = Console()


def match_job(resume_text: str, job: dict) -> dict:
    """
    Score how well a job matches the resume using LiteLLM.

    Returns a dict with keys:
        score (int 0-100): percentage match
        recommendation (str): LLM's recommendation text
    """
    prompt = f"""You are a career advisor. Compare the resume and the job description below.

Return ONLY a JSON object in this exact format (no markdown, no prose):
{{"score": <integer 0-100>, "recommendation": "<one or two sentences>"}}

Where:
- score: percentage match between the resume and job (0 = no match, 100 = perfect fit)
- recommendation: brief advice on alignment and any gaps

---
RESUME:
{resume_text}

---
JOB TITLE: {job.get("position", "N/A")}
COMPANY: {job.get("company", "N/A")}
LOCATION: {job.get("location", "N/A")} ({job.get("office_type", "N/A")})

JOB DESCRIPTION:
{job.get("description", "N/A")}
"""

    response = litellm.completion(
        model=config.LLM_MODEL,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.2,
    )

    raw = response.choices[0].message.content.strip()

    # Extract JSON even if the model wraps it in markdown fences
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        result = json.loads(json_match.group())
    else:
        result = {"score": 0, "recommendation": raw}

    score = int(result.get("score", 0))
    recommendation = result.get("recommendation", "")

    color = (
        "green"
        if score >= config.DEFAULT_THRESHOLD
        else "yellow"
        if score >= 50
        else "red"
    )
    console.print(
        Panel(
            f"[bold]{job.get('position')}[/bold] @ {job.get('company')}\n"
            f"Score: [{color}]{score}%[/{color}]\n"
            f"{recommendation}",
            title=job.get("url", ""),
            expand=False,
        )
    )

    return {"score": score, "recommendation": recommendation}
