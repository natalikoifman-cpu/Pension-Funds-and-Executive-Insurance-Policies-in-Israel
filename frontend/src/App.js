import React from 'react';
import { Routes, Route, Link, useLocation } from 'react-router-dom';
import SearchPage from './pages/SearchPage';
import ChatPage from './pages/ChatPage';
import './App.css';

function App() {
  const location = useLocation();

  return (
    <div className="app">
      <header className="navbar">
        <div className="navbar-content">
          <Link to="/" className="navbar-logo">
            השוואת מוצרי חיסכון
          </Link>
          <nav className="navbar-nav">
            <Link
              to="/"
              className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}
            >
              חיפוש
            </Link>
            <Link
              to="/chat"
              className={`nav-link ${location.pathname === '/chat' ? 'active' : ''}`}
            >
              הסוכן החכם שלך
            </Link>
          </nav>
        </div>
      </header>

      <main className="main-content">
        <Routes>
          <Route path="/" element={<SearchPage />} />
          <Route path="/chat" element={<ChatPage />} />
        </Routes>
      </main>

      <footer className="site-footer">
        <p>מאת: קויפמן-לרנר | מחובר למאגר המידע הממשלתי</p>
      </footer>
    </div>
  );
}

export default App;
