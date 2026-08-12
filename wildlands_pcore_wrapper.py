#!/usr/bin/env python3
"""
Wildlands P-Core Wrapper
- Detecte automatiquement les P-cores via l'API Windows.
- Cree GRW.exe suspendu.
- Applique l'affinite uniquement aux P-cores AVANT l'execution du jeu.
- Reprend ensuite le thread principal.

Aucune injection DLL, aucun patch memoire, aucune modification du jeu.
"""

from __future__ import annotations

import argparse
import ctypes
import os
import sys
from ctypes import wintypes
from pathlib import Path


if sys.platform != "win32":
    raise SystemExit("Ce wrapper fonctionne uniquement sous Windows.")

kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

# ---------------------------------------------------------------------------
# Win32 types / constants
# ---------------------------------------------------------------------------

DWORD = wintypes.DWORD
WORD = wintypes.WORD
BYTE = wintypes.BYTE
BOOL = wintypes.BOOL
HANDLE = wintypes.HANDLE
LPVOID = wintypes.LPVOID
ULONG_PTR = ctypes.c_size_t

RELATION_PROCESSOR_CORE = 0
ERROR_INSUFFICIENT_BUFFER = 122
CREATE_SUSPENDED = 0x00000004
INFINITE = 0xFFFFFFFF


class GROUP_AFFINITY(ctypes.Structure):
    _fields_ = [
        ("Mask", ULONG_PTR),
        ("Group", WORD),
        ("Reserved", WORD * 3),
    ]


class PROCESSOR_RELATIONSHIP(ctypes.Structure):
    # Pour RelationProcessorCore, GroupCount vaut toujours 1 selon Microsoft.
    _fields_ = [
        ("Flags", BYTE),
        ("EfficiencyClass", BYTE),
        ("Reserved", BYTE * 20),
        ("GroupCount", WORD),
        ("GroupMask", GROUP_AFFINITY * 1),
    ]


class STARTUPINFOW(ctypes.Structure):
    _fields_ = [
        ("cb", DWORD),
        ("lpReserved", wintypes.LPWSTR),
        ("lpDesktop", wintypes.LPWSTR),
        ("lpTitle", wintypes.LPWSTR),
        ("dwX", DWORD),
        ("dwY", DWORD),
        ("dwXSize", DWORD),
        ("dwYSize", DWORD),
        ("dwXCountChars", DWORD),
        ("dwYCountChars", DWORD),
        ("dwFillAttribute", DWORD),
        ("dwFlags", DWORD),
        ("wShowWindow", WORD),
        ("cbReserved2", WORD),
        ("lpReserved2", ctypes.POINTER(BYTE)),
        ("hStdInput", HANDLE),
        ("hStdOutput", HANDLE),
        ("hStdError", HANDLE),
    ]


class PROCESS_INFORMATION(ctypes.Structure):
    _fields_ = [
        ("hProcess", HANDLE),
        ("hThread", HANDLE),
        ("dwProcessId", DWORD),
        ("dwThreadId", DWORD),
    ]


kernel32.GetLogicalProcessorInformationEx.argtypes = [
    DWORD,
    LPVOID,
    ctypes.POINTER(DWORD),
]
kernel32.GetLogicalProcessorInformationEx.restype = BOOL

kernel32.CreateProcessW.argtypes = [
    wintypes.LPCWSTR,       # lpApplicationName
    wintypes.LPWSTR,        # lpCommandLine
    LPVOID,                 # lpProcessAttributes
    LPVOID,                 # lpThreadAttributes
    BOOL,                   # bInheritHandles
    DWORD,                  # dwCreationFlags
    LPVOID,                 # lpEnvironment
    wintypes.LPCWSTR,       # lpCurrentDirectory
    ctypes.POINTER(STARTUPINFOW),
    ctypes.POINTER(PROCESS_INFORMATION),
]
kernel32.CreateProcessW.restype = BOOL

kernel32.SetProcessAffinityMask.argtypes = [HANDLE, ULONG_PTR]
kernel32.SetProcessAffinityMask.restype = BOOL

kernel32.ResumeThread.argtypes = [HANDLE]
kernel32.ResumeThread.restype = DWORD

kernel32.CloseHandle.argtypes = [HANDLE]
kernel32.CloseHandle.restype = BOOL

kernel32.TerminateProcess.argtypes = [HANDLE, wintypes.UINT]
kernel32.TerminateProcess.restype = BOOL

kernel32.WaitForSingleObject.argtypes = [HANDLE, DWORD]
kernel32.WaitForSingleObject.restype = DWORD


def _winerr(prefix: str) -> OSError:
    err = ctypes.get_last_error()
    return OSError(err, f"{prefix}: {ctypes.FormatError(err).strip()}")


