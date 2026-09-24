"""InevioNet CLI Commands."""
import os
import sys
import json
import time
from typing import Optional

try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    RICH_AVAILABLE = True
except ImportError:
    RICH_AVAILABLE = False
    Console = None


console = Console() if RICH_AVAILABLE else None


def print_header(title):
    if RICH_AVAILABLE:
        console.print(Panel(f"[bold cyan]{title}[/bold cyan]", expand=False))
    else:
        print("=" * 70)
        print(f"  {title}")
        print("=" * 70)


def print_success(msg):
    if RICH_AVAILABLE:
        console.print(f"[bold green]OK:[/bold green] {msg}")
    else:
        print(f"OK: {msg}")


def print_error(msg):
    if RICH_AVAILABLE:
        console.print(f"[bold red]ERROR:[/bold red] {msg}")
    else:
        print(f"ERROR: {msg}")


def print_warning(msg):
    if RICH_AVAILABLE:
        console.print(f"[bold yellow]WARN:[/bold yellow] {msg}")
    else:
        print(f"WARN: {msg}")


def print_info(msg):
    if RICH_AVAILABLE:
        console.print(f"[bold blue]INFO:[/bold blue] {msg}")
    else:
        print(f"INFO: {msg}")


def print_table(title, columns, rows):
    if RICH_AVAILABLE:
        table = Table(title=title)
        for col in columns:
            table.add_column(col, style="cyan")
        for row in rows:
            table.add_row(*[str(c) for c in row])
        console.print(table)
    else:
        print(f"\n{title}")
        print(" | ".join(columns))
        print("-" * 60)
        for row in rows:
            print(" | ".join(str(c) for c in row))


# ================================================================
# Command implementations
# ================================================================

def cmd_demo(args):
    """Demo mode."""
    print_header("INEVIONET DEMO")
    from inevionet.orchestrator import InevioNet

    net = InevioNet(password="demo_password_123", node_id="cli_demo", auto_start=True)
    try:
        print_info("Sending simple messages...")
        messages = [
            ("alice", "Hello from CLI!"),
            ("bob", "InevioNet works!"),
            ("charlie", {"event": "test", "value": 42}),
        ]
        for receiver, msg in messages:
            packet = net.send(receiver, msg)
            if packet:
                print_success(f"-> {receiver}: {packet.packet_id[:16]}")
            time.sleep(0.1)

        print_info("Guaranteed delivery...")
        success, packet = net.send_with_guarantee("critical_user", "Important message!")
        print_success(f"Guaranteed: {success}")

        print_info("Steganography...")
        packet = net.send("stealth_user", b"Secret data", use_stealth=True)
        if packet:
            print_success(f"Stealth sent: {packet.packet_id[:16]}")

        print_info("Statistics:")
        stats = net.get_stats()
        print_table("Stats", ["Metric", "Value"], [
            ("Node ID", stats["node_id"]),
            ("Mode", stats["mode"]),
            ("Sent", stats["packets_sent"]),
            ("Delivered", stats["packets_delivered"]),
            ("Failed", stats["packets_failed"]),
            ("Uptime", f"{stats['uptime']:.1f}s"),
        ])

        print_success("Demo completed!")

    finally:
        net.stop()
    return 0


def cmd_send(args):
    """Send a message."""
    print_header("SEND MESSAGE")
    from inevionet.orchestrator import InevioNet

    password = args.password or os.environ.get("INEVIONET_PASSWORD", "default_password")
    net = InevioNet(password=password, node_id=args.node_id or "cli_sender", auto_start=True)

    try:
        if args.guarantee:
            print_info("Guaranteed delivery mode")
            success, packet = net.send_with_guarantee(args.to, args.message)
        else:
            packet = net.send(
                receiver=args.to,
                payload=args.message,
                protocol=args.protocol,
                use_stealth=args.stealth)
            success = packet is not None

        if success:
            print_success(f"Sent to {args.to}")
            if packet:
                print_info(f"Packet ID: {packet.packet_id}")
                print_info(f"Protocol: {packet.protocol}")
                print_info(f"Attractor: {packet.attractor}")
            return 0
        else:
            print_error("Send failed")
            return 1
    finally:
        net.stop()


