# ADR-0008: Batasan cakupan v1

- **Status:** Diusulkan
- **Tanggal:** 2026-10-12
- **Pengambil keputusan:** Dio Stania Adinata
- **Terkait:** Spesifikasi Desain Engine (Ruang lingkup, Keputusan terbuka), PRD (Non-tujuan)

## Konteks

Setiap fitur realisme menambah kompleksitas ke tiga implementasi simulator (ADR-0002). ADR ini mengelompokkan batasan cakupan v1 supaya alasan dan pemicu peninjauannya tercatat di satu tempat. Bila salah satu batasan dicabut, batasan itu mendapat ADR sendiri.

## Keputusan

| Batasan | Alasan | Pemicu peninjauan |
| --- | --- | --- |
| Bobot pecahan, tanpa lot | Sederhana dan identik antarimplementasi | Saat aset IDX menjadi fokus: lot 100 lembar membuat hasil modal kecil seperti Rp100 juta berbeda nyata |
| Satu kalender bursa per run | Menghindari aturan hari libur yang berbeda antarbursa | Saat dibutuhkan portofolio campuran IDX dan AS |
| Strategi stateless | Determinisme dan kesetaraan `signal` vs `signal_all` mudah dijaga | Saat dibutuhkan stop-loss berbasis harga masuk |
| Adjusted close (total return) | Dividen dan split tercakup tanpa data terpisah | Saat dibutuhkan analisis dividen tunai atau harga level absolut |
| Long-only, tanpa leverage | Bobot selalu di antara 0 dan 1, kas tidak pernah negatif | Saat strategi long-short mulai diuji |
| Data harian saja | Sesuai sumber data gratis dan konvensi eksekusi ADR-0001 | Saat ada sumber data intraday yang bisa direproduksi |

## Konsekuensi

**Positif:**

- Fase 1 sampai 3 tetap dalam cakupan yang realistis.
- Setiap batasan punya pemicu yang jelas, bukan "nanti saja".

**Negatif:**

- Hasil untuk aset IDX dengan modal kecil kurang realistis karena tanpa lot.
- Strategi yang butuh state atau short tidak bisa diuji sampai batasannya dicabut.
