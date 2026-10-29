FROM python:3.12.7-slim

ENV PYTHONUNBUFFERED True

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Check Python syntax during the image build.
RUN python -m compileall -q agent components db worker

CMD ["sh", "-c", "python -m db.migrate && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
