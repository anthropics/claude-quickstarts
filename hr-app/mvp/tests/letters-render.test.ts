import { describe, it, expect } from "vitest";
import { MERGE_FIELDS, renderTemplate } from "@/app/letters/_lib/render";

const FULL_DATA = {
  first_name: "Naledi",
  last_name: "Mokoena",
  job_title: "Chief Executive Officer",
  department: "Executive",
  start_date: "2020-01-15",
  employee_number: "EMP001",
  manager_name: "Thabo Nkosi",
  author_name: "Lerato Dlamini",
  reason: "repeated late arrival",
};

describe("renderTemplate", () => {
  it("substitutes every supported merge field", () => {
    const template = MERGE_FIELDS.map((f) => `${f}=[{{${f}}}]`).join("\n");
    const out = renderTemplate(template, FULL_DATA);
    for (const field of MERGE_FIELDS) {
      expect(out).toContain(`${field}=[${FULL_DATA[field]}]`);
    }
    expect(out).not.toContain("{{");
    expect(out).not.toContain("}}");
  });

  it("tolerates whitespace inside the braces", () => {
    expect(renderTemplate("Dear {{ first_name }} {{last_name }}", FULL_DATA)).toBe("Dear Naledi Mokoena");
  });

  it("renders unknown fields as blank instead of leaking raw placeholders", () => {
    const out = renderTemplate("Hello {{first_name}}{{does_not_exist}}!", FULL_DATA);
    expect(out).toBe("Hello Naledi!");
    expect(out).not.toContain("{{does_not_exist}}");
  });

  it("renders a missing optional reason as blank", () => {
    const { reason: _reason, ...withoutReason } = FULL_DATA;
    expect(renderTemplate("Regarding: {{reason}}.", withoutReason)).toBe("Regarding: .");
    expect(renderTemplate("Regarding: {{reason}}.", { ...withoutReason, reason: null })).toBe("Regarding: .");
    expect(renderTemplate("Regarding: {{reason}}.", { ...withoutReason, reason: undefined })).toBe("Regarding: .");
  });

  it("repeats substitution for every occurrence of a field", () => {
    expect(renderTemplate("{{first_name}} {{first_name}}", FULL_DATA)).toBe("Naledi Naledi");
  });

  // The renderer is a pure string substitution: HTML (or template syntax) in
  // employee data is carried through verbatim and never parsed or executed.
  // Display components render the output through React TEXT NODES only
  // (<p className="whitespace-pre-line">{content}</p> in the letter view and
  // preview — never dangerouslySetInnerHTML), so any markup below shows up on
  // screen as inert literal characters.
  it("passes HTML in employee data through as literal text", () => {
    const out = renderTemplate("Dear {{first_name}},", {
      first_name: '<script>alert("xss")</script><b>Bob</b>',
    });
    expect(out).toBe('Dear <script>alert("xss")</script><b>Bob</b>,');
  });

  it("does not re-expand placeholders introduced by employee data", () => {
    // A single left-to-right pass: values containing {{...}} are emitted
    // verbatim, they are not treated as new merge fields.
    const out = renderTemplate("Dear {{first_name}} {{last_name}},", {
      first_name: "{{author_name}}",
      last_name: "Smith",
      author_name: "SHOULD NOT APPEAR",
    });
    expect(out).toBe("Dear {{author_name}} Smith,");
  });

  it("preserves newlines so whitespace-pre-line display keeps paragraphs", () => {
    const out = renderTemplate("Dear {{first_name}},\n\nParagraph two.", FULL_DATA);
    expect(out).toBe("Dear Naledi,\n\nParagraph two.");
  });
});
