import { describe, it, expect } from "vitest";
import {
  isValidEmail,
  validateApplication,
  generateSlug,
} from "@/app/api/careers/_lib/validate";

const VALID_FIELDS = {
  first_name: "Naledi",
  last_name: "Mokoena",
  email: "naledi@example.com",
  phone: "+27 82 000 0000",
  website: "",
};

describe("isValidEmail", () => {
  it("accepts common valid addresses", () => {
    expect(isValidEmail("jane@example.com")).toBe(true);
    expect(isValidEmail("first.last+tag@sub.domain.co.za")).toBe(true);
    expect(isValidEmail("  padded@example.org  ")).toBe(true);
  });

  it("rejects invalid addresses", () => {
    expect(isValidEmail("")).toBe(false);
    expect(isValidEmail("plainaddress")).toBe(false);
    expect(isValidEmail("missing-at.example.com")).toBe(false);
    expect(isValidEmail("no-domain@")).toBe(false);
    expect(isValidEmail("@no-local.com")).toBe(false);
    expect(isValidEmail("spaces in@example.com")).toBe(false);
    expect(isValidEmail("no-tld@example")).toBe(false);
  });
});

describe("validateApplication", () => {
  it("accepts a complete valid submission and normalises fields", () => {
    const result = validateApplication({
      ...VALID_FIELDS,
      first_name: "  Naledi  ",
      email: "  Naledi@Example.COM ",
    });
    expect(result.ok).toBe(true);
    if (result.ok) {
      expect(result.data.first_name).toBe("Naledi");
      expect(result.data.email).toBe("naledi@example.com");
      expect(result.data.phone).toBe("+27 82 000 0000");
    }
  });

  it("treats empty phone as null", () => {
    const result = validateApplication({ ...VALID_FIELDS, phone: "  " });
    expect(result.ok && result.data.phone).toBe(null);
  });

  it("rejects missing required fields", () => {
    for (const field of ["first_name", "last_name", "email"] as const) {
      const result = validateApplication({ ...VALID_FIELDS, [field]: "" });
      expect(result.ok).toBe(false);
      const missing = validateApplication({ ...VALID_FIELDS, [field]: undefined });
      expect(missing.ok).toBe(false);
    }
  });

  it("rejects non-string required fields", () => {
    expect(validateApplication({ ...VALID_FIELDS, email: 42 }).ok).toBe(false);
  });

  it("rejects invalid email formats", () => {
    for (const email of ["not-an-email", "a@b", "a b@c.com", "@x.com"]) {
      const result = validateApplication({ ...VALID_FIELDS, email });
      expect(result.ok).toBe(false);
    }
  });

  it("rejects when the honeypot field is filled", () => {
    const result = validateApplication({ ...VALID_FIELDS, website: "https://spam.example" });
    expect(result.ok).toBe(false);
  });

  it("allows an empty or absent honeypot", () => {
    expect(validateApplication({ ...VALID_FIELDS, website: "" }).ok).toBe(true);
    expect(validateApplication({ ...VALID_FIELDS, website: undefined }).ok).toBe(true);
    expect(validateApplication({ ...VALID_FIELDS, website: "   " }).ok).toBe(true);
  });
});

describe("generateSlug", () => {
  it("kebab-cases a title and appends the id", () => {
    expect(generateSlug("Senior Software Engineer", 1)).toBe("senior-software-engineer-1");
  });

  it("handles special characters and punctuation", () => {
    expect(generateSlug("Account Executive — Enterprise", 7)).toBe("account-executive-enterprise-7");
    expect(generateSlug("C++ / .NET Developer (Senior!)", 12)).toBe("c-net-developer-senior-12");
    expect(generateSlug("HR & Payroll Специалист", 3)).toBe("hr-payroll-3");
  });

  it("collapses whitespace and repeated separators", () => {
    expect(generateSlug("  Data   Analyst -- Remote  ", 9)).toBe("data-analyst-remote-9");
  });

  it("strips diacritics", () => {
    expect(generateSlug("Café Manager — Zürich", 4)).toBe("cafe-manager-zurich-4");
  });

  it("falls back to 'job' when nothing survives", () => {
    expect(generateSlug("!!!", 42)).toBe("job-42");
    expect(generateSlug("", 5)).toBe("job-5");
  });

  it("keeps numbers in titles", () => {
    expect(generateSlug("Level 2 Support Engineer", 8)).toBe("level-2-support-engineer-8");
  });
});
