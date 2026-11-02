import { cp, mkdir, rm, rename, stat, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = resolve(dirname(fileURLToPath(import.meta.url)), '..');
const source = resolve(root, 'node_modules/@mediapipe/tasks-vision/wasm');
const destination = resolve(root, 'public/mediapipe/wasm');
const model = resolve(root, 'public/models/face_landmarker.task');
const modelUrl = 'https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task';

try {
  const info = await stat(model);
  if (info.size < 1_000_000) throw new Error('Face Landmarker model file is incomplete.');
} catch (error) {
  if (error.code !== 'ENOENT') throw error;
  await mkdir(resolve(root, 'public/models'), { recursive: true });
  const response = await fetch(modelUrl);
  if (!response.ok) throw new Error(`Could not download Face Landmarker model: HTTP ${response.status}`);
  const bytes = Buffer.from(await response.arrayBuffer());
  if (bytes.length < 1_000_000) throw new Error('Downloaded Face Landmarker model is incomplete.');
  const temporaryModel = `${model}.download`;
  await writeFile(temporaryModel, bytes);
  await rename(temporaryModel, model);
  console.log('Downloaded MediaPipe Face Landmarker model.');
}

await mkdir(dirname(destination), { recursive: true });
await rm(destination, { recursive: true, force: true });
await cp(source, destination, { recursive: true });
