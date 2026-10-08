(function () {
    "use strict";

    function computeDefaultStart(now) {
        var start = new Date(now);
        start.setSeconds(0, 0);
        var m = start.getMinutes();
        start.setMinutes(Math.ceil(m / 15) * 15);
        return start;
    }

    function endOfDay(d) {
        return new Date(d.getFullYear(), d.getMonth(), d.getDate(), 23, 45, 0, 0);
    }

    function computeDefaultEnd(now, nextDayAvailable) {
        var start = computeDefaultStart(now);
        var end;
        if (nextDayAvailable) {
            var nextDay = new Date(now.getFullYear(), now.getMonth(), now.getDate() + 1);
            end = endOfDay(nextDay);
        } else {
            end = endOfDay(now);
        }
        return end < start ? start : end;
    }

    function nextDayProbeRange(now) {
        var y = now.getFullYear();
        var mo = now.getMonth();
        var d = now.getDate();
        return {
            start: new Date(y, mo, d + 1, 0, 0, 0, 0),
            end: new Date(y, mo, d + 1, 23, 45, 0, 0)
        };
    }

    function nextDayPricesAvailable(payload) {
        return Array.isArray(payload) && payload.length > 0;
    }

    if (typeof window !== "undefined") {
        window.computeDefaultStart = computeDefaultStart;
        window.computeDefaultEnd = computeDefaultEnd;
        window.nextDayProbeRange = nextDayProbeRange;
        window.nextDayPricesAvailable = nextDayPricesAvailable;
    }
    if (typeof module !== "undefined" && module.exports) {
        module.exports = {
            computeDefaultStart: computeDefaultStart,
            endOfDay: endOfDay,
            computeDefaultEnd: computeDefaultEnd,
            nextDayProbeRange: nextDayProbeRange,
            nextDayPricesAvailable: nextDayPricesAvailable
        };
    }
})();
