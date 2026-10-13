// swift-tools-version: 5.10
// Research-only harness: calls the UNMODIFIED production ConditionsAggregator with synthetic inputs
// to measure its behaviour. Not part of the production package; nothing here ships.
import PackageDescription
let package = Package(
    name: "intelligence-probe",
    platforms: [.macOS(.v14)],
    dependencies: [.package(path: "../../..")],
    targets: [.executableTarget(name: "probe", dependencies: [.product(name: "SectorEngine", package: "Sector_Engine-intelligence-research")], path: "Sources/probe")]
)
