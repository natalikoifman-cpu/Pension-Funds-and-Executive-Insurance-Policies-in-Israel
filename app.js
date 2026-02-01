// Pension Fund Data Displayer and Comparer
// Data source: Israeli Government Open Data Portal

let allFunds = [];
let selectedFunds = [];
const MAX_COMPARISON = 3;

// Sample data structure - in production, this would come from the API
const sampleFunds = [
    {
        id: 1,
        name: "מבטחים קרן פנסיה מקיפה",
        type: "פנסיה",
        managementFee: 0.51,
        annualReturn: 7.8,
        threeYearReturn: 22.5,
        fiveYearReturn: 45.3,
        riskLevel: "בינוני",
        assets: 45000000000,
        members: 320000
    },
    {
        id: 2,
        name: "כלל פנסיה ותגמולים",
        type: "פנסיה",
        managementFee: 0.49,
        annualReturn: 8.1,
        threeYearReturn: 23.2,
        fiveYearReturn: 46.8,
        riskLevel: "בינוני",
        assets: 52000000000,
        members: 380000
    },
    {
        id: 3,
        name: "הראל פנסיה וגמל",
        type: "פנסיה",
        managementFee: 0.52,
        annualReturn: 7.5,
        threeYearReturn: 21.8,
        fiveYearReturn: 44.2,
        riskLevel: "בינוני-נמוך",
        assets: 58000000000,
        members: 425000
    },
    {
        id: 4,
        name: "מנורה מבטחים קרן השתלמות",
        type: "השתלמות",
        managementFee: 0.58,
        annualReturn: 9.2,
        threeYearReturn: 26.5,
        fiveYearReturn: 52.1,
        riskLevel: "בינוני-גבוה",
        assets: 12000000000,
        members: 95000
    },
    {
        id: 5,
        name: "אלטשולר שחם ביטוח מנהלים",
        type: "ביטוח",
        managementFee: 0.45,
        annualReturn: 8.5,
        threeYearReturn: 24.3,
        fiveYearReturn: 48.7,
        riskLevel: "בינוני",
        assets: 28000000000,
        members: 180000
    },
    {
        id: 6,
        name: "הפניקס פנסיה וגמל",
        type: "פנסיה",
        managementFee: 0.50,
        annualReturn: 7.9,
        threeYearReturn: 22.9,
        fiveYearReturn: 46.1,
        riskLevel: "בינוני",
        assets: 41000000000,
        members: 295000
    },
    {
        id: 7,
        name: "מגדל מקפת קרן פנסיה",
        type: "פנסיה",
        managementFee: 0.53,
        annualReturn: 7.6,
        threeYearReturn: 22.1,
        fiveYearReturn: 45.0,
        riskLevel: "בינוני",
        assets: 48000000000,
        members: 340000
    },
    {
        id: 8,
        name: "אי.בי.אי קרן השתלמות",
        type: "השתלמות",
        managementFee: 0.60,
        annualReturn: 9.5,
        threeYearReturn: 27.1,
        fiveYearReturn: 53.4,
        riskLevel: "גבוה",
        assets: 8000000000,
        members: 65000
    }
];

// Initialize the application
function init() {
    allFunds = [...sampleFunds];
    displayDataInfo();
    console.log('Application initialized with sample data');
}

// Load all funds
function loadAllFunds() {
    showLoading(true);
    hideError();
    
    // Simulate API call delay
    setTimeout(() => {
        allFunds = [...sampleFunds];
        displayFunds(allFunds);
        showLoading(false);
        updateDataInfo(`נטענו ${allFunds.length} קרנות`);
    }, 500);
}

