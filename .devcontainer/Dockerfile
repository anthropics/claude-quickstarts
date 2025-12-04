# Dev Container Dockerfile
# Includes additional development tools and non-root user

FROM python:3.14-slim

# Avoid prompts from apt
ENV DEBIAN_FRONTEND=noninteractive

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    curl \
    sudo \
    bash \
    zsh \
    vim \
    nano \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
ARG USERNAME=vscode
ARG USER_UID=1000
ARG USER_GID=$USER_UID

RUN groupadd --gid $USER_GID $USERNAME \
    && useradd --uid $USER_UID --gid $USER_GID -m $USERNAME \
    && echo $USERNAME ALL=\(root\) NOPASSWD:ALL > /etc/sudoers.d/$USERNAME \
    && chmod 0440 /etc/sudoers.d/$USERNAME

# Set working directory
WORKDIR /workspaces/claude-quickstarts

# Install Python development tools
RUN pip install --no-cache-dir \
    pytest \
    pytest-asyncio \
    ruff \
    mypy \
    ipython \
    jupyter

# Switch to non-root user
USER $USERNAME

# Set shell to zsh (matches your local environment)
ENV SHELL=/bin/zsh

# Default command
CMD ["sleep", "infinity"]
