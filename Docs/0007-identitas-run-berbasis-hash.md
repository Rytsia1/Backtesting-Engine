# ADR-0007: Identitas run berbasis hash

- **Status:** Diusulkan
- **Tanggal:** 2026-10-12
- **Pengambil keputusan:** Dio Stania Adinata
- **Terkait:** Spesifikasi Desain Engine (Identitas run dan determinisme), PRD (FR-R1, FR-A2), ADR-0003

## Konteks

Hasil run harus bisa direproduksi, dan API harus idempotent: dua request identik tidak boleh menghasilkan dua run. Kedua kebutuhan itu bisa dipenuhi dengan satu mekanisme bila identitas run diturunkan dari isinya sendiri.

## Opsi yang dipertimbangkan

1. **ID acak (UUID) + idempotency key dari klien.** Standar di API pembayaran, tetapi identitas tidak terkait dengan isi run, sehingga reproducibility harus dijamin terpisah.
2. **ID dari hash isi (konfigurasi + data + versi engine).** Identitas dan reproducibility menjadi satu konsep.
3. **Seperti opsi 2, ditambah git commit.** Paling ketat, tetapi setiap commit, termasuk yang hanya mengubah README, menghasilkan `run_id` baru.

## Keputusan

`run_id` = SHA-256 dari JSON kanonik berisi konfigurasi yang sudah dinormalisasi (semua default diisi eksplisit), `dataset_hash`, dan `engine_version`. `engine_version` berbentuk `<versi package>+<implementasi>`. Versi package naik minor setiap kali perubahan kode bisa mengubah angka hasil. Git commit disimpan sebagai metadata, tidak ikut di-hash.

## Konsekuensi

**Positif:**

- Idempotency API tanpa idempotency key terpisah.
- Run yang sama di mesin berbeda punya `run_id` yang sama.

**Negatif:**

- Kebenaran `run_id` bergantung pada disiplin menaikkan versi package. Lupa menaikkan versi berarti dua hasil berbeda bisa berbagi `run_id`.
- Mitigasi: test regresi angka (golden test) di CI yang gagal bila angka berubah tanpa kenaikan versi minor.

## Kapan ditinjau ulang

Bila lupa menaikkan versi terjadi berulang kali, pertimbangkan hash otomatis atas source code modul engine sebagai bagian dari `engine_version`.