// Search funds
function searchFunds() {
    const searchTerm = document.getElementById('searchInput').value.trim();
    const typeFilter = document.getElementById('typeFilter').value;
    
    if (!searchTerm && !typeFilter) {
        loadAllFunds();
        return;
    }
    
    showLoading(true);
    hideError();
    
    setTimeout(() => {
        let filtered = [...sampleFunds];
        
        if (searchTerm) {
            filtered = filtered.filter(fund => 
                fund.name.includes(searchTerm)
            );
        }
        
        if (typeFilter) {
            filtered = filtered.filter(fund => fund.type === typeFilter);
        }
        
        allFunds = filtered;
        displayFunds(filtered);
        showLoading(false);
        
        if (filtered.length === 0) {
            showError('לא נמצאו קרנות התואמות את הקריטריונים');
        } else {
            updateDataInfo(`נמצאו ${filtered.length} קרנות`);
        }
    }, 300);
}

// Display funds in the results section
function displayFunds(funds) {
    const resultsTable = document.getElementById('resultsTable');
    
    if (funds.length === 0) {
        resultsTable.innerHTML = '<p class="info-text">לא נמצאו תוצאות</p>';
        return;
    }
    
    // Apply sorting
    const sortBy = document.getElementById('sortBy').value;
    const sortedFunds = sortFunds(funds, sortBy);
    
    let html = '';
    sortedFunds.forEach(fund => {
        const isSelected = selectedFunds.some(f => f.id === fund.id);
        html += `
            <div class="fund-card ${isSelected ? 'selected' : ''}" onclick="toggleFundSelection(${fund.id})">
                <div class="fund-header">
                    <div class="fund-name">${fund.name}</div>
                    <div class="fund-type">${fund.type}</div>
                </div>
                <div class="fund-details">
                    <div class="detail-item">
                        <div class="detail-label">דמי ניהול שנתיים</div>
                        <div class="detail-value">${fund.managementFee}%</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">תשואה שנתית</div>
                        <div class="detail-value">${fund.annualReturn}%</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">תשואה 3 שנים</div>
                        <div class="detail-value">${fund.threeYearReturn}%</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">תשואה 5 שנים</div>
                        <div class="detail-value">${fund.fiveYearReturn}%</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">רמת סיכון</div>
                        <div class="detail-value">${fund.riskLevel}</div>
                    </div>
                    <div class="detail-item">
                        <div class="detail-label">מספר עמיתים</div>
                        <div class="detail-value">${formatNumber(fund.members)}</div>
                    </div>
                </div>
            </div>
        `;
    });
    
    resultsTable.innerHTML = html;
}

// Sort funds based on criteria
function sortFunds(funds, criteria) {
    const sorted = [...funds];
    
    switch(criteria) {
        case 'name':
            return sorted.sort((a, b) => a.name.localeCompare(b.name, 'he'));
        case 'return':
            return sorted.sort((a, b) => b.annualReturn - a.annualReturn);
        case 'fee':
            return sorted.sort((a, b) => a.managementFee - b.managementFee);
        case 'risk':
            const riskOrder = { 'נמוך': 1, 'בינוני-נמוך': 2, 'בינוני': 3, 'בינוני-גבוה': 4, 'גבוה': 5 };
            return sorted.sort((a, b) => riskOrder[a.riskLevel] - riskOrder[b.riskLevel]);
        default:
            return sorted;
    }
}

// Toggle fund selection for comparison
function toggleFundSelection(fundId) {
    const fund = allFunds.find(f => f.id === fundId);
    if (!fund) return;
    
    const index = selectedFunds.findIndex(f => f.id === fundId);
    
    if (index > -1) {
        // Deselect
        selectedFunds.splice(index, 1);
    } else {
        // Select
        if (selectedFunds.length >= MAX_COMPARISON) {
            showError(`ניתן לבחור עד ${MAX_COMPARISON} קרנות להשוואה`);
            return;
        }
        selectedFunds.push(fund);
    }
    
    displayFunds(allFunds);
    updateComparison();
}

