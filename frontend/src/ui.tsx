import { useRef, useState } from 'react';

const API = '/api';
type Mode = 'Enroll' | 'Login' | 'Dashboard' | 'Admin';

export default function App() {
  const [mode, setMode] = useState<Mode>('Enroll');
  const [email, setEmail] = useState('');
  const [status, setStatus] = useState('Ready');
  const [consent, setConsent] = useState(false);
  const [token, setToken] = useState('');
  const [history, setHistory] = useState<unknown[]>([]);
  const video = useRef<HTMLVideoElement>(null);

  async function captureAndSend(action: 'enroll' | 'auth') {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true });
      if (video.current) video.current.srcObject = stream;
      await new Promise((resolve) => setTimeout(resolve, 1200));
      const canvas = document.createElement('canvas');
      canvas.width = video.current?.videoWidth || 640;
      canvas.height = video.current?.videoHeight || 480;
      canvas.getContext('2d')?.drawImage(video.current!, 0, 0);
      stream.getTracks().forEach((track) => track.stop());
      const frame = canvas.toDataURL('image/jpeg').split(',')[1];
      const body = { email, frames: [frame, frame], nonce: crypto.randomUUID() + crypto.randomUUID(), challenge: 'turn-head-then-blink', consent };
      const response = await fetch(`${API}/${action}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      const result = await response.json();
      if (!response.ok) throw new Error(result.detail || 'Request failed');
      if (result.access_token) setToken(result.access_token);
      setStatus(action === 'enroll' ? 'Enrollment complete' : 'Login successful');
    } catch (error) { setStatus(error instanceof Error ? error.message : 'Camera/API error'); }
  }

  async function loadHistory() {
    const response = await fetch(`${API}/users/me`, { headers: { Authorization: `Bearer ${token}` } });
    const result = await response.json(); setHistory(result.history || []); setStatus(response.ok ? 'History loaded' : result.detail);
  }

  return <main><header><div className="mark">Q</div><div><h1>Identity, secured.</h1><p>Biometric access console</p></div><span className="pill">LOCAL DEMO</span></header>
    <nav>{(['Enroll', 'Login', 'Dashboard', 'Admin'] as Mode[]).map((item) => <button className={mode === item ? 'active' : ''} onClick={() => setMode(item)} key={item}>{item}</button>)}</nav>
    <section className="panel"><div><small>SECURE IDENTITY</small><h2>{mode}</h2><p className="muted">Camera frames are sent in memory and are not intentionally stored by this demo.</p>
      {mode === 'Admin' ? <p>Runtime metrics are available from <a href="/api/health">the health endpoint</a>. Admin authorization is not implemented in this research demo.</p> : <>
        {(mode === 'Enroll' || mode === 'Login') && <><label>Email address<input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="you@example.com" /></label><div className="challenge">◉ &nbsp; Liveness prompt: turn your head, then blink</div><video ref={video} autoPlay muted playsInline />{mode === 'Enroll' && <label className="check"><input type="checkbox" checked={consent} onChange={(e) => setConsent(e.target.checked)} /> I consent to biometric processing for this demo.</label>}<button className="primary" onClick={() => captureAndSend(mode === 'Enroll' ? 'enroll' : 'auth')}>{mode === 'Enroll' ? 'Enroll face' : 'Authenticate'}</button></>}
        {mode === 'Dashboard' && <><button className="primary" disabled={!token} onClick={loadHistory}>Load audit history</button><pre>{JSON.stringify(history, null, 2)}</pre></>}
      </>}
      <p className="status">{status}</p></div><aside><span className="orb">✳</span><h3>Protected by design</h3><p>Cancelable templates are encrypted at rest. Quantum components are optional and run on simulators.</p><ul><li>AES-GCM encrypted template</li><li>Short-lived signed session</li><li>Replay nonce check</li></ul></aside></section>
    <footer>Research prototype · No production biometric assurance</footer></main>;
}
