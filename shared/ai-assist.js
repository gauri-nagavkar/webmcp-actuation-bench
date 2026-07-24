// Shared on-device AI assist using Chrome's built-in Prompt API
// (LanguageModel / window.ai). Falls back gracefully with a clear message
// when the API isn't available (e.g. non-Chrome browser, flag not enabled,
// or model not yet downloaded) — demos should never hard-fail here.
//
// Docs: https://developer.chrome.com/docs/ai/prompt-api

window.AIAssist = (function () {
  let session = null;

  // Minimal fake "resume" context. In a real product this would come from
  // an uploaded resume or a profile the user filled in once.
  const RESUME_CONTEXT = `
Name: Applicant
Background: Software engineer with 5 years of experience in AI/ML systems,
including building on-device inference features, evaluation harnesses, and
developer-facing tooling. Has spoken at internal tech talks and written
technical blog posts about model evaluation and browser-based AI.
`;

  const PROMPTS = {
    whyInterested:
      "Write a concise, specific 2-3 sentence answer to 'Why are you interested in this Developer Relations Engineer, Chrome AI role?' " +
      "Reference the candidate's background below. Keep it natural, not generic corporate language.\n\n" + RESUME_CONTEXT,
    conferenceDetails:
      "Write a concise 1-2 sentence summary of the candidate's public speaking / technical writing experience, " +
      "based on the background below. Keep it factual and specific.\n\n" + RESUME_CONTEXT,
    description:
      "Write a concise 2-3 sentence job description summary for a Software Engineer role focused on AI/ML systems, " +
      "based on the background below. Use action verbs, past tense.\n\n" + RESUME_CONTEXT,
  };

  async function getSession() {
    if (session) return session;

    const LanguageModel = window.LanguageModel || (window.ai && window.ai.languageModel);
    if (!LanguageModel) {
      throw new Error("UNAVAILABLE");
    }

    const availability = await (LanguageModel.availability
      ? LanguageModel.availability()
      : LanguageModel.capabilities().then((c) => c.available));

    if (availability === "no" || availability === "unavailable") {
      throw new Error("UNAVAILABLE");
    }

    session = await LanguageModel.create({
      monitor(m) {
        m.addEventListener("downloadprogress", (e) => {
          console.log(`Model download: ${Math.round(e.loaded * 100)}%`);
        });
      },
    });
    return session;
  }

  async function draft(fieldName) {
    const promptText = PROMPTS[fieldName];
    if (!promptText) return null;

    try {
      const s = await getSession();
      const result = await s.prompt(promptText);
      return result.trim();
    } catch (err) {
      console.warn("On-device AI unavailable, using static fallback:", err.message);
      return FALLBACKS[fieldName] || null;
    }
  }

  // Static fallback text used when Chrome's built-in AI isn't available in
  // the current environment (e.g. CI, non-Chrome browser, headless Playwright
  // without the model downloaded). Keeps the demo/benchmark functional
  // end-to-end regardless of AI availability.
  const FALLBACKS = {
    whyInterested:
      "I've spent my career building AI/ML systems and I'm excited to bring that technical depth to advocating for developers building on Chrome's AI platform, especially around on-device inference and agentic web standards like WebMCP.",
    conferenceDetails:
      "I've given internal tech talks on model evaluation and written technical posts on browser-based AI tooling.",
    description:
      "Built and evaluated AI/ML systems end-to-end, including on-device inference features and internal evaluation tooling for model quality.",
  };

  return { draft };
})();