def cmd_receive(args):
    """Receive messages."""
    print_header("RECEIVE MESSAGES")
    from inevionet.orchestrator import InevioNet

    password = args.password or os.environ.get("INEVIONET_PASSWORD", "default_password")
    net = InevioNet(password=password, node_id=args.node_id or "cli_receiver", auto_start=True)

    def on_receive(packet):
        print_success(f"Received from: {packet.sender}")
        print_info(f"Packet: {packet.packet_id}")
        success, data = net.receive(packet)
        if success:
            print_info(f"Data: {data}")

    net.register_handler("on_receive", on_receive)

    print_info("Waiting for messages (Ctrl+C to exit)...")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print_warning("Stopped by user")
    finally:
        net.stop()
    return 0


def cmd_stats(args):
    """Show statistics."""
    print_header("INEVIONET STATS")
    from inevionet.orchestrator import InevioNet

    password = args.password or "default_password"
    net = InevioNet(password=password, auto_start=True)
    try:
        stats = net.get_stats()
        rows = [
            ("Node ID", stats["node_id"]),
            ("Mode", stats["mode"]),
            ("Running", stats["running"]),
            ("Uptime", f"{stats['uptime']:.1f}s"),
            ("Packets sent", stats["packets_sent"]),
            ("Packets received", stats["packets_received"]),
            ("Packets delivered", stats["packets_delivered"]),
            ("Packets failed", stats["packets_failed"]),
            ("Bytes sent", stats["bytes_sent"]),
            ("Bytes received", stats["bytes_received"]),
        ]
        if stats["packets_sent"] > 0:
            rate = stats["packets_delivered"] / stats["packets_sent"] * 100
            rows.append(("Delivery rate", f"{rate:.1f}%"))
        print_table("Statistics", ["Metric", "Value"], rows)
    finally:
        net.stop()
    return 0


def cmd_mycelium(args):
    """Mycelium operations."""
    print_header("MYCELIUM")
    from inevionet.orchestrator import InevioNet

    password = args.password or "default_password"
    net = InevioNet(password=password, auto_start=True)
    try:
        if args.spread:
            print_info("Spreading mycelium...")
            results = net.spread_mycelium()
            for network, ok in results.items():
                if ok:
                    print_success(f"{network}: OK")
                else:
                    print_warning(f"{network}: FAIL")
        elif args.harvest:
            print_info("Harvesting...")
            harvested = net.harvest()
            print_success(f"Harvested: {len(harvested)} items")
        else:
            stats = net.mycelium.get_stats()
            print_info(f"Spores: {stats.get('spores', {}).get('alive', 0)}")
            print_info(f"Networks: {stats.get('networks_count', 0)}")
            print_info(f"Known: {stats.get('known_networks', [])}")
    finally:
        net.stop()
    return 0


def cmd_evolve(args):
    """Run evolution."""
    print_header("EVOLUTION")
    from inevionet.orchestrator import InevioNet

    password = args.password or "default_password"
    net = InevioNet(password=password, auto_start=True)
    try:
        generations = args.generations or 10
        print_info(f"Evolving {generations} generations...")
        best = net.evolve(generations)
        if best:
            print_success(f"Best fitness: {best.fitness:.4f}")
            print_info(f"Generation: {best.generation}")
    finally:
        net.stop()
    return 0


def cmd_version(args):
    """Show version."""
    from inevionet import __version__
    print_header(f"InevioNet v{__version__}")
    from inevionet.core.constants import DataPaths
    print_info(f"Data dir: {DataPaths.get_root()}")
    return 0
