# Benchmarking AI Agents on Multi-Step Forms: DOM Clicking vs. Chrome's New WebMCP API

AI agents that promise to autofill multi-step forms are notoriously unreliable in practice. They misclick, skip conditional fields, lose track of repeatable sections (multiple line items, multiple entries), or give up halfway through a long flow. This is one of the most common tasks people now hand off to agents, and one of the least reliable.

So I built a benchmark to put some numbers on it.

## The setup

I built the same 5-step structured form twice — a job application form, since Chrome's own WebMCP docs cite exactly this use case (a `submit_application` tool) as one of their flagship examples:

1. **DOM baseline** — a plain HTML/JS form. An agent has to actuate it like a human: find inputs, click radios, type text, click "Next," handle a repeatable "Add another entry" button, across 5 pages.
2. **WebMCP version** — the identical form, but instrumented with [Chrome's new WebMCP API](https://developer.chrome.com/docs/ai/webmcp) (`document.modelContext.registerTool()`). Instead of clicking around, an agent calls structured tools directly: `fill_personal_info`, `add_work_experience`, `fill_education`, `fill_screening_questions`, `submit_application`.

Same underlying data model (`shared/schema.js` is the single source of truth for both), same validation, same conditional logic (e.g., a follow-up detail field that only appears if you answer "yes" to a specific question). The only variable is *how* the agent interacts with the page.

I also wired up Chrome's on-device Prompt API (Gemini Nano, running locally, no server round-trip) as a "Draft with AI" button on free-text fields — because the other half of the "Chrome AI" story is what runs *in* the browser, not just what agents call *into* it.

Then I ran a real LLM (GPT-4o) as an autonomous agent against both, 10 trials each, and measured success rate, steps taken, tokens consumed, and — critically — how it failed when it failed.

## The results

| Variant | Success rate | Avg. steps/tool-calls | Avg. tokens | Avg. time |
|---|---|---|---|---|
| DOM (plain actuation) | 100% (10/10) | 18.4 | 52,187 | 21.8s |
| WebMCP (tool calls) | 90% (9/10) | **7.6** | 36,745 | 10.3s |

WebMCP cut the number of actions less than half, used ~30% fewer tokens, and finished in about half the wall-clock time — when it worked.

## The interesting part: how WebMCP failed

DOM actuation was slower and more expensive, but boringly reliable — 10/10. WebMCP was faster, cheaper, and *almost* as reliable, but its one failure was genuinely instructive, not a fluke.

In trial 6, the agent correctly called `fill_personal_info` — verified in the raw action log, the tool executed and mutated the form's state. But my demo's WebMCP tools update application state directly without triggering the same step-navigation that clicking the DOM "Next" button does. So the visible UI stayed frozen on "Personal Information." The agent, relying on a `get_page_snapshot` tool to check its progress, saw no change, and called that same snapshot tool 34 times in a row before hitting my step cap — without ever calling `submit_application`.

That's a real coordination bug between a site's WebMCP-exposed state and its visible UI, and it's exactly the kind of failure mode you'd want to catch *before* shipping WebMCP tools on a production site: if your tool execution doesn't stay in sync with what a (possibly supervising) human sees on screen, an agent can silently stall even though every individual tool call "succeeded."

I've filed it as a fix in the repo (tools should trigger navigation, not just mutate data), but I'm keeping the original failing trial in the results — it's more useful undoctored.

## Why this matters

WebMCP is brand new — its origin trial only started in May 2026, and `document.modelContext` isn't in stable Chromium builds yet (I had to write a small, clearly-disclosed polyfill matching the real API's shape to run this benchmark today). There isn't much public, quantitative data yet on how much it actually helps agent reliability versus plain DOM automation. This is a first attempt at producing some.

The headline number (less than half the actions, faster, cheaper) is the expected story. The failure mode is the one I think is actually valuable: WebMCP moves a lot of "does the agent understand this page" complexity from the agent's reasoning into the site's tool design — which is great, until the site's tool design and its UI drift out of sync, and now you have a new failure mode that didn't exist with plain DOM actuation (where at least the agent and the human are always looking at the same rendered page).

## Try it yourself

Full repo, including the DOM/WebMCP demo apps, the Playwright + LLM benchmark harness, and raw per-trial data (including the failure): **[github.com/gauri-nagavkar/webmcp-actuation-bench](https://github.com/gauri-nagavkar/webmcp-actuation-bench)**

```bash
git clone https://github.com/gauri-nagavkar/webmcp-actuation-bench
cd webmcp-actuation-bench
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt && playwright install chromium
python3 -m http.server 8842 &
python harness/scripted_reference_trial.py   # no API key needed
python harness/run_benchmark.py --variant both --trials 10  # needs an API key
```

Next up: running this against Claude for a cross-model comparison, adding a "messy DOM" variant (ambiguous labels, dynamic IDs) to see if the gap widens, and testing the WebMCP Declarative API (HTML annotations) as a third variant.

If you're working on WebMCP, agentic web standards, or Chrome's built-in AI APIs, I'd love to compare notes.
