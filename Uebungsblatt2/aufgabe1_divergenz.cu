
#include <cstdio>
#include <cstdlib>
#include <chrono>

#define ITERS 10000  // arithmetische Iterationen (FMAs) pro Thread

// Rechenintensiver Kernel: 1 Element pro Thread
// Divergenz: die Lanes eines Warps werden über lane % k auf k verschiedene Pfade verteilt. 
// Jeder Pfad leistet gleich viel Arbeit (ITERS FMAs), aber der Warp muss die k Pfade nacheinander abarbeiten -> Laufzeit ~ k-fach.
// k=1 bedeutet keine Divergenz, k=32 heißt: jede Lane nimmt einen eigenen Pfad.
__global__ void alu_kernel(float *out, int n, int k) {
    int i = blockIdx.x * blockDim.x + threadIdx.x;
    if (i >= n) return;
    float x = out[i];
    int lane = threadIdx.x & 31;
    for (int p = 0; p < k; ++p) {
        if (lane % k == p) {
            // Konstante hängt vom Pfad ab, damit der Compiler nichts zusammenlegt
            float a = 1.000001f + p * 1e-7f;
            for (int j = 0; j < ITERS; ++j)
                x = x * a + 1e-6f;   // 1 FMA = 2 FLOPs
        }
    }
    out[i] = x;  // Rückschreiben verhindert Wegoptimieren
}

// Identische Logik auf der CPU: dieselbe Verzweigung über i % k ist dank
// Sprungvorhersage nahezu kostenlos, die Laufzeit bleibt von k unabhängig.
void cpu_version(float *out, int n, int k) {
    for (int i = 0; i < n; ++i) {
        float x = out[i];
        int lane = i & 31;
        for (int p = 0; p < k; ++p) {
            if (lane % k == p) {
                float a = 1.000001f + p * 1e-7f;
                for (int j = 0; j < ITERS; ++j)
                    x = x * a + 1e-6f;
            }
        }
        out[i] = x;
    }
}

// Misst eine Kernel-Ausführung (nach Warmup) und gibt GFLOP/s zurück
float messe_gpu(float *d_out, int n, int k) {
    int block = 256, grid = (n + block - 1) / block;
    alu_kernel<<<grid, block>>>(d_out, n, k);  // Warmup
    cudaDeviceSynchronize();

    cudaEvent_t start, stop;
    cudaEventCreate(&start); cudaEventCreate(&stop);
    cudaEventRecord(start);
    alu_kernel<<<grid, block>>>(d_out, n, k);
    cudaEventRecord(stop);
    cudaEventSynchronize(stop);
    float ms; cudaEventElapsedTime(&ms, start, stop);
    cudaEventDestroy(start); cudaEventDestroy(stop);

    return (2.0f * n * ITERS) / (ms * 1e6f);  // GFLOP/s
}

int main() {
    const int NMAX = 1 << 24;  // 16 Mio. Elemente
    float *d_out;
    cudaMalloc(&d_out, NMAX * sizeof(float));
    cudaMemset(d_out, 0, NMAX * sizeof(float));

    // Teil 1: Skalierung über n (ohne Divergenz)
    printf("# Skalierung ueber n (k=1)\nn,gflops\n");
    for (int n = 1024; n <= NMAX; n *= 4)
        printf("%d,%.1f\n", n, messe_gpu(d_out, n, 1));

    // Teil 2: Divergenzgrad k von 1 (keine) bis 32 (jede Lane ein eigener Pfad)
    printf("\n# Divergenz bei n=%d\nk,gflops\n", NMAX);
    for (int k = 1; k <= 32; k *= 2)
        printf("%d,%.1f\n", k, messe_gpu(d_out, NMAX, k));

    // Teil 3: CPU-Vergleich mit derselben Verzweigung (kleineres n genügt)
    const int NCPU = 1 << 16;
    float *h_out = (float*)calloc(NCPU, sizeof(float));
    printf("\n# CPU-Vergleich bei n=%d\nk,gflops\n", NCPU);
    for (int k = 1; k <= 32; k *= 2) {
        auto t0 = std::chrono::high_resolution_clock::now();
        cpu_version(h_out, NCPU, k);
        auto t1 = std::chrono::high_resolution_clock::now();
        double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
        printf("%d,%.1f\n", k, (2.0 * NCPU * ITERS) / (ms * 1e6));
    }

    free(h_out);
    cudaFree(d_out);
    return 0;
}
