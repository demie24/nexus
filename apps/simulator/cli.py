"""
NEXUS Simulator Command-Line Interface (CLI)
Provides operators and developers with commands to control, inspect, trigger scenarios,
and benchmark the Virtual Factory Simulator.
"""

import argparse
import asyncio
import json
import logging
import sys
import time
from typing import List

from services.simulation.config import get_default_factory_spec
from services.simulation.engine import VirtualFactorySimulator
from services.simulation.scenarios import ScenarioType
from services.simulation.transports import (
    BaseTelemetryTransport,
    InMemoryTransport,
    MQTTTransport,
    DatabaseTransport,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("nexus-sim")


def build_transports(names: List[str]) -> List[BaseTelemetryTransport]:
    transports: List[BaseTelemetryTransport] = []
    cleaned = [n.strip().lower() for n in names]

    if "mqtt" in cleaned:
        try:
            transports.append(MQTTTransport())
        except Exception as exc:
            logger.warning(f"Failed to initialize MQTT transport: {exc}")

    if "db" in cleaned or "database" in cleaned:
        try:
            transports.append(DatabaseTransport())
        except Exception as exc:
            logger.warning(f"Failed to initialize Database transport: {exc}")

    return transports


def cmd_start(args):
    """Starts continuous or bounded simulation streaming."""
    selected_transports = args.transports.split(",")
    transports = build_transports(selected_transports)

    sim = VirtualFactorySimulator(
        seed=args.seed,
        time_scale=args.time_scale,
        transports=transports
    )

    print("\n" + "=" * 60)
    print(f"  NEXUS VIRTUAL FACTORY SIMULATOR — STARTING")
    print(f"  Machines: 6 (M01 - M06) across 2 Production Lines")
    print(f"  Time Scale: {args.time_scale}x | Seed: {args.seed} | Interval: {args.interval}s")
    print(f"  Transports: {selected_transports}")
    print("=" * 60 + "\n")

    if args.scenario:
        scen_type = ScenarioType(args.scenario)
        sim.trigger_scenario(
            scenario_type=scen_type,
            machine_id=args.machine,
            severity=args.severity,
            duration_sim_seconds=args.duration
        )

    ticks_completed = 0
    try:
        while True:
            sim_dt = args.interval * args.time_scale
            telemetries = sim.step(sim_dt)
            ticks_completed += 1

            if ticks_completed % args.log_every == 0 or ticks_completed == 1:
                timestamp_str = telemetries[0].timestamp.strftime("%H:%M:%S")
                print(f"[{timestamp_str}] Tick #{ticks_completed:04d} | Sim Time: {sim.clock.current_time.strftime('%H:%M:%S')} | Generated {len(telemetries)} frames")
                for t in telemetries:
                    m = sim.machines[t.machine_id]
                    print(
                        f"   {t.machine_id} ({m.operating_status.value:<9}): "
                        f"Temp={t.temperature:5.1f}°C | Vib={t.vibration:4.2f} mm/s | "
                        f"Load={t.load:4.2f} | Health={m.health_score:5.1f}% | FailProb={m.failure_probability*100:4.1f}%"
                    )
                print("-" * 60)

            if args.ticks and ticks_completed >= args.ticks:
                print(f"\nCompleted specified {args.ticks} ticks. Exiting.")
                break

            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\nSimulator stopped by user.")
    finally:
        sim.close()


def cmd_step(args):
    """Executes a fixed number of stepped ticks and outputs results."""
    transports = build_transports(args.transports.split(",")) if args.transports else []
    sim = VirtualFactorySimulator(
        seed=args.seed,
        time_scale=args.time_scale,
        transports=transports
    )

    if args.scenario:
        sim.trigger_scenario(
            scenario_type=ScenarioType(args.scenario),
            machine_id=args.machine,
            severity=args.severity
        )

    for i in range(args.count):
        telemetries = sim.step(args.dt)
        print(f"Step {i+1}/{args.count}: Generated {len(telemetries)} records at {sim.clock.current_time.isoformat()}")

    # Print summary of final state
    print("\n--- FINAL MACHINE STATES ---")
    for summary in sim.get_machines_summary():
        print(json.dumps(summary, indent=2))
    sim.close()


def cmd_scenario(args):
    """Directly triggers and verifies a scenario on a simulated machine."""
    sim = VirtualFactorySimulator(seed=42)
    scen_type = ScenarioType(args.scenario_type)
    instance = sim.trigger_scenario(
        scenario_type=scen_type,
        machine_id=args.machine,
        severity=args.severity,
        duration_sim_seconds=args.duration
    )
    print(f"Successfully triggered scenario:")
    print(json.dumps(instance.to_dict(), indent=2))

    # Advance a few steps to show effect
    print("\nAdvancing 5 steps (50 seconds) to demonstrate progression:")
    for _ in range(5):
        sim.step(10.0)

    m = sim.machines[args.machine]
    tel = sim.get_latest_telemetry(args.machine)
    print(f"\nMachine {args.machine} State after progression:")
    print(f"  Operating Status:    {m.operating_status.value}")
    print(f"  Health Score:        {m.health_score:.1f}%")
    print(f"  Failure Probability: {m.failure_probability*100:.1f}%")
    if tel:
        print(f"  Observed Temp:       {tel.temperature} °C")
        print(f"  Observed Vibration:  {tel.vibration} mm/s")
        print(f"  Efficiency:          {tel.efficiency}%")
    sim.close()


def cmd_benchmark(args):
    """Runs a performance and throughput benchmark on the simulator."""
    sim = VirtualFactorySimulator(seed=args.seed)
    total_ticks = args.ticks
    machine_count = len(sim.machines)

    print(f"Benchmarking simulator across {machine_count} machines for {total_ticks} ticks...")
    start_time = time.perf_counter()

    for _ in range(total_ticks):
        sim.step(1.0)

    duration = time.perf_counter() - start_time
    total_frames = total_ticks * machine_count
    ticks_per_sec = total_ticks / duration if duration > 0 else 0
    frames_per_sec = total_frames / duration if duration > 0 else 0

    print("\n" + "=" * 50)
    print("  SIMULATOR BENCHMARK RESULTS")
    print("=" * 50)
    print(f"  Total Ticks:       {total_ticks}")
    print(f"  Total Machines:    {machine_count}")
    print(f"  Total Frames:      {total_frames}")
    print(f"  Execution Time:    {duration:.4f} seconds")
    print(f"  Throughput (Tick): {ticks_per_sec:.1f} ticks/second")
    print(f"  Throughput (Data): {frames_per_sec:.1f} telemetry frames/second")
    print(f"  Meets 10 Hz Requirement: {'YES (Exceeds by ' + str(round(ticks_per_sec/10, 1)) + 'x)' if ticks_per_sec >= 10 else 'NO'}")
    print("=" * 50 + "\n")
    sim.close()


def main():
    parser = argparse.ArgumentParser(
        prog="nexus-sim",
        description="NEXUS Virtual Industrial Factory Simulator CLI"
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: start
    p_start = subparsers.add_parser("start", help="Start simulation loop")
    p_start.add_argument("--interval", type=float, default=1.0, help="Wall-clock seconds per tick (default: 1.0)")
    p_start.add_argument("--time-scale", type=float, default=1.0, help="Simulated time speedup multiplier (default: 1.0)")
    p_start.add_argument("--seed", type=int, default=42, help="Deterministic random seed (default: 42)")
    p_start.add_argument("--ticks", type=int, default=None, help="Stop after N ticks (default: infinite)")
    p_start.add_argument("--log-every", type=int, default=1, help="Print telemetry every N ticks")
    p_start.add_argument("--transports", type=str, default="memory,db,mqtt", help="Comma-separated transports (memory,db,mqtt)")
    p_start.add_argument("--scenario", type=str, default=None, choices=[s.value for s in ScenarioType], help="Inject scenario on start")
    p_start.add_argument("--machine", type=str, default="M03", help="Target machine for initial scenario")
    p_start.add_argument("--severity", type=float, default=0.75, help="Scenario severity 0.1-1.0")
    p_start.add_argument("--duration", type=float, default=300.0, help="Scenario duration in sim seconds")
    p_start.set_defaults(func=cmd_start)

    # Subcommand: step
    p_step = subparsers.add_parser("step", help="Step simulation manually for N ticks")
    p_step.add_argument("--count", type=int, default=5, help="Number of ticks to advance")
    p_step.add_argument("--dt", type=float, default=1.0, help="Simulated seconds per step")
    p_step.add_argument("--time-scale", type=float, default=1.0)
    p_step.add_argument("--seed", type=int, default=42)
    p_step.add_argument("--transports", type=str, default="memory", help="Comma-separated transports")
    p_step.add_argument("--scenario", type=str, default=None, choices=[s.value for s in ScenarioType])
    p_step.add_argument("--machine", type=str, default="M03")
    p_step.add_argument("--severity", type=float, default=0.75)
    p_step.set_defaults(func=cmd_step)

    # Subcommand: scenario
    p_scen = subparsers.add_parser("scenario", help="Trigger abnormal failure scenario")
    p_scen.add_argument("scenario_type", choices=[s.value for s in ScenarioType], help="Scenario type")
    p_scen.add_argument("--machine", type=str, default="M03", help="Target machine ID (e.g. M01-M06)")
    p_scen.add_argument("--severity", type=float, default=0.8, help="Scenario severity 0.1-1.0")
    p_scen.add_argument("--duration", type=float, default=300.0, help="Duration in sim seconds")
    p_scen.set_defaults(func=cmd_scenario)

    # Subcommand: benchmark
    p_bench = subparsers.add_parser("benchmark", help="Measure simulator throughput and performance")
    p_bench.add_argument("--ticks", type=int, default=500, help="Number of ticks to benchmark")
    p_bench.add_argument("--seed", type=int, default=42)
    p_bench.set_defaults(func=cmd_benchmark)

    parsed = parser.parse_args()
    parsed.func(parsed)


if __name__ == "__main__":
    main()
