#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Example 6: Drone mesh network."""
from inevionet import InevioNet
from inevionet.mesh import AutoTopology
from inevionet.network.rf_scanner import RFScanner
from inevionet.masking.ambient import SpatialDensityModel


def main():
    print("=" * 60)
    print("  EXAMPLE 6: DRONE MESH NETWORK")
    print("=" * 60)
    print()

    # 1. Spatial density model
    print("1. Spatial density model:")
    model = SpatialDensityModel(density_per_km2=1000.0, detection_range_km=0.1)
    analysis = model.analyze(area_km2=1.0)
    print(f"   Density: {analysis['density']} nodes/km2")
    print(f"   Detection prob: {analysis['detection_probability']:.4f}")
    print(f"   Mean distance: {analysis['mean_nearest_distance']:.4f} km")
    print()

    # 2. RF scanner
    print("2. RF scanning:")
    scanner = RFScanner()
    wifi = scanner.scan_wifi()
    print(f"   WiFi scan: {wifi.total_count} networks")
    for sig in wifi.strongest(3):
        print(f"   {sig}")
    print()

    # 3. Auto topology
    print("3. Auto topology:")
    topology = AutoTopology(rf_scanner=scanner)
    build_info = topology.build_from_scanner()
    print(f"   Nodes: {build_info.get('nodes', 0)}")
    print(f"   Edges: {build_info.get('edges', 0)}")
    stats = topology.get_stats()
    print(f"   Connected: {stats['is_connected']}")
    print(f"   Diameter: {stats['diameter']}")
    print(f"   Clustering: {stats['clustering']:.4f}")
    print()

    # 4. Mesh + drones via InevioNet
    print("4. InevioNet mesh integration:")
    net = InevioNet("drone_password", node_id="drone_controller", auto_start=True)
    try:
        net.enable_rf_scanning()
        print("   RF scanning enabled")
        env = net.scan_environment()
        scan = env.get("scan", {})
        print(f"   Environment: {scan.get('signals', 0)} signals")
        mesh = net.build_mesh_topology()
        build = mesh.get("build", {})
        print(f"   Mesh topology: {build.get('nodes', 0)} nodes")
    finally:
        net.stop()
    print()

    print("=" * 60)


if __name__ == "__main__":
    main()
