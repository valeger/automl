FROM python:3.7-slim
RUN apt -y update &&\
    apt-get install -y git &&\
    apt -y install build-essential &&\
    apt-get clean &&\
    pip install -U pip
RUN git config --global user.email "automl@gmail.com" &&\
    git config --global user.name "automl"
WORKDIR /home/app