#!/usr/bin/env python3
# discovery_service.py
"""
Continuous network discovery daemon.
- skanuje podaną sieć co `scan_interval` sekund
- zapisuje wynik do `output_file` (atomowo)
- prosty backoff na błędy i obsługa SIGTERM/SIGINT
"""
from __future__ import annotations
import asyncio
import ipaddress
import json
import os
import signal
import sys
from pathlib import Path
from typing import List

# ---- Konfiguracja ----
CIDR_OR_RANGE = os.getenv("DISCOVERY_TARGET", "172.16.2.0/24")
CONCURRENCY = int(os.getenv("DISCOVERY_CONCURRENCY", "50"))
SCAN_INTERVAL = int(os.getenv("DISCOVERY_INTERVAL", "60"))   # seconds between scans
# OUTPUT_FILE = Path(os.getenv("DISCOVERY_OUTPUT", "/var/run/discovery_alive.json"))
OUTPUT_FILE = Path("./alive.json")
PING_CMD = ["ping", "-n", "-c", "1", "-W", "1"]  # Linux: 1 packet, timeout 1s
# fallback TCP port (odkomentuj w is_alive jeśli chcesz)
FALLBACK_TCP_PORT = int(os.getenv("DISCOVERY_TCP_FALLBACK_PORT", "22"))

# ---- Utility ----
def hosts_in(cidr_or_ip_range: str):
    if "-" in cidr_or_ip_range:
        start, end = cidr_or_ip_range.split("-", 1)
        a = ipaddress.ip_address(start.strip())
        b = ipaddress.ip_address(end.strip())
        for i in range(int(a), int(b) + 1):
            yield str(ipaddress.ip_address(i))
    else:
        net = ipaddress.ip_network(cidr_or_ip_range, strict=False)
        for ip in net.hosts():
            yield str(ip)

async def ping(ip: str) -> bool:
    proc = await asyncio.create_subprocess_exec(
        *PING_CMD, ip,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    rc = await proc.wait()
    print(f"{ip} : {rc}")
    return rc == 0

import socket
async def tcp_check(ip: str, port: int, timeout: float = 0.8) -> bool:
    loop = asyncio.get_running_loop()
    def _try():
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            s.settimeout(timeout)
            try:
                s.connect((ip, port))
                return True
            except Exception:
                return False
    return await loop.run_in_executor(None, _try)

async def is_alive(ip: str) -> bool:
    if await ping(ip):
        return True
    # fallback na TCP (odkomentuj jeśli chcesz)
    # if await tcp_check(ip, FALLBACK_TCP_PORT):
    #     return True
    return False

# atomowe zapisywanie JSON
def atomic_write_json(path: Path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=2))
    tmp.replace(path)

# ---- Main loop ----
class DiscoveryDaemon:
    def __init__(self, target: str, concurrency: int, interval: int, out_file: Path):
        self.target = target
        self.concurrency = concurrency
        self.interval = interval
        self.out_file = out_file
        self._stop = asyncio.Event()
        self._scan_task: asyncio.Task | None = None

    def stop(self):
        self._stop.set()

    async def run_once(self) -> List[str]:
        sem = asyncio.Semaphore(self.concurrency)
        alive: List[str] = []

        async def worker(ip: str):
            async with sem:
                try:
                    if await is_alive(ip):
                        alive.append(ip)
                except Exception:
                    # nie przerywamy całego skanu z powodu jednego IP
                    pass

        tasks = [asyncio.create_task(worker(ip)) for ip in hosts_in(self.target)]
        await asyncio.gather(*tasks)
        alive.sort(key=lambda s: tuple(int(x) for x in s.split(".")))
        return alive

    async def loop(self):
        backoff = 1
        while not self._stop.is_set():
            try:
                alive = await self.run_once()
                atomic_write_json(self.out_file, alive)
                # reset backoff po sukcesie
                backoff = 1
            except Exception as e:
                print(f"[discovery] error: {e}", file=sys.stderr)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)  # max 5 min
            # czekaj interval lub zakończ jeśli stop
            try:
                await asyncio.wait_for(self._stop.wait(), timeout=self.interval)
            except asyncio.TimeoutError:
                continue

async def _main():
    daemon = DiscoveryDaemon(CIDR_OR_RANGE, CONCURRENCY, SCAN_INTERVAL, OUTPUT_FILE)

    loop = asyncio.get_running_loop()
    loop.add_signal_handler(signal.SIGTERM, daemon.stop)
    loop.add_signal_handler(signal.SIGINT, daemon.stop)

    print(f"[discovery] starting target={CIDR_OR_RANGE} interval={SCAN_INTERVAL}s output={OUTPUT_FILE}")
    await daemon.loop()
    print("[discovery] stopped")

if __name__ == "__main__":
    try:
        asyncio.run(_main())
    except KeyboardInterrupt:
        pass
