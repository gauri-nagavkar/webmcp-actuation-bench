// Shared data model + validation logic for the job application form.
// Used identically by both the DOM-only and WebMCP demo versions so the
// underlying task complexity is held constant across the benchmark.

const APPLICATION_SCHEMA = {
  steps: [
    {
      id: "personal",
      title: "Personal Information",
      fields: [
        { name: "fullName", label: "Full name", type: "text", required: true },
        { name: "email", label: "Email", type: "email", required: true },
        { name: "phone", label: "Phone", type: "tel", required: true },
        { name: "location", label: "Location (City, State)", type: "text", required: true },
        {
          name: "workAuthorized",
          label: "Are you authorized to work in the US?",
          type: "radio",
          options: ["Yes", "No"],
          required: true,
        },
        {
          name: "needsSponsorship",
          label: "Will you now or in the future require visa sponsorship?",
          type: "radio",
          options: ["Yes", "No"],
          required: true,
          // conditional field revealed only when needsSponsorship === "Yes"
        },
        {
          name: "sponsorshipDetails",
          label: "Please describe your visa status",
          type: "text",
          required: false,
          showIf: { field: "needsSponsorship", equals: "Yes" },
        },
      ],
    },
    {
      id: "experience",
      title: "Work Experience",
      repeatable: true,
      minEntries: 1,
      maxEntries: 4,
      entryFields: [
        { name: "company", label: "Company", type: "text", required: true },
        { name: "title", label: "Job title", type: "text", required: true },
        { name: "startDate", label: "Start date", type: "month", required: true },
        { name: "endDate", label: "End date (leave blank if current)", type: "month", required: false },
        { name: "isCurrent", label: "I currently work here", type: "checkbox", required: false },
        { name: "description", label: "Description of responsibilities", type: "textarea", required: true },
      ],
    },
    {
      id: "education",
      title: "Education",
      fields: [
        { name: "degree", label: "Degree", type: "select", options: ["Bachelor's", "Master's", "PhD", "Other"], required: true },
        { name: "field", label: "Field of study", type: "text", required: true },
        { name: "school", label: "School", type: "text", required: true },
        { name: "gradYear", label: "Graduation year", type: "number", required: true },
      ],
    },
    {
      id: "screening",
      title: "Screening Questions",
      fields: [
        {
          name: "yearsExperience",
          label: "Years of relevant technical experience",
          type: "number",
          required: true,
        },
        {
          name: "hasConferenceExp",
          label: "Have you spoken at technical conferences or published technical articles?",
          type: "radio",
          options: ["Yes", "No"],
          required: true,
        },
        {
          name: "conferenceDetails",
          label: "Briefly describe your speaking/writing experience",
          type: "textarea",
          required: false,
          showIf: { field: "hasConferenceExp", equals: "Yes" },
        },
        {
          name: "whyInterested",
          label: "Why are you interested in this role?",
          type: "textarea",
          required: true,
        },
        {
          name: "relocate",
          label: "Are you willing to relocate to Mountain View, CA?",
          type: "radio",
          options: ["Yes", "No", "Open to hybrid/remote discussion"],
          required: true,
        },
      ],
    },
    {
      id: "review",
      title: "Review & Submit",
      review: true,
    },
  ],
};

if (typeof module !== "undefined") {
  module.exports = { APPLICATION_SCHEMA };
}
