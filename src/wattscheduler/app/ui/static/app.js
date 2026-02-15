// Set default dates
document.addEventListener('DOMContentLoaded', function () {
    const now = new Date();

    const earliest = new Date(now);
    earliest.setSeconds(0, 0);
    const m = earliest.getMinutes();
    earliest.setMinutes(Math.ceil(m / 15) * 15);

    const latest = new Date(earliest);
    latest.setHours(latest.getHours() + 24);

    flatpickr("#earliest_start", {
        enableTime: true,
        time_24hr: true,
        dateFormat: "d.m.Y H:i",
        locale: "fi",
        defaultDate: earliest,
        minuteIncrement: 15
    });

    flatpickr("#latest_end", {
        enableTime: true,
        time_24hr: true,
        dateFormat: "d.m.Y H:i",
        locale: "fi",
        defaultDate: latest,
        minuteIncrement: 15
    });
});

document.getElementById('scheduleForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    const formData = new FormData(this);
    const duration_minutes = parseInt(formData.get('duration_minutes'));
    const power_kw = parseFloat(formData.get('power_kw'));
    const earliest_start = document.getElementById("earliest_start")._flatpickr.selectedDates[0];
    const latest_end = document.getElementById("latest_end")._flatpickr.selectedDates[0];

    // Convert dates to ISO format for API calls
    const startStr = earliest_start.toISOString();
    const endStr = latest_end.toISOString();

    // Hide results initially
    document.getElementById('results').style.display = 'none';

    try {
        // Get price data
        const pricesResponse = await fetch(`/v1/prices?start=${startStr}&end=${endStr}`);
        const prices = await pricesResponse.json();

        // Prepare schedule request
        const scheduleRequest = {
            duration_minutes: duration_minutes,
            power_kw: power_kw,
            earliest_start: startStr,
            latest_end: endStr,
            top_n: 1
        };

        // Get schedule
        const scheduleResponse = await fetch('/v1/schedule', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(scheduleRequest)
        });

        const scheduleData = await scheduleResponse.json();

        // Display results
        displayResults(prices, scheduleData);

        // Show results card
        document.getElementById('results').style.display = 'block';
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('summary').innerHTML = '<p>Error processing request</p>';
        // Show results card even on error
        document.getElementById('results').style.display = 'block';
    }
});

function displayResults(prices, scheduleData) {
    if (!scheduleData.best_window) {
        document.getElementById('summary').innerHTML = '<p>No schedule found</p>';
        return;
    }

    const bestWindow = scheduleData.best_window;
    const worstWindow = scheduleData.worst_window;

    // Display summary
    const summaryDiv = document.getElementById('summary');
    summaryDiv.innerHTML = `
        <div class="best-schedule">
            <h3>Best Schedule</h3>
            <div class="best-grid">
                <label>Start:</label>
                <div>${formatDisplayTime(new Date(bestWindow.start))}</div>

                <label>End:</label>
                <div>${formatDisplayTime(new Date(bestWindow.end))}</div>

                <label>Estimated Cost:</label>
                <div>${bestWindow.estimated_cost_eur.toFixed(4)} €</div>

                <label>Savings vs Now:</label>
                <div>${bestWindow.savings_vs_now_eur.toFixed(4)} €</div>

                <label>Average Price:</label>
                <div>${(bestWindow.avg_price_eur_per_kwh * 100).toFixed(2)} snt/kWh</div>
            </div>
        </div>
    `;

    // Create chart
    console.log(scheduleData)
    createChart(prices, bestWindow, worstWindow, scheduleData.duration_minutes);
}

let priceChart;

