# syntax=docker/dockerfile:1.7
FROM python:3.11-slim
WORKDIR /srv
RUN apt-get update && apt-get install -y --no-install-recommends libgl1 libgomp1 && rm -rf /var/lib/apt/lists/*
RUN mkdir -p /models && python -c "import urllib.request,hashlib; files=[('https://huggingface.co/opencv/face_detection_yunet/resolve/b373a5f/face_detection_yunet_2023mar.onnx','/models/face_detection_yunet_2023mar.onnx','8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4'),('https://huggingface.co/opencv/face_recognition_sface/resolve/89e1f6f/face_recognition_sface_2021dec.onnx','/models/face_recognition_sface_2021dec.onnx','0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79')]; [(urllib.request.urlretrieve(url,path),None) for url,path,digest in files]; assert all(hashlib.sha256(open(path,'rb').read()).hexdigest()==digest for url,path,digest in files), 'Face model checksum mismatch'"
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    python -c "import subprocess,sys,tomllib; deps=tomllib.load(open('pyproject.toml','rb'))['project']['dependencies']; subprocess.check_call([sys.executable,'-m','pip','install','--retries','8','--timeout','600','setuptools>=68','wheel',*deps])"
COPY backend ./backend
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install --no-deps --no-build-isolation .
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
