import React, { useState } from 'react';
import './SearchPage.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

function SearchPage() {
  const [filters, setFilters] = useState({
    query: '',
    fundType: '',
    minReturn: '',
    maxManagementFee: '',
    riskLevel: ''
  });
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const handleInputChange = (e) => {
    const { name, value } = e.target;
    setFilters(prev => ({ ...prev, [name]: value }));
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      const params = new URLSearchParams();
      Object.entries(filters).forEach(([key, value]) => {
        if (value) params.append(key, value);
      });

      const response = await fetch(`${API_BASE_URL}/Search?${params}`);
      if (!response.ok) throw new Error('שגיאה בחיפוש');

      const data = await response.json();
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const clearFilters = () => {
    setFilters({
      query: '',
      fundType: '',
      minReturn: '',
      maxManagementFee: '',
      riskLevel: ''
    });
    setResults(null);
  };

  const getRiskLevelHebrew = (level) => {
    const levels = { Low: 'נמוך', Medium: 'בינוני', High: 'גבוה' };
    return levels[level] || level;
  };

  const getFundTypeHebrew = (type) => {
    const types = { Pension: 'קרן פנסיה', Executive: 'ביטוח מנהלים' };
    return types[type] || type;
  };

  return (
    <div className="search-page">
      <div className="search-header">
        <h2>חיפוש קרנות פנסיה וביטוחי מנהלים</h2>
        <p>סנן לפי קריטריונים שונים ומצא את הקרן המתאימה לך</p>
      </div>

      <form className="search-form" onSubmit={handleSearch}>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="query">חיפוש חופשי</label>
            <input
              type="text"
              id="query"
              name="query"
              value={filters.query}
              onChange={handleInputChange}
              placeholder="שם קרן או חברה מנהלת..."
            />
          </div>

          <div className="form-group">
            <label htmlFor="fundType">סוג מוצר</label>
            <select
              id="fundType"
              name="fundType"
              value={filters.fundType}
              onChange={handleInputChange}
            >
              <option value="">הכל</option>
              <option value="Pension">קרן פנסיה</option>
              <option value="Executive">ביטוח מנהלים</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="riskLevel">רמת סיכון</label>
            <select
              id="riskLevel"
              name="riskLevel"
              value={filters.riskLevel}
              onChange={handleInputChange}
            >
              <option value="">הכל</option>
              <option value="Low">נמוך</option>
              <option value="Medium">בינוני</option>
              <option value="High">גבוה</option>
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="minReturn">תשואה מינימלית (%)</label>
            <input
              type="number"
              id="minReturn"
              name="minReturn"
              value={filters.minReturn}
              onChange={handleInputChange}
              placeholder="לדוגמה: 5"
              step="0.1"
            />
          </div>

          <div className="form-group">
            <label htmlFor="maxManagementFee">דמי ניהול מקסימליים (%)</label>
            <input
              type="number"
              id="maxManagementFee"
              name="maxManagementFee"
              value={filters.maxManagementFee}
              onChange={handleInputChange}
              placeholder="לדוגמה: 0.5"
              step="0.01"
            />
          </div>
        </div>

        <div className="form-actions">
          <button type="submit" className="btn btn-primary" disabled={loading}>
            {loading ? 'מחפש...' : 'חפש'}
          </button>
          <button type="button" className="btn btn-secondary" onClick={clearFilters}>
            נקה סינון
          </button>
        </div>
      </form>

      {error && (
        <div className="error-message">
          <p>{error}</p>
        </div>
      )}

      {results && (
        <div className="results-section">
          <div className="results-header">
            <h3>תוצאות חיפוש</h3>
            <span className="results-count">נמצאו {results.totalCount} תוצאות</span>
          </div>

          {results.funds && results.funds.length > 0 ? (
            <div className="results-grid">
              {results.funds.map((fund) => (
                <div key={fund.id} className="fund-card">
                  <div className="fund-header">
                    <h4>{fund.name}</h4>
                    <span className={`fund-type ${fund.fundType.toLowerCase()}`}>
                      {getFundTypeHebrew(fund.fundType)}
                    </span>
                  </div>

                  <div className="fund-company">{fund.managingCompany}</div>

                  <div className="fund-stats">
                    <div className="stat">
                      <span className="stat-label">תשואה שנתית</span>
                      <span className="stat-value positive">{fund.annualReturn}%</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">דמי ניהול</span>
                      <span className="stat-value">{fund.managementFee}%</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">דמי הפקדה</span>
                      <span className="stat-value">{fund.depositFee}%</span>
                    </div>
                    <div className="stat">
                      <span className="stat-label">רמת סיכון</span>
                      <span className={`stat-value risk-${fund.riskLevel.toLowerCase()}`}>
                        {getRiskLevelHebrew(fund.riskLevel)}
                      </span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="no-results">
              <p>לא נמצאו תוצאות התואמות את הקריטריונים</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SearchPage;