function createChart(prices, bestWindow, worstWindow, duration_minutes) {
    const ctx = document.getElementById('priceChart').getContext('2d');

    // Destroy previous chart (Canvas is already in use -bugi)
    if (priceChart) priceChart.destroy();

    prices.sort((a, b) => new Date(a.timestamp) - new Date(b.timestamp));

    const timestamps = prices.map(p => new Date(p.timestamp));
    const labels = prices.map(p =>
        new Date(p.timestamp).toLocaleTimeString('fi-FI', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        })
    );
    const values = prices.map(p => p.price);

    const slotMinutes = 15;
    const slots = Math.max(1, Math.round(duration_minutes / slotMinutes));

    // Map timestamps -> index
    const indexByMs = new Map(timestamps.map((d, i) => [d.getTime(), i]));

    const bestStart = new Date(bestWindow.start);
    const worstStart = worstWindow ? new Date(worstWindow.start) : null;

    const bestStartIndex = indexByMs.get(bestStart.getTime());
    const worstStartIndex = worstStart ? indexByMs.get(worstStart.getTime()) : undefined;

    // Per-bar colors
    const rootStyles = getComputedStyle(document.documentElement);
    const bestColor = rootStyles.getPropertyValue('--color-best').trim();
    const worstColor = rootStyles.getPropertyValue('--color-worst').trim();
    const priceColor = rootStyles.getPropertyValue('--color-price').trim();
    const borderColor = rootStyles.getPropertyValue('--color-border').trim();
    const gridColor = rootStyles.getPropertyValue('--color-grid').trim();

    const bgColors = Array(values.length).fill(priceColor);
    const borderColors = Array(values.length).fill(borderColor);

    // Paint best window
    if (bestStartIndex !== undefined) {
        for (let i = bestStartIndex; i < Math.min(values.length, bestStartIndex + slots); i++) {
            bgColors[i] = bestColor;
            borderColors[i] = borderColor;
        }
    }

    // Paint worst window
    if (worstStartIndex !== undefined) {
        for (let i = worstStartIndex; i < Math.min(values.length, worstStartIndex + slots); i++) {
            bgColors[i] = worstColor;
            borderColors[i] = borderColor;
        }
    }

    console.log(bestStartIndex, worstStartIndex, slots, bgColors)

    priceChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Electricity Price (snt/kWh)',
                data: values,
                backgroundColor: bgColors,
                borderColor: borderColors,
                borderWidth: 0,
                categoryPercentage: 0.95,
                barPercentage: 0.95
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    type: 'category',
                    title: { display: true, text: 'Time' },
                    grid: { color: gridColor },
                    layer: -1
                },
                y: {
                    title: { display: true, text: 'Price (snt/kWh)' },
                    grid: { color: gridColor },
                    layer: -1,
                    ticks: {
                        callback: function (value, index, ticks) {
                            return (value * 100).toFixed(0);
                        }
                    }
                }
            },
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        generateLabels: function (chart) {
                            return [
                                {
                                    text: 'Electricity Price',
                                    fillStyle: priceColor
                                },
                                {
                                    text: 'Best Window',
                                    fillStyle: bestColor
                                },
                                {
                                    text: 'Most Expensive Window',
                                    fillStyle: worstColor
                                }
                            ];
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: (ctx) => `Price: ${(ctx.parsed.y * 100).toFixed(2)} snt/kWh`
                    }
                }
            }
        }
    });
}

function formatDateTime(date) {
    // Format date for datetime-local input
    const pad = (num) => num.toString().padStart(2, '0');
    const year = date.getFullYear();
    const month = pad(date.getMonth() + 1);
    const day = pad(date.getDate());
    const hours = pad(date.getHours());
    const minutes = pad(date.getMinutes());
    return `${year}-${month}-${day}T${hours}:${minutes}`;
}

function formatDisplayTime(date) {
    const dd = String(date.getDate()).padStart(2, '0');
    const mm = String(date.getMonth() + 1).padStart(2, '0');
    const yyyy = date.getFullYear();
    const hh = String(date.getHours()).padStart(2, '0');
    const min = String(date.getMinutes()).padStart(2, '0');
    return `${dd}.${mm}.${yyyy} ${hh}:${min}`;
}
