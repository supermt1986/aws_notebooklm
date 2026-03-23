import React, { useState, useEffect } from 'react';
import { useTranslation } from 'react-i18next';
import './App.css';
import './i18n';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000';

function App() {
  const { t, i18n } = useTranslation();
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [documents, setDocuments] = useState<string[]>([]);

  const fetchDocuments = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/documents`);
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch (e) {
      console.error(t('fetch_doc_error'), e);
    }
  };

  useEffect(() => {
    fetchDocuments();
  }, []);

  const handleSend = async () => {
    if (!input.trim()) return;
    const userMsg = input;
    setMessages(prev => [...prev, { role: 'user', content: userMsg }]);
    setInput('');
    setLoading(true);

    try {
      // 使用动态注入的基础 URL 以支持云端或本地后端
      const response = await fetch(`${API_BASE}/api/chat`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, session_id: 'test-session-1' })
      });
      const data = await response.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: t('server_error') }]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    setUploadStatus(`⏳ ${t('uploading')}`);

    try {
      const response = await fetch(`${API_BASE}/api/upload`, {
        method: 'POST',
        body: formData,
      });
      await response.json(); // Consume response to prevent unhandled promise, but don't assign to avoid TS6133
      setUploadStatus(`✅ ${t('upload_success')}`);
      fetchDocuments();
    } catch (err) {
      setUploadStatus(`❌ ${t('upload_fail')}`);
    }
  };

  return (
    <div className="app-wrapper">
      <div className="sidebar dark-theme glass-panel">
        <div className="sidebar-header">
          <h2>{t('knowledge_base_files')}</h2>
          <span className="doc-count">{t('files_count', { count: documents.length })}</span>
        </div>
        <div className="doc-list">
          {documents.map((doc, idx) => (
            <div key={idx} className="doc-item" title={doc}>
              📄 {doc}
            </div>
          ))}
          {documents.length === 0 && <div className="no-docs">{t('no_docs')}</div>}
        </div>
      </div>

      <div className="app-container dark-theme">
        <header className="glass-header" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <h1>{t('app_title')} <span>{t('app_subtitle')}</span></h1>

          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <button
              onClick={() => i18n.changeLanguage(i18n.language === 'zh' ? 'ja' : 'zh')}
              style={{ padding: '10px 16px', background: 'rgba(0,0,0,0.2)', border: '1px solid rgba(255,255,255,0.2)', color: '#fff', borderRadius: '8px', cursor: 'pointer', fontSize: '0.9rem', transition: 'all 0.2s', fontWeight: '500' }}
            >
              🌐 {t('switch_lang')}
            </button>

            <div className="upload-section" style={{ margin: 0, position: 'relative' }}>
              <label className="upload-btn">
                {t('upload_btn')}
                <input type="file" accept=".pdf,image/*,.txt,.md,.csv,.docx" hidden onChange={handleFileUpload} />
              </label>
              {uploadStatus &&
                <span className="status-text" style={{ position: 'absolute', top: '120%', right: '0', whiteSpace: 'nowrap' }}>
                  {uploadStatus}
                </span>
              }
            </div>
          </div>
        </header>

        <main className="chat-container">
          <div className="messages-list">
            {messages.length === 0 && (
              <div className="empty-state">
                <div className="hero-icon">☁️</div>
                <h3>{t('welcome_title')}</h3>
                <p>{t('welcome_desc')}</p>
              </div>
            )}
            {messages.map((msg, idx) => (
              <div key={idx} className={`message-bubble ${msg.role}`}>
                {msg.content}
              </div>
            ))}
            {loading && <div className="message-bubble assistant loading">
              <span className="dot">.</span><span className="dot">.</span><span className="dot">.</span> {t('retrieving')}
            </div>}
          </div>

          <div className="input-area">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder={t('search_placeholder')}
            />
            <button onClick={handleSend} disabled={loading}>
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
            </button>
          </div>
        </main>
      </div>
    </div>
  );
}

export default App;
