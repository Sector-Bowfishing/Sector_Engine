// swift-tools-version: 6.0
import PackageDescription

let package = Package(
    name: "SectorEngine",
    // Swift 6 language mode: data races between concurrent renders are COMPILE
    // ERRORS, not latent crashes. The 2026-09-14 audit found unsynchronized
    // adapter caches that Swift 5 mode silently allowed (prod logged SIGSEGVs).
    // Don't drop this to .v5 to get a build through — fix the isolation.
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "SectorEngine", targets: ["SectorEngine"]),
        .executable(name: "SectorEngineServer", targets: ["SectorEngineServer"]),
    ],
    dependencies: [
        .package(url: "https://github.com/hummingbird-project/hummingbird.git", from: "2.0.0"),
        // Outbound HTTP for every engine fetch (Sources/SectorEngine/Support/HTTP.swift).
        // Both were already resolved as Hummingbird dependencies; declaring them
        // makes the engine's direct use explicit without moving any pin.
        .package(url: "https://github.com/swift-server/async-http-client.git", from: "1.21.0"),
        .package(url: "https://github.com/apple/swift-nio.git", from: "2.62.0"),
    ],
    targets: [
        .target(
            name: "SectorEngine",
            dependencies: [
                .product(name: "AsyncHTTPClient", package: "async-http-client"),
                .product(name: "NIOCore", package: "swift-nio"),
                .product(name: "NIOHTTP1", package: "swift-nio"),
            ],
            path: "Sources/SectorEngine"),
        .executableTarget(
            name: "SectorEngineServer",
            dependencies: [
                "SectorEngine",
                .product(name: "Hummingbird", package: "hummingbird"),
            ],
            path: "Sources/SectorEngineServer"),
        .testTarget(
            name: "SectorEngineTests",
            dependencies: [
                "SectorEngine",
                // A tiny local socket server for HTTPTests (a stalled response body).
                .product(name: "NIOCore", package: "swift-nio"),
                .product(name: "NIOPosix", package: "swift-nio"),
            ],
            path: "Tests/SectorEngineTests"),
    ]
)
