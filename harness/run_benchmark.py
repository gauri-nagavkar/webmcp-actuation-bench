"""
Benchmark harness: measure how reliably an LLM-driven agent can complete a
multi-step job application on two versions of the same site:

  - demo-dom:    plain DOM actuation (agent reads the accessibility tree /
                 HTML and must click/type into individual fields, exactly
                 like a human using a mouse and keyboard).
  - demo-webmcp: the same task exposed as WebMCP tools (structured
                 function-calling against document.modelContext).

Supports Anthropic (Claude) and OpenAI (GPT) as the agent's underlying
model via ANTHROPIC_API_KEY / OPENAI_API_KEY. Set MODEL_PROVIDER=anthropic
or openai (defaults to whichever key is present).

Usage:
    python harness/run_benchmark.py --variant dom --trials 10
    python harness/run_benchmark.py --variant webmcp --trials 10
    python harness/run_benchmark.py --variant both --trials 10

Results are appended as JSON lines to harness/results/trials.jsonl for
downstream analysis (harness/analyze_results.py).
"""
import argparse
import asyncio
import json
import os
import time
import traceback
from pathlib import Path

from playwright.async_api import async_playwright

BASE_URL = os.environ.get("BENCH_BASE_URL", "http://localhost:8842")
RESULTS_PATH = Path(__file__).parent / "results" / "trials.jsonl"

TASK_DESCRIPTION = """
You are helping a job applicant fill out and submit a job application form
for a Software Engineer role. Use the following applicant profile:

Full name: Priya Shah
Email: priya.shah@example.com
Phone: 415-555-0192
Location: Oakland, CA
Work authorized in the US: Yes
Needs visa sponsorship: No

Work experience (most recent first):
1. ML Engineer at Northstar Robotics, Feb 2022 - present (currently works
   here). Description: "Designed and shipped on-device inference pipelines
   and built internal evaluation harnesses for model quality regression
   testing."
2. Software Engineer at Bright Analytics, Jun 2019 - Jan 2022.
   Description: "Built full-stack data pipeline tooling and internal
   developer platforms used by 40+ engineers."

Education: Bachelor's in Computer Science, University of Washington,
graduated 2019.

Screening answers:
- Years of relevant technical experience: 6
- Has given conference talks / written technical articles: Yes.
  Details: "Gave two internal tech talks on evaluation methodology and
  wrote a blog series on on-device AI tooling."
- Why interested in this role: "I'm passionate about developer tooling and
  want to help other engineers ship AI-first products more reliably."
- Willing to relocate to Mountain View, CA: Open to hybrid/remote discussion

Your job: complete every step of the application form and submit it. Do not
invent facts not given above. When finished, the page should show a success
banner confirming submission.
"""

DOM_ACTUATION_TOOLS = [
    {
        "name": "click",
        "description": "Click an element identified by a CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
    },
    {
        "name": "fill",
        "description": "Type a value into a text/number/textarea input identified by a CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["selector", "value"],
        },
    },
    {
        "name": "select_option",
        "description": "Choose an option in a <select> element by visible label or value.",
        "input_schema": {
            "type": "object",
            "properties": {
                "selector": {"type": "string"},
                "value": {"type": "string"},
            },
            "required": ["selector", "value"],
        },
    },
    {
        "name": "check",
        "description": "Check a checkbox or radio input identified by a CSS selector.",
        "input_schema": {
            "type": "object",
            "properties": {"selector": {"type": "string"}},
            "required": ["selector"],
        },
    },
    {
        "name": "get_page_snapshot",
        "description": (
            "Get a simplified snapshot of the current page's interactive elements "
            "(inputs, selects, buttons, radios/checkboxes with selectors, labels, and "
            "current values) plus visible text. Call this whenever you need to see "
            "the current state of the form before deciding the next action."
        ),
        "input_schema": {"type": "object", "properties": {}},
    },
]

WEBMCP_TOOLS_DESCRIPTION_HINT = (
    "This page exposes WebMCP tools via document.modelContext. Call "
    "get_page_snapshot first if you want to confirm available tools, then call "
    "the discovered tools directly by name with their documented input schema."
)


async def get_page_snapshot(page):
    """Extract a simplified, LLM-friendly snapshot of interactive elements."""
    return await page.evaluate(
        """
        () => {
            function describeEl(el) {
                const tag = el.tagName.toLowerCase();
                let selector = el.id ? `#${el.id}` : null;
                if (!selector && el.name) selector = `[name="${el.name}"][value="${el.value}"]`;
                if (!selector) return null;
                const label = el.closest('.field')?.querySelector('label')?.textContent
                    || el.closest('label')?.textContent || '';
                return {
                    tag, type: el.type || tag, selector,
                    label: label.trim(),
                    value: el.type === 'checkbox' || el.type === 'radio' ? el.checked : el.value,
                    visible: el.offsetParent !== null,
                };
            }
            const els = Array.from(document.querySelectorAll('input, select, textarea, button'));
            const fields = els.map(describeEl).filter(Boolean).filter(f => f.visible);
            const heading = document.querySelector('#step-container h2')?.textContent || '';
            const successVisible = document.getElementById('success-banner')?.style.display === 'block';
            return { currentStepTitle: heading, fields, successVisible };
        }
        """
    )


