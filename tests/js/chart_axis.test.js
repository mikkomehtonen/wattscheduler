const { describe, it } = require("node:test");
const assert = require("node:assert/strict");
const { chooseYAxisDecimals } = require("../../src/wattscheduler/app/ui/static/chart_axis.js");

describe("chooseYAxisDecimals", () => {
    it("returns 0 for distinct 0-decimal labels", () => {
        assert.equal(chooseYAxisDecimals([0, 5, 10, 15, 20]), 0);
    });

    it("returns 1 when 0-decimal labels collide", () => {
        assert.equal(chooseYAxisDecimals([0.5, 0.7, 0.9, 1.1, 1.3]), 1);
    });

    it("returns 0 for an empty array", () => {
        assert.equal(chooseYAxisDecimals([]), 0);
    });

    it("returns 0 for a single value", () => {
        assert.equal(chooseYAxisDecimals([7]), 0);
    });

    it("returns 0 for distinct negative values", () => {
        assert.equal(chooseYAxisDecimals([-1, 0, 1, 2]), 0);
    });

    it("returns 1 for colliding negative values", () => {
        assert.equal(chooseYAxisDecimals([-0.4, -0.2, 0]), 1);
    });

    it("caps decimals at 1 even when 1 decimal still collides", () => {
        assert.equal(chooseYAxisDecimals([0.04, 0.04]), 1);
    });
});
