#FROM ubuntu:16.04
#FROM matthewfeickert/docker-python3-ubuntu:latest
FROM python:3.7-alpine3.8

#RUN sudo apt-get update -y && \
#    sudo apt-get install  -y  python-dev
RUN python3 --version

# We copy just the requirements.txt first to leverage Docker cache
COPY ./requirements.txt /app/requirements.txt

WORKDIR /app

RUN env
RUN pip3 install --proxy="http://172.25.20.117:80" Flask

RUN pip3 install --proxy="http://172.25.20.117:80" --upgrade pip 
#RUN pip3 install --proxy="http://172.25.20.117:80" pybase64
RUN pip3 install --proxy="http://172.25.20.117:80" -r requirements.txt


COPY ./app /app

WORKDIR /app

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "wsgi:warden", "--certfile", "certs/tls.crt", "--keyfile", "certs/tls.key" ]
