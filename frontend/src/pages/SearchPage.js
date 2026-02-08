import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import './SearchPage.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

const PRODUCT_TYPES = [
  { id: 'Pension', icon: '📊', label: 'קרנות פנסיה', description: 'קרנות פנסיה מקיפות וכלליות' },
  { id: 'Executive', icon: '📋', label: 'ביטוחי מנהלים', description: 'פוליסות ביטוח מנהלים' },
  { id: 'Gemel', icon: '💰', label: 'קופות גמל', description: 'קופות גמל להשקעה' },
  { id: 'Hishtalmut', icon: '🎓', label: 'קרנות השתלמות', description: 'קרנות השתלמות לשכירים ועצמאים' },
  { id: 'GemelChild', icon: '👶', label: 'חסכון לילד', description: 'קופות גמל לחסכון לילד' },
];

// Fee sort fields should sort ascending (lower = better)
const FEE_SORT_FIELDS = ['AVG_ANNUAL_MANAGEMENT_FEE', 'AVG_DEPOSIT_FEE'];

function SearchPage() {
  const [filters, setFilters] = useState({
    query: '',
    fundType: 'Pension',
    classification: 'all',
    sortBy: 'AVG_ANNUAL_YIELD_TRAILING_3YRS',
    maxStockExposure: '',
    establishmentPeriod: 'all'
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

  const handleProductSelect = (productId) => {
    setFilters(prev => ({
      ...prev,
      fundType: productId,
      classification: 'all',
      establishmentPeriod: 'all'
    }));
    setSelectedFunds([]);
    // Trigger search with new product type
    setLoading(true);
    setError(null);
    setPage(1);

    const searchFilters = {
      ...filters,
      fundType: productId,
      classification: 'all',
      establishmentPeriod: 'all'
    };

    fetchResultsWithFilters(searchFilters, 1)
      .then(data => setResults(data))
      .catch(err => setError(err.message))
      .finally(() => setLoading(false));
  };

  const handleSearch = async (e) => {
    if (e) e.preventDefault();
    setLoading(true);
    setError(null);
    setPage(1);

    try {
      const data = await fetchResultsWithFilters(filters, 1);
      setResults(data);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  };

  const fetchResultsWithFilters = async (currentFilters, pageNum) => {
    const params = new URLSearchParams();

    if (currentFilters.query) params.append('query', currentFilters.query);
    if (currentFilters.fundType) params.append('fundType', currentFilters.fundType);
    if (currentFilters.sortBy) params.append('sortBy', currentFilters.sortBy);
    if (currentFilters.maxStockExposure) params.append('maxStockExposure', currentFilters.maxStockExposure);
    if (currentFilters.classification && currentFilters.classification !== 'all') {
      params.append('classification', currentFilters.classification);
    }
    if (currentFilters.fundType === 'Executive' && currentFilters.establishmentPeriod && currentFilters.establishmentPeriod !== 'all') {
      params.append('classification', currentFilters.establishmentPeriod);
    }

    // Sort ascending for fee fields (lower = better), descending for everything else
    const isFeeSort = FEE_SORT_FIELDS.includes(currentFilters.sortBy);
    params.append('sortDesc', isFeeSort ? 'false' : 'true');
    params.append('distinct', 'true');
    params.append('pageNumber', pageNum);
    params.append('pageSize', pageSize);

    const response = await fetch(`${API_BASE_URL}/Search?${params}`);
    if (!response.ok) {
      const errorText = await response.text().catch(() => '');
      throw new Error(`שגיאה בחיפוש (${response.status})${errorText ? ': ' + errorText : ''}`);
    }

    return await response.json();
  };

  const handlePageChange = async (newPage) => {
    setLoading(true);
    try {
      const data = await fetchResultsWithFilters(filters, newPage);
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
      classification: 'all',
      sortBy: 'AVG_ANNUAL_YIELD_TRAILING_3YRS',
      maxStockExposure: '',
      establishmentPeriod: 'all'
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

  const getFundTypeHebrew = (type) => {
    const types = {
      Pension: 'קרן פנסיה',
      Executive: 'ביטוח מנהלים',
      Gemel: 'קופת גמל להשקעה',
      Hishtalmut: 'קרנות השתלמות',
      GemelChild: 'קופת גמל - חסכון לילד'
    };
    return types[type] || type;
  };

  const isGemelType = (fundType) => {
    return ['gemel', 'hishtalmut', 'gemelchild'].includes(fundType?.toLowerCase());
  };

  const getPageTitle = () => {
    switch (filters.fundType) {
      case 'Pension':
        return 'השוואת קרנות פנסיה';
      case 'Executive':
        return 'השוואת ביטוחי מנהלים';
      case 'Gemel':
        return 'השוואת קופות גמל';
      case 'Hishtalmut':
        return 'השוואת קרנות השתלמות';
      case 'GemelChild':
        return 'השוואת קופות חסכון לילד';
      default:
        return 'השוואת מוצרי חיסכון';
    }
  };

  const getPageSubtitle = () => {
    const base = 'חפש, סנן והשווה בין';
    switch (filters.fundType) {
      case 'Pension':
        return `${base} קרנות פנסיה בישראל. נתונים רשמיים ממשרד האוצר.`;
      case 'Executive':
        return `${base} ביטוחי מנהלים בישראל. נתונים רשמיים ממשרד האוצר.`;
      case 'Gemel':
        return `${base} קופות גמל להשקעה בישראל. נתונים רשמיים ממשרד האוצר.`;
      case 'Hishtalmut':
        return `${base} קרנות השתלמות בישראל. נתונים רשמיים ממשרד האוצר.`;
      case 'GemelChild':
        return `${base} קופות גמל לחסכון לילד בישראל. נתונים רשמיים ממשרד האוצר.`;
      default:
        return 'השווה בין מוצרי חיסכון פנסיוני בישראל. נתונים רשמיים ממשרד האוצר.';
    }
  };

  const formatAssets = (num) => {
    if (num === null || num === undefined) return '-';
    if (num >= 1000) return `${(num / 1000).toFixed(1)} מיליארד ₪`;
    return `${Number(num).toFixed(0)} מיליון ₪`;
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

  const getBestValue = (funds, field, isLowerBetter = false) => {
    const values = funds.map(f => f[field]).filter(v => v !== null && v !== undefined);
    if (values.length === 0) return null;
    return isLowerBetter ? Math.min(...values) : Math.max(...values);
  };

  return (
    <div className="search-page">
      {/* Hero Section */}
      <section className="hero-section">
        <div className="feature-badge">נתונים רשמיים ממשרד האוצר</div>
        <h1 className="hero-title">
          {getPageTitle()}
        </h1>
        <p className="hero-subtitle">
          {getPageSubtitle()}
        </p>
      </section>

      {/* Product Selection Cards */}
      <div className="product-selection-grid">
        {PRODUCT_TYPES.map((product) => (
          <div
            key={product.id}
            className={`product-card ${filters.fundType === product.id ? 'active' : ''}`}
            onClick={() => handleProductSelect(product.id)}
          >
            <span className="product-icon">{product.icon}</span>
            <h3>{product.label}</h3>
            <p>{product.description}</p>
          </div>
        ))}
      </div>

      {/* Search Card */}
      <div className="search-card">
        <form onSubmit={handleSearch}>
          <div className="form-row">
            <div className="form-group form-group-grow">
              <label htmlFor="query">שם קרן, חברה מנהלת או מספר קרן</label>
              <input
                type="text"
                id="query"
                name="query"
                value={filters.query}
                onChange={handleInputChange}
                placeholder="חיפוש לפי שם, חברה או מספר..."
              />
            </div>

            <div className="form-group">
              <label htmlFor="sortBy">מיין לפי</label>
              <select
                id="sortBy"
                name="sortBy"
                value={filters.sortBy}
                onChange={handleInputChange}
              >
                <option value="AVG_ANNUAL_YIELD_TRAILING_3YRS">ממוצעת שנתית 3 שנים</option>
                <option value="AVG_ANNUAL_YIELD_TRAILING_5YRS">ממוצעת שנתית 5 שנים</option>
                <option value="SHARPE_RATIO">מדד שארפ</option>
                <option value="AVG_ANNUAL_MANAGEMENT_FEE">דמי ניהול (נמוך לגבוה)</option>
                <option value="AVG_DEPOSIT_FEE">דמי הפקדה (נמוך לגבוה)</option>
              </select>
            </div>
          </div>

          <div className="form-row">
            {filters.fundType === 'Pension' && (
              <div className="form-group">
                <label htmlFor="classification">סוג קרן</label>
                <select
                  id="classification"
                  name="classification"
                  value={filters.classification}
                  onChange={handleInputChange}
                >
                  <option value="all">כל הקרנות</option>
                  <option value="קרנות כלליות">קרנות כלליות</option>
                  <option value="קרנות חדשות">קרנות חדשות</option>
                </select>
              </div>
            )}
          </div>

          <div className="form-actions">
            <button type="submit" className="btn btn-cta" disabled={loading}>
              {loading ? 'מחפש...' : 'חפש'}
            </button>
            <button type="button" className="btn btn-outline" onClick={clearFilters}>
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
      </div>

      {error && (
        <div className="error-banner">
          <p>{error}</p>
        </div>
      )}

      {/* Comparison Modal */}
      {showComparison && selectedFunds.length > 0 && (
        <div className="modal-overlay" onClick={() => setShowComparison(false)}>
          <div className="modal-card" onClick={(e) => e.stopPropagation()}>
            <div className="modal-header">
              <h2>השוואת קרנות</h2>
              <button className="modal-close" onClick={() => setShowComparison(false)}>×</button>
            </div>
            <div className="modal-body">
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
                    <td>מספר קרן</td>
                    {selectedFunds.map(fund => (
                      <td key={fund.id}>{fund.id}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>חברה מנהלת</td>
                    {selectedFunds.map(fund => (
                      <td key={fund.id}>{fund.managingCompany}</td>
                    ))}
                  </tr>
                  <tr>
                    <td>דמי ניהול</td>
                    {selectedFunds.map(fund => {
                      const best = getBestValue(selectedFunds, 'managementFee', true);
                      const isBest = fund.managementFee === best;
                      return (
                        <td key={fund.id} className={isBest ? 'best-value' : ''}>
                          {formatPercent(fund.managementFee)}
                        </td>
                      );
                    })}
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
                    <td>ממוצעת שנתית 3 שנים</td>
                    {selectedFunds.map(fund => {
                      const best = getBestValue(selectedFunds, 'avgAnnualYield3Years');
                      const isBest = fund.avgAnnualYield3Years === best;
                      return (
                        <td key={fund.id} className={isBest ? 'best-value' : ''}>
                          {formatPercent(fund.avgAnnualYield3Years)}
                        </td>
                      );
                    })}
                  </tr>
                  <tr>
                    <td>ממוצעת שנתית 5 שנים</td>
                    {selectedFunds.map(fund => {
                      const best = getBestValue(selectedFunds, 'avgAnnualYield5Years');
                      const isBest = fund.avgAnnualYield5Years === best;
                      return (
                        <td key={fund.id} className={isBest ? 'best-value' : ''}>
                          {formatPercent(fund.avgAnnualYield5Years)}
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
                </tbody>
              </table>
            </div>
            <div className="modal-footer">
              <p>
                <strong>הערה:</strong> מדד שארפ מודד תשואה מתואמת סיכון - ככל שהוא גבוה יותר, כך הקרן מניבה תשואה טובה יותר ביחס לסיכון.
                סטיית תקן מודדת את רמת התנודתיות - ככל שהיא נמוכה יותר, כך ההשקעה יציבה יותר.
              </p>
            </div>
          </div>
        </div>
      )}

      {/* Results */}
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
                      <div className="fund-card-header">
                        <h4>{fund.name}</h4>
                        <span className={`fund-type-badge ${fund.fundType?.toLowerCase()}`}>
                          {getFundTypeHebrew(fund.fundType)}
                        </span>
                      </div>

                      <div className="fund-meta">
                        <span className="fund-number">מספר: {fund.id}</span>
                        <span className="fund-company">{fund.managingCompany}</span>
                      </div>
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
                          <span className="stat-label">ממוצעת 3 שנים</span>
                          <span className={`stat-value ${fund.avgAnnualYield3Years > 0 ? 'positive' : 'negative'}`}>
                            {formatPercent(fund.avgAnnualYield3Years)}
                          </span>
                        </div>
                        <div className="stat">
                          <span className="stat-label">ממוצעת 5 שנים</span>
                          <span className={`stat-value ${fund.avgAnnualYield5Years > 0 ? 'positive' : 'negative'}`}>
                            {formatPercent(fund.avgAnnualYield5Years)}
                          </span>
                        </div>
                        <div className="stat">
                          <span className="stat-label">מדד שארפ</span>
                          <span className="stat-value">{formatNumber(fund.sharpeRatio)}</span>
                        </div>
                        {isGemelType(fund.fundType) && (
                          <>
                            <div className="stat">
                              <span className="stat-label">דמי ניהול</span>
                              <span className="stat-value">{formatPercent(fund.managementFee)}</span>
                            </div>
                            <div className="stat">
                              <span className="stat-label">דמי הפקדה</span>
                              <span className="stat-value">{formatPercent(fund.depositFee)}</span>
                            </div>
                            {fund.totalAssets && (
                              <div className="stat">
                                <span className="stat-label">סך נכסים</span>
                                <span className="stat-value">{formatAssets(fund.totalAssets)}</span>
                              </div>
                            )}
                          </>
                        )}
                      </div>

                      {isSelected && <div className="selected-badge">נבחר להשוואה</div>}
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

      {/* Feature Cards */}
      <div className="features-grid">
        <div className="feature-card">
          <div className="feature-icon">📈</div>
          <h3>השוואת תשואות</h3>
          <p>השווה תשואות שנתיות, 3 שנים ו-5 שנים בין קרנות וקופות</p>
        </div>

        <div className="feature-card">
          <div className="feature-icon">🔍</div>
          <h3>כל המוצרים הפיננסיים</h3>
          <p>פנסיה, ביטוח מנהלים, קופות גמל, קרנות השתלמות וחסכון לילד</p>
        </div>

        <Link to="/chat" className="feature-card feature-card-link">
          <div className="feature-icon">🤖</div>
          <h3>סוכן חכם</h3>
          <p>שאל שאלות בשפה חופשית וקבל תשובות מהנתונים</p>
        </Link>
      </div>
    </div>
  );
}

export default SearchPage;
