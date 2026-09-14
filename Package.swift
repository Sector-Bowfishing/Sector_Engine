// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "SectorEngine",
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
        .testTarget(name: "SectorEngineTests", dependencies: ["SectorEngine"], path: "Tests/SectorEngineTests"),
    ]
)
