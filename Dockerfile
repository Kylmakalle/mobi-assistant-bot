FROM python:3.6

RUN mkdir -p /opt/app
WORKDIR /opt/app
COPY . /opt/app/
RUN pip install -r requirements.txt
