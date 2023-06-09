FROM python:3.8

EXPOSE 8000

# Keeps Python from generating .pyc files in the container.
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements.
COPY requirements.txt .

RUN python -m pip install -r requirements.txt

WORKDIR /app
COPY . /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder.
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

ENV FLASK_APP=app.py
# Provides defaults for an executing container; can be overridden with Docker CLI.
# CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:app"]
CMD ["gunicorn", "--bind",  "0.0.0.0:8000", "--workers=2", "app:app"]
