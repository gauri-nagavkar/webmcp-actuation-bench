AI agents that promise to "autofill" multi-step forms are notoriously unreliable — misclicks, skipped conditional fields, lost track of repeatable sections. I wanted actual numbers on why, so I built a benchmark.

I built the same 5-step structured form (a job application, since that's Chrome's own flagship WebMCP example) twice — once as plain DOM (agent has to click/type like a human), once instrumented with Chrome's brand-new WebMCP API (agent calls structured tools instead: fill_personal_info, add_work_experience, submit_application, etc.). Then I ran GPT-4o as an autonomous agent against both, 10 trials each.

Results:
→ DOM: 100% success, avg 18.4 actions, 52k tokens, 21.8s
→ WebMCP: 90% success, avg 7.6 tool calls (< half), 37k tokens, 10.3s

WebMCP was faster and cheaper when it worked — but its one failure was the most interesting result: the agent called a tool correctly, the data updated, but the visible UI never advanced (a real sync bug between WebMCP state and DOM rendering), so the agent stalled checking the page 34 times without noticing nothing was moving. That's a genuinely useful finding about a failure mode plain DOM automation doesn't have.

Also wired up Chrome's on-device Prompt API (Gemini Nano, no server round-trip) for an AI-assisted answer drafter on the free-text fields.

Full writeup + repo (Playwright harness, raw per-trial data including the failure, reproducible in ~10 min): [link]

Genuinely interested in this space — WebMCP, agentic web standards, on-device AI in the browser. Would love to hear from anyone else experimenting with this.

#ChromeAI #WebMCP #DeveloperRelations #AIagents
