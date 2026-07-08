(function () {
    "use strict";

    function chooseYAxisDecimals(tickValues) {
        if (!Array.isArray(tickValues) || tickValues.length === 0) return 0;
        var seen = {};
        for (var i = 0; i < tickValues.length; i++) {
            var label = Number(tickValues[i]).toFixed(0);
            if (seen[label]) return 1;
            seen[label] = true;
        }
        return 0;
    }

    if (typeof window !== "undefined") window.chooseYAxisDecimals = chooseYAxisDecimals;
    if (typeof module !== "undefined" && module.exports) module.exports = { chooseYAxisDecimals: chooseYAxisDecimals };
})();
