FROM python:3.10-bullseye AS producer
COPY . /app
WORKDIR /app
RUN apt update # && apt install iputils-ping
RUN pip install -r requirements.txt
ENTRYPOINT ["python","producer.py"]


FROM python:3.10-bullseye AS consumer
COPY . /app
WORKDIR /app
RUN apt update # && apt install iputils-ping
RUN pip install -r requirements.txt
ENTRYPOINT ["python","consumer.py"]

FROM python:3.10-bullseye AS flaskapi
COPY . /app
WORKDIR /app
RUN apt update # && apt install iputils-ping
RUN pip install -r requirements.txt
ENTRYPOINT ["python","flaskapi.py"]
