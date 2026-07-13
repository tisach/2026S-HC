#include <cstdio>
#include <cstdlib>
#include <chrono>
#include <immintrin.h>

#define ITERS 10000
#define N (1 << 16)

// Skalare Referenz: identisch zur CPU-Version aus Aufgabe 1
void skalar(float *out, int n, int k) {
    for (int i = 0; i < n; ++i) {
        float x = out[i];
        for (int p = 0; p < k; ++p) {
            if ((i & 7) % k == p) {
                float a = 1.000001f + p * 1e-7f;
                for (int j = 0; j < ITERS; ++j)
                    x = x * a + 1e-6f;
            }
        }
        out[i] = x;
    }
}

// Maske: welche der 8 Vektor-Lanes gehören zu Pfad p? (Analog zur aktiven Maske eines Warps, nur 8 statt 32 Lanes breit)
__m256 maske(int k, int p) {
    alignas(32) int m[8];
    for (int l = 0; l < 8; ++l) m[l] = ((l % k) == p) ? -1 : 0;
    return _mm256_castsi256_ps(_mm256_load_si256((__m256i*)m));
}

// AVX-Version: der Vektor kann nicht verzweigen
// Wie ein Warp muss er alle k Pfade nacheinander komplett rechnen und per blendv nur die Lanes des jeweiligen Pfads übernehmen
void avx(float *out, int n, int k) {
    __m256 b = _mm256_set1_ps(1e-6f);
    for (int i = 0; i < n; i += 8) {
        __m256 x = _mm256_load_ps(out + i);
        for (int p = 0; p < k; ++p) {
            __m256 a = _mm256_set1_ps(1.000001f + p * 1e-7f);
            __m256 t = x;
            for (int j = 0; j < ITERS; ++j)
                t = _mm256_fmadd_ps(t, a, b);      // 8 FMAs pro Instruktion
            x = _mm256_blendv_ps(x, t, maske(k, p)); // nur Pfad-Lanes übernehmen
        }
        _mm256_store_ps(out + i, x);
    }
}

// Misst GFLOP/s der *nutzbaren* FLOPs (2*n*ITERS), wie in Aufgabe 1
double messe(void (*f)(float*, int, int), float *out, int k) {
    auto t0 = std::chrono::high_resolution_clock::now();
    f(out, N, k);
    auto t1 = std::chrono::high_resolution_clock::now();
    double ms = std::chrono::duration<double, std::milli>(t1 - t0).count();
    return (2.0 * N * ITERS) / (ms * 1e6);
}

int main() {
    float *out = (float*)_aligned_malloc(N * sizeof(float), 32);
    for (int i = 0; i < N; ++i) out[i] = 0.0f;

    // k maximal 8, da der AVX-Vektor nur 8 Lanes hat (Warp: 32)
    printf("k,gflops_skalar,gflops_avx\n");
    for (int k = 1; k <= 8; k *= 2)
        printf("%d,%.1f,%.1f\n", k, messe(skalar, out, k), messe(avx, out, k));

    _aligned_free(out);
    return 0;
}