# Architecture Decision Records

Folder ini mencatat keputusan desain penting untuk Quant Research & Backtesting Platform. Setiap ADR menjelaskan konteks, opsi yang dipertimbangkan, keputusan, dan konsekuensinya.

## Status

| Status | Arti |
| --- | --- |
| Diusulkan | Sudah dipakai sementara di dokumen desain, belum dikunci |
| Diterima | Dikunci; perubahan butuh ADR baru yang menggantikannya |
| Ditolak | Dipertimbangkan lalu tidak dipakai |
| Digantikan | Diganti oleh ADR lain (disebutkan nomornya) |

ADR yang sudah **Diterima** tidak diedit isinya. Kalau keputusannya berubah, tulis ADR baru dan ubah status ADR lama menjadi **Digantikan oleh ADR-XXXX**.

## Daftar ADR

| Nomor | Judul | Status |
| --- | --- | --- |
| [0001](0001-konvensi-eksekusi-next-close.md) | Konvensi eksekusi `next_close` | Diusulkan |
| [0002](0002-tiga-implementasi-simulator.md) | Tiga implementasi simulator dengan satu referensi | Diusulkan |
| [0003](0003-penyimpanan-parquet-dan-postgres.md) | Harga di Parquet, metadata dan hasil di Postgres | Diusulkan |
| [0004](0004-cpp-untuk-core-simulator.md) | C++ untuk core simulator | Diusulkan |
| [0005](0005-model-biaya-transaksi.md) | Model biaya transaksi dan slippage | Diusulkan |
| [0006](0006-imbal-hasil-kas.md) | Kas menghasilkan risk-free rate | Diusulkan |
| [0007](0007-identitas-run-berbasis-hash.md) | Identitas run berbasis hash | Diusulkan |
| [0008](0008-batasan-cakupan-v1.md) | Batasan cakupan v1 | Diusulkan |

Template untuk ADR baru ada di [template.md](template.md).
