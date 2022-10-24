FROM python:3-slim-buster

RUN apt update -y
RUN apt install tzdata

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY static/ static/
COPY templates/ templates/
COPY app.py .
COPY nhltv.py .

CMD flask run --host 0.0.0.0 --port 80
