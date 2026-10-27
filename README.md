# Bambu Multi-Plate Studio 🚀

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Bambu Studio](https://img.shields.io/badge/Bambu%20Studio-Compatible-00AE42.svg)](https://bambulab.com)
[![OrcaSlicer](https://img.shields.io/badge/OrcaSlicer-Compatible-0088cc.svg)](https://github.com/SoftFever/OrcaSlicer)
[![Release](https://img.shields.io/github/v/release/Dedalo-Studio/bambu-multiplate-studio?color=orange)](https://github.com/Dedalo-Studio/bambu-multiplate-studio/releases/latest)

[🇮🇹 **Italiano**](#-italiano) | [🇬🇧 **English**](#-english)

---

## 🇮🇹 Italiano

**Bambu Multi-Plate Studio** è un'applicazione desktop moderna e veloce progettata per superare uno dei limiti più frustranti di **Bambu Studio** e **OrcaSlicer**: l'impossibilità di unire più piatti provenienti da diversi file `.3mf` mantenendo per ciascuno le **proprie impostazioni di stampa indipendenti (altezze layer, riempimenti, velocità e sequenza di stampa Per Livello vs Per Oggetto)**.

### 💡 Il Problema in Bambu Studio
In Bambu Studio esiste **un unico profilo di processo globale per progetto**. Se ad esempio possiedi:
* **Piatto 1**: Profilo `0.20 mm Standard`, riempimento Griglia, 2 perimetri, stampato *per livello*.
* **Piatto 2**: Profilo `0.08 mm Extra Fine`, riempimento Giroide, 6 perimetri, stampato *per oggetto* (stampa sequenziale).

Se provi a fare copia/incolla o ad importare piatti in Bambu Studio:
1. Il software **appiattisce tutti i piatti sullo stesso preset globale**, cancellando le altezze layer fini o i supporti personalizzati del secondo piatto.
2. Non permette di gestire facilmente sequenze miste (*Stampa per livello* su un piatto e *Stampa per oggetto* sull'altro).

### 🛠️ La Soluzione
Il motore di slicing (`libslic3r`) in realtà supporta parametri differenti, a patto che vengano convertiti in **override a livello di oggetto** (`<object>`) e configurazioni specifiche del piatto (`<plate>`).

**Bambu Multi-Plate Studio** automatizza tutto questo processo:
- 📐 **Preserva altezze layer differenti nello stesso progetto** (es. Piatto 1 a 0.20mm e Piatto 2 a 0.08mm).
- ⚡ **Preserva la sequenza di stampa per singolo piatto** (es. *Stampa per Oggetto* solo dove serve).
- 🎨 **Mappatura Intelligente Filamenti AMS**: associa automaticamente i filamenti dello stesso colore e materiale sullo stesso slot per non sprecare canali dell'AMS.
- 🗺️ **Disposizione Automatica nella Griglia 3D**: trasla i piatti con il passo esatto di Bambu Studio (`+307.2 mm` per colonna) evitando sovrapposizioni visive nel piano di lavoro.
- 🖼️ **Miniature Reali dei Piatti**: estrae e indicizza le anteprime renderizzate (`plate_1.png`, `plate_2.png`, ecc.).
- 📈 **Preserva layer variabili** (`layer_heights_profile.txt`) e dati di taglio.

---

### 📦 Download Diretto

Non è necessario installare Python! Puoi scaricare la versione pre-compilata:

#### 🪟 Windows
* 💾 [**Scarica Eseguibile Standalone (.exe)**](https://github.com/Dedalo-Studio/bambu-multiplate-studio/releases/latest/download/BambuPlateMerger.exe) — *Avvio immediato, file singolo portatile*.
* 📦 [**Scarica Archivio Completo (.zip)**](https://github.com/Dedalo-Studio/bambu-multiplate-studio/releases/latest/download/BambuPlateMerger-v1.0.0-windows.zip) — *Pacchetto zip estraibile*.

#### 🍎 macOS
* 🍏 [**Scarica Applicazione per macOS (.zip)**](https://github.com/Dedalo-Studio/bambu-multiplate-studio/releases/latest/download/BambuPlateMerger-macOS.zip) — *Contiene `BambuPlateMerger.app` nativa per Mac*.

---

### 🚀 Come Usare l'Applicazione

#### Metodo Grafico (GUI)
1. Avvia **`BambuPlateMerger.exe`** (oppure `Avvia_App.bat` se usi il codice sorgente).
2. Clicca su **`+ Aggiungi File .3MF`** (oppure trascina i file 3MF sopra l'icona dell'app).
3. Visualizza le schede con le miniature e i parametri rilevati (puoi riordinare i piatti con ▲ / ▼).
4. Scegli le opzioni desiderate nel pannello in basso (riconciliazione filamenti, sequenza, ecc.).
5. Clicca su **`🚀 Unisci Piatti in un Unico File 3MF`**: il file unito si genererà in un istante e, se attivo, si aprirà subito in Bambu Studio pronto per lo slicing!

#### Metodo da Riga di Comando (CLI)
Puoi usare il motore di fusione direttamente dal terminale:
```bash
python merge_3mf.py "piatto1.3mf" "piatto2.3mf" "piatto3.3mf" -o "progetto_unito.3mf"
```

---

### 💻 Installazione da Sorgente Python (Opzionale)

Se preferisci eseguire il codice sorgente Python:

1. Clona il repository:
   ```bash
   git clone https://github.com/Dedalo-Studio/bambu-multiplate-studio.git
   cd bambu-multiplate-studio
   ```
2. Installa i requisiti:
   ```bash
   pip install -r requirements.txt
   ```
3. Avvia l'interfaccia:
   ```bash
   python bambu_merger_app.py
   ```

---

## 🇬🇧 English

**Bambu Multi-Plate Studio** is a lightweight, modern desktop application designed to solve one of the most frustrating limitations in **Bambu Studio** and **OrcaSlicer**: merging multiple `.3mf` project plates while **preserving independent print profiles, layer heights, infills, and print sequences (e.g. By Layer vs By Object)**.

### 💡 The Problem with Bambu Studio
In Bambu Studio, there is only **one global process preset** per project. If you have:
* **Plate 1**: Printed at `0.20 mm` Standard, Grid infill, 2 walls, printed *by layer*.
* **Plate 2**: Printed at `0.08 mm` Extra Fine, Gyroid infill, 6 walls, printed *by object* (sequential printing).

If you try to copy/paste or import plates inside Bambu Studio:
1. Bambu Studio **forces all plates onto the same global process profile**, wiping out your fine layer heights, speeds, or custom support settings.
2. It resets or conflicts with mixed print sequences (*By Layer* on one plate vs *By Object* on another).

### 🛠️ The Solution
The underlying slicing engine (`libslic3r`) actually supports mixed settings, provided they are converted to **object-level parameter overrides** (`<object>` metadata) and **plate-level configuration** (`<plate>` metadata).

**Bambu Multi-Plate Studio** does all the heavy lifting automatically:
- 📐 **Preserves different layer heights** (e.g. Plate 1 at 0.20mm, Plate 2 at 0.08mm).
- ⚡ **Preserves print sequences** (e.g. By Object / sequential printing on specific plates).
- 🎨 **Smart AMS Filament Reconciliation**: automatically maps matching filament colors/types to the same slot to avoid wasting AMS channels.
- 🗺️ **3D Plate Grid Spatial Offset**: shifts each build plate by `+307.2 mm` per column so plates sit in the exact Bambu Studio workspace grid.
- 🖼️ **Thumbnail Previews**: extracts and re-indexes plate thumbnails (`plate_1.png`, `plate_2.png`, etc.).
- 📈 **Preserves variable layer heights** (`layer_heights_profile.txt`) and cut information.

---

### 📦 Direct Downloads

No Python installation required:

#### 🪟 Windows
* 💾 [**Download Standalone Executable (.exe)**](https://github.com/Dedalo-Studio/bambu-multiplate-studio/releases/latest/download/BambuPlateMerger.exe) — *Single portable file, runs instantly*.
* 📦 [**Download Complete Archive (.zip)**](https://github.com/Dedalo-Studio/bambu-multiplate-studio/releases/latest/download/BambuPlateMerger-v1.0.0-windows.zip) — *Extractable zip package*.

#### 🍎 macOS
* 🍏 [**Download macOS Application (.zip)**](https://github.com/Dedalo-Studio/bambu-multiplate-studio/releases/latest/download/BambuPlateMerger-macOS.zip) — *Contains native `BambuPlateMerger.app` bundle*.

---

### 🚀 How to Use

#### Graphical Interface (GUI)
1. Run **`BambuPlateMerger.exe`** (or `Avvia_App.bat` if running from source).
2. Click **`+ Aggiungi File .3MF`** or drag and drop `.3mf` files onto the window.
3. Review the visual plate cards and adjust plate order (▲ / ▼).
4. Configure options in the bottom panel (filament matching, sequence preservation, etc.).
5. Click **`🚀 Unisci Piatti in un Unico File 3MF`**: the merged file will be generated and can automatically launch in Bambu Studio!

#### Command-Line Interface (CLI)
```bash
python merge_3mf.py "plate1.3mf" "plate2.3mf" "plate3.3mf" -o "merged_project.3mf"
```

---

### 🛠️ Building Standalone `.exe`

To build the standalone single-file `.exe` executable yourself:

```bash
pip install pyinstaller
python -m PyInstaller --noconsole --onefile --collect-data customtkinter --name "BambuPlateMerger" bambu_merger_app.py
```

The compiled file will be located at `dist/BambuPlateMerger.exe`.

---

## 📄 License

This project is licensed under the [MIT License](LICENSE).
