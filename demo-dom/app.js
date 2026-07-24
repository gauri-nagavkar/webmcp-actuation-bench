// DOM-baseline job application app.
// No WebMCP instrumentation — an agent must actuate this purely via
// standard DOM interactions (find inputs, click, type, no declared tools).

(function () {
  const schema = APPLICATION_SCHEMA;
  const state = {
    stepIndex: 0,
    data: {
      personal: {},
      experience: [{}], // repeatable
      education: {},
      screening: {},
    },
  };

  const stepperEl = document.getElementById("stepper");
  const stepContainer = document.getElementById("step-container");
  const prevBtn = document.getElementById("prev-btn");
  const nextBtn = document.getElementById("next-btn");
  const submitBtn = document.getElementById("submit-btn");
  const form = document.getElementById("app-form");
  const successBanner = document.getElementById("success-banner");

  function renderStepper() {
    stepperEl.innerHTML = "";
    schema.steps.forEach((step, i) => {
      const div = document.createElement("div");
      div.className = "step" + (i === state.stepIndex ? " active" : i < state.stepIndex ? " done" : "");
      div.textContent = step.title;
      stepperEl.appendChild(div);
    });
  }

  function fieldValue(stepId, name, entryIndex) {
    if (entryIndex !== undefined) {
      return (state.data[stepId][entryIndex] || {})[name];
    }
    return state.data[stepId][name];
  }

  function setFieldValue(stepId, name, value, entryIndex) {
    if (entryIndex !== undefined) {
      if (!state.data[stepId][entryIndex]) state.data[stepId][entryIndex] = {};
      state.data[stepId][entryIndex][name] = value;
    } else {
      state.data[stepId][name] = value;
    }
  }

  function shouldShowField(field, stepId, entryIndex) {
    if (!field.showIf) return true;
    const dependentVal = fieldValue(stepId, field.showIf.field, entryIndex);
    return dependentVal === field.showIf.equals;
  }

  function renderField(field, stepId, entryIndex) {
    const wrap = document.createElement("div");
    wrap.className = "field";
    wrap.dataset.fieldName = field.name;
    if (!shouldShowField(field, stepId, entryIndex)) {
      wrap.style.display = "none";
    }

    const label = document.createElement("label");
    label.textContent = field.label + (field.required ? " *" : "");
    wrap.appendChild(label);

    const inputId = `f_${stepId}_${entryIndex !== undefined ? entryIndex + "_" : ""}${field.name}`;
    const currentVal = fieldValue(stepId, field.name, entryIndex);

    if (field.type === "radio") {
      const group = document.createElement("div");
      group.className = "radio-group";
      field.options.forEach((opt) => {
        const rLabel = document.createElement("label");
        const rInput = document.createElement("input");
        rInput.type = "radio";
        rInput.name = inputId;
        rInput.value = opt;
        rInput.checked = currentVal === opt;
        rInput.addEventListener("change", () => {
          setFieldValue(stepId, field.name, opt, entryIndex);
          renderStep(); // re-render to reveal/hide conditional fields
        });
        rLabel.appendChild(rInput);
        rLabel.appendChild(document.createTextNode(opt));
        group.appendChild(rLabel);
      });
      wrap.appendChild(group);
    } else if (field.type === "select") {
      const select = document.createElement("select");
      select.id = inputId;
      const blank = document.createElement("option");
      blank.value = "";
      blank.textContent = "Select...";
      select.appendChild(blank);
      field.options.forEach((opt) => {
        const o = document.createElement("option");
        o.value = opt;
        o.textContent = opt;
        if (currentVal === opt) o.selected = true;
        select.appendChild(o);
      });
      select.addEventListener("change", (e) => setFieldValue(stepId, field.name, e.target.value, entryIndex));
      wrap.appendChild(select);
    } else if (field.type === "textarea") {
      const ta = document.createElement("textarea");
      ta.id = inputId;
      ta.value = currentVal || "";
      ta.addEventListener("input", (e) => setFieldValue(stepId, field.name, e.target.value, entryIndex));
      wrap.appendChild(ta);

      // AI-assist hook only present in this DOM version as a plain button;
      // wired up in ai-assist.js if Chrome's built-in Prompt API is available.
      if (field.name === "whyInterested" || field.name === "conferenceDetails" || field.name === "description") {
        const assistBox = document.createElement("div");
        assistBox.className = "ai-assist-box";
        assistBox.innerHTML = `<div>✨ On-device AI can draft this for you from your resume.</div>`;
        const assistBtn = document.createElement("button");
        assistBtn.type = "button";
        assistBtn.textContent = "Draft with on-device AI";
        assistBtn.addEventListener("click", async () => {
          assistBtn.disabled = true;
          assistBtn.textContent = "Thinking...";
          const draft = await window.AIAssist?.draft(field.name);
          if (draft) {
            ta.value = draft;
            setFieldValue(stepId, field.name, draft, entryIndex);
          }
          assistBtn.disabled = false;
          assistBtn.textContent = "Draft with on-device AI";
        });
        assistBox.appendChild(assistBtn);
        wrap.appendChild(assistBox);
      }
    } else if (field.type === "checkbox") {
      const row = document.createElement("div");
      row.className = "checkbox-row";
      const cLabel = document.createElement("label");
      const cInput = document.createElement("input");
      cInput.type = "checkbox";
      cInput.id = inputId;
      cInput.checked = !!currentVal;
      cInput.addEventListener("change", (e) => setFieldValue(stepId, field.name, e.target.checked, entryIndex));
      cLabel.appendChild(cInput);
      cLabel.appendChild(document.createTextNode(field.label));
      row.appendChild(cLabel);
      wrap.innerHTML = ""; // checkbox renders its own label
      wrap.appendChild(row);
    } else {
      const input = document.createElement("input");
      input.type = field.type;
      input.id = inputId;
      input.value = currentVal || "";
      input.addEventListener("input", (e) => setFieldValue(stepId, field.name, e.target.value, entryIndex));
      wrap.appendChild(input);
    }

    const err = document.createElement("div");
    err.className = "error-msg";
    err.textContent = `${field.label} is required.`;
    wrap.appendChild(err);

    return wrap;
  }

  function renderStep() {
    renderStepper();
    stepContainer.innerHTML = "";
    const step = schema.steps[state.stepIndex];

    const heading = document.createElement("h2");
    heading.textContent = step.title;
    stepContainer.appendChild(heading);

    if (step.review) {
      renderReview();
    } else if (step.repeatable) {
      const entries = state.data[step.id];
      entries.forEach((_, idx) => {
        const block = document.createElement("div");
        block.className = "entry-block";
        block.dataset.entryIndex = idx;

        const title = document.createElement("div");
        title.className = "entry-title";
        title.textContent = `Entry ${idx + 1}`;
        block.appendChild(title);

        if (entries.length > step.minEntries) {
          const removeBtn = document.createElement("button");
          removeBtn.type = "button";
          removeBtn.className = "remove-entry-btn";
          removeBtn.textContent = "Remove";
          removeBtn.addEventListener("click", () => {
            entries.splice(idx, 1);
            renderStep();
          });
          block.appendChild(removeBtn);
        }

        step.entryFields.forEach((f) => block.appendChild(renderField(f, step.id, idx)));
        stepContainer.appendChild(block);
      });

      if (entries.length < step.maxEntries) {
        const addBtn = document.createElement("button");
        addBtn.type = "button";
        addBtn.className = "add-entry-btn";
        addBtn.id = "add-experience-btn";
        addBtn.textContent = "+ Add another position";
        addBtn.addEventListener("click", () => {
          entries.push({});
          renderStep();
        });
        stepContainer.appendChild(addBtn);
      }
    } else {
      step.fields.forEach((f) => stepContainer.appendChild(renderField(f, step.id)));
    }

    prevBtn.style.display = state.stepIndex === 0 ? "none" : "inline-block";
    const isLast = state.stepIndex === schema.steps.length - 1;
    nextBtn.style.display = isLast ? "none" : "inline-block";
    submitBtn.style.display = isLast ? "inline-block" : "none";
  }

  function renderReview() {
    schema.steps.forEach((step) => {
      if (step.review) return;
      const section = document.createElement("div");
      section.className = "review-section";
      const h3 = document.createElement("h3");
      h3.textContent = step.title;
      section.appendChild(h3);

      if (step.repeatable) {
        state.data[step.id].forEach((entry, idx) => {
          step.entryFields.forEach((f) => {
            const row = document.createElement("div");
            row.className = "review-row";
            row.innerHTML = `<span>${step.title} #${idx + 1} — ${f.label}</span><span>${entry[f.name] ?? ""}</span>`;
            section.appendChild(row);
          });
        });
      } else {
        step.fields.forEach((f) => {
          const row = document.createElement("div");
          row.className = "review-row";
          row.innerHTML = `<span>${f.label}</span><span>${state.data[step.id][f.name] ?? ""}</span>`;
          section.appendChild(row);
        });
      }
      stepContainer.appendChild(section);
    });
  }

  function validateStep() {
    const step = schema.steps[state.stepIndex];
    if (step.review) return true;
    let valid = true;

    const fieldsToCheck = step.repeatable
      ? state.data[step.id].flatMap((_, idx) => step.entryFields.map((f) => ({ f, idx })))
      : step.fields.map((f) => ({ f, idx: undefined }));

    fieldsToCheck.forEach(({ f, idx }) => {
      if (!f.required) return;
      if (!shouldShowField(f, step.id, idx)) return;
      const val = fieldValue(step.id, f.name, idx);
      const selector = idx !== undefined
        ? `.entry-block[data-entry-index="${idx}"] .field[data-field-name="${f.name}"]`
        : `.field[data-field-name="${f.name}"]`;
      const el = stepContainer.querySelector(selector);
      if (val === undefined || val === "" || val === null) {
        valid = false;
        el?.classList.add("error");
      } else {
        el?.classList.remove("error");
      }
    });

    return valid;
  }

  nextBtn.addEventListener("click", () => {
    if (!validateStep()) return;
    state.stepIndex = Math.min(state.stepIndex + 1, schema.steps.length - 1);
    renderStep();
    window.scrollTo(0, 0);
  });

  prevBtn.addEventListener("click", () => {
    state.stepIndex = Math.max(state.stepIndex - 1, 0);
    renderStep();
    window.scrollTo(0, 0);
  });

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    form.style.display = "none";
    stepperEl.style.display = "none";
    successBanner.style.display = "block";
    // Expose final payload for the benchmark harness to assert against.
    window.__SUBMITTED_APPLICATION__ = JSON.parse(JSON.stringify(state.data));
    document.title = "Application Submitted";
  });

  renderStep();

  // Expose state for debugging / harness introspection.
  window.__APP_STATE__ = state;
  window.__rerenderCurrentStep__ = renderStep;
})();
