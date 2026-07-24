"""
Quick smoke test: exercise the DOM-baseline job application form via
Playwright, filling every step by hand (as a real DOM-actuation agent would
have to) and asserting it reaches the success banner. This validates the
demo app itself works correctly before building the full agent harness.
"""
import asyncio
from playwright.async_api import async_playwright

BASE = "http://localhost:8842"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(f"{BASE}/demo-dom/index.html")

        # Step 1: personal
        await page.fill("#f_personal_fullName", "Gauri Nagavkar")
        await page.fill("#f_personal_email", "gauri@example.com")
        await page.fill("#f_personal_phone", "555-123-4567")
        await page.fill("#f_personal_location", "San Francisco, CA")
        await page.check("input[name='f_personal_workAuthorized'][value='Yes']")
        await page.check("input[name='f_personal_needsSponsorship'][value='No']")
        await page.click("#next-btn")

        # Step 2: experience (repeatable, index 0 pre-exists)
        await page.fill("#f_experience_0_company", "Acme Corp")
        await page.fill("#f_experience_0_title", "ML Engineer")
        await page.fill("#f_experience_0_startDate", "2021-01")
        await page.check("#f_experience_0_isCurrent")
        await page.fill("#f_experience_0_description", "Built ML systems and eval tooling.")
        await page.click("#next-btn")

        # Step 3: education
        await page.select_option("#f_education_degree", "Bachelor's")
        await page.fill("#f_education_field", "Computer Science")
        await page.fill("#f_education_school", "State University")
        await page.fill("#f_education_gradYear", "2018")
        await page.click("#next-btn")

        # Step 4: screening
        await page.fill("#f_screening_yearsExperience", "5")
        await page.check("input[name='f_screening_hasConferenceExp'][value='No']")
        await page.fill("#f_screening_whyInterested", "I love browser AI and developer advocacy.")
        await page.check("input[name='f_screening_relocate'][value='Yes']")
        await page.click("#next-btn")

        # Step 5: review + submit
        await page.click("#submit-btn")
        await page.wait_for_selector("#success-banner", state="visible", timeout=5000)
        print("DOM demo: SUCCESS banner shown.")

        submitted = await page.evaluate("window.__SUBMITTED_APPLICATION__")
        print("Submitted payload:", submitted)

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
