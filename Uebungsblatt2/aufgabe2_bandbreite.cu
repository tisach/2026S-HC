#include <cstdio>
#include <cstdlib>
#include <algorithm>
#include <random>

// Speicherintensiver Streaming-Kernel mit minimaler Arithmetik: b[i] = a[i] * c
// Das Zugriffsmuster wird über ein Index-Array idx gesteuert, der Kernel selbst bleibt für alle drei Muster identisch
__global__ void stream_kernel(const float *a, float *b, const int *idx, int n, float c) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i < n) b[i] = a[idx[i]] * c;
}

// Misst eine Kernel-Ausführung (nach Warmup) und gibt GB/s zurück.
// Bewegte Bytes: Lesen von a und idx, Schreiben von b = 12 Byte pro Element.
float messe(const float *a, float *b, const int *idx, int n, int block) {
    const int REPS = 5;
    int grid = (n + block - 1) / block;
    // Mehrfacher Warmup: ein einzelner Launch reicht nicht, damit die GPU ihre Boost-Taktraten erreicht
    for (int r = 0; r < 3; ++r)
        stream_kernel<<<grid, block>>>(a, b, idx, n, 2.0f);
    cudaDeviceSynchronize();

    cudaEvent_t start, stop;
    cudaEventCreate(&start); cudaEventCreate(&stop);
    cudaEventRecord(start);
    for (int r = 0; r < REPS; ++r)  // Mittelung über mehrere Läufe
        stream_kernel<<<grid, block>>>(a, b, idx, n, 2.0f);
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    float ms; cudaEventElapsedTime(&ms, start, stop);
    cudaEventDestroy(start); cudaEventDestroy(stop);

    return (12.0f * n * REPS) / (ms * 1e6f);  // GB/s
}

int main() {
    const int N = 1 << 24;  // 16 Mio. Elemente

    // Theoretische Spitzenbandbreite: Speichertakt (kHz) x Busbreite x 2 (DDR).
    // Ab CUDA 13 gibt es memoryClockRate nicht mehr im Struct, daher Attribut-API.
    cudaDeviceProp prop;
    cudaGetDeviceProperties(&prop, 0);
    int takt_khz, bus_bit;
    cudaDeviceGetAttribute(&takt_khz, cudaDevAttrMemoryClockRate, 0);
    cudaDeviceGetAttribute(&bus_bit, cudaDevAttrGlobalMemoryBusWidth, 0);
    float peak = 2.0f * takt_khz * (bus_bit / 8) / 1e6f;
    printf("# GPU: %s, theoretische Bandbreite: %.0f GB/s\n", prop.name, peak);

    float *d_a, *d_b;
    int *d_idx;
    cudaMalloc(&d_a, N * sizeof(float));
    cudaMalloc(&d_b, N * sizeof(float));
    cudaMalloc(&d_idx, N * sizeof(int));
    cudaMemset(d_a, 0, N * sizeof(float));

    int *h_idx = (int*)malloc(N * sizeof(int));

    // Teil 1: drei Zugriffsmuster bei fester Blockgröße 256
    // Coalesced (Stride 1), gestriped (Stride k) und zufällig (Gather)
    printf("\n# Zugriffsmuster (Blockgroesse 256)\nmuster,gbs,prozent_vom_peak\n");

    for (int i = 0; i < N; ++i) h_idx[i] = i;  // Stride 1
    cudaMemcpy(d_idx, h_idx, N * sizeof(int), cudaMemcpyHostToDevice);
    float gbs = messe(d_a, d_b, d_idx, N, 256);
    printf("coalesced,%.1f,%.0f%%\n", gbs, 100 * gbs / peak);

    for (int k = 2; k <= 32; k *= 2) {  // Stride k: benachbarte Threads greifen k Elemente auseinander zu
        for (int i = 0; i < N; ++i) h_idx[i] = (long long)i * k % N;
        cudaMemcpy(d_idx, h_idx, N * sizeof(int), cudaMemcpyHostToDevice);
        gbs = messe(d_a, d_b, d_idx, N, 256);
        printf("stride_%d,%.1f,%.0f%%\n", k, gbs, 100 * gbs / peak);
    }

    for (int i = 0; i < N; ++i) h_idx[i] = i;  // Gather: zufällige Permutation
    std::shuffle(h_idx, h_idx + N, std::mt19937(42));
    cudaMemcpy(d_idx, h_idx, N * sizeof(int), cudaMemcpyHostToDevice);
    gbs = messe(d_a, d_b, d_idx, N, 256);
    printf("gather,%.1f,%.0f%%\n", gbs, 100 * gbs / peak);

    // Teil 2: Latency Hiding über die Occupancy — Blockgröße variieren.
    // Occupancy = aktive Warps / maximal mögliche aktive Warps pro SM.
    // Coalesced-Muster, damit nur der Warp-Effekt sichtbar wird.
    for (int i = 0; i < N; ++i) h_idx[i] = i;
    cudaMemcpy(d_idx, h_idx, N * sizeof(int), cudaMemcpyHostToDevice);
    int max_warps = prop.maxThreadsPerMultiProcessor / 32;

    printf("\n# Occupancy (coalesced)\nblockgroesse,occupancy,gbs\n");
    for (int block = 32; block <= 1024; block *= 2) {
        int blocks_pro_sm;
        cudaOccupancyMaxActiveBlocksPerMultiprocessor(&blocks_pro_sm, stream_kernel, block, 0);
        float occ = (float)(blocks_pro_sm * block / 32) / max_warps;
        printf("%d,%.2f,%.1f\n", block, occ, messe(d_a, d_b, d_idx, N, block));
    }

    free(h_idx);
    cudaFree(d_a); cudaFree(d_b); cudaFree(d_idx);
    return 0;
}
