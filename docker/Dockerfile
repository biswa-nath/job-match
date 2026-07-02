FROM public.ecr.aws/lambda/python:3.12

# Lambda task root — defined by the base image at runtime, declared here
# explicitly so Docker build instructions can reference it reliably.
ENV LAMBDA_TASK_ROOT=/var/task

# Playwright Chromium dependencies for Amazon Linux 2023.
# Listed manually because `playwright install-deps` does not recognise AL2023
# and falls back to apt-get, which is not available here.
RUN dnf install -y \
        alsa-lib \
        at-spi2-atk \
        at-spi2-core \
        atk \
        cups-libs \
        dbus-glib \
        gtk3 \
        libX11 \
        libXcomposite \
        libXdamage \
        libXext \
        libXfixes \
        libXi \
        libXrandr \
        libXScrnSaver \
        libXtst \
        libXt \
        libxcb \
        libxkbcommon \
        libdrm \
        mesa-libgbm \
        nss \
        nspr \
        pango \
    && dnf clean all

# Install uv for dependency resolution
RUN pip install uv

# Copy dependency manifests first to maximise Docker layer cache reuse.
# Dependencies are only reinstalled when pyproject.toml or uv.lock changes.
COPY pyproject.toml uv.lock ${LAMBDA_TASK_ROOT}/
WORKDIR ${LAMBDA_TASK_ROOT}

# Export pinned requirements from the lockfile (excluding the project package
# itself — its source is copied directly below) and install with pip.
RUN uv export --frozen --no-dev --no-emit-project -o /tmp/requirements.txt \
    && pip install -r /tmp/requirements.txt

# Download Playwright Chromium binary. Dependencies are installed via dnf above;
# install-deps is intentionally omitted — it does not support AL2023.
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN playwright install chromium

# Copy application source. Contents of src/ land directly in LAMBDA_TASK_ROOT
# so Python finds browser/, db/, main.py, lambda_handler.py, etc. without
# any sys.path manipulation.
COPY src/ ${LAMBDA_TASK_ROOT}/

CMD ["lambda_handler.handler"]
