# Ghost Recon Wildlands — Intel Hybrid CPU Fix

Small tools for **Ghost Recon Wildlands startup issues on Intel P-core / E-core CPUs**.

This repository contains:

* `wildlands_pcore_wrapper.py` — launches Wildlands on P-cores only.
* `wildlands_startup_logger_v2.py` — logs the normal startup without changing CPU affinity.

---

# English

## P-Core Wrapper

### Requirements

* Windows 10/11
* Python 3 64-bit added to `PATH`

Check Python in PowerShell:

```powershell
python --version
```

### Installation

Put these files next to `GRW.exe`:

```text
wildlands_pcore_wrapper.py
launch_wildlands_pcores.bat
```

Then run:

```text
launch_wildlands_pcores.bat
```

The wrapper automatically detects the P-cores and launches `GRW.exe` using only them.

Tested on:

```text
Intel Core i5-13600K
6 P-cores / 8 E-cores
P-core mask: 0xFFF
```

On this system, the game starts successfully but can remain on the splash screen for **2–3 minutes**.

No DLL injection, no game modification and no BIOS change.

---

## Startup Logger

Use the logger if you want to help investigate the startup problem.

Install `psutil` in PowerShell:

```powershell
python -m pip install psutil
```

Put these files next to `GRW.exe`:

```text
wildlands_startup_logger_v2.py
launch_wildlands_logger_v2.bat
```

Run:

```text
launch_wildlands_logger_v2.bat
```

The logger launches Wildlands normally through Steam **without changing CPU affinity**.

Leave the splash screen running for several minutes.

A CSV file is automatically created with:

* GRW.exe CPU usage
* P-core / E-core usage
* RAM
* threads
* I/O
* PID changes
* startup time

Example:

```text
wildlands_startup_20260812_231649.csv
```

If you share a log, please include your exact CPU model.

---

# Français

## Wrapper P-Core

### Prérequis

* Windows 10/11
* Python 3 64 bits ajouté au `PATH`

Vérification dans PowerShell :

```powershell
python --version
```

### Installation

Placez ces fichiers à côté de `GRW.exe` :

```text
wildlands_pcore_wrapper.py
launch_wildlands_pcores.bat
```

Puis lancez :

```text
launch_wildlands_pcores.bat
```

Le wrapper détecte automatiquement les P-cores et lance `GRW.exe` uniquement dessus.

Testé sur :

```text
Intel Core i5-13600K
6 P-cores / 8 E-cores
Masque P-core : 0xFFF
```

Sur cette configuration, le jeu démarre correctement mais peut rester **2 à 3 minutes** sur le splash screen.

Aucune injection DLL, aucune modification du jeu et aucun changement BIOS.

---

## Logger de démarrage

Le logger permet d'étudier le problème sans modifier l'affinité CPU.

Installez `psutil` dans PowerShell :

```powershell
python -m pip install psutil
```

Placez ces fichiers à côté de `GRW.exe` :

```text
wildlands_startup_logger_v2.py
launch_wildlands_logger_v2.bat
```

Puis lancez :

```text
launch_wildlands_logger_v2.bat
```

Laissez le splash screen tourner plusieurs minutes même si le jeu semble bloqué.

Le logger crée automatiquement un fichier CSV contenant :

* CPU de GRW.exe
* activité P-core / E-core
* RAM
* threads
* I/O
* changements de PID
* temps de démarrage

Si vous partagez un log, indiquez également votre modèle exact de processeur.
