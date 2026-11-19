FROM python:3.12-slim

WORKDIR /srv
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 MODEL_PATH=/srv/models/model.joblib

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY ddx ./ddx
COPY app ./app
# Mô hình được train trước trên máy (scripts/train.py) rồi mới build image
COPY models/model.joblib ./models/model.joblib

RUN useradd --create-home ml && chown -R ml /srv
USER ml
EXPOSE 8000
HEALTHCHECK --interval=30s --timeout=3s --retries=3 \
  CMD python -c "import urllib.request,json,sys; r=json.load(urllib.request.urlopen('http://localhost:8000/health')); sys.exit(r['status']!='UP')"
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
