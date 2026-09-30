import { describe, it, expect } from "vitest";
import {
  clockStateFromEvents,
  hhmmToMinutes,
  isValidHHMM,
  manualEntryOverlaps,
  minutesToHHMM,
  validateClockTransition,
} from "@/app/time/_lib/time";

function ev(type: string, hhmm: string) {
  return { type, timestamp: `2026-07-06 ${hhmm}:00` };
}

describe("clockStateFromEvents", () => {
  it("is 'out' with no events", () => {
    expect(clockStateFromEvents([])).toBe("out");
  });

  it("follows in → break → back → out", () => {
    const events: { type: string }[] = [];
    events.push({ type: "clock_in" });
    expect(clockStateFromEvents(events)).toBe("in");
    events.push({ type: "break_start" });
    expect(clockStateFromEvents(events)).toBe("on_break");
    events.push({ type: "break_end" });
    expect(clockStateFromEvents(events)).toBe("in");
    events.push({ type: "clock_out" });
    expect(clockStateFromEvents(events)).toBe("out");
  });
});

describe("validateClockTransition", () => {
  it("allows a full valid sequence", () => {
    const events: { type: string }[] = [];
    for (const type of ["clock_in", "break_start", "break_end", "clock_out"] as const) {
      expect(validateClockTransition(events, type)).toBeNull();
      events.push({ type });
    }
    // second shift on the same day is allowed
    expect(validateClockTransition(events, "clock_in")).toBeNull();
  });

  it("rejects clocking in twice", () => {
    expect(validateClockTransition([{ type: "clock_in" }], "clock_in")).toMatch(/Cannot clock in/);
  });

  it("rejects clock out / break end while out", () => {
    expect(validateClockTransition([], "clock_out")).toMatch(/Cannot clock out/);
    expect(validateClockTransition([], "break_end")).toMatch(/Cannot break end/);
    expect(validateClockTransition([], "break_start")).toMatch(/Cannot break start/);
  });

  it("rejects everything except break_end while on break", () => {
    const events = [{ type: "clock_in" }, { type: "break_start" }];
    expect(validateClockTransition(events, "clock_in")).toMatch(/on break/);
    expect(validateClockTransition(events, "clock_out")).toMatch(/on break/);
    expect(validateClockTransition(events, "break_start")).toMatch(/on break/);
    expect(validateClockTransition(events, "break_end")).toBeNull();
  });
});

describe("HH:MM helpers", () => {
  it("validates HH:MM strings", () => {
    expect(isValidHHMM("08:30")).toBe(true);
    expect(isValidHHMM("23:59")).toBe(true);
    expect(isValidHHMM("24:00")).toBe(false);
    expect(isValidHHMM("8:30")).toBe(false);
    expect(isValidHHMM("08:60")).toBe(false);
    expect(isValidHHMM(830)).toBe(false);
  });

  it("round-trips minutes and HH:MM", () => {
    expect(hhmmToMinutes("08:30")).toBe(510);
    expect(minutesToHHMM(510)).toBe("08:30");
    expect(minutesToHHMM(0)).toBe("00:00");
  });
});

describe("manualEntryOverlaps", () => {
  const closedDay = [ev("clock_in", "08:00"), ev("clock_out", "12:00")];

  it("no events → no overlap", () => {
    expect(manualEntryOverlaps([], "09:00", "10:00")).toBe(false);
  });

  it("detects overlap with a completed interval", () => {
    expect(manualEntryOverlaps(closedDay, "11:00", "13:00")).toBe(true);
    expect(manualEntryOverlaps(closedDay, "07:00", "09:00")).toBe(true);
    expect(manualEntryOverlaps(closedDay, "09:00", "10:00")).toBe(true); // fully inside
    expect(manualEntryOverlaps(closedDay, "07:00", "13:00")).toBe(true); // fully covering
  });

  it("allows entries outside the interval; touching boundaries are fine", () => {
    expect(manualEntryOverlaps(closedDay, "12:00", "13:00")).toBe(false);
    expect(manualEntryOverlaps(closedDay, "06:00", "08:00")).toBe(false);
    expect(manualEntryOverlaps(closedDay, "13:00", "17:00")).toBe(false);
  });

  it("ignores breaks inside a worked interval", () => {
    const withBreak = [
      ev("clock_in", "08:00"),
      ev("break_start", "10:00"),
      ev("break_end", "10:30"),
      ev("clock_out", "12:00"),
    ];
    // still counts as one 08:00-12:00 worked block
    expect(manualEntryOverlaps(withBreak, "10:00", "10:30")).toBe(true);
  });

  it("treats an open clock_in as running to end of day", () => {
    const openDay = [ev("clock_in", "08:00")];
    expect(manualEntryOverlaps(openDay, "18:00", "20:00")).toBe(true);
    expect(manualEntryOverlaps(openDay, "06:00", "07:30")).toBe(false);
  });

  it("handles multiple intervals in a day", () => {
    const twoShifts = [
      ev("clock_in", "08:00"),
      ev("clock_out", "12:00"),
      ev("clock_in", "14:00"),
      ev("clock_out", "17:00"),
    ];
    expect(manualEntryOverlaps(twoShifts, "12:00", "14:00")).toBe(false);
    expect(manualEntryOverlaps(twoShifts, "13:00", "15:00")).toBe(true);
  });
});
