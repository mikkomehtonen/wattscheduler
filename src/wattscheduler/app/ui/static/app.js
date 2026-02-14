// Set default dates
document.addEventListener('DOMContentLoaded', function() {
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

document.getElementById('scheduleForm').addEventListener('submit', async function(e) {
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
    createChart(prices, bestWindow, worstWindow);
}

let priceChart = null;

function createChart(prices, bestWindow, worstWindow) {
    console.log(bestWindow, worstWindow)

    const ctx = document.getElementById('priceChart').getContext('2d');

    // Destroy previous chart if it exists
    if (priceChart) {
        priceChart.destroy();
    }

    // Prepare labels and data (no time scale, no adapter needed)
    const labels = prices.map(p => {
        // show HH:MM in local time
        const d = new Date(p.timestamp);
        return d.toLocaleTimeString('fi-FI', {
            hour: '2-digit',
            minute: '2-digit',
            hour12: false
        });
    });
    const pricesValues = prices.map(p => p.price);

    // Best window indices (compare using ISO timestamps)
    const windowStart = new Date(bestWindow.start);
    const windowEnd = new Date(bestWindow.end);

    const startIndex = prices.findIndex(p => new Date(p.timestamp) >= windowStart);
    const endIndex = prices.findIndex(p => new Date(p.timestamp) >= windowEnd);

    const datasets = [{
        label: 'Electricity Price (€/kWh)',
        data: pricesValues,
        borderColor: '#1f77b4',
        backgroundColor: 'transparent',
        borderWidth: 3,
        pointRadius: 0,
        tension: 0.25
    }];

    // Highlight best window as a second dataset
    if (startIndex >= 0 && endIndex >= 0) {
        const windowData = Array(prices.length).fill(null);
        for (let i = startIndex; i < endIndex; i++) {
            windowData[i] = pricesValues[i];
        }

        datasets.push({
            label: 'Best Window',
            data: windowData,
            borderColor: '#2a9d8f',
            backgroundColor: '#2a9d8f',
            borderWidth: 3,
            pointRadius: 0,
            fill: true,
            spanGaps: true
        });

        const worstWindowStart = new Date(worstWindow.start);
        const worstWindowEnd = new Date(worstWindow.end);
        const worstStartIndex = prices.findIndex(p => new Date(p.timestamp) >= worstWindowStart);
        const worstEndIndex = prices.findIndex(p => new Date(p.timestamp) >= worstWindowEnd);
        const worstWindowData = Array(prices.length).fill(null);
        for (let i = worstStartIndex; i < worstEndIndex; i++) {
            worstWindowData[i] = pricesValues[i];
        }
        datasets.push({
            label: 'Most Expensive Window',
            data: worstWindowData,
            borderColor: '#e63946',
            backgroundColor: '#e63946',
            borderWidth: 3,
            pointRadius: 0,
            fill: true,
            spanGaps: true
        });
    }

    priceChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: labels,
            datasets: datasets
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            scales: {
                x: {
                    title: {
                        display: true,
                        text: 'Time'
                    },
                    ticks: {
                        maxTicksLimit: 12
                    }
                },
                y: {
                    title: {
                        display: true,
                        text: 'Price (€/kWh)'
                    }
                }
            },
            plugins: {
                legend: { display: true },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return `Price: €${context.parsed.y.toFixed(4)}/kWh`;
                        }
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