// swift-tools-version: 5.10
import PackageDescription

let package = Package(
    name: "SectorEngine",
    platforms: [.macOS(.v14)],
    products: [
        .library(name: "SectorEngine", targets: ["SectorEngine"]),
        .executable(name: "SectorEngineServer", targets: ["SectorEngineServer"]),
        .executable(name: "ClarityReplay", targets: ["ClarityReplay"]),
        .executable(name: "WaterTempBrainJob", targets: ["WaterTempBrainJob"]),
        .executable(name: "LakeBrainJob", targets: ["LakeBrainJob"]),
        .executable(name: "ClarityPrecompute", targets: ["ClarityPrecompute"]),
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
        // Clarity Fusion Stage 2's historical replay; not built into the image.
        .executableTarget(name: "ClarityReplay", dependencies: ["SectorEngine"], path: "Sources/ClarityReplay"),
        // Specialist Brains with a Swift runtime live in their canonical Brain packages (brains/<dir>/runtime), as their own targets on top of the
        // shared SectorEngine library (fetchers, lake directory, the Swift Brain platform). Nothing in the customer server imports them.
        // Lake Brain (`lake-brain`): one on-demand run → gs://sector-lake-brain history + the Brain RTDB (Sector Ops reads it).
        .target(name: "LakeBrain", dependencies: ["SectorEngine"], path: "brains/lake/runtime/LakeBrain"),
        .executableTarget(name: "LakeBrainJob", dependencies: ["SectorEngine", "LakeBrain"], path: "brains/lake/runtime/LakeBrainJob"),
        // Water Temperature Brain (`water-temp`): the fleet run → the Brain RTDB (Sector Ops reads it).
        .target(name: "WaterTemperatureBrain", dependencies: ["SectorEngine"], path: "brains/water-temperature/runtime/WaterTemperatureBrain"),
        .executableTarget(name: "WaterTempBrainJob", dependencies: ["SectorEngine", "WaterTemperatureBrain"], path: "brains/water-temperature/runtime/WaterTempBrainJob"),
        // Clarity Fusion Stage 5: the hourly job that prepares each Current Clarity world.
        .executableTarget(
            name: "ClarityPrecompute",
            dependencies: [
                "SectorEngine",
                .product(name: "AsyncHTTPClient", package: "async-http-client"),
                .product(name: "NIOCore", package: "swift-nio"),
            ],
            path: "Sources/ClarityPrecompute"),
        .testTarget(name: "SectorEngineTests", dependencies: ["SectorEngine"], path: "Tests/SectorEngineTests"),
        .testTarget(name: "LakeBrainTests", dependencies: ["SectorEngine", "LakeBrain"], path: "brains/lake/tests/swift"),
        .testTarget(name: "WaterTemperatureBrainTests", dependencies: ["SectorEngine", "WaterTemperatureBrain"], path: "brains/water-temperature/tests/swift"),
    ]
)
