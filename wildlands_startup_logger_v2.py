#!/usr/bin/env python3
"""
Ghost Recon Wildlands Startup Logger v2
=======================================

- Lance Wildlands normalement via Steam (AppID 460930).
- N'applique AUCUNE affinite CPU.
- Attend GRW.exe puis le suit meme si son PID change.
- Continue a journaliser pendant les transitions de processus.
- Ecrit un CSV chaque seconde.
- Detecte la premiere fenetre visible de GRW.exe.

Prerequis:
    py -3 -m pip install psutil

Place ce fichier dans le dossier Wildlands et lance-le avec le BAT fourni.
"""

from __future__ import annotations

import argparse
import csv
import ctypes
import os
import sys
import time
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

try:
    import psutil
except ImportError:
    print("ERREUR: psutil n'est pas installe.")
    print("Installe-le avec: py -3 -m pip install psutil")
    raise SystemExit(1)

if sys.platform != "win32":
    raise SystemExit("Windows uniquement.")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
user32 = ctypes.WinDLL("user32", use_last_error=True)

DWORD = wintypes.DWORD
WORD = wintypes.WORD
BYTE = wintypes.BYTE
BOOL = wintypes.BOOL
ULONG_PTR = ctypes.c_size_t

RELATION_PROCESSOR_CORE = 0
ERROR_INSUFFICIENT_BUFFER = 122


class GROUP_AFFINITY(ctypes.Structure):
    _fields_ = [
        ("Mask", ULONG_PTR),
        ("Group", WORD),
        ("Reserved", WORD * 3),
    ]


class PROCESSOR_RELATIONSHIP(ctypes.Structure):
    _fields_ = [
        ("Flags", BYTE),
        ("EfficiencyClass", BYTE),
        ("Reserved", BYTE * 20),
        ("GroupCount", WORD),
        ("GroupMask", GROUP_AFFINITY * 1),
    ]


kernel32.GetLogicalProcessorInformationEx.argtypes = [
    DWORD, wintypes.LPVOID, ctypes.POINTER(DWORD)
]
kernel32.GetLogicalProcessorInformationEx.restype = BOOL


def enumerate_cores():
    needed = DWORD(0)
    kernel32.GetLogicalProcessorInformationEx(
        RELATION_PROCESSOR_CORE, None, ctypes.byref(needed)
    )
    if ctypes.get_last_error() != ERROR_INSUFFICIENT_BUFFER:
        raise OSError("Impossible de lire la topologie CPU.")

    buf = ctypes.create_string_buffer(needed.value)
    if not kernel32.GetLogicalProcessorInformationEx(
        RELATION_PROCESSOR_CORE, buf, ctypes.byref(needed)
    ):
        err = ctypes.get_last_error()
        raise OSError(err, ctypes.FormatError(err))

    cores = []
    base = ctypes.addressof(buf)
    offset = 0

    while offset < needed.value:
        addr = base + offset
        relationship = DWORD.from_address(addr).value
        size = DWORD.from_address(addr + 4).value
        if size <= 0:
            break

        if relationship == RELATION_PROCESSOR_CORE:
            proc = PROCESSOR_RELATIONSHIP.from_address(addr + 8)
            if proc.GroupCount == 1:
                mask = int(proc.GroupMask[0].Mask)
                logical = [
                    i for i in range(ctypes.sizeof(ULONG_PTR) * 8)
                    if mask & (1 << i)
                ]
                cores.append({
                    "efficiency": int(proc.EfficiencyClass),
                    "logical": logical,
                })
        offset += size

    return cores


def classify_cpu():
    cores = enumerate_cores()
    if not cores:
        return [], []

    classes = {c["efficiency"] for c in cores}

    if len(classes) > 1:
        best = max(classes)
        p = [c for c in cores if c["efficiency"] == best]
        e = [c for c in cores if c["efficiency"] != best]
    else:
        p = [c for c in cores if len(c["logical"]) > 1]
        e = [c for c in cores if len(c["logical"]) == 1]
        if not p:
            p, e = cores, []

    return (
        sorted(x for c in p for x in c["logical"]),
        sorted(x for c in e for x in c["logical"]),
    )


EnumWindowsProc = ctypes.WINFUNCTYPE(
    BOOL, wintypes.HWND, wintypes.LPARAM
)

user32.EnumWindows.argtypes = [EnumWindowsProc, wintypes.LPARAM]
user32.EnumWindows.restype = BOOL
user32.GetWindowThreadProcessId.argtypes = [
    wintypes.HWND, ctypes.POINTER(DWORD)
]
user32.IsWindowVisible.argtypes = [wintypes.HWND]
user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
user32.GetWindowTextW.argtypes = [
    wintypes.HWND, wintypes.LPWSTR, ctypes.c_int
]


