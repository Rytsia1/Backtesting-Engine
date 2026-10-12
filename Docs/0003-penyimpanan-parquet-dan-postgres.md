# ADR-0003: Harga di Parquet, metadata dan hasil di Postgres

- **Status:** Diusulkan
- **Tanggal:** 2026-10-12
- **Pengambil keputusan:** Dio Stania Adinata
- **Terkait:** PRD (Model data), ADR-0007

## Konteks

Ada dua jenis data dengan pola akses berbeda. Harga historis besar, jarang berubah, dibaca utuh per rentang tanggal, dan harus bisa di-hash untuk reproducibility. Metadata dan hasil run kecil, sering di-query dengan filter, dan butuh constraint serta transaksi.

## Opsi yang dipertimbangkan

1. **Semua di Postgres.** Satu sistem, tetapi menyimpan time series harian di tabel relasional lebih lambat untuk analitik dan menyulitkan hashing per dataset.
2. **Semua di Parquet + DuckDB.** Sederhana untuk fase riset, tetapi kurang cocok untuk API multi-request dengan status job dan constraint.
3. **Harga di Parquet, metadata dan hasil di Postgres.** Masing-masing data disimpan di tempat yang sesuai pola aksesnya.

## Keputusan

- Harga disimpan sebagai **snapshot Parquet yang tidak pernah ditimpa**, dengan SHA-256 sebagai identitas dataset. Query analitik atas snapshot memakai DuckDB.
- **Fase 1 (CLI):** setiap run disimpan sebagai direktori `runs/<run_id>/` berisi `config.json`, `equity.parquet`, `trades.parquet`, dan `metrics.json`.
- **Fase 2 (API):** Postgres menyimpan metadata dataset, strategi, run, metrik, equity curve, dan trades. Direktori run fase 1 bisa diimpor.

## Konsekuensi

**Positif:**

- Hash dataset sederhana dan stabil karena satu snapshot adalah satu file.
- Fase 1 tidak butuh server database sama sekali.
- Postgres hanya menyimpan data yang memang butuh constraint dan query.

**Negatif:**

- Dua sistem penyimpanan yang harus konsisten. Mitigasi: tabel `datasets` mencatat hash, dan engine memverifikasi hash file setiap kali snapshot dimuat.
- Ada langkah impor dari format fase 1 ke Postgres.

## Kapan ditinjau ulang

Ketika volume data membuat file Parquet tunggal per snapshot tidak praktis (misalnya data intraday), atau ketika dibutuhkan akses bersama ke snapshot dari beberapa mesin.
