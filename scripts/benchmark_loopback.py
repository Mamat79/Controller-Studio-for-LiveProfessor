from __future__ import annotations

import socket
import statistics
import threading
import time

from ec4lpbridge.osc_codec import decode_message, encode_message


def main(samples: int = 2000) -> None:
    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind(("127.0.0.1", 0))
    server.settimeout(1.0)
    target = server.getsockname()
    stop = threading.Event()

    def echo() -> None:
        while not stop.is_set():
            try:
                data, peer = server.recvfrom(4096)
            except (TimeoutError, OSError):
                continue
            server.sendto(data, peer)

    thread = threading.Thread(target=echo, daemon=True)
    thread.start()
    client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    client.settimeout(1.0)
    packet = encode_message("/Companion/Rotary1", [0.5])
    timings_ms = []
    cpu_start = time.process_time()
    wall_start = time.perf_counter()
    try:
        for _ in range(samples):
            start = time.perf_counter_ns()
            client.sendto(packet, target)
            data, _ = client.recvfrom(4096)
            decode_message(data)
            timings_ms.append((time.perf_counter_ns() - start) / 1_000_000)
    finally:
        wall = time.perf_counter() - wall_start
        cpu = time.process_time() - cpu_start
        stop.set()
        client.close()
        server.close()
        thread.join(timeout=1.0)

    ordered = sorted(timings_ms)
    p95 = ordered[int(len(ordered) * 0.95)]
    print(f"samples={samples}")
    print(f"median_ms={statistics.median(timings_ms):.4f}")
    print(f"p95_ms={p95:.4f}")
    print(f"max_ms={max(timings_ms):.4f}")
    print(f"wall_s={wall:.4f}")
    print(f"cpu_s={cpu:.4f}")
    print(f"cpu_share_one_core_pct={(cpu / wall * 100):.2f}")


if __name__ == "__main__":
    main()
