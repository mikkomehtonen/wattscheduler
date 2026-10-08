process.env.TZ = "Europe/Helsinki";

const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const {
    computeDefaultStart,
    endOfDay,
    computeDefaultEnd,
    nextDayProbeRange,
    nextDayPricesAvailable
} = require("../../src/wattscheduler/app/ui/static/price_range_defaults.js");

function assertLocalTime(date, year, month, day, hours, minutes, seconds, ms) {
    assert.equal(date.getFullYear(), year);
    assert.equal(date.getMonth(), month);
    assert.equal(date.getDate(), day);
    assert.equal(date.getHours(), hours);
    assert.equal(date.getMinutes(), minutes);
    assert.equal(date.getSeconds(), seconds === undefined ? 0 : seconds);
    assert.equal(date.getMilliseconds(), ms === undefined ? 0 : ms);
}

describe("computeDefaultStart", () => {
    it("zeroes seconds/ms and rounds minutes up to the next 15-minute boundary", () => {
        const now = new Date(2026, 5, 15, 10, 7, 33, 500);
        assertLocalTime(computeDefaultStart(now), 2026, 5, 15, 10, 15);
    });

    it("returns an exact 15-minute boundary unchanged", () => {
        const now = new Date(2026, 5, 15, 10, 15, 0, 0);
        assertLocalTime(computeDefaultStart(now), 2026, 5, 15, 10, 15);
    });

    it("rolls over the hour when rounding past :45", () => {
        const now = new Date(2026, 5, 15, 10, 50, 0, 0);
        assertLocalTime(computeDefaultStart(now), 2026, 5, 15, 11, 0);
    });

    it("normalizes across the spring-forward gap (03:00 does not exist on Mar 29 2026)", () => {
        const now = new Date(2026, 2, 29, 2, 50, 0, 0);
        assertLocalTime(computeDefaultStart(now), 2026, 2, 29, 4, 0);
    });
});

describe("endOfDay", () => {
    it("returns 23:45:00.000 of the same local day", () => {
        const d = new Date(2026, 2, 3, 4, 5, 6, 7);
        assertLocalTime(endOfDay(d), 2026, 2, 3, 23, 45);
    });

    it("does not mutate the input date", () => {
        const d = new Date(2026, 2, 3, 4, 5, 6, 7);
        const before = d.getTime();
        endOfDay(d);
        assert.equal(d.getTime(), before);
    });
});

describe("computeDefaultEnd", () => {
    it("returns next local day 23:45 when next-day prices are available", () => {
        const now = new Date(2026, 5, 15, 10, 7, 0, 0);
        assertLocalTime(computeDefaultEnd(now, true), 2026, 5, 16, 23, 45);
    });

    it("returns current local day 23:45 when next-day prices are unavailable", () => {
        const now = new Date(2026, 5, 15, 10, 7, 0, 0);
        assertLocalTime(computeDefaultEnd(now, false), 2026, 5, 15, 23, 45);
    });

    it("clamps to the default start at 23:50 with no next-day prices (never inverts)", () => {
        const now = new Date(2026, 5, 15, 23, 50, 0, 0);
        const end = computeDefaultEnd(now, false);
        assert.equal(end.getTime(), computeDefaultStart(now).getTime());
    });

    it("is DST-safe across the Helsinki changeover (Oct 25 2026)", () => {
        const now = new Date(2026, 9, 24, 23, 50, 0, 0);
        assertLocalTime(computeDefaultEnd(now, true), 2026, 9, 25, 23, 45);
    });
});

describe("nextDayProbeRange", () => {
    it("spans the full next local day from 00:00 to 23:45", () => {
        const now = new Date(2026, 5, 15, 10, 7, 0, 0);
        const range = nextDayProbeRange(now);
        assertLocalTime(range.start, 2026, 5, 16, 0, 0);
        assertLocalTime(range.end, 2026, 5, 16, 23, 45);
    });

    it("handles month rollover", () => {
        const now = new Date(2026, 5, 30, 22, 0, 0, 0);
        const range = nextDayProbeRange(now);
        assertLocalTime(range.start, 2026, 6, 1, 0, 0);
        assertLocalTime(range.end, 2026, 6, 1, 23, 45);
    });
});

describe("nextDayPricesAvailable", () => {
    it("returns false for an empty array", () => {
        assert.equal(nextDayPricesAvailable([]), false);
    });

    it("returns true for an array with one price point", () => {
        const payload = [{ timestamp: "2026-06-16T00:00:00Z", price: 0.12 }];
        assert.equal(nextDayPricesAvailable(payload), true);
    });

    it("returns false for a non-array payload", () => {
        assert.equal(nextDayPricesAvailable({}), false);
        assert.equal(nextDayPricesAvailable(null), false);
        assert.equal(nextDayPricesAvailable(undefined), false);
    });
});
