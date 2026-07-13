// Erweiterung zu Aufgabe 2: Speicherlatenz messen und mit Little's Law den
// noetigen Parallelitaetsgrad *vorhersagen*, der die Bandbreite saettigt.
// Little's Law: Bytes "in flight" = Bandbreite x Latenz. Daraus folgt, wie
// viele Warps pro SM mindestens ausstehende Anfragen halten muessen.
// Kompilieren: nvcc -O3 -o latenz.exe aufgabe2_latenz.cu

#include <cstdio>
#include <cstdlib>
#include <random>
#include <numeric>

#define STEPS (1 << 20)  // Anzahl Zeigerverfolgungs-Schritte

// Pointer Chasing mit einem einzigen Thread: jeder Zugriff haengt vom
// vorherigen ab, nichts ueberlappt -> misst die rohe DRAM-Latenz pro Zugriff.
// Genau diese Latenz muss die GPU sonst durch viele Warps verstecken.
__global__ void chase(const int *next, int steps, int *out) {
    int i = 0;
    for (int s = 0; s < steps; ++s) i = next[i];
    *out = i;  // verhindert Wegoptimieren
}

int main() {
    // Array deutlich groesser als der L2-Cache (RTX 3070: 4 MB), damit
    // wirklich DRAM-Latenz gemessen wird und nicht die Cache-Latenz
    const int M = 1 << 25;  // 32 Mio. Eintraege = 128 MB
    int *h_next = (int*)malloc(M * sizeof(int));

    // Zufaelliger Zyklus ueber alle M Eintraege (Sattolo-Algorithmus),
    // damit weder Cache noch Prefetcher das Muster vorhersagen koennen
    std::iota(h_next, h_next + M, 0);
    std::mt19937 rng(42);
    int *perm = (int*)malloc(M * sizeof(int));
    std::iota(perm, perm + M, 0);
    for (int i = M - 1; i > 0; --i) {
        std::uniform_int_distribution<int> d(0, i - 1);
        std::swap(perm[i], perm[d(rng)]);
    }
    for (int i = 0; i < M; ++i)
        h_next[perm[i]] = perm[(i + 1) % M];

    int *d_next, *d_out;
    cudaMalloc(&d_next, M * sizeof(int));
    cudaMalloc(&d_out, sizeof(int));
    cudaMemcpy(d_next, h_next, M * sizeof(int), cudaMemcpyHostToDevice);

    chase<<<1, 1>>>(d_next, STEPS, d_out);  // Warmup
    cudaDeviceSynchronize();

    cudaEvent_t start, stop;
    cudaEventCreate(&start); cudaEventCreate(&stop);
    cudaEventRecord(start);
    chase<<<1, 1>>>(d_next, STEPS, d_out);
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    float ms; cudaEventElapsedTime(&ms, start, stop);
    float latenz_ns = ms * 1e6f / STEPS;

    // Geraetedaten fuer die Little's-Law-Rechnung
    cudaDeviceProp prop;
    cudaGetDeviceProperties(&prop, 0);
    int takt_khz, bus_bit;
    cudaDeviceGetAttribute(&takt_khz, cudaDevAttrMemoryClockRate, 0);
    cudaDeviceGetAttribute(&bus_bit, cudaDevAttrGlobalMemoryBusWidth, 0);
    float peak = 2.0f * takt_khz * (bus_bit / 8) / 1e6f;  // GB/s

    // Little's Law: um die Bandbreite zu saettigen, muessen so viele Bytes
    // gleichzeitig unterwegs sein wie in einer Latenzperiode transportierbar
    float bytes_in_flight = peak * latenz_ns;               // GB/s * ns = Byte
    // Annahme: ein Warp haelt beim coalesced Streaming ca. eine ausstehende
    // 128-Byte-Ladeanfrage (32 Threads x 4 Byte)
    float warps_gesamt = bytes_in_flight / 128.0f;
    float warps_pro_sm = warps_gesamt / prop.multiProcessorCount;
    int max_warps = prop.maxThreadsPerMultiProcessor / 32;

    printf("GPU: %s (%d SMs, max. %d Warps/SM)\n",
           prop.name, prop.multiProcessorCount, max_warps);
    printf("Gemessene DRAM-Latenz:      %.0f ns\n", latenz_ns);
    printf("Theoretische Bandbreite:    %.0f GB/s\n", peak);
    printf("Bytes in flight (BW x Lat): %.0f Byte\n", bytes_in_flight);
    printf("Noetige Warps gesamt:       %.0f\n", warps_gesamt);
    printf("Noetige Warps pro SM:       %.1f  -> Mindest-Occupancy: %.0f%%\n",
           warps_pro_sm, 100.0f * warps_pro_sm / max_warps);

    free(h_next); free(perm);
    cudaFree(d_next); cudaFree(d_out);
    return 0;
}
