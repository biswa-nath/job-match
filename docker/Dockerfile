FROM ubuntu:24.04

ENV DEBIAN_FRONTEND=noninteractive \
    LAMBDA_TASK_ROOT=/var/task \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright \
    VIRTUAL_ENV=/opt/venv \
    PATH=/opt/venv/bin:$PATH

# Python 3.14 from the deadsnakes PPA, installed into an isolated virtualenv.
# The venv ignores Debian's /usr/lib/python3/dist-packages, which avoids pip
# failing to uninstall apt-managed packages (e.g. pyparsing, no RECORD file).
# uv and the Lambda Runtime Interface Client are installed here so they land in
# an early, stable layer. All apt state is purged in the same RUN.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        software-properties-common ca-certificates curl libatomic1 \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        python3.14 python3.14-dev python3.14-venv \
    && python3.14 -m venv /opt/venv \
    && pip install --no-cache-dir uv awslambdaric \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /root/.cache

COPY pyproject.toml uv.lock scripts/ensure-models.sh ${LAMBDA_TASK_ROOT}/
WORKDIR ${LAMBDA_TASK_ROOT}

# Download the spaCy model wheel, install all Python dependencies, then remove
# every cache and intermediate file in the same layer.
RUN mkdir -p wheels \
    && mv ensure-models.sh wheels/ \
    && cd wheels && /bin/bash ensure-models.sh && cd .. \
    && uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
    && pip install --no-cache-dir -r /tmp/requirements.txt \
    && rm -rf /tmp/requirements.txt wheels /root/.cache

# playwright install --with-deps handles all Chromium system-library deps via
# apt automatically on Ubuntu/Debian, replacing the manual dnf list.
RUN playwright install --with-deps chromium \
    && apt-get clean && rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

COPY src/ ${LAMBDA_TASK_ROOT}/

ENTRYPOINT ["/opt/venv/bin/python", "-m", "awslambdaric"]
CMD ["lambda_handler.handler"]
