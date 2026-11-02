import { useEffect, useRef, useState } from 'react';
import { useFaceMesh } from './face-mesh';

const API = '/api';
type Mode = 'Enroll' | 'Login' | 'Dashboard' | 'Admin';
const FRAMES_PER_POSE = 3;
const POSE_TIMEOUT_MS = 15_000;
const POSE_HOLD_FRAMES = 3;
const TURN_DELTA = 0.035;

function wait(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms));
}

function cameraErrorMessage(error: unknown): string {
  const name = error instanceof DOMException ? error.name : '';
  if (name === 'NotAllowedError' || name === 'PermissionDeniedError') {
    return 'Camera permission is blocked. Allow camera access for localhost in the browser site settings, then reconnect the camera.';
  }
  if (name === 'NotFoundError' || name === 'DevicesNotFoundError') {
    return 'No camera was found. Connect a camera or choose another device from the camera menu.';
  }
  if (name === 'NotReadableError' || name === 'TrackStartError') {
    return 'The camera is busy or unavailable. Close other apps using it, check the privacy shutter, and try again.';
  }
  if (name === 'OverconstrainedError' || name === 'ConstraintNotSatisfiedError') {
    return 'This camera cannot use the requested settings. Select another camera and reconnect.';
  }
  if (name === 'SecurityError') {
    return 'The browser blocked camera access. Open the app at http://localhost:5173 and allow camera access.';
  }
  if (name === 'AbortError') return 'Camera startup was interrupted. Reconnect the camera and try again.';
  if (error instanceof Error && error.message) return error.message;
  return 'Could not start the camera. Check browser permission and Windows camera privacy settings.';
}

function waitForVideoFrame(video: HTMLVideoElement): Promise<void> {
  if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0) {
    return Promise.resolve();
  }
  return new Promise((resolve, reject) => {
    const finish = (error?: Error) => {
      window.clearTimeout(timeout);
      video.removeEventListener('loadeddata', checkReady);
      video.removeEventListener('canplay', checkReady);
      if (error) reject(error);
      else resolve();
    };
    const checkReady = () => {
      if (video.readyState >= HTMLMediaElement.HAVE_CURRENT_DATA && video.videoWidth > 0) finish();
    };
    const timeout = window.setTimeout(
      () => finish(new Error('The camera connected but did not send video. Check its shutter or select another camera.')),
      8000,
    );
    video.addEventListener('loadeddata', checkReady);
    video.addEventListener('canplay', checkReady);
  });
}

function decodeBase64Url(value: string): Uint8Array {
  const base64 = value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4);
  const binary = atob(base64);
  return Uint8Array.from(binary, (character) => character.charCodeAt(0));
}

function encodeBase64Url(value: ArrayBuffer | null): string | null {
  if (!value) return null;
  let binary = '';
  for (const byte of new Uint8Array(value)) binary += String.fromCharCode(byte);
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
}

function creationOptions(options: any): PublicKeyCredentialCreationOptions {
  return {
    ...options,
    challenge: decodeBase64Url(options.challenge),
    user: { ...options.user, id: decodeBase64Url(options.user.id) },
    excludeCredentials: (options.excludeCredentials || []).map((item: any) => ({
      ...item,
      id: decodeBase64Url(item.id),
    })),
  } as PublicKeyCredentialCreationOptions;
}

function requestOptions(options: any): PublicKeyCredentialRequestOptions {
  return {
    ...options,
    challenge: decodeBase64Url(options.challenge),
    allowCredentials: (options.allowCredentials || []).map((item: any) => ({
      ...item,
      id: decodeBase64Url(item.id),
    })),
  } as PublicKeyCredentialRequestOptions;
}

function serializeCredential(credential: PublicKeyCredential) {
  const common = {
    id: credential.id,
    rawId: encodeBase64Url(credential.rawId),
    type: credential.type,
    authenticatorAttachment: credential.authenticatorAttachment,
    clientExtensionResults: credential.getClientExtensionResults(),
  };
  if (credential.response instanceof AuthenticatorAttestationResponse) {
    return {
      ...common,
      response: {
        attestationObject: encodeBase64Url(credential.response.attestationObject),
        clientDataJSON: encodeBase64Url(credential.response.clientDataJSON),
      },
    };
  }
  if (credential.response instanceof AuthenticatorAssertionResponse) {
    return {
      ...common,
      response: {
        authenticatorData: encodeBase64Url(credential.response.authenticatorData),
        clientDataJSON: encodeBase64Url(credential.response.clientDataJSON),
        signature: encodeBase64Url(credential.response.signature),
        userHandle: encodeBase64Url(credential.response.userHandle),
      },
    };
  }
  throw new Error('This browser returned an unsupported passkey response.');
}

