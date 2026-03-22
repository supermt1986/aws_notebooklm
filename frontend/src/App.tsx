import React, { useState, useEffect } from 'react';
import './App.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
}

function App() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [documents, setDocuments] = useState<string[]>([]);

  const fetchDocuments = async () => {
    try {
      const res = await fetch('http://localhost:8000/api/documents');
      const data = await res.json();
      setDocuments(data.documents || []);
    } catch (e) {
      console.error('获取文档列表失败', e);
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
      // 本地开发用地址，后续在 Amplify 部署时通过环境变量替换为真实的 API Gateway HTTPS 链接
      const response = await fetch('http://localhost:8000/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: userMsg, session_id: 'test-session-1' })
      });
      const data = await response.json();
      setMessages(prev => [...prev, { role: 'assistant', content: data.reply }]);
    } catch (e) {
      setMessages(prev => [...prev, { role: 'assistant', content: '连接服务器失败，请检查后端服务是否正在运行。' }]);
    } finally {
      setLoading(false);
    }
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const formData = new FormData();
    formData.append('file', file);
    setUploadStatus('正在上传至模拟S3...');

    try {
      const response = await fetch('http://localhost:8000/api/upload', {
        method: 'POST',
        body: formData,
      });
      const data = await response.json();
      setUploadStatus(`✅ ${data.message || '上传成功'}`);
      fetchDocuments();
    } catch (err) {
      setUploadStatus('❌ 上传失败');
    }
  };

  return (
    <div className="app-wrapper">
      <div className="sidebar dark-theme glass-panel">
        <div className="sidebar-header">
          <h2>知识库文件</h2>
          <span className="doc-count">{documents.length} 份</span>
        </div>
        <div className="doc-list">
          {documents.map((doc, idx) => (
            <div key={idx} className="doc-item" title={doc}>
              📄 {doc}
            </div>
          ))}
          {documents.length === 0 && <div className="no-docs">暂无文档</div>}
        </div>
      </div>

      <div className="app-container dark-theme">
        <header className="glass-header">
          <h1>AWS NotebookLM <span>(Cloud Variant)</span></h1>
          <div className="upload-section">
            <label className="upload-btn">
              准备知识库资源 (多模态)
              <input type="file" accept=".pdf,image/*,.txt,.md,.csv,.docx" hidden onChange={handleFileUpload} />
            </label>
            {uploadStatus && <span className="status-text">{uploadStatus}</span>}
          </div>
        </header>

        <main className="chat-container">
          <div className="messages-list">
            {messages.length === 0 && (
              <div className="empty-state">
                <div className="hero-icon">☁️</div>
                <h3>欢迎使用全栈云原生知识库</h3>
                <p>采用 React + Serverless + 架构无关适配层。您可以尝试上传文档并交流！</p>
              </div>
            )}
            {messages.map((msg, idx) => (
              <div key={idx} className={`message-bubble ${msg.role}`}>
                {msg.content}
              </div>
            ))}
            {loading && <div className="message-bubble assistant loading">
              <span className="dot">.</span><span className="dot">.</span><span className="dot">.</span> 知识库检索中
            </div>}
          </div>

          <div className="input-area">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyPress={(e) => e.key === 'Enter' && handleSend()}
              placeholder="问关于上传文档的任何问题..."
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
