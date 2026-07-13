import matplotlib.pyplot as plt


LITTLE = 0.47  # Mindest-Occupancy


def lese_bloecke(datei):
    bloecke, aktuell = [], None
    for zeile in open(datei, encoding="utf-8"):
        zeile = zeile.strip()
        if not zeile or zeile.startswith("#"):
            aktuell = None
            continue
        werte = zeile.split(",")
        if aktuell is None:          
            aktuell = {"header": werte, "daten": []}
            bloecke.append(aktuell)
        else:
            aktuell["daten"].append(werte)
    return bloecke


def spalte(block, i, typ=float):
    return [typ(zeile[i]) for zeile in block["daten"]]


def peak_aus_kommentar(datei):
    for zeile in open(datei, encoding="utf-8"):
        if "Bandbreite" in zeile:
            return float(zeile.split(":")[-1].replace("GB/s", "").strip())
    return None


# ---- Aufgabe 1: drei Bloecke (Skalierung, GPU-Divergenz, CPU-Divergenz) ----
b1 = lese_bloecke("ergebnisse1.csv")
n, gf_n = spalte(b1[0], 0), spalte(b1[0], 1)
k, gf_gpu = spalte(b1[1], 0), spalte(b1[1], 1)
gf_cpu = spalte(b1[2], 1)

# ---- AVX-Erweiterung: ein Block (k, skalar, avx) ----
b_avx = lese_bloecke("avx.csv")
k_avx, gf_avx = spalte(b_avx[0], 0), spalte(b_avx[0], 2)

# ---- Aufgabe 2: zwei Bloecke (Zugriffsmuster, Occupancy) + Peak ----
b2 = lese_bloecke("ergebnisse2.csv")
PEAK = peak_aus_kommentar("ergebnisse2.csv")
muster = spalte(b2[0], 0, str)
gbs_m = spalte(b2[0], 1)
blk, occ, gbs_o = spalte(b2[1], 0, int), spalte(b2[1], 1), spalte(b2[1], 2)

# ---- Plot 1: Skalierung ueber n ----
plt.figure(figsize=(6, 4))
plt.semilogx(n, gf_n, "o-")
plt.xlabel("Problemgroesse n")
plt.ylabel("GFLOP/s")
plt.title("GPU-Auslastung ueber die Problemgroesse (k=1)")
plt.grid(True, which="both", alpha=0.3)
plt.tight_layout()
plt.savefig("plot1_skalierung.png", dpi=150)

# ---- Plot 2: Divergenz GPU vs. CPU skalar vs. CPU AVX ----
plt.figure(figsize=(6, 4))
plt.loglog(k, gf_gpu, "o-", label="GPU (Warp, 32 Lanes)")
plt.loglog(k_avx, gf_avx, "s-", label="CPU AVX2 (8 Lanes)")
plt.loglog(k, gf_cpu, "^-", label="CPU skalar")
plt.loglog(k, [gf_gpu[0] / x for x in k], "k--", alpha=0.5, label="Ideal 1/k")
plt.xlabel("Divergenzgrad k (Pfade pro Warp/Vektor)")
plt.ylabel("GFLOP/s")
plt.title("Divergenz: SIMT/SIMD serialisiert, skalarer Code nicht")
plt.legend()
plt.grid(True, which="both", alpha=0.3)
plt.tight_layout()
plt.savefig("plot2_divergenz.png", dpi=150)

# ---- Plot 3: Bandbreite nach Zugriffsmuster ----
plt.figure(figsize=(6, 4))
plt.bar(muster, gbs_m)
plt.axhline(PEAK, color="k", linestyle="--", label=f"theor. Peak {PEAK:.0f} GB/s")
plt.ylabel("effektive Bandbreite (GB/s)")
plt.title("Bandbreite nach Zugriffsmuster (Block 256)")
plt.xticks(rotation=30)
plt.legend()
plt.grid(True, axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig("plot3_zugriffsmuster.png", dpi=150)

# ---- Plot 4: Bandbreite ueber Occupancy + Little's-Law-Vorhersage ----
plt.figure(figsize=(6, 4))
plt.plot(occ, gbs_o, "o")
for b, o, g in zip(blk, occ, gbs_o):
    plt.annotate(f"Block {b}", (o, g), textcoords="offset points",
                 xytext=(8, -4), fontsize=8)
plt.axvline(LITTLE, color="r", linestyle="--",
            label=f"Little's Law: min. {100*LITTLE:.0f} % Occupancy")
plt.axhline(PEAK, color="k", linestyle=":", alpha=0.5, label="theor. Peak")
plt.xlabel("Occupancy (aktive / max. Warps)")
plt.ylabel("effektive Bandbreite (GB/s)")
plt.title("Latency Hiding: Bandbreite ueber Occupancy (coalesced)")
plt.legend(fontsize=8)
plt.grid(True, alpha=0.3)
plt.tight_layout()
plt.savefig("plot4_occupancy.png", dpi=150)

print("4 Plots erzeugt.")