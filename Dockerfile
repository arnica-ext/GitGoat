# For more information, please refer to https://aka.ms/vscode-docker-python
FROM python:3.9-slim-buster

ARG github_token
ENV github_token=${github_token}

ARG config_file="config.yaml"
ARG org_names=[]

# Install Git Client
RUN apt-get -y update
RUN apt-get -y install git

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip requirements
COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

WORKDIR /app
COPY . /app

# Creates a non-root user with an explicit UID and adds permission to access the /app folder
# For more info, please refer to https://aka.ms/vscode-docker-python-configure-containers
RUN adduser -u 5678 --disabled-password --gecos "" appuser && chown -R appuser /app
USER appuser

# During debugging, this entry point will be overridden. For more information, please refer to https://aka.ms/vscode-docker-python-debug
CMD python3 run.py --config ${config_file} --org ${org_names}
