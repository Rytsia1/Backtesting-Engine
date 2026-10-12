# ADR-0006: Kas menghasilkan risk-free rate

- **Status:** Diusulkan
- **Tanggal:** 2026-10-12
- **Pengambil keputusan:** Dio Stania Adinata
- **Terkait:** Spesifikasi Desain Engine (Akuntansi portofolio, Metrik)

## Konteks

Strategi seperti time-series momentum sering memegang kas. Untuk aset berdenominasi IDR, risk-free rate jauh lebih tinggi daripada untuk aset berdenominasi USD. Bila kas diasumsikan tidak menghasilkan apa-apa, strategi yang sering memegang kas dirugikan secara tidak realistis, dan Sharpe ratio menjadi tidak konsisten dengan cara excess return dihitung.

## Opsi yang dipertimbangkan

1. **Kas tidak menghasilkan apa-apa.** Paling sederhana, tetapi bias terhadap strategi yang sering di kas.
2. **Kas menghasilkan risk-free rate.** Realistis dan konsisten dengan definisi excess return, tetapi butuh seri data risk-free rate.

## Keputusan

Parameter `cash_yield` dengan nilai `risk_free` (default) atau `zero`. Return kas harian = (1 + y)^(1/252) − 1, dengan y yield tahunan yang diketahui di tanggal t−1. Excess return untuk metrik selalu memakai risk-free rate, apa pun nilai `cash_yield`.

## Konsekuensi

**Positif:**

- Perbandingan strategi yang sering di kas dengan buy-and-hold menjadi adil.
- Strategi 100% kas punya excess return 0, sesuai intuisi.

**Negatif:**

- Butuh sumber seri risk-free rate per mata uang (misalnya yield SBN untuk IDR, T-bill untuk USD). Sumber dan tenornya masih pertanyaan terbuka di PRD.
- Sharpe strategi 100% kas tidak terdefinisi (standar deviasi 0) dan harus dilaporkan sebagai NaN.

## Kapan ditinjau ulang

Ketika sumber data risk-free rate IDR sudah dipilih, atau bila ternyata tidak ada sumber yang bisa direproduksi.
