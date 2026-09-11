// Market Prices API Handler
class MarketPricesAPI {
    constructor(apiKey = '') {
        this.apiKey = apiKey;
        this.baseUrl = '/api/market-prices';
    }

    async getPrices(commodity, state = '', date = '', limit = 15) {
        try {
            let url = `${this.baseUrl}?commodity=${encodeURIComponent(commodity)}`;
            if (state) {
                url += `&state=${encodeURIComponent(state)}`;
            }
            if (date) {
                url += `&date=${encodeURIComponent(date)}`;
            }
            
            const response = await fetch(url);
            
            if (!response.ok) {
                throw new Error(`API request failed: ${response.status}`);
            }
            
            const data = await response.json();
            return this.processData(data);
        } catch (error) {
            console.error('Error fetching market prices:', error);
            return null;
        }
    }

    processData(data) {
        if (!data || !data.records) return null;

        return {
            date: data.date || '',
            records: data.records.map(record => ({
                commodity: record.Commodity,
                variety: record.Variety,
                state: record.State,
                district: record.District,
                market: record.Market,
                date: record.Arrival_Date,
                minPrice: record.Min_Price,
                maxPrice: record.Max_Price,
                modalPrice: record.Modal_Price,
                grade: record.Grade
            }))
        };
    }
}

// Chart Manager
class PriceChart {
    constructor(canvasId) {
        this.canvasId = canvasId;
        this.chart = null;
    }

    initialize() {
        if (this.chart) return;
        const canvas = document.getElementById(this.canvasId);
        if (!canvas) return;
        
        const ctx = canvas.getContext('2d');
        this.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: [],
                datasets: [{
                    label: 'Modal Price',
                    data: [],
                    borderColor: '#4caf50',
                    backgroundColor: 'rgba(76, 175, 80, 0.1)',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { display: false },
                    tooltip: {
                        mode: 'index',
                        intersect: false,
                        backgroundColor: '#1a2e1d',
                        titleColor: '#ffffff',
                        bodyColor: '#e2e8f0',
                        borderColor: '#4caf50',
                        borderWidth: 1,
                        callbacks: {
                            label: function(context) { return '₹' + context.parsed.y; }
                        }
                    }
                },
                scales: {
                    x: {
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: { color: '#9ca3af', maxRotation: 45, minRotation: 45 }
                    },
                    y: {
                        beginAtZero: false,
                        grid: { color: 'rgba(255, 255, 255, 0.05)' },
                        ticks: {
                            color: '#9ca3af',
                            callback: function(value) { return '₹' + value; }
                        }
                    }
                }
            }
        });
    }

    updateData(data) {
        if (!this.chart) this.initialize();
        if (!this.chart || !data || !data.records || data.records.length === 0) return;

        const sortedRecords = [...data.records].sort((a, b) => a.market.localeCompare(b.market));
        this.chart.data.labels = sortedRecords.map(p => p.market);
        this.chart.data.datasets[0].data = sortedRecords.map(p => p.modalPrice);
        this.chart.update();
    }
}

// UI Manager
class MarketPricesUI {
    constructor() {
        this.api = new MarketPricesAPI();
        this.chart = new PriceChart('priceChart');
        this.initializeEventListeners();
        this.setDefaultDate();
        this.chart.initialize();
        this.updateData();
    }

    setDefaultDate() {
        const today = new Date();
        const twoDaysAgo = new Date(today);
        twoDaysAgo.setDate(today.getDate() - 2);
        const formattedDate = twoDaysAgo.toISOString().split('T')[0];
        const dateInput = document.getElementById('date-select');
        if (dateInput) {
            dateInput.value = formattedDate;
        }
    }

    initializeEventListeners() {
        const cropSelect = document.getElementById('crop-select');
        const stateSelect = document.getElementById('state-select');
        const dateSelect = document.getElementById('date-select');

        if (cropSelect) cropSelect.addEventListener('change', () => this.updateData());
        if (stateSelect) stateSelect.addEventListener('change', () => this.updateData());
        if (dateSelect) dateSelect.addEventListener('change', () => this.updateData());
    }

    async updateData() {
        const crop = document.getElementById('crop-select')?.value || 'Tomato';
        const state = document.getElementById('state-select')?.value || '';
        const date = document.getElementById('date-select')?.value || '';

        const chartCanvas = document.getElementById('priceChart');
        if (chartCanvas) chartCanvas.style.opacity = '0.5';

        try {
            const response = await this.api.getPrices(crop, state, date);
            if (response) {
                const dateEl = document.getElementById('data-date');
                if (dateEl) dateEl.textContent = `Data as of ${response.date}`;
                
                this.chart.updateData(response);
                this.updatePriceTable(response.records);
            }
        } catch (error) {
            console.error('Error updating data:', error);
        } finally {
            if (chartCanvas) chartCanvas.style.opacity = '1';
        }
    }

    updatePriceTable(prices) {
        const tbody = document.querySelector('#price-table tbody');
        if (!tbody) return;

        tbody.innerHTML = '';

        if (!prices || prices.length === 0) {
            tbody.innerHTML = `<tr><td colspan="4" class="py-4 text-center text-gray-400">No market price data available for selected filter</td></tr>`;
            return;
        }

        prices.forEach(price => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="py-3 px-4 text-sm text-white">${price.market}</td>
                <td class="py-3 px-4 text-sm text-gray-300">${price.district}, ${price.state}</td>
                <td class="py-3 px-4 text-sm text-white font-medium">₹${price.modalPrice}</td>
                <td class="py-3 px-4 text-sm text-gray-300">${price.date}</td>
            `;
            tbody.appendChild(row);
        });
    }

    setApiKey(apiKey) {
        this.api = new MarketPricesAPI(apiKey);
    }
}

// Auto-initialize cleanly when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
        if (!window.marketPricesUI) {
            window.marketPricesUI = new MarketPricesUI();
        }
    });
} else {
    if (!window.marketPricesUI) {
        window.marketPricesUI = new MarketPricesUI();
    }
}