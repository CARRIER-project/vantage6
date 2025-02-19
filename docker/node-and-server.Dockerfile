# Dockerfile for the node an server images
#
# IMAGES
# ------
# * harbor2.vantage6.ai/infrastructure/node:x.x.x
# * harbor2.vantage6.ai/infrastructure/server:x.x.x
#
ARG TAG=latest
ARG BASE=3
FROM harbor2.vantage6.ai/infrastructure/infrastructure-base:${BASE}

LABEL version=${TAG}
LABEL maintainer="Frank Martin <f.martin@iknl.nl>"

# Enable SSH access in Azure App service
RUN apt update -y
RUN apt upgrade -y

RUN apt install openssh-server sudo -y
RUN useradd -rm -d /home/ubuntu -s /bin/bash -g root -G sudo -u 1000 test
RUN  echo 'root:Docker!' | chpasswd

COPY sshd_config /etc/ssh/
RUN mkdir /run/sshd

# Fix DB issue
RUN apt install python-psycopg2 -y
RUN pip install psycopg2-binary

# copy source
COPY . /vantage6

# Install requirements. We cannot rely on setup.py because of the way
# python resolves package versions. To control all dependencies we install
# them from the requirements.txt
# This is also done in the base-image to safe build time. We redo it here
# to allow for dependency upgrades in minor and patch versions.
RUN pip install -r /vantage6/requirements.txt \
    --extra-index-url https://www.piwheels.org/simple

# install individual packages
RUN pip install -e /vantage6/vantage6-common
RUN pip install -e /vantage6/vantage6-client
RUN pip install -e /vantage6/vantage6
RUN pip install -e /vantage6/vantage6-node
RUN pip install -e /vantage6/vantage6-server

# Overwrite uWSGI installation from the requirements.txt
# Install uWSGI from source (for RabbitMQ)
RUN apt-get install --no-install-recommends --no-install-suggests -y \
  libssl-dev python3-setuptools
RUN CFLAGS="-I/usr/local/opt/openssl/include" \
  LDFLAGS="-L/usr/local/opt/openssl/lib" \
  UWSGI_PROFILE_OVERRIDE=ssl=true \
  pip install uwsgi -Iv

RUN chmod +x /vantage6/configs/server.sh

# expose the proxy server port
ARG port=80
EXPOSE ${port} 2222
ENV PROXY_SERVER_PORT ${port}
