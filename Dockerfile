# ── Build stage ─────────────────────────────────────────────────────────────
# Full Swift toolchain on Ubuntu 22.04 (jammy). This is where the Linux build of
# the engine actually gets exercised — any Linux-only compile error surfaces here.
FROM swift:6.1-jammy AS build
WORKDIR /build

# Resolve dependencies first so this layer caches across source-only changes.
COPY Package.swift ./
COPY Package.resolved ./
RUN swift package resolve

# Build the server, statically linking the Swift stdlib so the runtime image
# doesn't need the full toolchain.
COPY Sources ./Sources
COPY Tests ./Tests
RUN swift build -c release --product SectorEngineServer \
      -Xswiftc -static-stdlib \
    || swift build -c release --product SectorEngineServer
# The hourly job that prepares each lake's Current Clarity world runs from the
# same image (Clarity Fusion Stage 5).
RUN swift build -c release --product ClarityPrecompute \
      -Xswiftc -static-stdlib \
    || swift build -c release --product ClarityPrecompute
RUN cp "$(swift build -c release --show-bin-path)/SectorEngineServer" /build/SectorEngineServer \
    && cp "$(swift build -c release --show-bin-path)/ClarityPrecompute" /build/ClarityPrecompute

# ── Runtime stage ───────────────────────────────────────────────────────────
# Slim image: Swift runtime libraries, no compiler. Add TLS roots + timezone data
# so HTTPS fetches (Open-Meteo, USGS, TVA…) and date math work.
FROM swift:6.1-jammy-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /build/SectorEngineServer /app/SectorEngineServer
COPY --from=build /build/ClarityPrecompute /app/ClarityPrecompute

# Cloud Run sets PORT; the server reads it and binds 0.0.0.0.
ENV PORT=8080
EXPOSE 8080
CMD ["/app/SectorEngineServer"]
