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
        defaultDate: earliest
    });

    flatpickr("#latest_end", {
        enableTime: true,
        time_24hr: true,
        dateFormat: "d.m.Y H:i",
        locale: "fi",
        defaultDate: latest
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
    } catch (error) {
        console.error('Error:', error);
        document.getElementById('summary').innerHTML = '<p>Error processing request</p>';
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
        <h3>Best Schedule:</h3>
        <p><strong>Start:</strong> ${formatDisplayTime(new Date(bestWindow.start))}</p>
        <p><strong>End:</strong> ${formatDisplayTime(new Date(bestWindow.end))}</p>
        <p><strong>Estimated Cost:</strong> ${bestWindow.estimated_cost_eur.toFixed(4)} €</p>
        <p><strong>Savings vs Now:</strong> ${bestWindow.savings_vs_now_eur.toFixed(4)} €</p>
        <p><strong>Average Price:</strong> ${bestWindow.avg_price_eur_per_kwh.toFixed(4)} €/kWh</p>
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
    const bestColor = 'rgba(0, 150, 0, 0.8)';
    const worstColor = 'rgba(230, 57, 70, 1)';
    const backgroundColor = '#3A7CA5';
    const borderColor = '#1F4E70';

    const bgColors = Array(values.length).fill(backgroundColor);
    const borderColors = Array(values.length).fill(borderColor);

    // Paint best window
    if (bestStartIndex !== undefined) {
        for (let i = bestStartIndex; i < Math.min(values.length, bestStartIndex + slots); i++) {
            bgColors[i] = bestColor;
            borderColors[i] = 'rgba(42, 157, 143, 1)';
        }
    }

    // Paint worst window
    if (worstStartIndex !== undefined) {
        for (let i = worstStartIndex; i < Math.min(values.length, worstStartIndex + slots); i++) {
            bgColors[i] = worstColor;
            borderColors[i] = 'rgba(230, 57, 70, 1)';
        }
    }

    console.log(bestStartIndex, worstStartIndex, slots, bgColors)

    priceChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Electricity Price (€/kWh)',
                data: values,
                backgroundColor: bgColors,
                borderColor: borderColors,
                borderWidth: 1,
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
                    title: { display: true, text: 'Aika' },
                    grid: { color: 'rgba(0,0,0,0.1)' },
                    layer: -1
                },
                y: {
                    grid: { color: 'rgba(0,0,0,0.1)' },
                    title: { display: true, text: 'Price (€/kWh)' },
                    layer: -1
                }
            },
            plugins: {
                legend: {
                    labels: {
                        generateLabels: function (chart) {
                            return [
                                {
                                    text: 'Electricity Price',
                                    fillStyle: backgroundColor
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
                        label: (ctx) => `Price: €${ctx.parsed.y.toFixed(4)}/kWh`
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