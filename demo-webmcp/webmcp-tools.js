// WebMCP tool registration for the job application form.
// Exposes the same functional surface as demo-dom/app.js, but instead of
// requiring an agent to locate and click/type into individual DOM elements,
// each logical action is registered as a WebMCP tool with a JSON Schema.
//
// This file assumes app.js has already run and exposed window.__APP_STATE__
// plus the module-level render functions are NOT exported, so we replicate
// the minimal state-mutation + re-render call by dispatching synthetic
// interactions through the same input elements app.js rendered. This keeps
// a SINGLE source of truth for form state/validation (shared/schema.js +
// app.js) while giving agents a structured, declarative way in.
//
// API reference: https://developer.chrome.com/docs/ai/webmcp/imperative-api
// Note: navigator.modelContext is deprecated in Chrome 150+; use
// document.modelContext instead.

(function () {
  function getModelContext() {
    return document.modelContext || navigator.modelContext;
  }

  const modelContext = getModelContext();
  if (!modelContext) {
    console.warn(
      "[webmcp-tools] document.modelContext is not available in this browser. " +
      "Enable chrome://flags/#enable-webmcp-testing or run in a Chrome build with the WebMCP origin trial."
    );
    return;
  }

  function currentStep() {
    return APPLICATION_SCHEMA.steps[window.__APP_STATE__.stepIndex];
  }

  function goToStep(targetId) {
    const idx = APPLICATION_SCHEMA.steps.findIndex((s) => s.id === targetId);
    if (idx === -1) throw new Error(`Unknown step: ${targetId}`);
    window.__APP_STATE__.stepIndex = idx;
    document.getElementById("next-btn").dispatchEvent(new Event("__noop__"));
    window.dispatchEvent(new CustomEvent("__webmcp_rerender__"));
  }

  // --- Tool 1: fill_personal_info -------------------------------------
  modelContext.registerTool({
    name: "fill_personal_info",
    description:
      "Fill the Personal Information step of the job application (name, email, phone, " +
      "location, work authorization, sponsorship needs). Call this once with all known values.",
    inputSchema: {
      type: "object",
      properties: {
        fullName: { type: "string" },
        email: { type: "string" },
        phone: { type: "string" },
        location: { type: "string", description: "City, State" },
        workAuthorized: { type: "string", enum: ["Yes", "No"] },
        needsSponsorship: { type: "string", enum: ["Yes", "No"] },
        sponsorshipDetails: { type: "string" },
      },
      required: ["fullName", "email", "phone", "location", "workAuthorized", "needsSponsorship"],
    },
    execute: async (args) => {
      Object.assign(window.__APP_STATE__.data.personal, args);
      window.dispatchEvent(new CustomEvent("__webmcp_apply__", { detail: { step: "personal" } }));
      return `Personal information filled: ${args.fullName}, ${args.email}`;
    },
  });

  // --- Tool 2: add_work_experience -------------------------------------
  modelContext.registerTool({
    name: "add_work_experience",
    description:
      "Add one work experience entry to the application. Call multiple times for multiple " +
      "positions (up to 4). Use isCurrent=true and omit endDate for the current role.",
    inputSchema: {
      type: "object",
      properties: {
        company: { type: "string" },
        title: { type: "string" },
        startDate: { type: "string", description: "YYYY-MM" },
        endDate: { type: "string", description: "YYYY-MM, omit if current" },
        isCurrent: { type: "boolean" },
        description: { type: "string" },
      },
      required: ["company", "title", "startDate", "description"],
    },
    execute: async (args) => {
      const entries = window.__APP_STATE__.data.experience;
      // Fill first empty slot, or push a new one.
      const emptyIdx = entries.findIndex((e) => !e.company);
      if (emptyIdx !== -1) {
        entries[emptyIdx] = args;
      } else {
        entries.push(args);
      }
      window.dispatchEvent(new CustomEvent("__webmcp_apply__", { detail: { step: "experience" } }));
      return `Added work experience: ${args.title} at ${args.company}`;
    },
  });

  // --- Tool 3: fill_education -------------------------------------------
  modelContext.registerTool({
    name: "fill_education",
    description: "Fill the Education step of the job application.",
    inputSchema: {
      type: "object",
      properties: {
        degree: { type: "string", enum: ["Bachelor's", "Master's", "PhD", "Other"] },
        field: { type: "string" },
        school: { type: "string" },
        gradYear: { type: "number" },
      },
      required: ["degree", "field", "school", "gradYear"],
    },
    execute: async (args) => {
      Object.assign(window.__APP_STATE__.data.education, args);
      window.dispatchEvent(new CustomEvent("__webmcp_apply__", { detail: { step: "education" } }));
      return `Education filled: ${args.degree} in ${args.field} from ${args.school}`;
    },
  });

  // --- Tool 4: fill_screening_questions ---------------------------------
  modelContext.registerTool({
    name: "fill_screening_questions",
    description:
      "Fill the Screening Questions step: years of experience, conference/speaking " +
      "experience, motivation for the role, and relocation willingness.",
    inputSchema: {
      type: "object",
      properties: {
        yearsExperience: { type: "number" },
        hasConferenceExp: { type: "string", enum: ["Yes", "No"] },
        conferenceDetails: { type: "string" },
        whyInterested: { type: "string" },
        relocate: { type: "string", enum: ["Yes", "No", "Open to hybrid/remote discussion"] },
      },
      required: ["yearsExperience", "hasConferenceExp", "whyInterested", "relocate"],
    },
    execute: async (args) => {
      Object.assign(window.__APP_STATE__.data.screening, args);
      window.dispatchEvent(new CustomEvent("__webmcp_apply__", { detail: { step: "screening" } }));
      return "Screening questions filled.";
    },
  });

  // --- Tool 5: draft_with_ai --------------------------------------------
  modelContext.registerTool({
    name: "draft_with_ai",
    description:
      "Use Chrome's on-device AI (Prompt API) to draft free-text answer content for a given " +
      "field (whyInterested, conferenceDetails, or description) based on the applicant's resume context.",
    inputSchema: {
      type: "object",
      properties: {
        fieldName: { type: "string", enum: ["whyInterested", "conferenceDetails", "description"] },
      },
      required: ["fieldName"],
    },
    execute: async ({ fieldName }) => {
      const draft = await window.AIAssist.draft(fieldName);
      return draft || "";
    },
  });

  // --- Tool 6: submit_application ----------------------------------------
  modelContext.registerTool({
    name: "submit_application",
    description:
      "Submit the job application. Only call after all required steps (personal, at least " +
      "one work experience, education, screening) have been filled.",
    inputSchema: { type: "object", properties: {} },
    execute: async () => {
      window.__SUBMITTED_APPLICATION__ = JSON.parse(JSON.stringify(window.__APP_STATE__.data));
      document.getElementById("app-form").style.display = "none";
      document.getElementById("stepper").style.display = "none";
      document.getElementById("success-banner").style.display = "block";
      document.title = "Application Submitted";
      return "Application submitted successfully.";
    },
  });

  // Force a re-render whenever tool-driven state changes happen, by
  // replaying step navigation to the step the just-filled data belongs to,
  // then invoking the same render path app.js uses internally.
  // Since app.js's render functions are closures (not exported), we trigger
  // re-render by simulating the Next/Prev button no-op and relying on
  // app.js's own step-render-on-load behavior plus a full page state dump.
  // For a production implementation, app.js's `renderStep` would be
  // exported directly; here we re-render by forcing the visible step to
  // reflect current data via a lightweight custom re-render call exposed
  // by app.js (see window.__rerenderCurrentStep__ below, wired in app.js).
  window.addEventListener("__webmcp_apply__", () => {
    if (typeof window.__rerenderCurrentStep__ === "function") {
      window.__rerenderCurrentStep__();
    }
  });

  console.log(
    "[webmcp-tools] Registered tools:",
    ["fill_personal_info", "add_work_experience", "fill_education", "fill_screening_questions", "draft_with_ai", "submit_application"]
  );
})();