def enumerate_cores() -> list[dict]:
    """
    Retourne chaque coeur physique sous la forme:
    {
        "efficiency": int,
        "group": int,
        "mask": int,
        "logical": [indices...],
        "smt": bool,
    }
    """
    needed = DWORD(0)

    ok = kernel32.GetLogicalProcessorInformationEx(
        RELATION_PROCESSOR_CORE, None, ctypes.byref(needed)
    )
    if ok:
        raise RuntimeError("Reponse Win32 inattendue lors du calcul de taille.")

    err = ctypes.get_last_error()
    if err != ERROR_INSUFFICIENT_BUFFER:
        raise _winerr("GetLogicalProcessorInformationEx(size)")

    buf = ctypes.create_string_buffer(needed.value)

    if not kernel32.GetLogicalProcessorInformationEx(
        RELATION_PROCESSOR_CORE, buf, ctypes.byref(needed)
    ):
        raise _winerr("GetLogicalProcessorInformationEx(data)")

    cores: list[dict] = []
    base = ctypes.addressof(buf)
    offset = 0

    while offset < needed.value:
        record_addr = base + offset
        relationship = DWORD.from_address(record_addr).value
        size = DWORD.from_address(record_addr + ctypes.sizeof(DWORD)).value

        if size <= 0:
            raise RuntimeError("Structure CPU Win32 invalide (Size=0).")

        if relationship == RELATION_PROCESSOR_CORE:
            proc_addr = record_addr + ctypes.sizeof(DWORD) * 2
            proc = PROCESSOR_RELATIONSHIP.from_address(proc_addr)

            if proc.GroupCount != 1:
                raise RuntimeError(
                    f"Topologie inattendue: un coeur appartient a {proc.GroupCount} groupes."
                )

            group = int(proc.GroupMask[0].Group)
            mask = int(proc.GroupMask[0].Mask)
            logical = [i for i in range(ctypes.sizeof(ULONG_PTR) * 8) if mask & (1 << i)]

            cores.append(
                {
                    "efficiency": int(proc.EfficiencyClass),
                    "group": group,
                    "mask": mask,
                    "logical": logical,
                    "smt": len(logical) > 1,
                }
            )

        offset += size

    if not cores:
        raise RuntimeError("Aucun coeur CPU detecte.")

    return cores


def select_pcores(cores: list[dict]) -> list[dict]:
    """
    Microsoft definit EfficiencyClass ainsi:
    une valeur plus elevee = coeur plus performant / moins efficient.

    Fallback utile sur certains firmwares:
    si toutes les EfficiencyClass sont identiques mais que la machine melange
    coeurs SMT et non-SMT, on prend les coeurs SMT (cas typique 13600K:
    P-cores = 2 threads, E-cores = 1 thread).
    """
    classes = {c["efficiency"] for c in cores}

    if len(classes) > 1:
        best_class = max(classes)
        return [c for c in cores if c["efficiency"] == best_class]

    smt_cores = [c for c in cores if c["smt"]]
    non_smt_cores = [c for c in cores if not c["smt"]]

    if smt_cores and non_smt_cores:
        return smt_cores

    # CPU homogene: aucun E-core a exclure.
    return cores


def affinity_mask_for(cores: list[dict]) -> tuple[int, int, list[int]]:
    groups = {c["group"] for c in cores}
    if len(groups) != 1:
        raise RuntimeError(
            "Les P-cores sont repartis sur plusieurs Processor Groups. "
            "Ce wrapper est volontairement optimise pour les CPU desktop < 64 threads."
        )

    group = next(iter(groups))
    mask = 0
    logical: list[int] = []

    for core in cores:
        mask |= core["mask"]
        logical.extend(core["logical"])

    logical.sort()

    if mask == 0:
        raise RuntimeError("Masque d'affinite P-core vide.")

    return group, mask, logical


def print_topology(cores: list[dict], pcores: list[dict]) -> None:
    p_ids = {id(c) for c in pcores}

    print("\nTopologie CPU detectee")
    print("----------------------")
    for index, core in enumerate(cores):
        kind = "P" if id(core) in p_ids else "E"
        lp = ",".join(str(x) for x in core["logical"])
        print(
            f"Core {index:02d} | {kind}-core | "
            f"EfficiencyClass={core['efficiency']:3d} | "
            f"Group={core['group']} | LP=[{lp}]"
        )


