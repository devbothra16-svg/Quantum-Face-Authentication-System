import { useEffect, useRef, useState, type RefObject } from 'react';
import { FaceLandmarker, FilesetResolver } from '@mediapipe/tasks-vision';

export type FaceReading = {
  faceCount: number;
  pose: number | null;
  capturedAt: number;
};

export function useFaceMesh(
  videoRef: RefObject<HTMLVideoElement | null>,
  overlayRef: RefObject<HTMLCanvasElement | null>,
  enabled: boolean,
) {
  const readingRef = useRef<FaceReading>({ faceCount: 0, pose: null, capturedAt: 0 });
  const [faceCount, setFaceCount] = useState(0);
  const [modelReady, setModelReady] = useState(false);
  const [modelError, setModelError] = useState('');

  useEffect(() => {
    if (!enabled) {
      readingRef.current = { faceCount: 0, pose: null, capturedAt: 0 };
      setFaceCount(0);
      setModelReady(false);
      return;
    }

    let cancelled = false;
    let frameRequest = 0;
    let lastVideoTime = -1;
    let lastDetectionAt = 0;
    let lastStatusAt = 0;
    let landmarker: FaceLandmarker | undefined;

    const clearOverlay = () => {
      const canvas = overlayRef.current;
      const context = canvas?.getContext('2d');
      if (canvas && context) context.clearRect(0, 0, canvas.width, canvas.height);
    };

    const drawMesh = (landmarks: { x: number; y: number }[]) => {
      const canvas = overlayRef.current;
      const video = videoRef.current;
      const context = canvas?.getContext('2d');
      if (!canvas || !video || !context) return;

      const bounds = canvas.getBoundingClientRect();
      const pixelRatio = window.devicePixelRatio || 1;
      const width = Math.max(1, bounds.width);
      const height = Math.max(1, bounds.height);
      const bitmapWidth = Math.round(width * pixelRatio);
      const bitmapHeight = Math.round(height * pixelRatio);
      if (canvas.width !== bitmapWidth || canvas.height !== bitmapHeight) {
        canvas.width = bitmapWidth;
        canvas.height = bitmapHeight;
      }

      context.setTransform(pixelRatio, 0, 0, pixelRatio, 0, 0);
      context.clearRect(0, 0, width, height);
      const scale = Math.max(width / video.videoWidth, height / video.videoHeight);
      const drawnWidth = video.videoWidth * scale;
      const drawnHeight = video.videoHeight * scale;
      const offsetX = (width - drawnWidth) / 2;
      const offsetY = (height - drawnHeight) / 2;
      const point = (index: number) => {
        const landmark = landmarks[index];
        return landmark
          ? [offsetX + landmark.x * drawnWidth, offsetY + landmark.y * drawnHeight] as const
          : null;
      };

      context.beginPath();
      context.strokeStyle = 'rgba(129, 239, 207, 0.57)';
      context.lineWidth = 0.7;
      for (const connection of FaceLandmarker.FACE_LANDMARKS_TESSELATION) {
        const start = point(connection.start);
        const end = point(connection.end);
        if (!start || !end) continue;
        context.moveTo(start[0], start[1]);
        context.lineTo(end[0], end[1]);
      }
      context.stroke();

      context.fillStyle = 'rgba(207, 255, 241, 0.9)';
      for (let index = 0; index < landmarks.length; index += 1) {
        const position = point(index);
        if (!position) continue;
        context.beginPath();
        context.arc(position[0], position[1], 1.1, 0, Math.PI * 2);
        context.fill();
      }
    };

    const processVideo = () => {
      if (cancelled) return;
      frameRequest = requestAnimationFrame(processVideo);
      const video = videoRef.current;
      if (!landmarker || !video || video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA
        || !video.videoWidth || !video.videoHeight) return;
      const now = performance.now();
      if (video.currentTime === lastVideoTime || now - lastDetectionAt < 80) return;
      lastVideoTime = video.currentTime;
      lastDetectionAt = now;

      try {
        const result = landmarker.detectForVideo(video, now);
        const faces = result.faceLandmarks || [];
        const onlyFace = faces.length === 1 ? faces[0] : null;
        const nose = onlyFace?.[1];
        const eyeA = onlyFace?.[33];
        const eyeB = onlyFace?.[263];
        const eyeSpan = eyeA && eyeB ? Math.abs(eyeB.x - eyeA.x) : 0;
        const pose = nose && eyeA && eyeB && eyeSpan > 0.01
          ? (nose.x - Math.min(eyeA.x, eyeB.x)) / eyeSpan
          : null;

        readingRef.current = {
          faceCount: faces.length,
          pose: pose !== null && Number.isFinite(pose) ? pose : null,
          capturedAt: now,
        };
        if (onlyFace) drawMesh(onlyFace);
        else clearOverlay();
        if (now - lastStatusAt > 250) {
          setFaceCount(faces.length);
          lastStatusAt = now;
        }
      } catch {
        readingRef.current = { faceCount: 0, pose: null, capturedAt: now };
        clearOverlay();
      }
    };

    const loadLandmarker = async () => {
      try {
        const files = await FilesetResolver.forVisionTasks('/mediapipe/wasm');
        const instance = await FaceLandmarker.createFromOptions(files, {
          baseOptions: { modelAssetPath: '/models/face_landmarker.task' },
          runningMode: 'VIDEO',
          numFaces: 2,
          minFaceDetectionConfidence: 0.55,
          minFacePresenceConfidence: 0.5,
          minTrackingConfidence: 0.5,
        });
        if (cancelled) {
          instance.close();
          return;
        }
        landmarker = instance;
        setModelReady(true);
        setModelError('');
        frameRequest = requestAnimationFrame(processVideo);
      } catch {
        if (!cancelled) {
          setModelReady(false);
          setModelError('Face guide could not start. Reload the app and check the local model files.');
        }
      }
    };

    void loadLandmarker();
    return () => {
      cancelled = true;
      cancelAnimationFrame(frameRequest);
      landmarker?.close();
      clearOverlay();
    };
  }, [enabled, overlayRef, videoRef]);

  return { faceCount, modelReady, modelError, readingRef };
}
