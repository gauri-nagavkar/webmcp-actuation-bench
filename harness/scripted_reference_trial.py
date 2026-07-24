"""
Scripted reference trial (NO LLM involved).

This exercises both demo variants with a hand-written, deterministic script
that performs the equivalent task, purely to:
  1. Prove the end-to-end pipeline (page load -> fill -> submit -> metrics ->
     results file -> analysis) works correctly.
  2. Produce a real, honest "steps taken" comparison for the MECHANICAL floor
     of each approach: how many discrete actions are required at minimum to
     complete the task, assuming perfect knowledge of the page (no LLM
     reasoning errors, no misclicks, no retries).

This is NOT a substitute for the real LLM-agent benchmark in
run_benchmark.py -- it deliberately cannot capture reasoning failures,
hallucinated selectors, or retries, which are exactly the failure modes the
real benchmark is designed to measure. Results from this script are tagged
"scripted_reference" and must never be conflated with LLM-driven trial data
in analysis or write-ups.
"""
import asyncio
import json
import time
from pathlib import Path

from playwright.async_api import async_playwright

BASE_URL = "http://localhost:8842"
RESULTS_PATH = Path(__file__).parent / "results" / "trials.jsonl"


async def run_dom_scripted():
    action_log = []
    start = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{BASE_URL}/demo-dom/index.html")

        actions = [
            ("fill", "#f_personal_fullName", "Priya Shah"),
            ("fill", "#f_personal_email", "priya.shah@example.com"),
            ("fill", "#f_personal_phone", "415-555-0192"),
            ("fill", "#f_personal_location", "Oakland, CA"),
            ("check", "input[name='f_personal_workAuthorized'][value='Yes']", None),
            ("check", "input[name='f_personal_needsSponsorship'][value='No']", None),
            ("click", "#next-btn", None),
            ("fill", "#f_experience_0_company", "Northstar Robotics"),
            ("fill", "#f_experience_0_title", "ML Engineer"),
            ("fill", "#f_experience_0_startDate", "2022-02"),
            ("check", "#f_experience_0_isCurrent", None),
            ("fill", "#f_experience_0_description", "Designed and shipped on-device inference pipelines and built internal evaluation harnesses."),
            ("click", "#add-experience-btn", None),
            ("fill", "#f_experience_1_company", "Bright Analytics"),
            ("fill", "#f_experience_1_title", "Software Engineer"),
            ("fill", "#f_experience_1_startDate", "2019-06"),
            ("fill", "#f_experience_1_endDate", "2022-01"),
            ("fill", "#f_experience_1_description", "Built full-stack data pipeline tooling and internal developer platforms."),
            ("click", "#next-btn", None),
            ("select", "#f_education_degree", "Bachelor's"),
            ("fill", "#f_education_field", "Computer Science"),
            ("fill", "#f_education_school", "University of Washington"),
            ("fill", "#f_education_gradYear", "2019"),
            ("click", "#next-btn", None),
            ("fill", "#f_screening_yearsExperience", "6"),
            ("check", "input[name='f_screening_hasConferenceExp'][value='Yes']", None),
            ("fill", "#f_screening_conferenceDetails", "Gave two internal tech talks on evaluation methodology and wrote a blog series on on-device AI tooling."),
            ("fill", "#f_screening_whyInterested", "I'm passionate about developer tooling and want to help other engineers ship AI-first products more reliably."),
            ("check", "input[name='f_screening_relocate'][value='Open to hybrid/remote discussion']", None),
            ("click", "#next-btn", None),
            ("click", "#submit-btn", None),
        ]

        for kind, selector, value in actions:
            if kind == "fill":
                await page.fill(selector, value, timeout=5000)
            elif kind == "check":
                await page.check(selector, timeout=5000)
            elif kind == "click":
                await page.click(selector, timeout=5000)
            elif kind == "select":
                await page.select_option(selector, value, timeout=5000)
            action_log.append({"tool": kind, "selector": selector})

        await page.wait_for_selector("#success-banner", state="visible", timeout=5000)
        submitted = await page.evaluate("window.__SUBMITTED_APPLICATION__")
        await browser.close()

    return {
        "variant": "dom",
        "trial_id": "scripted_reference",
        "success": True,
        "steps_taken": len(action_log),
        "elapsed_seconds": round(time.time() - start, 2),
        "total_tokens": None,
        "provider": "scripted_reference",
        "model": None,
        "error": None,
        "action_log": action_log,
        "submitted_payload": submitted,
    }


async def run_webmcp_scripted():
    action_log = []
    start = time.time()
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{BASE_URL}/demo-webmcp/index.html")
        await page.wait_for_timeout(200)

        tool_calls = [
            ("fill_personal_info", {
                "fullName": "Priya Shah",
                "email": "priya.shah@example.com",
                "phone": "415-555-0192",
                "location": "Oakland, CA",
                "workAuthorized": "Yes",
                "needsSponsorship": "No",
            }),
            ("add_work_experience", {
                "company": "Northstar Robotics",
                "title": "ML Engineer",
                "startDate": "2022-02",
                "isCurrent": True,
                "description": "Designed and shipped on-device inference pipelines and built internal evaluation harnesses.",
            }),
            ("add_work_experience", {
                "company": "Bright Analytics",
                "title": "Software Engineer",
                "startDate": "2019-06",
                "endDate": "2022-01",
                "description": "Built full-stack data pipeline tooling and internal developer platforms.",
            }),
            ("fill_education", {
                "degree": "Bachelor's",
                "field": "Computer Science",
                "school": "University of Washington",
                "gradYear": 2019,
            }),
            ("fill_screening_questions", {
                "yearsExperience": 6,
                "hasConferenceExp": "Yes",
                "conferenceDetails": "Gave two internal tech talks on evaluation methodology and wrote a blog series on on-device AI tooling.",
                "whyInterested": "I'm passionate about developer tooling and want to help other engineers ship AI-first products more reliably.",
                "relocate": "Open to hybrid/remote discussion",
            }),
            ("submit_application", {}),
        ]

        for name, args in tool_calls:
            result = await page.evaluate(
                """
                async ({name, args}) => {
                    const mc = document.modelContext || navigator.modelContext;
                    return await mc.__callTool(name, args);
                }
                """,
                {"name": name, "args": args},
            )
            action_log.append({"tool": name, "input": args, "result": result})

        await page.wait_for_selector("#success-banner", state="visible", timeout=5000)
        submitted = await page.evaluate("window.__SUBMITTED_APPLICATION__")
        await browser.close()

    return {
        "variant": "webmcp",
        "trial_id": "scripted_reference",
        "success": True,
        "steps_taken": len(action_log),
        "elapsed_seconds": round(time.time() - start, 2),
        "total_tokens": None,
        "provider": "scripted_reference",
        "model": None,
        "error": None,
        "action_log": action_log,
        "submitted_payload": submitted,
    }


async def main():
    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    dom_result = await run_dom_scripted()
    webmcp_result = await run_webmcp_scripted()

    with open(RESULTS_PATH, "a") as f:
        f.write(json.dumps(dom_result, default=str) + "\n")
        f.write(json.dumps(webmcp_result, default=str) + "\n")

    print("Scripted reference trials complete (NOT LLM-driven; mechanical floor only).")
    print(f"  dom:    steps={dom_result['steps_taken']}  success={dom_result['success']}")
    print(f"  webmcp: steps={webmcp_result['steps_taken']}  success={webmcp_result['success']}")
    print(f"\nAppended to {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
