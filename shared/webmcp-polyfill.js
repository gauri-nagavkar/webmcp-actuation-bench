// Minimal WebMCP polyfill for benchmarking purposes.
//
// WebMCP (document.modelContext) is currently gated behind a Chrome flag
// (chrome://flags/#enable-webmcp-testing) or an origin trial on bleeding-edge
// Chrome builds, and is NOT yet present in stable/Playwright-bundled
// Chromium. To make this benchmark runnable today -- and to give a concrete,
// working reference for what the imperative API surface looks like -- this
// file polyfills `document.modelContext` with the same shape described in
// Chrome's docs (registerTool / getTools), IF AND ONLY IF the browser does
// not already provide a native implementation.
//
// This is a deliberate, disclosed shim for benchmarking, not a spec
// implementation: it does not enforce origin isolation, permissions policy,
// or JSON Schema validation the way the real browser API will. When Chrome
// ships WebMCP more broadly, this file becomes a no-op (the `if` guard below
// skips polyfilling) and the real browser API takes over transparently,
// since demo-webmcp/webmcp-tools.js only ever calls the modelContext
// surface, never this file directly.
//
// Reference: https://developer.chrome.com/docs/ai/webmcp/imperative-api

(function () {
  if (document.modelContext || navigator.modelContext) {
    // Native (or real origin-trial) WebMCP is present -- do nothing.
    return;
  }

  const registeredTools = new Map();

  const modelContextPolyfill = {
    async registerTool(tool, options) {
      registeredTools.set(tool.name, tool);
      if (options && options.signal) {
        options.signal.addEventListener("abort", () => {
          registeredTools.delete(tool.name);
        });
      }
      return undefined;
    },

    async getTools() {
      return Array.from(registeredTools.values()).map((t) => ({
        name: t.name,
        description: t.description,
        inputSchema: JSON.stringify(t.inputSchema),
        annotations: t.annotations || {},
        origin: window.location.origin,
      })).sort((a, b) => a.name.localeCompare(b.name));
    },

    // Not part of the real spec surface (real agents call tools through the
    // browser's own agent integration, not JS) -- but our benchmark harness
    // needs a way to actually invoke a discovered tool, playing the role
    // that Chrome's built-in agent would play in production. Exposed only
    // by this polyfill, and clearly documented as a bench-harness bridge.
    async __callTool(name, args) {
      const tool = registeredTools.get(name);
      if (!tool) throw new Error(`Unknown WebMCP tool: ${name}`);
      return tool.execute(args);
    },
  };

  Object.defineProperty(document, "modelContext", {
    value: modelContextPolyfill,
    writable: false,
    configurable: true,
  });

  console.log("[webmcp-polyfill] document.modelContext polyfilled for benchmarking (native API not detected).");
})();
