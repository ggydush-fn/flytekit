FROM python:3.8-slim-buster

WORKDIR /app
ENV VENV /opt/venv
ENV LANG C.UTF-8
ENV LC_ALL C.UTF-8
ENV PYTHONPATH /app
ENV FLYTE_SDK_USE_STRUCTURED_DATASET TRUE

RUN pip install awscli
RUN pip install gsutil

# Virtual environment
RUN python3.8 -m venv ${VENV}
RUN ${VENV}/bin/pip install wheel

RUN ${VENV}/bin/pip install flytekit sqlalchemy

# Copy over the helper script that the SDK relies on
RUN cp ${VENV}/bin/flytekit_venv /usr/local/bin
RUN chmod a+x /usr/local/bin/flytekit_venv

# Enable the virtualenv for this image. Note this relies on the VENV variable we've set in this image.
ENTRYPOINT ["/usr/local/bin/flytekit_venv"]
