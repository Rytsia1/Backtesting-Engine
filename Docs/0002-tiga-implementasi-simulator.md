# ADR-0002: Tiga implementasi simulator dengan satu referensi

- **Status:** Diusulkan
- **Tanggal:** 2026-10-12
- **Pengambil keputusan:** Dio Stania Adinata
- **Terkait:** Spesifikasi Desain Engine (Akuntansi portofolio, Interface strategi, Test), ADR-0004

## Konteks

Backtest butuh dua hal yang saling bertentangan: kebenaran yang bisa dibuktikan dan kecepatan untuk parameter sweep. Satu implementasi saja tidak bisa memverifikasi dirinya sendiri, karena bug di akuntansi akan menghasilkan angka yang konsisten tetapi salah.

## Opsi yang dipertimbangkan

1. **Hanya vectorized.** Cepat, tetapi canggung untuk logika yang bergantung pada path dan tidak punya pembanding.
2. **Hanya event-driven.** Mudah dipahami dan dekat dengan cara pasar bekerja, tetapi lambat untuk sweep.
3. **Memakai library yang sudah ada sebagai engine.** Menghilangkan inti proyek. Library tetap dipakai, tetapi hanya sebagai pembanding hasil.
4. **Beberapa implementasi yang diuji satu sama lain.** Lebih banyak kode, tetapi setiap ketidaksesuaian menjadi sinyal bug.

## Keputusan

Engine punya tiga implementasi akuntansi yang mengikuti persamaan yang sama di spesifikasi:

| Implementasi | Peran | Input strategi |
| --- | --- | --- |
| Python event-driven | Referensi (sumber kebenaran) | `signal` per bar |
| Python vectorized | Jalur cepat untuk sweep | `signal_all` |
| C++ | Jalur cepat dan sinyal portofolio quant dev | `signal_all` |

Implementasi vectorized dan C++ wajib identik dengan referensi dalam toleransi relatif 1e-10 pada equity di setiap tanggal. Toleransi ini sementara dan divalidasi ulang setelah implementasi pertama.

## Konsekuensi

**Positif:**

- Bug akuntansi terdeteksi sebagai ketidaksesuaian antarimplementasi.
- Cerita yang kuat untuk portofolio: kebenaran dibuktikan lewat differential testing, bukan diklaim.
- Strategi dan akuntansi terpisah tegas.

**Negatif:**

- Setiap perubahan persamaan akuntansi harus diterapkan tiga kali.
- Mitigasi: persamaan hanya didefinisikan di spesifikasi, dan test parity berjalan di CI untuk setiap commit.

## Kapan ditinjau ulang

Ketika biaya memelihara tiga implementasi jelas melebihi manfaatnya, misalnya bila implementasi vectorized tidak lagi dibutuhkan setelah core C++ cukup cepat.
