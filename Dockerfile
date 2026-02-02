FROM python:3.12-slim

COPY ./ /app
WORKDIR /app

RUN pip3 install -r requirements.txt

CMD uvicorn main:app --host 0.0.0.0 --port 5000
