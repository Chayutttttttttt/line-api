FROM python:3.12.7-slim

ENV PYTHONUNBUFFERED True

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Catch Python import/syntax regressions and test the PDF reader without API calls.
RUN python -m compileall -q agent components db worker tests
RUN python -m unittest discover -s tests -p 'test_pdf_ai_ingest.py' -v

CMD ["sh", "-c", "python -m db.migrate && exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
