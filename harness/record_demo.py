"""
Record a side-by-side demo video: DOM actuation (left) vs WebMCP tool
calls (right), completing the same job application task.

Uses Playwright's built-in video recording (record_video_dir) so each
variant is captured as a clean .webm, then harness/compose_video.py
stitches them together with ffmpeg into a labeled side-by-side MP4/GIF
for the README and LinkedIn post.

Both runs use the same scripted, deterministic action sequence as
harness/scripted_reference_trial.py (not LLM-driven) -- this is a visual
demo of *what the two interaction models look like*, not a benchmark run.
Pacing is deliberately slowed down (small waits between actions) so the
recording is watchable, unlike the benchmark's speed-run trials.
"""
import asyncio
import shutil
from pathlib import Path

from playwright.async_api import async_playwright

BASE_URL = "http://localhost:8842"
RAW_DIR = Path(__file__).parent.parent / "assets" / "recording_raw"
STEP_PAUSE_MS = 550  # pause between actions so the recording is watchable


async def record_dom():
    video_dir = RAW_DIR / "dom_video"
    video_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 800, "height": 900},
            record_video_dir=str(video_dir),
            record_video_size={"width": 800, "height": 900},
        )
        page = await context.new_page()
        await page.goto(f"{BASE_URL}/demo-dom/index.html")
        await page.wait_for_timeout(STEP_PAUSE_MS)

        async def pause():
            await page.wait_for_timeout(STEP_PAUSE_MS)

        await page.fill("#f_personal_fullName", "Priya Shah"); await pause()
        await page.fill("#f_personal_email", "priya.shah@example.com"); await pause()
        await page.fill("#f_personal_phone", "415-555-0192"); await pause()
        await page.fill("#f_personal_location", "Oakland, CA"); await pause()
        await page.check("input[name='f_personal_workAuthorized'][value='Yes']"); await pause()
        await page.check("input[name='f_personal_needsSponsorship'][value='No']"); await pause()
        await page.click("#next-btn"); await pause()

        await page.fill("#f_experience_0_company", "Northstar Robotics"); await pause()
        await page.fill("#f_experience_0_title", "ML Engineer"); await pause()
        await page.fill("#f_experience_0_startDate", "2022-02"); await pause()
        await page.check("#f_experience_0_isCurrent"); await pause()
        await page.fill(
            "#f_experience_0_description",
            "Designed and shipped on-device inference pipelines and built internal evaluation harnesses.",
        )
        await pause()
        await page.click("#next-btn"); await pause()

        await page.select_option("#f_education_degree", "Bachelor's"); await pause()
        await page.fill("#f_education_field", "Computer Science"); await pause()
        await page.fill("#f_education_school", "University of Washington"); await pause()
        await page.fill("#f_education_gradYear", "2019"); await pause()
        await page.click("#next-btn"); await pause()

        await page.fill("#f_screening_yearsExperience", "6"); await pause()
        await page.check("input[name='f_screening_hasConferenceExp'][value='Yes']"); await pause()
        await page.fill(
            "#f_screening_conferenceDetails",
            "Gave two internal tech talks on evaluation methodology and wrote a blog series on on-device AI tooling.",
        )
        await pause()
        await page.fill(
            "#f_screening_whyInterested",
            "I'm passionate about developer tooling and want to help other engineers ship AI-first products more reliably.",
        )
        await pause()
        await page.check("input[name='f_screening_relocate'][value='Open to hybrid/remote discussion']"); await pause()
        await page.click("#next-btn"); await pause()

        await page.click("#submit-btn")
        await page.wait_for_selector("#success-banner", state="visible", timeout=5000)
        await page.wait_for_timeout(1200)  # linger on success state

        await context.close()
        await browser.close()

    # Playwright names the video file automatically; find and rename it.
    produced = list(video_dir.glob("*.webm"))
    assert produced, "no video produced for dom variant"
    final_path = RAW_DIR / "dom.webm"
    shutil.move(str(produced[0]), str(final_path))
    shutil.rmtree(video_dir)
    print(f"DOM recording saved: {final_path}")


async def record_webmcp():
    video_dir = RAW_DIR / "webmcp_video"
    video_dir.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={"width": 800, "height": 900},
            record_video_dir=str(video_dir),
            record_video_size={"width": 800, "height": 900},
        )
        page = await context.new_page()
        await page.goto(f"{BASE_URL}/demo-webmcp/index.html")
        await page.wait_for_timeout(STEP_PAUSE_MS)

        async def call(name, args):
            await page.evaluate(
                """
                async ({name, args}) => {
                    const mc = document.modelContext || navigator.modelContext;
                    return await mc.__callTool(name, args);
                }
                """,
                {"name": name, "args": args},
            )
            await page.wait_for_timeout(STEP_PAUSE_MS * 2)  # longer pause: each call does more visible work

        await call("fill_personal_info", {
            "fullName": "Priya Shah",
            "email": "priya.shah@example.com",
            "phone": "415-555-0192",
            "location": "Oakland, CA",
            "workAuthorized": "Yes",
            "needsSponsorship": "No",
        })
        await call("add_work_experience", {
            "company": "Northstar Robotics",
            "title": "ML Engineer",
            "startDate": "2022-02",
            "isCurrent": True,
            "description": "Designed and shipped on-device inference pipelines and built internal evaluation harnesses.",
        })
        await call("fill_education", {
            "degree": "Bachelor's",
            "field": "Computer Science",
            "school": "University of Washington",
            "gradYear": 2019,
        })
        await call("fill_screening_questions", {
            "yearsExperience": 6,
            "hasConferenceExp": "Yes",
            "conferenceDetails": "Gave two internal tech talks on evaluation methodology and wrote a blog series on on-device AI tooling.",
            "whyInterested": "I'm passionate about developer tooling and want to help other engineers ship AI-first products more reliably.",
            "relocate": "Open to hybrid/remote discussion",
        })
        await call("submit_application", {})

        await page.wait_for_selector("#success-banner", state="visible", timeout=5000)
        await page.wait_for_timeout(1200)

        await context.close()
        await browser.close()

    produced = list(video_dir.glob("*.webm"))
    assert produced, "no video produced for webmcp variant"
    final_path = RAW_DIR / "webmcp.webm"
    shutil.move(str(produced[0]), str(final_path))
    shutil.rmtree(video_dir)
    print(f"WebMCP recording saved: {final_path}")


async def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    await record_dom()
    await record_webmcp()
    print("\nBoth raw recordings done. Run harness/compose_video.py next to stitch side by side.")


if __name__ == "__main__":
    asyncio.run(main())
