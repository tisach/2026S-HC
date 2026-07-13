# Übungsblatt 2 — SIMT & Warp-Divergenz, Bandbreite & Latency Hiding

Vier CUDA/C++-Benchmarks zur RTX 3070, die die Kosten der Warp-Divergenz (Aufgabe 1) und den Einfluss von Zugriffsmuster und Occupancy auf die Speicherbandbreite (Aufgabe 2) messen. Zwei Erweiterungen zeigen zusätzlich, dass Divergenz eine SIMD-Eigenschaft ist (AVX2) und wie sich der nötige Parallelitätsgrad mit Little's Law vorhersagen lässt.

## Dateien

| Datei | Inhalt |
|---|---|
| `aufgabe1_divergenz.cu` | Aufgabe 1: Skalierung über n und Divergenzgrad k |
| `aufgabe1_avx.cpp` | Erweiterung 1: dieselbe Divergenz mit AVX2 auf der CPU |
| `aufgabe2_bandbreite.cu` | Aufgabe 2: Zugriffsmuster und Occupancy |
| `aufgabe2_latenz.cu` | Erweiterung 2: DRAM-Latenz + Little's-Law-Vorhersage |
| `plots.py` | erzeugt die vier Abbildungen aus den CSVs |
| `bericht_hc_übungsblatt2.pdf` | Ergebnisbericht |

## Kompilieren und Ausführen

Die Programme wurden in der **x64 Native Tools Command Prompt for VS 2022** ausgeführt:

```
nvcc -O3 -o aufgabe1     aufgabe1_divergenz.cu
nvcc -O3 -o aufgabe2     aufgabe2_bandbreite.cu
nvcc -O3 -o latenz       aufgabe2_latenz.cu
cl   /O2 /arch:AVX2 /EHsc aufgabe1_avx.cpp

aufgabe1.exe     > ergebnisse1.csv
aufgabe1_avx.exe > avx.csv
aufgabe2.exe     > ergebnisse2.csv
latenz.exe       > latenz.txt

```

Getestet auf Windows mit CUDA Toolkit 13 und MSVC Build Tools 2022.
