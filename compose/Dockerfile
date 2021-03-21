FROM python:3.8-slim-buster

ENV DEBIAN_FRONTEND noninteractive
ENV PYTHONIOENCODING UTF-8
ENV TERRAFORM_VERSION 0.13.6

WORKDIR /app/

RUN apt-get -y -qq update
RUN apt-get install -y -qq curl unzip make wget vim nano watch\
    git tmate locales-all openssh-client gnupg2 lsb-release > /dev/null

# Install terraform
RUN curl --silent --location https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip --output terraform.zip
RUN unzip terraform.zip && \
    mv terraform /usr/local/bin/ && \
    rm terraform.zip

ADD ./compose/requirements.txt .
RUN pip install -r /app/requirements.txt

# User sem permissão
RUN useradd -ms /bin/bash nonrootuser
RUN usermod -aG sudo nonrootuser


ADD ./compose/docker-entrypoint.sh /app/compose/docker-entrypoint.sh
RUN chmod +x /app/compose/docker-entrypoint.sh

# USER nonrootuser
ENTRYPOINT ["/app/compose/docker-entrypoint.sh"]
