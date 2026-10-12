# ADR-0005: Model biaya transaksi dan slippage

- **Status:** Diusulkan
- **Tanggal:** 2026-10-12
- **Pengambil keputusan:** Dio Stania Adinata
- **Terkait:** Spesifikasi Desain Engine (Akuntansi portofolio), ADR-0002

## Konteks

Biaya transaksi sering menjadi pembeda antara strategi yang tampak menguntungkan dan yang benar-benar menguntungkan. Model biaya juga harus bisa diimplementasikan identik di tiga simulator (ADR-0002).

## Opsi yang dipertimbangkan

1. **Slippage sebagai penyesuaian harga eksekusi, biaya dipotong dari kas.** Intuitif, tetapi kas bisa negatif saat bobot 100% dan sulit dibuat identik secara eksak antarimplementasi.
2. **Biaya dan slippage sebagai persentase notional, dipotong proporsional dari seluruh posisi.** Sederhana, eksak, dan bobot pasca-transaksi tepat sama dengan target.

## Keputusan

Biaya per periode κ_t = (c + s) × 10⁻⁴ × τ_t, dengan c biaya transaksi dan s slippage dalam basis poin, dan τ_t turnover aset (tanpa kas). Biaya dipotong proporsional dari seluruh posisi termasuk kas, sehingga V_t = V_{t−1}(1 + R_t)(1 − κ_t). Tidak ada biaya tetap atau komisi minimum di v1.

## Konsekuensi

**Positif:**

- Ketiga implementasi bisa identik secara eksak.
- Kas tidak pernah negatif, bobot pasca-transaksi tepat sama dengan target.
- Biaya terlihat jelas sebagai satu seri κ_t.

**Negatif:**

- Biaya beli dan jual dianggap sama. Di IDX biaya jual umumnya lebih tinggi daripada biaya beli karena pajak penjualan saham, jadi model ini sedikit meremehkan biaya untuk strategi dengan turnover tinggi.
- Komisi minimum per transaksi tidak dimodelkan, sehingga hasil dengan modal kecil terlalu optimistis.

## Kapan ditinjau ulang

Ketika aset IDX menjadi fokus utama: tambahkan biaya beli dan jual terpisah (`cost_buy_bps`, `cost_sell_bps`) sebagai ADR baru.
