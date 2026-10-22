# SolidCraft MCP lab (fillet + shell): the pinned Linux release asset, checked against the release's
# SHA256SUMS.txt. No Rust compile. Pinned: 0.17.0 (the release the maintainers call current, 20 Oct 2026).
# Build another version for the smoke check with --build-arg SC_VER=0.18.1 (or 0.16.2).
FROM ubuntu:24.04
ARG SC_VER=0.17.0
ARG SC_ASSET=solidcraft-${SC_VER}-linux-x86_64.tar.gz
ARG SC_BASE=https://github.com/tangency-labs/solidcraft/releases/download/v${SC_VER}
ENV DEBIAN_FRONTEND=noninteractive
# mesa-vulkan-drivers + libvulkan1: llvmpipe, a software Vulkan device, so headless screenshots use
# the viewport's own pipelines ("gpu-software").
RUN apt-get update \
 && apt-get install -y --no-install-recommends ca-certificates curl \
      mesa-vulkan-drivers libvulkan1 python3 python3-pytest python3-numpy \
 && rm -rf /var/lib/apt/lists/*
WORKDIR /tmp/dl
RUN curl -fsSLO "$SC_BASE/$SC_ASSET" \
 && curl -fsSLO "$SC_BASE/SHA256SUMS.txt" \
 && grep " $SC_ASSET\$" SHA256SUMS.txt > check.txt \
 && test "$(wc -l < check.txt)" = 1 \
 && sha256sum -c check.txt \
 && mkdir -p /opt/solidcraft \
 && tar -xzf "$SC_ASSET" -C /opt/solidcraft --strip-components=1 \
 && cp SHA256SUMS.txt check.txt /opt/solidcraft/ \
 && cd / && rm -rf /tmp/dl
ENV PATH=/opt/solidcraft/bin:$PATH
RUN mkdir -p /lab/out /lab/forbidden
WORKDIR /work
