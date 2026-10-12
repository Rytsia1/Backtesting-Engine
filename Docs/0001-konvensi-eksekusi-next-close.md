# ADR-0001: Konvensi eksekusi `next_close`

- **Status:** Diusulkan
- **Tanggal:** 2026-10-12
- **Pengambil keputusan:** Dio Stania Adinata
- **Terkait:** Spesifikasi Desain Engine (Konvensi waktu dan eksekusi), ADR-0002

## Konteks

Engine memakai data harian. Sinyal yang dihitung dari harga close hari t baru bisa diketahui setelah pasar tutup di hari t. Konvensi eksekusi menentukan kapan sinyal itu boleh memengaruhi posisi, dan konvensi yang salah adalah sumber look-ahead bias yang paling umum di backtest.

## Opsi yang dipertimbangkan

1. **Close yang sama (close t).** Paling sederhana dan sering dipakai di tutorial. Ditolak karena mengasumsikan sinyal bisa dihitung dan order masuk sebelum harga close yang dipakai untuk menghitungnya diketahui.
2. **Open berikutnya (open t+1).** Realistis untuk order yang dikirim sebelum pasar buka. Butuh harga open yang di-adjust dan memecah return satu periode menjadi dua bagian (close t ke open t+1 dengan bobot lama, open t+1 ke close t+1 dengan bobot baru).
3. **Close berikutnya (close t+1).** Konservatif, cukup dengan data close, dan perhitungannya paling sederhana.

## Keputusan

Default dan satu-satunya mode wajib di v1 adalah **close t+1** (`next_close`). Bobot yang diputuskan di close d dieksekusi di close d+1 dan pertama kali menghasilkan return di periode d+2, sehingga h_t = w*_{t−2}. Mode `next_open` boleh ditambahkan belakangan sebagai opsi. Eksekusi di close yang sama tidak disediakan sebagai flag konfigurasi; studi dampak look-ahead dilakukan di test atau notebook terpisah.

## Konsekuensi

**Positif:**

- Look-ahead bias dari timing eksekusi tertutup secara struktural.
- Hanya butuh harga adjusted close.
- Test lag eksekusi punya definisi yang presisi.

**Negatif:**

- Ada lag satu periode penuh. Strategi dengan sinyal cepat (misalnya mean reversion jangka pendek) akan tampak lebih buruk daripada kenyataannya.
- Buy-and-hold baru membeli di close 1, sehingga invarian test-nya menjadi V_T / V_0 = P_T / P_1, bukan rasio harga akhir/awal.

## Kapan ditinjau ulang

Ketika strategi dengan horizon pendek (beberapa hari) mulai diuji dan lag satu periode mendominasi hasil, atau ketika data open yang di-adjust tersedia dengan kualitas yang bisa diverifikasi.
