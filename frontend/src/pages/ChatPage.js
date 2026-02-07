import React, { useState, useRef, useEffect } from 'react';
import './ChatPage.css';

const API_BASE_URL = process.env.REACT_APP_API_URL || '/api';

const DISCLAIMER = '\n\n---\n\u26a0\ufe0f אתר זה אינו מספק ייעוץ פנסיוני.\nהאתר מציג נתונים מאתר משרד האוצר בלבד.\nלקבלת ייעוץ פנסיוני יש לפנות לבעל רישיון מטעם משרד האוצר.';

function ChatPage() {
  const [messages, setMessages] = useState([
    {
      type: 'bot',
      content: 'שלום! אני כאן לעזור לך להציג ולהשוות נתונים על קרנות פנסיה וביטוחי מנהלים. אתה יכול לשאול אותי על השוואות בין קרנות ותשואות.',
      suggestedQuestions: [
        'השוואה בין קרנות פנסיה',
        'איזו קרן מניבה את התשואה הגבוהה ביותר?'
      ]
    }
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async (messageText) => {
    const text = messageText || input.trim();
    if (!text) return;

    setInput('');
    setMessages(prev => [...prev, { type: 'user', content: text }]);
    setLoading(true);

    try {
      const response = await fetch(`${API_BASE_URL}/Chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: text,
          sessionId: sessionId,
          context: { previousMessages: messages.slice(-5) }
        })
      });

      if (!response.ok) throw new Error('שגיאה בשליחת ההודעה');

      const data = await response.json();
      setSessionId(data.sessionId);

      setMessages(prev => [...prev, {
        type: 'bot',
        content: data.message + DISCLAIMER,
        suggestedFunds: data.suggestedFunds,
        suggestedQuestions: data.suggestedQuestions
      }]);
    } catch (err) {
      setMessages(prev => [...prev, {
        type: 'bot',
        content: 'מצטער, אירעה שגיאה. אנא נסה שוב.',
        isError: true
      }]);
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    sendMessage();
  };

  const handleSuggestedQuestion = (question) => {
    sendMessage(question);
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
    <div className="chat-page">
      <div className="chat-header">
        <h2>צ'אט</h2>
        <p>שאל שאלות בשפה חופשית וקבל נתונים מאתר משרד האוצר</p>
      </div>

      <div className="chat-container">
        <div className="messages-container">
          {messages.map((message, index) => (
            <div key={index} className={`message ${message.type}`}>
              <div className={`message-bubble ${message.isError ? 'error' : ''}`}>
                <p style={{ whiteSpace: 'pre-line' }}>{message.content}</p>

                {message.suggestedFunds && message.suggestedFunds.length > 0 && (
                  <div className="suggested-funds">
                    <h4>נתוני קרנות:</h4>
                    <div className="funds-list">
                      {message.suggestedFunds.map((fund) => (
                        <div key={fund.id} className="mini-fund-card">
                          <div className="mini-fund-name">{fund.name}</div>
                          <div className="mini-fund-details">
                            <span>{getFundTypeHebrew(fund.fundType)}</span>
                            <span>תשואה: {fund.annualReturn}%</span>
                            <span>דמי ניהול: {fund.managementFee}%</span>
                            <span>סיכון: {getRiskLevelHebrew(fund.riskLevel)}</span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {message.suggestedQuestions && message.suggestedQuestions.length > 0 && (
                  <div className="suggested-questions">
                    {message.suggestedQuestions.map((question, qIndex) => (
                      <button
                        key={qIndex}
                        className="suggested-question-btn"
                        onClick={() => handleSuggestedQuestion(question)}
                        disabled={loading}
                      >
                        {question}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ))}

          {loading && (
            <div className="message bot">
              <div className="message-bubble loading">
                <div className="typing-indicator">
                  <span></span>
                  <span></span>
                  <span></span>
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        <form className="chat-input-form" onSubmit={handleSubmit}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="הקלד את שאלתך כאן..."
            disabled={loading}
          />
          <button type="submit" disabled={loading || !input.trim()}>
            שלח
          </button>
        </form>
      </div>
    </div>
  );
}

export default ChatPage;