async def call_dom_tool(page, tool_name, tool_input):
    if tool_name == "get_page_snapshot":
        return await get_page_snapshot(page)
    if tool_name == "click":
        await page.click(tool_input["selector"], timeout=5000)
        return {"ok": True}
    if tool_name == "fill":
        await page.fill(tool_input["selector"], tool_input["value"], timeout=5000)
        return {"ok": True}
    if tool_name == "select_option":
        await page.select_option(tool_input["selector"], tool_input["value"], timeout=5000)
        return {"ok": True}
    if tool_name == "check":
        await page.check(tool_input["selector"], timeout=5000)
        return {"ok": True}
    raise ValueError(f"Unknown tool: {tool_name}")


async def get_webmcp_tools(page):
    """Discover WebMCP tools and normalize to the harness's internal
    tool-dict shape ({name, description, input_schema}), since the real
    WebMCP JS API uses `inputSchema` (camelCase) while our Agent tool
    builders (_anthropic_tools/_openai_tools) expect `input_schema`
    (snake_case) to match Anthropic's/OpenAI's respective conventions."""
    raw_tools = await page.evaluate(
        """
        async () => {
            const mc = document.modelContext || navigator.modelContext;
            if (!mc) return [];
            const tools = await mc.getTools();
            return tools.map(t => ({
                name: t.name,
                description: t.description,
                inputSchema: typeof t.inputSchema === 'string' ? JSON.parse(t.inputSchema) : t.inputSchema,
            }));
        }
        """
    )
    return [
        {"name": t["name"], "description": t["description"], "input_schema": t["inputSchema"]}
        for t in raw_tools
    ]


async def call_webmcp_tool(page, tool_name, tool_input):
    result = await page.evaluate(
        """
        async ({name, args}) => {
            const mc = document.modelContext || navigator.modelContext;
            return await mc.__callTool(name, args);
        }
        """,
        {"name": tool_name, "args": tool_input},
    )
    return {"ok": True, "result": result}


async def is_submitted(page):
    return await page.evaluate(
        "() => document.getElementById('success-banner')?.style.display === 'block'"
    )


class Agent:
    """Thin wrapper over Anthropic or OpenAI tool-calling APIs."""

    def __init__(self):
        self.provider = os.environ.get("MODEL_PROVIDER")
        if not self.provider:
            if os.environ.get("ANTHROPIC_API_KEY"):
                self.provider = "anthropic"
            elif os.environ.get("OPENAI_API_KEY"):
                self.provider = "openai"
            else:
                raise RuntimeError(
                    "No API key found. Set ANTHROPIC_API_KEY or OPENAI_API_KEY."
                )

        if self.provider == "anthropic":
            import anthropic
            self.client = anthropic.Anthropic()
            self.model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        elif self.provider == "openai":
            import openai
            self.client = openai.OpenAI()
            self.model = os.environ.get("OPENAI_MODEL", "gpt-4o")
        else:
            raise RuntimeError(f"Unknown MODEL_PROVIDER: {self.provider}")

        self.total_tokens = 0

    def _anthropic_tools(self, tools):
        return [
            {"name": t["name"], "description": t["description"], "input_schema": t["input_schema"]}
            for t in tools
        ]

    def _openai_tools(self, tools):
        return [
            {
                "type": "function",
                "function": {
                    "name": t["name"],
                    "description": t["description"],
                    "parameters": t["input_schema"],
                },
            }
            for t in tools
        ]

    def step(self, messages, tools):
        if self.provider == "anthropic":
            resp = self.client.messages.create(
                model=self.model,
                max_tokens=2048,
                system=(
                    "You are an autonomous browser agent filling out a job application. "
                    "Use the provided tools to inspect and interact with the page. "
                    "Work step by step: get a page snapshot, act, verify, and move on. "
                    "Call submit_application (or click the submit button) only once all "
                    "required steps are complete."
                ),
                messages=messages,
                tools=self._anthropic_tools(tools),
            )
            self.total_tokens += resp.usage.input_tokens + resp.usage.output_tokens
            return resp
        else:
            resp = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                tools=self._openai_tools(tools),
            )
            if resp.usage:
                self.total_tokens += resp.usage.total_tokens
            return resp


