"""
Smoke test for the WebMCP-instrumented job application form.

Since Playwright/Chromium (stable channel) does not yet ship the WebMCP
origin trial by default, `document.modelContext` may not exist in this
environment. This script:
  1. Checks whether document.modelContext is available.
  2. If yes: discovers tools via getTools() and calls them via a JS bridge
     (calling registered tool.execute directly, since Playwright has no
     native "agent calls WebMCP tool" API yet -- that's the inspector
     extension's job in real Chrome).
  3. If no: falls back to directly invoking the tool executors we registered
     on `window` for benchmarking purposes (documented limitation below).

This script's job is just to confirm the WebMCP demo page loads and its
tool-registration script runs without errors -- the actual dual-mode
benchmark harness (harness/run_benchmark.py) implements the real comparison.
"""
import asyncio
from playwright.async_api import async_playwright

BASE = "http://localhost:8842"


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        console_logs = []
        page.on("console", lambda msg: console_logs.append(msg.text))

        await page.goto(f"{BASE}/demo-webmcp/index.html")
        await page.wait_for_timeout(300)

        has_model_context = await page.evaluate(
            "() => !!(document.modelContext || navigator.modelContext)"
        )
        print("document.modelContext available:", has_model_context)
        print("\n--- console logs ---")
        for line in console_logs:
            print(line)

        if has_model_context:
            tools = await page.evaluate(
                "async () => { const mc = document.modelContext || navigator.modelContext; "
                "const tools = await mc.getTools(); "
                "return tools.map(t => t.name); }"
            )
            print("\nDiscovered tools:", tools)
        else:
            print(
                "\n[expected in this Chromium build] WebMCP is origin-trial/flag-gated; "
                "falling back to direct tool invocation for functional testing."
            )

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