// Update comparison section
function updateComparison() {
    const comparisonArea = document.getElementById('comparisonArea');
    
    if (selectedFunds.length === 0) {
        comparisonArea.innerHTML = '<p class="info-text">בחר עד 3 קרנות להשוואה</p>';
        return;
    }
    
    if (selectedFunds.length === 1) {
        comparisonArea.innerHTML = '<p class="info-text">בחר לפחות 2 קרנות להשוואה</p>';
        return;
    }
    
    // Create comparison table
    let html = '<table class="comparison-table">';
    html += '<thead><tr><th>פרמטר</th>';
    selectedFunds.forEach(fund => {
        html += `<th>${fund.name}</th>`;
    });
    html += '</tr></thead><tbody>';
    
    // Management Fee
    html += '<tr><td>דמי ניהול שנתיים</td>';
    const minFee = Math.min(...selectedFunds.map(f => f.managementFee));
    selectedFunds.forEach(fund => {
        const isBest = fund.managementFee === minFee;
        html += `<td class="${isBest ? 'metric-best' : ''}">${fund.managementFee}%</td>`;
    });
    html += '</tr>';
    
    // Annual Return
    html += '<tr><td>תשואה שנתית</td>';
    const maxReturn = Math.max(...selectedFunds.map(f => f.annualReturn));
    selectedFunds.forEach(fund => {
        const isBest = fund.annualReturn === maxReturn;
        html += `<td class="${isBest ? 'metric-best' : ''}">${fund.annualReturn}%</td>`;
    });
    html += '</tr>';
    
    // 3 Year Return
    html += '<tr><td>תשואה 3 שנים</td>';
    const max3Year = Math.max(...selectedFunds.map(f => f.threeYearReturn));
    selectedFunds.forEach(fund => {
        const isBest = fund.threeYearReturn === max3Year;
        html += `<td class="${isBest ? 'metric-best' : ''}">${fund.threeYearReturn}%</td>`;
    });
    html += '</tr>';
    
    // 5 Year Return
    html += '<tr><td>תשואה 5 שנים</td>';
    const max5Year = Math.max(...selectedFunds.map(f => f.fiveYearReturn));
    selectedFunds.forEach(fund => {
        const isBest = fund.fiveYearReturn === max5Year;
        html += `<td class="${isBest ? 'metric-best' : ''}">${fund.fiveYearReturn}%</td>`;
    });
    html += '</tr>';
    
    // Risk Level
    html += '<tr><td>רמת סיכון</td>';
    selectedFunds.forEach(fund => {
        html += `<td>${fund.riskLevel}</td>`;
    });
    html += '</tr>';
    
    // Members
    html += '<tr><td>מספר עמיתים</td>';
    selectedFunds.forEach(fund => {
        html += `<td>${formatNumber(fund.members)}</td>`;
    });
    html += '</tr>';
    
    html += '</tbody></table>';
    comparisonArea.innerHTML = html;
}

// Utility functions
function showLoading(show) {
    document.getElementById('loadingIndicator').style.display = show ? 'block' : 'none';
}

function showError(message) {
    const errorDiv = document.getElementById('errorMessage');
    errorDiv.textContent = message;
    errorDiv.style.display = 'block';
    setTimeout(() => {
        errorDiv.style.display = 'none';
    }, 5000);
}

function hideError() {
    document.getElementById('errorMessage').style.display = 'none';
}

function formatNumber(num) {
    return num.toLocaleString('he-IL');
}

function displayDataInfo() {
    const dataInfo = document.getElementById('dataInfo');
    dataInfo.innerHTML = `
        <p>המערכת כוללת ${sampleFunds.length} קרנות לדוגמה.</p>
        <p>בגרסת ייצור, הנתונים יגיעו מ-API של data.gov.il</p>
    `;
}

function updateDataInfo(message) {
    const dataInfo = document.getElementById('dataInfo');
    dataInfo.innerHTML = `<p class="success-message">${message}</p>`;
}

// Event listeners for filters
document.addEventListener('DOMContentLoaded', () => {
    init();
    
    document.getElementById('typeFilter').addEventListener('change', searchFunds);
    document.getElementById('sortBy').addEventListener('change', () => {
        if (allFunds.length > 0) {
            displayFunds(allFunds);
        }
    });
    
    document.getElementById('searchInput').addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
            searchFunds();
        }
    });
});