def launch_suspended_on_pcores(exe: Path, affinity_mask: int, extra_args: list[str]) -> int:
    exe = exe.resolve()

    if not exe.is_file():
        raise FileNotFoundError(f"Executable introuvable: {exe}")

    # CreateProcess peut modifier le buffer de ligne de commande.
    cmdline = ctypes.create_unicode_buffer(
        subprocess_cmdline([str(exe), *extra_args])
    )

    si = STARTUPINFOW()
    si.cb = ctypes.sizeof(si)
    pi = PROCESS_INFORMATION()

    ok = kernel32.CreateProcessW(
        str(exe),
        cmdline,
        None,
        None,
        False,
        CREATE_SUSPENDED,
        None,
        str(exe.parent),
        ctypes.byref(si),
        ctypes.byref(pi),
    )

    if not ok:
        err = ctypes.get_last_error()
        if err == 740:
            raise PermissionError(
                "Windows exige une elevation. Lance ce wrapper en administrateur."
            )
        raise _winerr("CreateProcessW")

    resumed = False
    try:
        if not kernel32.SetProcessAffinityMask(pi.hProcess, affinity_mask):
            raise _winerr("SetProcessAffinityMask")

        resume_result = kernel32.ResumeThread(pi.hThread)
        if resume_result == 0xFFFFFFFF:
            raise _winerr("ResumeThread")
        resumed = True

        print(f"\nGRW.exe lance, PID {pi.dwProcessId}")
        print(f"Affinite appliquee AVANT execution: 0x{affinity_mask:X}")
        return int(pi.dwProcessId)

    except Exception:
        # Ne laisse jamais un GRW.exe orphelin en etat suspendu.
        if not resumed:
            kernel32.TerminateProcess(pi.hProcess, 1)
        raise

    finally:
        kernel32.CloseHandle(pi.hThread)
        kernel32.CloseHandle(pi.hProcess)


def subprocess_cmdline(argv: list[str]) -> str:
    """
    Equivalent minimal de subprocess.list2cmdline sans importer subprocess.
    """
    import subprocess
    return subprocess.list2cmdline(argv)



def choose_game_exe() -> Path:
    """
    Ouvre un vrai selecteur de fichier Windows.
    Fallback console si tkinter n'est pas disponible.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog

        root = tk.Tk()
        root.withdraw()
        root.attributes("-topmost", True)

        selected = filedialog.askopenfilename(
            title="Selectionner GRW.exe",
            filetypes=[
                ("Ghost Recon Wildlands", "GRW.exe"),
                ("Executables Windows", "*.exe"),
                ("Tous les fichiers", "*.*"),
            ],
        )
        root.destroy()

        if not selected:
            raise SystemExit("Aucun executable selectionne.")

        return Path(selected)

    except ImportError:
        value = input(
            "\nChemin vers GRW.exe : "
        ).strip().strip('"')
        if not value:
            raise SystemExit("Aucun executable selectionne.")
        return Path(value)


def normalize_game_path(value: str | None) -> Path:
    if not value:
        return choose_game_exe()

    # Drag & drop sur le .bat peut entourer le chemin de guillemets.
    value = value.strip().strip('"')
    path = Path(value)

    # Si l'utilisateur donne le dossier Wildlands, trouve GRW.exe dedans.
    if path.is_dir():
        candidate = path / "GRW.exe"
        if candidate.is_file():
            return candidate

    return path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Lance Ghost Recon Wildlands uniquement sur les P-cores."
    )
    parser.add_argument(
        "game",
        nargs="?",
        help=r'Chemin vers GRW.exe, ex: "D:\Games\Wildlands\GRW.exe"',
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Affiche seulement la topologie CPU et le masque choisi.",
    )
    parser.add_argument(
        "game_args",
        nargs=argparse.REMAINDER,
        help="Arguments optionnels transmis a GRW.exe.",
    )
    args = parser.parse_args()

    cores = enumerate_cores()
    pcores = select_pcores(cores)
    group, mask, logical = affinity_mask_for(pcores)

    print_topology(cores, pcores)

    print("\nSelection")
    print("---------")
    print(f"P-cores physiques : {len(pcores)}")
    print(f"Threads logiques  : {logical}")
    print(f"Processor Group   : {group}")
    print(f"Affinity mask     : 0x{mask:X}")

    if args.test:
        return 0

    game = normalize_game_path(args.game)
    print(f"\nExecutable Wildlands : {game}")

    launch_suspended_on_pcores(game, mask, args.game_args)
    print("\nLe wrapper peut maintenant etre ferme.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nAnnule.")
        raise SystemExit(130)
    except Exception as exc:
        print(f"\nERREUR: {exc}", file=sys.stderr)
        print(
            "\nAstuce: commence par `python wildlands_pcore_wrapper.py --test` "
            "pour verifier que les P/E-cores sont correctement detectes.",
            file=sys.stderr,
        )
        raise SystemExit(1)
