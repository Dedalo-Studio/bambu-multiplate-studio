# Bambu Multi-Plate Studio 🚀

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Bambu Studio](https://img.shields.io/badge/Bambu%20Studio-Compatible-00AE42.svg)](https://bambulab.com)
[![OrcaSlicer](https://img.shields.io/badge/OrcaSlicer-Compatible-0088cc.svg)](https://github.com/SoftFever/OrcaSlicer)

**Bambu Multi-Plate Studio** is a lightweight, modern desktop application designed to solve one of the most frustrating limitations in **Bambu Studio** and **OrcaSlicer**: merging multiple `.3mf` project plates while **preserving independent print profiles, layer heights, infills, and print sequences (e.g. By Layer vs By Object)**.

---

## 💡 The Problem with Bambu Studio

In Bambu Studio, there is only **one global process preset** per project. If you have:
* **Plate 1**: Printed at `0.20 mm` Standard, Grid infill, 2 walls, printed *by layer*.
* **Plate 2**: Printed at `0.08 mm` Extra Fine, Gyroid infill, 6 walls, printed *by object* (sequential printing).

If you try to copy/paste or import plates inside Bambu Studio:
1. Bambu Studio **forces all plates onto the same global process profile**, wiping out your fine layer heights, speeds, or custom support settings.
2. It resets or conflicts with mixed print sequences (*By Layer* on one plate vs *By Object* on another).

### The Solution
The underlying slicing engine (`libslic3r`) actually supports mixed settings, provided they are converted to **object-level parameter overrides** (`<object>` metadata) and **plate-level configuration** (`<plate>` metadata).

**Bambu Multi-Plate Studio** does all the heavy lifting automatically:
- 📐 **Preserves different layer heights** (e.g. Plate 1 at 0.20mm, Plate 2 at 0.08mm).
- ⚡ **Preserves print sequences** (e.g. By Object / sequential printing on specific plates).
- 🎨 **Smart AMS Filament Reconciliation**: automatically maps matching filament colors/types to the same slot to avoid wasting AMS channels.
- 🗺️ **3D Plate Grid Spatial Offset**: shifts each build plate by `+307.2 mm` per column so plates sit in the exact Bambu Studio workspace grid.
- 🖼️ **Thumbnail Previews**: extracts and re-indexes plate thumbnails (`plate_1.png`, `plate_2.png`, etc.).
- 📈 **Preserves variable layer heights** (`layer_heights_profile.txt`) and cut information.

---

## ✨ Features

- **Modern UI**: Dark-themed desktop interface styled to match Bambu Studio.
- **Visual Plate Cards**: Live preview thumbnails, object counts, layer heights, infill badges, wall loops, and filament color swatches.
- **Easy Reordering**: Move plates up/down or remove them with a single click.
- **Configurable Options**:
  - Reconcile matching filaments (AMS optimization).
  - Convert conflicting settings into object-level overrides.
  - Preserve sequential printing per plate.
  - Automatically launch Bambu Studio when merging finishes.
- **Dual Mode**: Can be used via the **GUI app** or via the **command-line (CLI)**.
- **Drag-and-Drop**: Drag `.3mf` files directly onto `Avvia_App.bat` to load them immediately.

---

## 📥 Installation & Running

### Requirements
- Python 3.10 or newer (tested on Python 3.13)
- Windows 10 / 11

### 1. Clone or Download the repository
```bash
git clone https://github.com/Dedalo-Studio/bambu-multiplate-studio.git
cd bambu-multiplate-studio
```

### 2. Install dependencies
```bash
pip install -r requirements.txt
```

### 3. Launch the Application
- **Double click**: `Avvia_App.bat`
- **Or via terminal**:
```bash
python bambu_merger_app.py
```

---

## 💻 CLI Usage

You can also merge 3MF files directly from the command line without opening the GUI:

```bash
python merge_3mf.py "plate1.3mf" "plate2.3mf" "plate3.3mf" -o "merged_project.3mf"
```

Available arguments:
- `-o`, `--output`: Path to the merged `.3mf` file (default: `progetto_unito.3mf`).
- `--no-match-filaments`: Disable automatic filament slot matching.
- `--gui`: Force opening the graphical user interface.

---

## 🛠️ Building Standalone `.exe`

To compile the application into a standalone Windows executable:

```bash
pip install pyinstaller
python -m PyInstaller --noconsole --onedir --collect-data customtkinter --name "BambuPlateMerger" bambu_merger_app.py
```

The resulting executable will be available inside `dist/BambuPlateMerger/BambuPlateMerger.exe`.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