def visible_windows(pid: int):
    titles = []

    @EnumWindowsProc
    def cb(hwnd, _):
        target = DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(target))
        if target.value != pid or not user32.IsWindowVisible(hwnd):
            return True

        n = user32.GetWindowTextLengthW(hwnd)
        if n > 0:
            buf = ctypes.create_unicode_buffer(n + 1)
            user32.GetWindowTextW(hwnd, buf, n + 1)
            if buf.value.strip():
                titles.append(buf.value.strip())
        return True

    user32.EnumWindows(cb, 0)
    return titles


def find_grw_processes():
    found = []
    for p in psutil.process_iter(["pid", "name", "create_time"]):
        try:
            if (p.info["name"] or "").lower() == "grw.exe":
                found.append(p)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    found.sort(key=lambda p: p.info.get("create_time", 0), reverse=True)
    return found


def avg(values):
    return sum(values) / len(values) if values else 0.0


def safe(proc, func, default=None):
    try:
        return func()
    except (psutil.NoSuchProcess, psutil.AccessDenied, AttributeError):
        return default


def human(seconds):
    m, s = divmod(seconds, 60)
    h, m = divmod(int(m), 60)
    if h:
        return f"{h} h {m:02d} min {s:05.2f} s"
    if m:
        return f"{m} min {s:05.2f} s"
    return f"{s:.2f} s"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument(
        "--max-minutes", type=float, default=120,
        help="Duree max du test. Defaut: 120 minutes."
    )
    parser.add_argument(
        "--wait-after-exit", type=float, default=30,
        help="Attente apres disparition de GRW.exe pour detecter un nouveau PID."
    )
    args = parser.parse_args()

    p_lp, e_lp = classify_cpu()
    logical_count = psutil.cpu_count(logical=True) or 1

    root = Path(__file__).resolve().parent
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log = root / f"wildlands_startup_{stamp}.csv"

    print()
    print("==========================================")
    print(" Ghost Recon Wildlands - Startup Logger v2")
    print("==========================================")
    print()
    print("Mode          : lancement NORMAL via Steam")
    print("Affinite CPU  : AUCUNE MODIFICATION")
    print(f"P-core LP     : {p_lp}")
    print(f"E-core LP     : {e_lp}")
    print(f"CSV           : {log}")
    print()

    psutil.cpu_percent(interval=None, percpu=True)

    start = time.perf_counter()
    first_grw = None
    first_window = None
    current_pid = None
    current_proc = None
    last_seen_grw = None
    announced_pids = set()
    cpu_initialized = set()

    cpu_cols = [f"cpu_lp_{i:02d}_percent" for i in range(logical_count)]

    fields = [
        "sample", "timestamp", "elapsed_s",
        "grw_present", "pid", "pid_changed",
        "process_status",
        "process_cpu_percent",
        "process_cpu_normalized_percent",
        "system_cpu_percent",
        "pcores_avg_percent",
        "ecores_avg_percent",
        "rss_mib", "threads", "handles",
        "read_mib_total", "write_mib_total",
        "visible_window", "window_title",
        *cpu_cols,
    ]

    # Lancement normal via le protocole Steam.
    print("Lancement de Steam AppID 460930...")
    os.startfile("steam://rungameid/460930")
    print("En attente de GRW.exe...")
    print()

    sample = 0

    with log.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        f.flush()

        try:
            while True:
                loop = time.perf_counter()
                elapsed = loop - start

                if elapsed >= args.max_minutes * 60:
                    print(f"\nLimite de {args.max_minutes:g} minutes atteinte.")
                    break

                grws = find_grw_processes()
                proc = grws[0] if grws else None
                pid_changed = 0

                if proc is not None:
                    last_seen_grw = elapsed

                    if first_grw is None:
                        first_grw = elapsed
                        print(f"[{human(elapsed)}] Premier GRW.exe detecte.")

                    if current_pid != proc.pid:
                        old = current_pid
                        current_pid = proc.pid
                        current_proc = proc
                        pid_changed = 1

                        if proc.pid not in cpu_initialized:
                            try:
                                proc.cpu_percent(interval=None)
                            except Exception:
                                pass
                            cpu_initialized.add(proc.pid)

                        if proc.pid not in announced_pids:
                            if old is None:
                                print(f"[PID] GRW.exe = {proc.pid}")
                            else:
                                print(f"[PID] GRW.exe a change: {old} -> {proc.pid}")
                            announced_pids.add(proc.pid)

                else:
                    current_proc = None
                    current_pid = None

                per_cpu = psutil.cpu_percent(interval=None, percpu=True)
                system_cpu = avg(per_cpu)
                p_avg = avg([per_cpu[i] for i in p_lp if i < len(per_cpu)])
                e_avg = avg([per_cpu[i] for i in e_lp if i < len(per_cpu)])

                status = ""
                proc_cpu = 0.0
                rss = 0.0
                threads = 0
                handles = -1
                read_mib = 0.0
                write_mib = 0.0
                titles = []

                if current_proc is not None:
                    try:
                        status = current_proc.status()
                        proc_cpu = current_proc.cpu_percent(interval=None)
                        mem = current_proc.memory_info()
                        rss = mem.rss / 1024 / 1024
                        threads = current_proc.num_threads()
                        handles = safe(current_proc, current_proc.num_handles, -1)

                        io = safe(current_proc, current_proc.io_counters, None)
                        if io:
                            read_mib = io.read_bytes / 1024 / 1024
                            write_mib = io.write_bytes / 1024 / 1024

                        titles = visible_windows(current_proc.pid)

                    except psutil.NoSuchProcess:
                        current_proc = None
                        current_pid = None

                if titles and first_window is None:
                    first_window = elapsed
                    print()
                    print("==========================================")
                    print(" PREMIERE FENETRE GRW VISIBLE")
                    print("==========================================")
                    print(f"Temps : {human(elapsed)}")
                    print(f"Titre : {' | '.join(titles)}")
                    print("==========================================")
                    print()

                row = {
                    "sample": sample,
                    "timestamp": datetime.now().isoformat(timespec="milliseconds"),
                    "elapsed_s": round(elapsed, 3),
                    "grw_present": int(current_proc is not None),
                    "pid": current_pid or "",
                    "pid_changed": pid_changed,
                    "process_status": status,
                    "process_cpu_percent": round(proc_cpu, 3),
                    "process_cpu_normalized_percent": round(
                        proc_cpu / logical_count, 3
                    ),
                    "system_cpu_percent": round(system_cpu, 3),
                    "pcores_avg_percent": round(p_avg, 3),
                    "ecores_avg_percent": round(e_avg, 3),
                    "rss_mib": round(rss, 3),
                    "threads": threads,
                    "handles": handles,
                    "read_mib_total": round(read_mib, 3),
                    "write_mib_total": round(write_mib, 3),
                    "visible_window": int(bool(titles)),
                    "window_title": " | ".join(titles),
                }

                for i in range(logical_count):
                    row[f"cpu_lp_{i:02d}_percent"] = (
                        round(per_cpu[i], 3) if i < len(per_cpu) else ""
                    )

                writer.writerow(row)
                f.flush()

                if sample % max(1, round(5 / args.interval)) == 0:
                    state = f"GRW PID {current_pid}" if current_pid else "waiting GRW"
                    print(
                        f"T+{elapsed:7.1f}s | {state:<18} | "
                        f"GRW {proc_cpu:6.1f}% | "
                        f"P {p_avg:5.1f}% | E {e_avg:5.1f}% | "
                        f"RAM {rss:7.1f} MiB | "
                        f"Threads {threads:3d} | "
                        f"Window {'YES' if titles else 'no'}"
                    )

                # Ne pas quitter au premier PID disparu.
                if (
                    first_grw is not None
                    and current_proc is None
                    and last_seen_grw is not None
                    and elapsed - last_seen_grw >= args.wait_after_exit
                ):
                    print()
                    print(
                        f"Aucun GRW.exe depuis {args.wait_after_exit:g} secondes."
                    )
                    print("Fin du suivi.")
                    break

                sample += 1
                sleep = args.interval - (time.perf_counter() - loop)
                if sleep > 0:
                    time.sleep(sleep)

        except KeyboardInterrupt:
            print("\nLogger arrete manuellement.")

    total = time.perf_counter() - start

    print()
    print("==========================================")
    print(" Resume")
    print("==========================================")
    print(f"Duree totale       : {human(total)}")
    print(
        f"Premier GRW.exe    : "
        f"{human(first_grw) if first_grw is not None else 'jamais detecte'}"
    )
    print(
        f"Premiere fenetre   : "
        f"{human(first_window) if first_window is not None else 'jamais detectee'}"
    )
    print(f"CSV                : {log}")
    print("==========================================")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nERREUR: {exc}")
        input("\nAppuie sur Entree pour fermer...")
        raise SystemExit(1)
