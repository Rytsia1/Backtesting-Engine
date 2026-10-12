# ADR-0004: C++ untuk core simulator

- **Status:** Diusulkan
- **Tanggal:** 2026-10-12
- **Pengambil keputusan:** Dio Stania Adinata
- **Terkait:** ADR-0002, PRD (Fase 3)

## Konteks

Tujuan karier utama proyek ini adalah posisi quant developer. Banyak lowongan quant developer, terutama di trading firm, mensyaratkan C++. Python sudah cukup untuk kebenaran, sehingga implementasi berperforma tinggi di fase 3 dipilih terutama untuk menunjukkan kemampuan systems programming dan performa.

## Opsi yang dipertimbangkan

1. **Numba.** Paling mudah dan tetap di Python, tetapi sinyalnya lemah untuk lowongan yang meminta C++.
2. **Rust (PyO3 + maturin).** Memory safety dan tooling yang sangat baik, makin sering muncul di lowongan, tetapi masih jauh lebih jarang disyaratkan daripada C++ untuk quant dev.
3. **C++ (pybind11 + scikit-build-core).** Paling sering disyaratkan, binding Python matang. Risikonya bug memori dan kompleksitas build.

## Keputusan

Core simulator fase 3 ditulis dalam **C++ (standar C++20 bila toolchain CI mendukung, C++17 bila tidak)** dengan binding pybind11 dan build lewat scikit-build-core. Cakupannya hanya loop akuntansi: input berupa matriks bobot target dari `signal_all`, matriks return, dan parameter biaya; output berupa equity, holdings, turnover, dan biaya. Strategi tetap di Python.

## Konsekuensi

**Positif:**

- Sinyal paling kuat untuk lowongan quant developer.
- Cakupan sempit membuat fase 3 realistis.
- Implementasi Python berperan sebagai oracle untuk test parity.

**Negatif:**

- Build lebih kompleks, terutama di CI dan untuk membuat wheel.
- Kurva belajar dan risiko bug memori. Mitigasi: sanitizer (ASan, UBSan) di build debug CI.

## Kapan ditinjau ulang

Bila target karier bergeser ke perusahaan yang memakai Rust, atau bila kompleksitas build C++ menghambat fase lain lebih dari beberapa minggu.
