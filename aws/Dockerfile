FROM python:3.14.3-slim@sha256:486b8092bfb12997e10d4920897213a06563449c951c5506c2a2cfaf591c599f
COPY --from=docker.io/astral/uv:python3.13-alpine@sha256:8da29d4ddc9e3fd77c32d0ba090620e2cf11263c81f98a6b5e918508a055c273 /usr/local/bin/uv /usr/local/bin/uvx /usr/local/bin/

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl \
        git \
        less \
        mandoc \
        nodejs \
        npm \
        unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && rm awscliv2.zip \
    && ./aws/install \
    && rm -rf aws \
    && curl -L "https://github.com/aws/aws-sam-cli/releases/latest/download/aws-sam-cli-linux-x86_64.zip" -o "aws-sam-cli-linux-x86_64.zip" \
    && unzip aws-sam-cli-linux-x86_64.zip -d sam-installation \
    && ./sam-installation/install \
    && rm -rf sam-installation aws-sam-cli-linux-x86_64.zip \
    && npm install -g aws-cdk

RUN useradd --create-home user
WORKDIR /home/user
USER user

COPY --chown=user:user . .
RUN cd gastown && uv sync --frozen