async def run_trial(variant: str, trial_id: int, max_steps: int = 40):
    """Run a single agent trial against one variant. Returns a result dict."""
    agent = Agent()
    start = time.time()
    steps_taken = 0
    action_log = []
    error = None
    success = False

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        url = f"{BASE_URL}/demo-{variant}/index.html"
        await page.goto(url)
        await page.wait_for_timeout(200)

        if variant == "webmcp":
            tools = await get_webmcp_tools(page)
            # Add get_page_snapshot for agent orientation even in WebMCP mode.
            tools = tools + [DOM_ACTUATION_TOOLS[-1]]
        else:
            tools = DOM_ACTUATION_TOOLS

        # Anthropic-style running message list (works fine as our own log too)
        messages = [
            {
                "role": "user",
                "content": TASK_DESCRIPTION
                + ("\n\n" + WEBMCP_TOOLS_DESCRIPTION_HINT if variant == "webmcp" else ""),
            }
        ]

        try:
            while steps_taken < max_steps:
                resp = agent.step(messages, tools)
                steps_taken += 1

                if agent.provider == "anthropic":
                    messages.append({"role": "assistant", "content": resp.content})
                    tool_use_blocks = [b for b in resp.content if b.type == "tool_use"]
                    if not tool_use_blocks:
                        # Model produced text with no tool call; treat as
                        # a stall unless it also completed submission already.
                        if await is_submitted(page):
                            success = True
                            break
                        # Nudge once, then keep going; do not loop forever.
                        messages.append({
                            "role": "user",
                            "content": "Continue by calling a tool to make progress, or submit the application if ready.",
                        })
                        continue

                    tool_results = []
                    for block in tool_use_blocks:
                        try:
                            if variant == "dom":
                                result = await call_dom_tool(page, block.name, block.input)
                            else:
                                if block.name == "get_page_snapshot":
                                    result = await get_page_snapshot(page)
                                else:
                                    result = await call_webmcp_tool(page, block.name, block.input)
                        except Exception as tool_err:
                            result = {"ok": False, "error": str(tool_err)}
                        action_log.append({"tool": block.name, "input": block.input, "result": result})
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": json.dumps(result, default=str),
                        })
                    messages.append({"role": "user", "content": tool_results})

                else:  # openai
                    msg = resp.choices[0].message
                    messages.append(msg.model_dump())
                    tool_calls = msg.tool_calls or []
                    if not tool_calls:
                        if await is_submitted(page):
                            success = True
                            break
                        messages.append({
                            "role": "user",
                            "content": "Continue by calling a tool to make progress, or submit the application if ready.",
                        })
                        continue
                    for tc in tool_calls:
                        args = json.loads(tc.function.arguments or "{}")
                        try:
                            if variant == "dom":
                                result = await call_dom_tool(page, tc.function.name, args)
                            else:
                                if tc.function.name == "get_page_snapshot":
                                    result = await get_page_snapshot(page)
                                else:
                                    result = await call_webmcp_tool(page, tc.function.name, args)
                        except Exception as tool_err:
                            result = {"ok": False, "error": str(tool_err)}
                        action_log.append({"tool": tc.function.name, "input": args, "result": result})
                        messages.append({
                            "role": "tool",
                            "tool_call_id": tc.id,
                            "content": json.dumps(result, default=str),
                        })

                if await is_submitted(page):
                    success = True
                    break

        except Exception:
            error = traceback.format_exc()

        submitted_payload = None
        if success:
            submitted_payload = await page.evaluate("window.__SUBMITTED_APPLICATION__")

        await browser.close()

    elapsed = time.time() - start
    return {
        "variant": variant,
        "trial_id": trial_id,
        "success": success,
        "steps_taken": steps_taken,
        "elapsed_seconds": round(elapsed, 2),
        "total_tokens": agent.total_tokens,
        "provider": agent.provider,
        "model": agent.model,
        "error": error,
        "action_log": action_log,
        "submitted_payload": submitted_payload,
    }


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["dom", "webmcp", "both"], default="both")
    parser.add_argument("--trials", type=int, default=5)
    parser.add_argument("--max-steps", type=int, default=40)
    args = parser.parse_args()

    variants = ["dom", "webmcp"] if args.variant == "both" else [args.variant]

    RESULTS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(RESULTS_PATH, "a") as f:
        for variant in variants:
            for i in range(args.trials):
                print(f"=== Running variant={variant} trial={i} ===")
                result = await run_trial(variant, i, max_steps=args.max_steps)
                print(
                    f"  success={result['success']} steps={result['steps_taken']} "
                    f"tokens={result['total_tokens']} time={result['elapsed_seconds']}s"
                )
                f.write(json.dumps(result, default=str) + "\n")
                f.flush()

    print(f"\nResults appended to {RESULTS_PATH}")


if __name__ == "__main__":
    asyncio.run(main())
