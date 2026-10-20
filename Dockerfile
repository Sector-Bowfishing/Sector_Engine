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
# Swift Brain runtimes live in their canonical Brain packages (Package.swift targets LakeBrain / WaterTemperatureBrain and their jobs).
# Only the Swift target directories are copied; SwiftPM needs every declared target path, including the test targets, to exist.
COPY brains/lake/runtime/LakeBrain ./brains/lake/runtime/LakeBrain
COPY brains/lake/runtime/LakeBrainJob ./brains/lake/runtime/LakeBrainJob
COPY brains/lake/tests/swift ./brains/lake/tests/swift
COPY brains/water-temperature/runtime/WaterTemperatureBrain ./brains/water-temperature/runtime/WaterTemperatureBrain
COPY brains/water-temperature/runtime/WaterTempBrainJob ./brains/water-temperature/runtime/WaterTempBrainJob
COPY brains/water-temperature/tests/swift ./brains/water-temperature/tests/swift
RUN swift build -c release --product SectorEngineServer \
      -Xswiftc -static-stdlib \
    || swift build -c release --product SectorEngineServer
RUN cp "$(swift build -c release --show-bin-path)/SectorEngineServer" /build/SectorEngineServer
# The Water Temperature Brain job (Sector Brain Platform) runs from the same image (the brain-jobs image, jobs/brain-image-build.sh):
# brains/water-temperature/deploy/deploy-job.sh deploys the Cloud Run job. Nothing in the request path imports the Brain targets.
RUN swift build -c release --product WaterTempBrainJob \
      -Xswiftc -static-stdlib \
    || swift build -c release --product WaterTempBrainJob
RUN cp "$(swift build -c release --show-bin-path)/WaterTempBrainJob" /build/WaterTempBrainJob
# The Lake Brain job (pilot lakes; started by brain-orchestrator when due): brains/lake/deploy/deploy-job.sh.
RUN swift build -c release --product LakeBrainJob \
      -Xswiftc -static-stdlib \
    || swift build -c release --product LakeBrainJob
RUN cp "$(swift build -c release --show-bin-path)/LakeBrainJob" /build/LakeBrainJob
# The hourly job that prepares each lake's Current Clarity world runs from the
# same image (Clarity Fusion Stage 5).
RUN swift build -c release --product ClarityPrecompute \
      -Xswiftc -static-stdlib \
    || swift build -c release --product ClarityPrecompute
RUN cp "$(swift build -c release --show-bin-path)/ClarityPrecompute" /build/ClarityPrecompute

# ── Runtime stage ───────────────────────────────────────────────────────────
# Slim image: Swift runtime libraries, no compiler. Add TLS roots + timezone data
# so HTTPS fetches (Open-Meteo, USGS, TVA…) and date math work.
FROM swift:6.1-jammy-slim
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates tzdata \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY --from=build /build/SectorEngineServer /app/SectorEngineServer
COPY --from=build /build/WaterTempBrainJob /app/WaterTempBrainJob
COPY --from=build /build/LakeBrainJob /app/LakeBrainJob
COPY --from=build /build/ClarityPrecompute /app/ClarityPrecompute

# Cloud Run sets PORT; the server reads it and binds 0.0.0.0.
ENV PORT=8080
EXPOSE 8080
CMD ["/app/SectorEngineServer"]
