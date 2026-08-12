# Ghost Recon Wildlands — Hybrid CPU Fix

Simple workaround for **Ghost Recon Wildlands** on modern Intel CPUs with **P-cores and E-cores**.

On some Intel 12th, 13th and 14th Gen CPUs, Wildlands may stay stuck on the splash screen or take several minutes to start.

This wrapper launches the game using only the **P-cores**.

---

# English

## Installation

1. Download:

   * `wildlands_pcore_wrapper.py`
   * `launch_wildlands_pcores.bat`

2. Copy both files directly into your **Ghost Recon Wildlands** folder.

Example:

```text
D:\SteamLibrary\steamapps\common\Wildlands\
```

Your folder should look like this:

```text
Wildlands\
├── GRW.exe
├── wildlands_pcore_wrapper.py
├── launch_wildlands_pcores.bat
└── ...
```

3. Double-click:

```text
launch_wildlands_pcores.bat
```

That's it.

The wrapper automatically detects the P-cores and launches `GRW.exe` with the correct CPU affinity.

## Tested on

```text
Intel Core i5-13600K

6 P-cores / 12 threads
8 E-cores

P-core affinity:
0xFFF
```

The game successfully starts without disabling the E-cores in the BIOS.

On the tested system, the splash screen may still stay visible for around **2–3 minutes** before the game window appears.

## What does it do?

The wrapper:

```text
Detects CPU topology
        ↓
Finds the P-cores
        ↓
Creates the CPU affinity mask
        ↓
Launches GRW.exe
        ↓
Runs Wildlands only on P-cores
```

It does **not**:

* modify the game files;
* inject DLLs;
* patch memory;
* modify Easy Anti-Cheat;
* disable E-cores globally;
* change BIOS settings.

It only uses standard Windows CPU affinity functions.

## Requirements

* Windows 10 or Windows 11
* Python 3
* Ghost Recon Wildlands
* Intel hybrid CPU

No additional Python packages are required.

## Troubleshooting

If the game stays on the splash screen, wait a few minutes.

On the tested i5-13600K, Wildlands can take approximately:

```text
2–3 minutes
```

before displaying the game window.

You can also check the detected CPU topology with:

```powershell
py -3 wildlands_pcore_wrapper.py --test
```

---

# Français

## Installation

1. Téléchargez :

   * `wildlands_pcore_wrapper.py`
   * `launch_wildlands_pcores.bat`

2. Copiez directement les deux fichiers dans le dossier de **Ghost Recon Wildlands**.

Exemple :

```text
D:\SteamLibrary\steamapps\common\Wildlands\
```

Le dossier doit ressembler à ceci :

```text
Wildlands\
├── GRW.exe
├── wildlands_pcore_wrapper.py
├── launch_wildlands_pcores.bat
└── ...
```

3. Double-cliquez sur :

```text
launch_wildlands_pcores.bat
```

C'est tout.

Le wrapper détecte automatiquement les P-cores et lance `GRW.exe` avec la bonne affinité CPU.

## Configuration testée

```text
Intel Core i5-13600K

6 P-cores / 12 threads
8 E-cores

Affinité P-cores :
0xFFF
```

Le jeu démarre correctement sans avoir besoin de désactiver les E-cores dans le BIOS.

Sur la configuration testée, le splash screen peut néanmoins rester affiché environ **2 à 3 minutes** avant l'apparition de la fenêtre du jeu.

## Fonctionnement

Le wrapper :

```text
Détecte le processeur
        ↓
Identifie les P-cores
        ↓
Génère le masque d'affinité
        ↓
Lance GRW.exe
        ↓
Wildlands utilise uniquement les P-cores
```

Le wrapper ne :

* modifie pas les fichiers du jeu ;
* n'injecte aucune DLL ;
* ne modifie pas la mémoire du jeu ;
* ne modifie pas Easy Anti-Cheat ;
* ne désactive pas les E-cores pour Windows ;
* ne modifie pas le BIOS.

Il utilise uniquement les fonctions standards de gestion de l'affinité CPU de Windows.

## Prérequis

* Windows 10 ou Windows 11
* Python 3
* Ghost Recon Wildlands
* processeur Intel hybride P-core / E-core

Aucune bibliothèque Python supplémentaire n'est nécessaire.

## En cas de problème

Si le jeu reste sur le splash screen, attendez quelques minutes.

Sur le i5-13600K utilisé pour les tests, Wildlands peut mettre environ :

```text
2 à 3 minutes
```

avant d'afficher la fenêtre du jeu.

Pour vérifier la détection du processeur :

```powershell
py -3 wildlands_pcore_wrapper.py --test
```

## Goal / Objectif

The goal is simple: make **Ghost Recon Wildlands** work correctly on modern Intel hybrid CPUs without disabling E-cores in the BIOS.

L'objectif est simple : permettre à **Ghost Recon Wildlands** de fonctionner correctement sur les processeurs Intel hybrides modernes sans désactiver les E-cores dans le BIOS.