export default function App() {
  const [mode, setMode] = useState<Mode>('Enroll');
  const [email, setEmail] = useState('');
  const [fullName, setFullName] = useState('');
  const [department, setDepartment] = useState('');
  const [employeeId, setEmployeeId] = useState('');
  const [enrollStep, setEnrollStep] = useState<1 | 2>(1);
  const [status, setStatus] = useState('Enable the camera to begin.');
  const [busy, setBusy] = useState(false);
  const [consent, setConsent] = useState(false);
  const [token, setToken] = useState('');
  const [history, setHistory] = useState<unknown[]>([]);
  const [vault, setVault] = useState<{ id: string; classification: string; title: string; summary: string }[]>([]);
  const [cameraReady, setCameraReady] = useState(false);
  const [cameraIssue, setCameraIssue] = useState('');
  const [videoDevices, setVideoDevices] = useState<MediaDeviceInfo[]>([]);
  const [selectedDeviceId, setSelectedDeviceId] = useState('');
  const [cameraFallbackOpen, setCameraFallbackOpen] = useState(false);
  const [passkeyReady, setPasskeyReady] = useState(false);
  const [booting, setBooting] = useState(true);
  const video = useRef<HTMLVideoElement>(null);
  const faceOverlay = useRef<HTMLCanvasElement>(null);
  const stream = useRef<MediaStream | null>(null);
  const [scanDirection, setScanDirection] = useState<number | null>(null);
  const [scanning, setScanning] = useState(false);
  const { faceCount, modelReady, modelError, readingRef } = useFaceMesh(video, faceOverlay, cameraReady);

  useEffect(() => () => stream.current?.getTracks().forEach((track) => track.stop()), []);

  useEffect(() => {
    const timer = window.setTimeout(() => setBooting(false), 1500);
    return () => window.clearTimeout(timer);
  }, []);

  async function enableCamera(deviceId = selectedDeviceId) {
    let camera: MediaStream | null = null;
    try {
      if (!navigator.mediaDevices?.getUserMedia) {
        throw new Error('This browser cannot access a camera. Use a current browser at http://localhost:5173.');
      }
      stream.current?.getTracks().forEach((track) => {
        track.onended = null;
        track.stop();
      });
      stream.current = null;
      if (video.current) video.current.srcObject = null;
      setCameraReady(false);
      setCameraIssue('Waiting for browser camera permission…');
      const videoSettings = { width: { ideal: 640 }, height: { ideal: 480 } };
      try {
        camera = await navigator.mediaDevices.getUserMedia({
          audio: false,
          video: deviceId
            ? { ...videoSettings, deviceId: { exact: deviceId } }
            : { ...videoSettings, facingMode: { ideal: 'user' } },
        });
      } catch (error) {
        const name = error instanceof DOMException ? error.name : '';
        if (!['NotFoundError', 'OverconstrainedError'].includes(name)) throw error;
        // Some integrated webcams reject ideal/facingMode constraints. Retry the browser default.
        camera = await navigator.mediaDevices.getUserMedia({ audio: false, video: true });
      }
      stream.current = camera;
      const preview = video.current;
      if (!preview) throw new Error('The camera preview is not ready. Return to the face scan step and try again.');
      preview.muted = true;
      preview.playsInline = true;
      preview.srcObject = camera;
      await preview.play();
      await waitForVideoFrame(preview);
      const devices = (await navigator.mediaDevices.enumerateDevices())
        .filter((device) => device.kind === 'videoinput');
      setVideoDevices(devices);
      const activeDeviceId = camera.getVideoTracks()[0]?.getSettings().deviceId || deviceId;
      if (activeDeviceId) setSelectedDeviceId(activeDeviceId);
      const track = camera.getVideoTracks()[0];
      if (track) {
        track.onended = () => {
          if (stream.current !== camera) return;
          stream.current = null;
          setCameraReady(false);
          setCameraIssue('Camera disconnected. Reconnect it before starting a scan.');
          setStatus('Camera disconnected. Reconnect it before starting a scan.');
        };
      }
      setCameraReady(true);
      setCameraIssue('');
      const activeLabel = devices.find((device) => device.deviceId === activeDeviceId)?.label;
      setStatus(`${activeLabel ? `${activeLabel} connected. ` : ''}Camera ready. Wait for the live face guide, then start your scan.`);
    } catch (error) {
      camera?.getTracks().forEach((track) => {
        track.onended = null;
        track.stop();
      });
      if (stream.current === camera) stream.current = null;
      if (video.current) video.current.srcObject = null;
      setCameraReady(false);
      const message = cameraErrorMessage(error);
      setCameraIssue(message);
      setStatus(message);
    }
  }

  function stopCamera() {
    const camera = stream.current;
    stream.current = null;
    camera?.getTracks().forEach((track) => {
      track.onended = null;
      track.stop();
    });
    if (video.current) video.current.srcObject = null;
    setCameraReady(false);
    setCameraIssue('Camera is off. Select Enable laptop camera to start the preview.');
  }

  function scanDirectionLabel(sign: number) {
    // The preview and mesh are mirrored; raw frame x coordinates run the other way.
    return sign > 0 ? '←' : '→';
  }

  async function waitForStablePose(
    prompt: string,
    predicate: (pose: number, recent: number[]) => boolean,
  ): Promise<number[]> {
    setStatus(prompt);
    const deadline = performance.now() + POSE_TIMEOUT_MS;
    const recent: number[] = [];
    let lastCapture = 0;
    let lastFaceCount = -1;
    while (performance.now() < deadline) {
      const reading = readingRef.current;
      if (reading.capturedAt === lastCapture || performance.now() - reading.capturedAt > 700) {
        await wait(35);
        continue;
      }
      lastCapture = reading.capturedAt;
      if (reading.faceCount !== 1 || reading.pose === null) {
        recent.length = 0;
        if (reading.faceCount !== lastFaceCount) {
          if (reading.faceCount > 1) setStatus('More than one face is visible. Keep only your face in the frame.');
          else if (reading.faceCount === 0) setStatus('Face the camera so the mesh guide can find your face.');
          else setStatus(prompt);
          lastFaceCount = reading.faceCount;
        }
        await wait(35);
        continue;
      }
      lastFaceCount = 1;
      recent.push(reading.pose);
      if (recent.length > POSE_HOLD_FRAMES) recent.shift();
      if (recent.length === POSE_HOLD_FRAMES && predicate(reading.pose, recent)) {
        return [...recent];
      }
      await wait(35);
    }
    throw new Error('The camera could not confirm that pose. Keep your full face visible and follow the arrow, then start a new scan.');
  }

  async function capturePoseFrames(): Promise<string[]> {
    const camera = video.current;
    if (!camera || !camera.videoWidth || !camera.videoHeight) {
      throw new Error('Camera is starting. Wait for the live preview, then try again.');
    }
    const canvas = document.createElement('canvas');
    canvas.width = Math.min(camera.videoWidth, 640);
    canvas.height = Math.round((camera.videoHeight / camera.videoWidth) * canvas.width);
    const context = canvas.getContext('2d');
    if (!context) throw new Error('Could not capture a camera frame.');
    const frames: string[] = [];
    for (let index = 0; index < FRAMES_PER_POSE; index += 1) {
      const previousTime = camera.currentTime;
      const deadline = performance.now() + 1000;
      while (camera.currentTime === previousTime && performance.now() < deadline) await wait(35);
      if (camera.currentTime === previousTime) {
        throw new Error('The camera feed stopped updating. Reconnect the camera and try again.');
      }
      context.drawImage(camera, 0, 0, canvas.width, canvas.height);
      if (frames.length === 0) {
        const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
        let total = 0;
        let brightest = 0;
        const stride = Math.max(4, Math.floor(pixels.length / 2048 / 4) * 4);
        for (let pixel = 0; pixel < pixels.length; pixel += stride) {
          const light = (pixels[pixel] + pixels[pixel + 1] + pixels[pixel + 2]) / 3;
          total += light;
          brightest = Math.max(brightest, light);
        }
        const meanBrightness = total / Math.ceil(pixels.length / stride);
        if (meanBrightness < 5 && brightest < 24) {
          throw new Error('Camera is connected, but its video is black. Check the camera shutter and Windows camera privacy settings, or select another camera.');
        }
      }
      frames.push(canvas.toDataURL('image/jpeg', 0.82).split(',')[1]);
      if (index < FRAMES_PER_POSE - 1) await wait(150);
    }
    return frames;
  }

  async function captureAndSend(action: 'enroll' | 'auth') {
    if (!email.trim()) {
      setStatus('Enter your company email address first.');
      return;
    }
    if (!cameraReady) {
      setStatus('Enable the camera first.');
      return;
    }
    if (!modelReady) {
      setStatus(modelError || 'The local face guide is still loading. Wait a moment and try again.');
      return;
    }
    if (action === 'enroll' && !consent) {
      setStatus('Consent is required before registering a face template.');
      return;
    }
    setBusy(true);
    setScanning(true);
    try {
      setScanDirection(null);
      const challengeResponse = await fetch(`${API}/face/challenge`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      });
      const challenge = await challengeResponse.json();
      if (!challengeResponse.ok) throw new Error(challenge.detail || 'Could not start a face scan.');
      const firstSign = Number(challenge.first_turn_sign);
      if (!challenge.challenge_id || ![-1, 1].includes(firstSign)) {
        throw new Error('The server returned an invalid face scan. Restart the app and try again.');
      }

      setStatus('Center your face inside the guide and hold still.');
      const centered = await waitForStablePose(
        'Center your face inside the guide and hold still.',
        (pose, recent) => Math.abs(pose - 0.5) <= 0.2 && Math.max(...recent) - Math.min(...recent) <= 0.035,
      );
      const centerBaseline = centered.reduce((sum, pose) => sum + pose, 0) / centered.length;
      const frames = await capturePoseFrames();

      const waitForTurn = async (sign: number, label: string) => {
        setScanDirection(sign);
        await waitForStablePose(
          `Turn your head toward ${label} and hold until the next prompt.`,
          (pose) => (pose - centerBaseline) * sign >= TURN_DELTA,
        );
        frames.push(...await capturePoseFrames());
      };
      await waitForTurn(firstSign, scanDirectionLabel(firstSign));
      await waitForTurn(-firstSign, scanDirectionLabel(-firstSign));
      setScanDirection(null);
      await waitForStablePose(
        'Return to the center of the guide and hold still.',
        (pose, recent) => Math.abs(pose - centerBaseline) <= 0.04
          && Math.max(...recent) - Math.min(...recent) <= 0.035,
      );
      frames.push(...await capturePoseFrames());

      const body = {
        email: email.trim(),
        ...(action === 'enroll' ? {
          full_name: fullName.trim(),
          department: department.trim(),
          employee_id: employeeId.trim(),
        } : {}),
        frames,
        challenge_id: challenge.challenge_id,
        consent: action === 'enroll' && consent,
      };
      setStatus('Movement verified. Checking the registered face…');
      const response = await fetch(`${API}/${action}`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      const result = await response.json();
      if (!response.ok) {
        const detail = result.detail || 'Request failed.';
        throw new Error(detail);
      }
      if (result.access_token) setToken(result.access_token);
      stopCamera();
      setMode('Dashboard');
      if (action === 'enroll') {
        setStatus('Face enrollment complete. Add a Windows Hello passkey for phone-style sign-in.');
      } else {
        await fetchVault(result.access_token);
        setStatus('Registered face verified. Protected workspace unlocked.');
      }
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Camera or server error.');
    } finally {
      setBusy(false);
      setScanning(false);
      setScanDirection(null);
    }
  }

  async function registerPasskey() {
    if (!token) {
      setStatus('Sign in or complete face enrollment before setting up a passkey.');
      return;
    }
    if (!window.PublicKeyCredential || !navigator.credentials?.create) {
      setStatus('This browser does not support device passkeys. Try current Chrome or Edge.');
      return;
    }
    setBusy(true);
    try {
      const optionsResponse = await fetch(`${API}/passkeys/register/options`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
      });
      const ceremony = await optionsResponse.json();
      if (!optionsResponse.ok) throw new Error(ceremony.detail || 'Could not start passkey setup.');
      const credential = await navigator.credentials.create({ publicKey: creationOptions(ceremony.options) });
      if (!(credential instanceof PublicKeyCredential)) throw new Error('Passkey setup was cancelled.');
      const verifyResponse = await fetch(`${API}/passkeys/register/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
        body: JSON.stringify({ ceremony_id: ceremony.ceremony_id, credential: serializeCredential(credential) }),
      });
      const result = await verifyResponse.json();
      if (!verifyResponse.ok) throw new Error(result.detail || 'Could not save this passkey.');
      setPasskeyReady(true);
      setStatus('Passkey added. Windows Hello verifies you on this device; your face data is not sent to the app.');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Passkey setup failed.');
    } finally {
      setBusy(false);
    }
  }

  async function authenticateWithPasskey() {
    if (!email.trim()) {
      setStatus('Enter the email address used when setting up your passkey.');
      return;
    }
    if (!window.PublicKeyCredential || !navigator.credentials?.get) {
      setStatus('This browser does not support device passkeys. Try current Chrome or Edge.');
      return;
    }
    setBusy(true);
    try {
      const optionsResponse = await fetch(`${API}/passkeys/auth/options`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: email.trim() }),
      });
      const ceremony = await optionsResponse.json();
      if (!optionsResponse.ok) throw new Error(ceremony.detail || 'No passkey is set up for this account.');
      const credential = await navigator.credentials.get({ publicKey: requestOptions(ceremony.options) });
      if (!(credential instanceof PublicKeyCredential)) throw new Error('Passkey sign-in was cancelled.');
      const verifyResponse = await fetch(`${API}/passkeys/auth/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ceremony_id: ceremony.ceremony_id, credential: serializeCredential(credential) }),
      });
      const result = await verifyResponse.json();
      if (!verifyResponse.ok) throw new Error(result.detail || 'Passkey sign-in failed.');
      stopCamera();
      setToken(result.access_token);
      setCameraFallbackOpen(false);
      setMode('Dashboard');
      await fetchVault(result.access_token);
      setStatus('Verified by your device passkey. Protected workspace unlocked.');
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Passkey sign-in failed.');
    } finally {
      setBusy(false);
    }
  }

  async function loadHistory() {
    const response = await fetch(`${API}/users/me`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    const result = await response.json();
    setHistory(result.history || []);
    setStatus(response.ok ? 'Audit history loaded.' : result.detail || 'Could not load history.');
  }

  async function fetchVault(accessToken: string) {
    const response = await fetch(`${API}/vault`, {
      headers: { Authorization: `Bearer ${accessToken}` },
    });
    const result = await response.json();
    if (!response.ok) {
      setVault([]);
      throw new Error(result.detail || 'Your session expired. Sign in again.');
    }
    setVault(result.records || []);
  }

  async function openVault() {
    try {
      await fetchVault(token);
    } catch (error) {
      setStatus(error instanceof Error ? error.message : 'Your session expired. Sign in again.');
      return;
    }
    setStatus('Protected sample workspace opened.');
  }

  function toggleCameraFallback() {
    if (cameraFallbackOpen) stopCamera();
    setCameraFallbackOpen(!cameraFallbackOpen);
    setStatus(cameraFallbackOpen ? 'Webcam stopped.' : 'Enable the camera to begin webcam sign-in.');
  }

  function changeMode(next: Mode) {
    if (next !== mode) stopCamera();
    setCameraFallbackOpen(false);
    if (next === 'Enroll') setEnrollStep(1);
    setMode(next);
    setStatus(next === 'Enroll' || next === 'Login' ? 'Enable the camera to begin.' : 'Ready.');
  }

  function continueToFaceScan() {
    if (!fullName.trim() || !email.trim() || !department.trim() || !employeeId.trim()) {
      setStatus('Complete all user details before continuing to face setup.');
      return;
    }
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())) {
      setStatus('Enter a valid company email address before continuing.');
      return;
    }
    setEnrollStep(2);
    setStatus('Details are ready. Enable the camera to begin face enrollment.');
  }

  const cameraMode = (mode === 'Enroll' && enrollStep === 2) || (mode === 'Login' && cameraFallbackOpen);

  useEffect(() => {
    if (!cameraMode || !navigator.mediaDevices?.enumerateDevices) return undefined;
    let cancelled = false;
    const refreshDevices = async () => {
      try {
        const devices = (await navigator.mediaDevices.enumerateDevices())
          .filter((device) => device.kind === 'videoinput');
        if (!cancelled) setVideoDevices(devices);
      } catch {
        if (!cancelled) setVideoDevices([]);
      }
    };
    void refreshDevices();
    navigator.mediaDevices.addEventListener?.('devicechange', refreshDevices);
    return () => {
      cancelled = true;
      navigator.mediaDevices.removeEventListener?.('devicechange', refreshDevices);
    };
  }, [cameraMode]);

  return <>
  <main className="app-shell">
    <header className="app-header">
      <div className="brand-lockup">
        <div className="mark" aria-hidden="true">Q</div>
        <div><h1>Identity Access</h1><p>Company identity workspace</p></div>
      </div>
      <span className="pill"><i /> LOCAL RESEARCH DEMO</span>
    </header>
    <section className="page-intro">
      <div><small>IDENTITY LAYER <span> / </span> 01</small><h2>Access, built around identity.</h2></div>
      <p>Set up a team profile, verify with a face scan, or use a device passkey.</p>
    </section>
    <nav className="mode-tabs" aria-label="Workspace sections">{(['Enroll', 'Login', 'Dashboard', 'Admin'] as Mode[]).map((item) =>
      <button className={mode === item ? 'active' : ''} aria-current={mode === item ? 'page' : undefined} disabled={busy} onClick={() => changeMode(item)} key={item}>{item}</button>)}</nav>
    <section className="panel">
      <div className="panel-main">
        <div className="panel-heading"><div>
          <small>BIOMETRIC ACCESS</small><h2>{mode === 'Enroll' ? `Setup · Step ${enrollStep} of 2` : mode}</h2>
        </div><span className="panel-heading-mark" aria-hidden="true">{mode === 'Enroll' ? `0${enrollStep}` : '→'}</span></div>
        <p className="muted">Device passkeys verify locally and share only a signed proof with the server. Webcam enrollment is available for this demo.</p>
        {mode === 'Admin' ? <p>Admin authorization and enrollment approval are not implemented. Do not connect this prototype to sensitive company data.</p> : <>
          {mode === 'Login' && <>
            <label>Email address<input type="email" autoComplete="email" value={email} disabled={busy} onChange={(event) => setEmail(event.target.value)} placeholder="you@company.com" /></label>
            <button className="primary" disabled={!email.trim() || busy} onClick={authenticateWithPasskey}>
              {busy ? 'Waiting for device…' : 'Continue with Windows Hello / passkey'}
            </button>
            <p className="muted">Windows checks you on this device using face, fingerprint, or your device PIN. Your biometric data stays local.</p>
            <button className="secondary" disabled={busy} onClick={toggleCameraFallback}>
              {cameraFallbackOpen ? 'Hide webcam sign-in' : 'Use webcam face sign-in instead'}
            </button>
          </>}
          {mode === 'Enroll' && enrollStep === 1 && <>
            <div className="setup-progress" aria-label="Signup progress">
              <span className="current"><b>1</b> User details</span><i aria-hidden="true" />
              <span><b>2</b> Face scan</span>
            </div>
            <p className="muted">Enter the company profile for the person being enrolled. The details and face template are saved after the face scan succeeds.</p>
            <label>Full name<input type="text" autoComplete="name" value={fullName} disabled={busy} onChange={(event) => setFullName(event.target.value)} placeholder="Alex Morgan" maxLength={120} /></label>
            <label>Company email<input type="email" autoComplete="email" value={email} disabled={busy} onChange={(event) => setEmail(event.target.value)} placeholder="alex@company.com" maxLength={320} /></label>
            <label>Department<input type="text" autoComplete="organization-title" value={department} disabled={busy} onChange={(event) => setDepartment(event.target.value)} placeholder="Engineering" maxLength={120} /></label>
            <label>Employee ID<input type="text" autoComplete="off" value={employeeId} disabled={busy} onChange={(event) => setEmployeeId(event.target.value)} placeholder="EMP-1042" maxLength={80} /></label>
            <button className="primary" disabled={!fullName.trim() || !email.trim() || !department.trim() || !employeeId.trim() || busy} onClick={continueToFaceScan}>Continue to face scan</button>
            <p className="risk-note">This demo collects the profile but does not verify it against a company directory or admin approval list.</p>
          </>}
          {cameraMode && <>
            {mode === 'Enroll' && <>
              <div className="setup-progress" aria-label="Signup progress">
                <span className="complete"><b>✓</b> User details</span><i aria-hidden="true" />
                <span className="current"><b>2</b> Face scan</span>
              </div>
              <div className="profile-summary"><strong>{fullName}</strong><span>{email}</span><span>{department} · {employeeId}</span></div>
              <button className="secondary" disabled={busy} onClick={() => { stopCamera(); setEnrollStep(1); setStatus('Edit the user details, then continue to face setup.'); }}>Back to user details</button>
            </>}
            <div className="challenge"><strong>Guided face scan</strong><span>The live mesh shows when your face is detected. Hold center, follow the arrow to turn to one side, turn the opposite way, then return to center. The scan verifies automatically.</span></div>
            <div className="camera-frame">
              <video ref={video} autoPlay muted playsInline aria-label="Live camera preview" />
              <canvas ref={faceOverlay} className="face-mesh" aria-hidden="true" />
              {!cameraReady && <div className="camera-placeholder" role="status">
                <span className="camera-placeholder-icon" aria-hidden="true">◉</span>
                <strong>{cameraIssue || 'Camera preview is off'}</strong>
                <span>{cameraIssue ? 'Check browser site permission or choose another camera, then reconnect.' : 'Select Enable laptop camera to start the live preview.'}</span>
              </div>}
              {scanning && scanDirection !== null && <span className={`scan-arrow ${scanDirection > 0 ? 'left' : 'right'}`} aria-hidden="true">{scanDirectionLabel(scanDirection)}</span>}
              <span className={`camera-badge ${cameraReady ? 'on' : ''}`}>{cameraReady ? '● CAMERA LIVE' : 'CAMERA OFF'}</span>
            </div>
            {cameraReady && <p className={`face-detection ${faceCount === 1 && modelReady ? 'detected' : ''}`} role="status">
              {modelError || (!modelReady ? 'Loading the local face guide…' : faceCount === 1 ? '● Face detected · live mesh active' : faceCount > 1 ? 'More than one face detected · only one person can scan' : 'Searching for one clear face…')}
            </p>}
            {videoDevices.length > 1 && <label className="camera-select">Camera
              <select value={selectedDeviceId} disabled={busy} onChange={(event) => {
                const nextDevice = event.target.value;
                setSelectedDeviceId(nextDevice);
                void enableCamera(nextDevice);
              }}>
                {videoDevices.map((device, index) => <option key={device.deviceId} value={device.deviceId}>
                  {device.label || `Camera ${index + 1}`}
                </option>)}
              </select>
            </label>}
            <button className="secondary" onClick={() => enableCamera()} disabled={busy}>{cameraReady ? 'Reconnect camera' : 'Enable laptop camera'}</button>
            {mode === 'Enroll' && <label className="check"><input type="checkbox" disabled={busy} checked={consent} onChange={(event) => setConsent(event.target.checked)} /> I consent to biometric processing for this demo.</label>}
            <button className="primary" disabled={!cameraReady || !modelReady || busy} onClick={() => captureAndSend(mode === 'Enroll' ? 'enroll' : 'auth')}>
              {scanning ? 'Following face movement…' : mode === 'Enroll' ? 'Register this face' : 'Unlock with face'}
            </button>
          </>}
          {mode === 'Dashboard' && <>
            <p className="muted">Add a device passkey for future sign-ins. Windows Hello checks you locally, and the app stores only the passkey public key. The session expires after a short period.</p>
            <button className="secondary" disabled={!token || busy} onClick={registerPasskey}>
              {busy ? 'Waiting for Windows Hello…' : passkeyReady ? 'Add another device passkey' : 'Set up Windows Hello / passkey'}
            </button>
            <button className="primary" disabled={!token} onClick={openVault}>Open protected workspace</button>
            <div className="vault-list">{vault.map((record) => <article className="vault-card" key={record.id}>
              <small>{record.classification}</small><h3>{record.title}</h3><p>{record.summary}</p>
            </article>)}</div>
            <button className="primary" disabled={!token} onClick={loadHistory}>Load audit history</button>
            <pre>{JSON.stringify(history, null, 2)}</pre>
            {token && <button className="secondary" onClick={() => { setToken(''); setHistory([]); setVault([]); setStatus('Signed out.'); }}>Sign out</button>}
          </>}
        </>}
        <p className="status" role="status" aria-live="polite">{status}</p>
      </div>
      <aside className="trust-panel">
        <div className="trust-icon" aria-hidden="true"><svg viewBox="0 0 24 24" fill="none"><path d="M12 3 20 6v5.4c0 5.2-3.4 8.5-8 10.6-4.6-2.1-8-5.4-8-10.6V6l8-3Z"/><path d="m8.5 12 2.2 2.2 4.8-5"/></svg></div>
        <small>SECURITY AT A GLANCE</small><h3>Private by design.</h3>
        <p>Passkeys let your device verify you locally. The server receives a signed proof, never your Windows Hello face or fingerprint.</p>
        <ul><li><span>01</span> Biometric stays on your device</li><li><span>02</span> Server stores a public passkey</li><li><span>03</span> Webcam frames are not retained</li></ul>
        <div className="trust-note"><i /> Webcam face matching is a prototype fallback, not production-grade face unlock.</div>
        <p className="risk-note">Company directory verification, recovery controls, and a security review are still needed before protecting sensitive company data.</p>
      </aside>
    </section>
    <footer className="app-footer"><span>The webcam is used only during enrollment or when you choose the fallback. Device passkey biometrics stay local.</span><span>RESEARCH PROTOTYPE · NOT PRODUCTION ASSURANCE</span></footer>
  </main>
  <div className={`boot-screen ${booting ? 'boot-screen-visible' : 'boot-screen-leaving'}`} aria-hidden={!booting}>
    <div className="boot-shell">
      <div className="boot-topline"><span><b>Q</b> QUANTUM FACE AUTH</span><span>LOCAL ACCESS SYSTEM <i /></span></div>
      <div className="boot-layout">
        <div className="boot-scan-card">
          <div className="boot-card-head"><span><i /> IDENTITY SCAN</span><span>MESH PREVIEW</span></div>
          <div className="boot-face-stage" aria-hidden="true">
            <span className="boot-face-orbit orbit-a" /><span className="boot-face-orbit orbit-b" />
            <svg viewBox="0 0 300 340" role="presentation">
              <defs>
                <linearGradient id="meshStroke" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#a8f2da" /><stop offset="1" stopColor="#62bdab" /></linearGradient>
                <radialGradient id="meshFill"><stop offset="0" stopColor="#58bea0" stopOpacity=".17" /><stop offset="1" stopColor="#58bea0" stopOpacity="0" /></radialGradient>
              </defs>
              <ellipse className="face-halo" cx="150" cy="166" rx="111" ry="145" fill="url(#meshFill)" />
              <path className="face-outline" d="M150 32 C91 32 65 75 68 133 C70 207 101 273 150 295 C199 273 230 207 232 133 C235 75 209 32 150 32Z" />
              <g className="face-lines">
                <path d="M69 126 Q108 91 150 105 Q192 91 231 126 M76 153 Q111 139 143 154 Q175 139 224 153 M83 180 Q114 166 145 181 Q177 166 217 180 M91 207 Q121 194 150 210 Q179 194 209 207 M103 232 Q128 221 150 235 Q172 221 197 232 M111 81 Q133 91 150 104 Q167 91 189 81 M101 104 L111 139 L114 167 L121 195 L128 222 M199 104 L189 139 L186 167 L179 195 L172 222 M150 105 L145 154 L150 181 L150 210 L150 235 M92 127 L117 139 L145 154 L177 139 L209 127 M83 180 L114 167 L150 181 L186 167 L217 180 M91 207 L121 195 L150 210 L179 195 L209 207" />
                <path className="face-eye" d="M92 135 Q112 119 134 137 Q114 151 92 135Z M166 137 Q188 119 208 135 Q186 151 166 137Z M137 253 Q150 260 163 253" />
              </g>
              <g className="face-dots">
                {[[150,32],[115,39],[185,39],[91,58],[209,58],[73,91],[227,91],[68,133],[232,133],[76,153],[224,153],[83,180],[217,180],[91,207],[209,207],[103,232],[197,232],[121,263],[179,263],[150,295],[92,127],[117,139],[134,137],[166,137],[188,119],[208,135],[145,154],[150,181],[150,210],[150,235],[128,222],[172,222],[111,139],[189,139]].map(([cx, cy], index) => <circle key={index} cx={cx} cy={cy} r={index % 4 === 0 ? 2.5 : 1.6} />)}
              </g>
            </svg>
            <span className="boot-scan-beam" />
            <span className="boot-corner corner-tl" /><span className="boot-corner corner-tr" />
            <span className="boot-corner corner-bl" /><span className="boot-corner corner-br" />
          </div>
          <div className="boot-card-foot"><span><i /> MESH ENGINE</span><span>INITIALIZING</span></div>
        </div>
        <div className="boot-copy">
          <span className="boot-eyebrow"><i /> PRIVATE IDENTITY PLATFORM</span>
          <h1>Welcome to<br /><em>Identity Access.</em></h1>
          <p>Your sign-in workspace is being prepared.</p>
          <div className="boot-progress-block">
            <div className="boot-progress-label"><span>Loading experience</span><span className="boot-progress-value">PLEASE WAIT</span></div>
            <div className="boot-progress"><span /></div>
          </div>
          <div className="boot-features"><span><b>01</b> Face mesh</span><span><b>02</b> Device verification</span><span><b>03</b> Private session</span></div>
        </div>
      </div>
      <div className="boot-bottomline"><span>SECURE ACCESS · RESEARCH DEMO</span><span>PROTECTED BY DESIGN <i /></span></div>
    </div>
  </div>
  </>;
}
