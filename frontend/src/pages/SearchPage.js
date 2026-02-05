import React, { useState, useEffect } from 'react';
import './SearchPage.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

function SearchPage() {
  const [filters, setFilters] = useState({
    query: '',
    fundType: 'Pension',
    minReturn: '',
    minReturn3Years: '',
    minReturn5Years: '',
    maxStockExposure: '',
    sortBy: 'YEAR_TO_DATE_YIELD',
    sortDesc: true
  });
  const [results, setResults] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [page, setPage] = useState(1);
  const [selectedFunds, setSelectedFunds] = useState([]);
  const [showComparison, setShowComparison] = useState(false);
  const pageSize = 12;

  // Auto-search on initial load
  useEffect(() => {
    handleSearch();
  }, []);

  const handleInputChange = (e) => {
    const { name, value, type, checked } = e.target;
    setFilters(prev => ({
      ...prev,
      [name]: type === 'checkbox' ? checked : value
    }));
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);
    setPage(1);

    try {
      const data = await fetchResults(1);
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchResults = async (pageNum) => {
    const params = new URLSearchParams();

    if (filters.query) params.append('query', filters.query);
    if (filters.fundType) params.append('fundType', filters.fundType);
    if (filters.minReturn) params.append('minReturn', filters.minReturn);
    if (filters.minReturn3Years) params.append('minReturn3Years', filters.minReturn3Years);
    if (filters.minReturn5Years) params.append('minReturn5Years', filters.minReturn5Years);
    if (filters.maxStockExposure) params.append('maxStockExposure', filters.maxStockExposure);
    if (filters.sortBy) params.append('sortBy', filters.sortBy);
    params.append('sortDesc', filters.sortDesc);
    params.append('pageNumber', pageNum);
    params.append('pageSize', pageSize);

    const response = await fetch(`${API_BASE_URL}/Search?${params}`);
    if (!response.ok) throw new Error('שגיאה בחיפוש');

    return await response.json();
  };

  const handlePageChange = async (newPage) => {
    setLoading(true);
    try {
      const data = await fetchResults(newPage);
      setResults(data);
      setPage(newPage);
      window.scrollTo({ top: 0, behavior: 'smooth' });
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const clearFilters = () => {
    setFilters({
      query: '',
      fundType: 'Pension',
      minReturn: '',
      minReturn3Years: '',
      minReturn5Years: '',
      maxStockExposure: '',
      sortBy: 'YEAR_TO_DATE_YIELD',
      sortDesc: true
    });
    setResults(null);
    setSelectedFunds([]);
  };

  const toggleFundSelection = (fund) => {
    setSelectedFunds(prev => {
      const isSelected = prev.find(f => f.id === fund.id);
      if (isSelected) {
        return prev.filter(f => f.id !== fund.id);
      } else if (prev.length < 3) {
        return [...prev, fund];
      }
      return prev;
    });
  };

  const getRiskLevelHebrew = (level) => {
    const levels = { Low: 'נמוך', Medium: 'בינוני', High: 'גבוה' };
    return levels[level] || level || '-';
  };

  const getFundTypeHebrew = (type) => {
    const types = { Pension: 'קרן פנסיה', Executive: 'ביטוח מנהלים' };
    return types[type] || type;
  };

  const formatNumber = (num, decimals = 2) => {
    if (num === null || num === undefined) return '-';
    return Number(num).toFixed(decimals);
  };

  const formatPercent = (num) => {
    if (num === null || num === undefined) return '-';
    const formatted = Number(num).toFixed(2);
    return `${formatted}%`;
  };

  const formatAssets = (num) => {
    if (num === null || num === undefined) return '-';
    if (num >= 1000000) return `${(num / 1000000).toFixed(1)} מיליון`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)} אלף`;
    return num.toFixed(0);
  };

  const getBestValue = (funds, field, isLowerBetter = false) => {
    const values = funds.map(f => f[field]).filter(v => v !== null && v !== undefined);
    if (values.length === 0) return null;
    return isLowerBetter ? Math.min(...values) : Math.max(...values);
  };

  return (
    <div className="search-page">
      <div className="search-header">
        <h1>השוואת קרנות פנסיה וביטוחי מנהלים</h1>
        <p>חפש, סנן והשווה בין מאות קרנות פנסיה וביטוחי מנהלים בישראל</p>
      </div>

      <form className="search-form" onSubmit={handleSearch}>
        <div className="form-row">
          <div className="form-group">
            <label htmlFor="query">שם קרן או חברה מנהלת</label>
            <input
              type="text"
              id="query"
              name="query"
              value={filters.query}
              onChange={handleInputChange}
              placeholder="חיפוש חופשי..."
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
              <option value="Pension">קרן פנסיה</option>
              <option value="Executive">ביטוח מנהלים</option>
            </select>
          </div>

          <div className="form-group">
            <label htmlFor="sortBy">מיין לפי</label>
            <select
              id="sortBy"
              name="sortBy"
              value={filters.sortBy}
              onChange={handleInputChange}
            >
              <option value="YEAR_TO_DATE_YIELD">תשואה שנתית</option>
              <option value="YIELD_TRAILING_3_YRS">תשואה 3 שנים</option>
              <option value="YIELD_TRAILING_5_YRS">תשואה 5 שנים</option>
              <option value="AVG_ANNUAL_MANAGEMENT_FEE">דמי ניהול</option>
              <option value="SHARPE_RATIO">מדד שארפ</option>
              <option value="ALPHA">אלפא</option>
              <option value="TOTAL_ASSETS">סך נכסים</option>
            </select>
          </div>
        </div>

        <div className="form-row">
          <div className="form-group">
            <label htmlFor="minReturn">תשואה שנתית מינימלית (%)</label>
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
            <label htmlFor="minReturn5Years">תשואה 5 שנים מינימלית (%)</label>
            <input
              type="number"
              id="minReturn5Years"
              name="minReturn5Years"
              value={filters.minReturn5Years}
              onChange={handleInputChange}
              placeholder="לדוגמה: 30"
              step="1"
            />
          </div>

          <div className="form-group">
            <label htmlFor="maxStockExposure">חשיפה מקס' למניות (%)</label>
            <input
              type="number"
              id="maxStockExposure"
              name="maxStockExposure"
              value={filters.maxStockExposure}
              onChange={handleInputChange}
              placeholder="לדוגמה: 50"
              step="5"
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
          {selectedFunds.length > 0 && (
            <button
              type="button"
              className="btn btn-compare"
              onClick={() => setShowComparison(true)}
            >
              השווה ({selectedFunds.length}/3)
            </button>
          )}
        </div>
      </form>

      {error && (
        <div className="error-message">
          <p>{error}</p>
        </div>
      )}

      {/* Comparison Modal */}
      {showComparison && selectedFunds.length > 0 && (
        <div className="comparison-overlay" onClick={() => setShowComparison(false)}>
          <div className="comparison-modal" onClick={(e) => e.stopPropagation()}>
            <div className="comparison-header">
              <h2>השוואת קרנות</h2>
              <button className="close-btn" onClick={() => setShowComparison(false)}>×</button>
            </div>
            <div className="comparison-table-container">
              <table className="comparison-table">
                <thead>
                  <tr>
                    <th>מדד</th>
                    {selectedFunds.map(fund => (
                      <th key={fund.id}>{fund.name}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  <tr>
                    <td>חברה מנהלת</td>
                    {selectedFunds.map(fund => (
                      <td key={fund.id}>{fund.managingCompany}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>דמי הפקדה</td>
                    {selectedFunds.map(fund => {
                      const best = getBestValue(selectedFunds, 'depositFee', true);
                      const isBest = fund.depositFee === best;
                      return (
                        <td key={fund.id} className={isBest ? 'best-value' : ''}>
                          {formatPercent(fund.depositFee)}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td>תשואה שנתית</td>
                    {selectedFunds.map(fund => {
                      const best = getBestValue(selectedFunds, 'annualReturn');
                      const isBest = fund.annualReturn === best;
                      return (
                        <td key={fund.id} className={isBest ? 'best-value' : ''}>
                          {formatPercent(fund.annualReturn)}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td>תשואה מצטברת 3 שנים</td>
                    {selectedFunds.map(fund => {
                      const best = getBestValue(selectedFunds, 'yieldTrailing3Years');
                      const isBest = fund.yieldTrailing3Years === best;
                      return (
                        <td key={fund.id} className={isBest ? 'best-value' : ''}>
                          {formatPercent(fund.yieldTrailing3Years)}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td>תשואה מצטברת 5 שנים</td>
                    {selectedFunds.map(fund => {
                      const best = getBestValue(selectedFunds, 'yieldTrailing5Years');
                      const isBest = fund.yieldTrailing5Years === best;
                      return (
                        <td key={fund.id} className={isBest ? 'best-value' : ''}>
                          {formatPercent(fund.yieldTrailing5Years)}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td>סטיית תקן</td>
                    {selectedFunds.map(fund => {
                      const best = getBestValue(selectedFunds, 'standardDeviation', true);
                      const isBest = fund.standardDeviation === best;
                      return (
                        <td key={fund.id} className={isBest ? 'best-value' : ''}>
                          {formatNumber(fund.standardDeviation)}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td>מדד שארפ</td>
                    {selectedFunds.map(fund => {
                      const best = getBestValue(selectedFunds, 'sharpeRatio');
                      const isBest = fund.sharpeRatio === best;
                      return (
                        <td key={fund.id} className={isBest ? 'best-value' : ''}>
                          {formatNumber(fund.sharpeRatio)}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td>אלפא</td>
                    {selectedFunds.map(fund => {
                      const best = getBestValue(selectedFunds, 'alpha');
                      const isBest = fund.alpha === best;
                      return (
                        <td key={fund.id} className={isBest ? 'best-value' : ''}>
                          {formatNumber(fund.alpha)}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td>חשיפה למניות</td>
                    {selectedFunds.map(fund => (
                      <td key={fund.id}>{formatPercent(fund.stockMarketExposure)}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>חשיפה לחו"ל</td>
                    {selectedFunds.map(fund => (
                      <td key={fund.id}>{formatPercent(fund.foreignExposure)}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>סך נכסים</td>
                    {selectedFunds.map(fund => (
                      <td key={fund.id}>{formatAssets(fund.totalAssets)}</td>
                    ))}
                  </tr>
                </tbody>
              </table>
            </div>
            <div className="comparison-footer">
              <p className="comparison-note">
                <strong>הערה:</strong> מדד שארפ מודד תשואה מתואמת סיכון - ככל שהוא גבוה יותר, כך הקרן מניבה תשואה טובה יותר ביחס לסיכון.
                אלפא מודד ביצועי יתר ביחס למדד ייחוס.
              </p>
            </div>
          </div>
        </div>
      )}

      {results && (
        <div className="results-section">
          <div className="results-header">
            <h3>תוצאות חיפוש</h3>
            <span className="results-count">
              נמצאו {results.totalCount} תוצאות
              {selectedFunds.length > 0 && ` | נבחרו ${selectedFunds.length} להשוואה`}
            </span>
          </div>

          {results.funds && results.funds.length > 0 ? (
            <>
              <div className="results-grid">
                {results.funds.map((fund) => {
                  const isSelected = selectedFunds.find(f => f.id === fund.id);
                  return (
                    <div
                      key={fund.id}
                      className={`fund-card ${isSelected ? 'selected' : ''}`}
                      onClick={() => toggleFundSelection(fund)}
                    >
                      <div className="fund-header">
                        <h4>{fund.name}</h4>
                        <span className={`fund-type ${fund.fundType?.toLowerCase()}`}>
                          {getFundTypeHebrew(fund.fundType)}
                        </span>
                      </div>

                      <div className="fund-company">{fund.managingCompany}</div>
                      {fund.classification && (
                        <div className="fund-classification">{fund.classification}</div>
                      )}

                      <div className="fund-stats">
                        <div className="stat">
                          <span className="stat-label">תשואה שנתית</span>
                          <span className={`stat-value ${fund.annualReturn > 0 ? 'positive' : 'negative'}`}>
                            {formatPercent(fund.annualReturn)}
                          </span>
                        </div>
                        <div className="stat">
                          <span className="stat-label">תשואה 3 שנים</span>
                          <span className={`stat-value ${fund.yieldTrailing3Years > 0 ? 'positive' : 'negative'}`}>
                            {formatPercent(fund.yieldTrailing3Years)}
                          </span>
                        </div>
                        <div className="stat">
                          <span className="stat-label">תשואה 5 שנים</span>
                          <span className={`stat-value ${fund.yieldTrailing5Years > 0 ? 'positive' : 'negative'}`}>
                            {formatPercent(fund.yieldTrailing5Years)}
                          </span>
                        </div>
                        <div className="stat">
                          <span className="stat-label">מדד שארפ</span>
                          <span className="stat-value">{formatNumber(fund.sharpeRatio)}</span>
                        </div>
                      </div>

                      {isSelected && <div className="selected-indicator">✓ נבחר להשוואה</div>}
                    </div>
                  );
                })}
              </div>

              {/* Pagination */}
              {Math.ceil(results.totalCount / pageSize) > 1 && (
                <div className="pagination">
                  <button
                    className="btn btn-page"
                    disabled={page === 1}
                    onClick={() => handlePageChange(page - 1)}
                  >
                    הקודם
                  </button>
                  <span className="page-info">
                    עמוד {page} מתוך {Math.ceil(results.totalCount / pageSize)}
                  </span>
                  <button
                    className="btn btn-page"
                    disabled={page >= Math.ceil(results.totalCount / pageSize)}
                    onClick={() => handlePageChange(page + 1)}
                  >
                    הבא
                  </button>
                </div>
              )}
            </>
          ) : (
            <div className="no-results">
              <p>לא נמצאו תוצאות התואמות את הקריטריונים</p>
              <p className="no-results-hint">נסה לשנות את פרמטרי החיפוש</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default SearchPage;
