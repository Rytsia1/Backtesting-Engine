# Spesifikasi Desain Engine: Quant Research & Backtesting Platform

Oct 12, 2026 · @Dio

Engine adalah package Python mandiri yang mengubah data harga dan konfigurasi menjadi hasil backtest yang deterministik. Dokumen ini menetapkan kontraknya: konvensi waktu, interface strategi, rumus akuntansi, dan metrik. Dokumen ini melengkapi PRD v0.1; jika keduanya bertentangan, dokumen ini yang berlaku untuk detail engine.

## Ruang lingkup dan prinsip desain

Engine mencakup lima modul: `data` (memuat dan memvalidasi snapshot), `strategies` (menghasilkan bobot target), `sim` (akuntansi portofolio), `metrics`, dan `validation` (split out-of-sample, walk-forward, sweep). API, worker, database, dan UI berada di luar engine dan hanya memanggilnya.

Prinsip yang tidak boleh dilanggar:

- **Kausal:** keputusan di tanggal t hanya boleh memakai informasi yang tersedia sampai close t.
- **Deterministik:** input yang sama selalu menghasilkan output yang sama, bit-per-bit di implementasi yang sama.
- **Gagal dengan keras:** pelanggaran batasan melempar error. Tidak ada pemotongan, pengisian, atau koreksi diam-diam.
- **Strategi terpisah dari akuntansi:** strategi hanya menghasilkan bobot target. Ia tidak pernah tahu kas, harga eksekusi, atau biaya.
- **Satu sumber kebenaran:** simulator Python event-driven adalah implementasi referensi. Versi vectorized dan C++ harus identik dengannya dalam toleransi yang ditetapkan di bagian test.

Cakupan v1: data harian, satu kalender bursa per run, long-only, tanpa leverage, bobot pecahan (tanpa lot).

## Konvensi waktu dan eksekusi

Default v1 adalah **close t+1**: sinyal dihitung setelah close t, dieksekusi di close t+1, dan return pertama yang terdampak adalah periode dari close t+1 ke close t+2. Konvensi ini konservatif dan cukup dengan data close saja.

Notasi yang dipakai di seluruh dokumen:

- Tanggal perdagangan diindeks 0, 1, …, T. Periode t adalah interval dari close t−1 ke close t.
- w\*\_d adalah bobot target yang diputuskan strategi setelah close d.
- h\_t adalah bobot yang dipegang selama periode t.

Dengan eksekusi close t+1, keputusan di d dieksekusi di close d+1 dan dipegang selama periode d+2:

```latex
h_t = w^{*}_{t-2}
```

Aturan tambahan:

| Aturan | Isi |
| --- | --- |
| Mode eksekusi | `next_close` (default, wajib) dan `next_open` (opsional, butuh harga open yang di-adjust) |
| Eksekusi di close yang sama | Tidak disediakan. Studi dampak look-ahead dilakukan di test atau notebook terpisah, bukan lewat flag konfigurasi |
| Risk-free rate | Yield yang diketahui di tanggal t dipakai untuk periode t+1 |
| Harga adjusted | Adjusted close mengubah level harga masa lalu saat ada dividen atau split, tetapi rasio antarhari tetap. Sinyal harus berbasis return atau rasio, bukan level harga absolut |
| Warm-up | Strategi tidak dipanggil sebelum datanya cukup untuk `lookback`; selama itu portofolio 100% kas |

&#91;embedded content: Konvensi next\_close · keputusan, eksekusi, return pertama\]

Satu periode penuh (d+1) masih memakai bobot lama. Itulah harga realisme konvensi `next_close`, dan alasan test lag eksekusi memeriksa h\_{d+2}, bukan h\_{d+1}.

## Tipe data inti

Semua angka di engine memakai float64. Decimal hanya dipakai di lapisan API untuk nilai uang, sesuai PRD.

| Tipe | Field | Aturan |
| --- | --- | --- |
| `MarketData` | `close`: DataFrame adjusted close, index tanggal, kolom ticker | Index naik ketat, unik, tanpa timezone; tanpa NaN setelah validasi; harga > 0 |
| `MarketData` | `open`: DataFrame opsional, bentuk sama dengan `close` | Wajib hanya untuk mode `next_open` |
| `MarketData` | `dataset_hash`, `calendar` | Hash SHA-256 snapshot; satu kalender bursa per objek |
| `Weights` | `Mapping[str, float]` ticker ke bobot | Setiap bobot ≥ 0; total ≤ 1 + 1e-12; ticker harus ada di data; kas = 1 − total |
| `BacktestResult` | `equity`: Series nilai portofolio di close setiap tanggal, setelah biaya | Nilai di tanggal 0 = modal awal |
| `BacktestResult` | `returns_gross`, `returns_net`: Series return per periode | Sebelum dan sesudah biaya |
| `BacktestResult` | `holdings`: DataFrame h\_t, termasuk kolom `CASH` | Setiap baris berjumlah 1 |
| `BacktestResult` | `trades`: DataFrame (tanggal, ticker, bobot sebelum, bobot sesudah, notional, biaya) | Satu baris per ticker yang bobotnya berubah |
| `BacktestResult` | `metrics`: dict nama metrik ke nilai | Lihat bagian Metrik |
| `BacktestResult` | `run`: `RunInfo` (run\_id, snapshot konfigurasi, dataset\_hash, engine\_version) | Lihat bagian Identitas run |

`BacktestConfig` mengikuti field di PRD (FR-C2). Objek konfigurasi dan hasil bersifat immutable: dataclass `frozen=True` atau model Pydantic `frozen`.

## Interface strategi

Strategi kausal karena konstruksinya, bukan karena disiplin: engine memotong data sebelum memanggil strategi, jadi data masa depan memang tidak ada di tangannya.

```python
class Strategy(Protocol):
    name: ClassVar[str]
    version: ClassVar[str]
    lookback: int  # jumlah bar minimum sebelum strategi dipanggil

    def signal(self, history: MarketData) -> Weights | None:
        """Bobot target setelah close tanggal terakhir di history.
        None berarti target tidak berubah."""

    def signal_all(self, data: MarketData) -> pd.DataFrame:
        """Opsional: bobot target untuk semua tanggal sekaligus.
        Index = tanggal keputusan, kolom = ticker.
        Baris NaN berarti target tidak berubah."""
```

Aturan:

- `history` hanya berisi data sampai tanggal keputusan. Engine membuat potongan itu sebelum setiap panggilan.
- Base class menyediakan `signal_all` default yang memanggil `signal` pada jendela data yang terus membesar. Lambat, tapi kausal dengan sendirinya.
- Strategi boleh meng-override `signal_all` demi kecepatan, tetapi wajib lolos test kesetaraan: hasilnya identik dengan versi default.
- Simulator event-driven referensi memakai `signal`. Simulator vectorized dan core C++ memakai keluaran `signal_all`, jadi C++ hanya menggantikan akuntansi, bukan strategi.
- Parameter masuk lewat constructor, divalidasi Pydantic, dan tersimpan di snapshot konfigurasi.
- Strategi v1 stateless: semua yang dibutuhkan diturunkan dari `history`. Tidak ada I/O, waktu sistem, atau angka acak.

## Akuntansi portofolio

Setiap bar diproses dengan urutan tetap: hitung return, geser bobot karena pergerakan harga, eksekusi target yang tertunda, potong biaya, lalu panggil strategi. Ketiga implementasi (Python event-driven, Python vectorized, C++) wajib mengikuti persamaan yang sama; cara menghitungnya bebas.

Kondisi awal: V\_0 = modal awal, h\_1 = 100% kas. Untuk setiap t ≥ 1:

```latex
\begin{aligned}
r_{i,t} &= P_{i,t} / P_{i,t-1} - 1 \\
R_t &= \textstyle\sum_i h_{i,t}\, r_{i,t} + h_{\text{cash},t}\, r_{\text{cash},t} \\
\tilde{w}_{i,t} &= h_{i,t}\,(1 + r_{i,t}) \,/\, (1 + R_t) \\
n_t &= w^{*}_{t-1} \ \text{jika ada target tertunda, selain itu } \tilde{w}_t \\
\tau_t &= \textstyle\sum_i \lvert n_{i,t} - \tilde{w}_{i,t} \rvert \\
\kappa_t &= (c + s) \cdot 10^{-4} \cdot \tau_t \\
V_t &= V_{t-1}\,(1 + R_t)\,(1 - \kappa_t) \\
h_{t+1} &= n_t
\end{aligned}
```

Keterangan:

- P adalah adjusted close; c dan s adalah biaya transaksi dan slippage dalam basis poin.
- Return kas r\_cash,t = risk-free rate harian dari yield yang diketahui di t−1 bila `cash_yield = risk_free` (default), atau 0 bila `cash_yield = zero`. Yield tahunan y dikonversi menjadi (1 + y)^(1/252) − 1.
- Turnover τ hanya menjumlahkan aset, bukan kas, sehingga sama dengan notional yang diperdagangkan dibagi nilai portofolio.
- Biaya dipotong proporsional dari seluruh posisi termasuk kas. Akibatnya bobot setelah transaksi tepat sama dengan target, dan kas tidak pernah negatif.
- Slippage dimodelkan sebagai biaya tambahan atas notional, bukan penyesuaian harga eksekusi. Pada orde pertama hasilnya sama, dan pilihan ini membuat ketiga implementasi bisa identik secara eksak.
- Strategi yang mengembalikan `None` tidak memicu transaksi; bobot dibiarkan bergeser mengikuti harga. Strategi yang mengembalikan target yang sama setiap hari berarti rebalancing harian, dengan biayanya.
- Notional per transaksi di tabel `trades` = (n − w̃) × V\_{t−1}(1 + R\_t).

## Metrik

Semua metrik dihitung dari return net (setelah biaya) dengan A = 252 periode per tahun dan N = jumlah periode di jendela evaluasi. Excess return e\_t = R\_net,t − rf\_t selalu memakai risk-free rate, apa pun nilai `cash_yield`.

| Metrik | Rumus | Catatan |
| --- | --- | --- |
| CAGR | (V\_akhir / V\_awal)^(A/N) − 1, dengan V\_awal = nilai di awal jendela evaluasi |  |
| Volatilitas tahunan | std(R\_net, ddof=1) × √A |  |
| Sharpe ratio | mean(e) / std(e, ddof=1) × √A | Risk-free rate sesuai mata uang aset |
| Sortino ratio | mean(e) / √mean(min(e, 0)²) × √A | Downside deviation terhadap 0 excess return |
| Maximum drawdown | min\_t (V\_t / max\_{s≤t} V\_s − 1) | Bernilai ≤ 0 |
| Durasi drawdown terpanjang | Jumlah periode berturut-turut terpanjang dengan V\_t di bawah puncak sebelumnya | Dalam periode perdagangan |
| Turnover tahunan | Σ τ\_t × A / N |  |
| Total biaya | Σ κ\_t × V\_{t−1}(1 + R\_t) | Dalam mata uang modal |
| Excess CAGR | CAGR strategi − CAGR benchmark |  |
| Tracking error | std(R\_net strategi − R\_net benchmark, ddof=1) × √A |  |
| Information ratio | mean(selisih return) / std(selisih return, ddof=1) × √A |  |

Benchmark dijalankan sebagai backtest tersendiri lewat simulator yang sama, dengan biaya dan konvensi waktu yang sama. Jendela evaluasi dimulai pada periode pertama setelah eksekusi pertama strategi, dan benchmark dipotong ke jendela yang persis sama. Tanpa aturan ini, strategi dengan lookback 90 hari dibandingkan dengan benchmark yang periodenya lebih panjang.

## Identitas run dan determinisme

`run_id` adalah SHA-256 dari JSON kanonik berisi tiga hal: konfigurasi yang sudah dinormalisasi, `dataset_hash`, dan `engine_version`. Input yang sama selalu menghasilkan `run_id` yang sama, dan itulah dasar idempotency di API.

| Aturan | Isi |
| --- | --- |
| Normalisasi konfigurasi | Semua nilai default diisi eksplisit sebelum hashing, sehingga field default yang dihilangkan dan yang ditulis menghasilkan `run_id` sama |
| JSON kanonik | Key diurutkan, tanpa spasi, UTF-8, tanggal ISO 8601, float dengan representasi round-trip terpendek, NaN ditolak |
| `engine_version` | `<versi package>+<implementasi>`, misalnya `0.3.0+py-event`, `0.3.0+py-vec`, `0.3.0+cpp` |
| Versi package | Naik minor setiap kali perubahan kode bisa mengubah angka hasil; naik patch hanya untuk perubahan yang tidak menyentuh angka |
| Versi strategi | Nama dan versi strategi bagian dari konfigurasi, jadi ikut di-hash |
| Git commit | Disimpan di `RunInfo` sebagai metadata, tidak ikut di-hash. Bila ikut, setiap commit yang tidak menyentuh engine akan merusak idempotency |
| Tampilan | UI menampilkan 12 karakter pertama; database menyimpan hash penuh |

Determinisme dijaga dengan tiga aturan: tidak ada angka acak di v1 (bila nanti ada, misalnya bootstrap, seed wajib masuk konfigurasi), ticker selalu diurutkan alfabetis sehingga urutan penjumlahan tetap, dan perhitungan backtest (strategies, sim, metrics, validation) tidak membaca waktu sistem. Metadata ingestion dikecualikan: `write_snapshot` boleh mencatat `created_at` dengan membaca jam sistem di batas I/O bila nilainya tidak disuntikkan; nilai ini hanya ada di manifest dan tidak memengaruhi hash snapshot maupun hasil run.

`dataset_hash` adalah SHA-256 dari byte file Parquet snapshot setelah dikanonikalkan (index `datetime64[ns]` tanpa timezone bernama `date`, ticker urut alfabetis, float64). Byte itu juga memuat versi pyarrow dan pandas penulisnya, sehingga data yang sama yang ditulis dengan versi library berbeda menghasilkan hash berbeda. Reproducibility hash dijaga oleh versi yang dikunci `uv.lock`; snapshot lama tetap bisa dimuat karena hash diverifikasi terhadap byte filenya sendiri.

## Error dan validasi

Semua error turunan dari `EngineError` dan dilempar sedini mungkin, sebelum simulasi berjalan bila memungkinkan. Engine tidak pernah menangkap lalu mengabaikan error-nya sendiri. Pesan error menyertakan tanggal dan ticker yang bermasalah.

| Error | Dilempar ketika |
| --- | --- |
| `ConfigError` | Tanggal mulai setelah tanggal akhir, biaya negatif, mode eksekusi tidak dikenal, atau `next_open` tanpa data open |
| `DataValidationError` | Snapshot mengandung NaN, tanggal duplikat atau tidak urut, harga ≤ 0, atau isi file tidak cocok dengan `dataset_hash` yang tercatat |
| `InsufficientDataError` | Data di rentang yang diminta tidak cukup untuk `lookback` ditambah minimal 2 periode evaluasi |
| `WeightConstraintError` | Bobot negatif, total bobot > 1 + 1e-12, ticker tidak ada di data, atau bobot berisi NaN |
| `StrategyContractError` | Keluaran `signal_all` salah bentuk (index atau kolom tidak sesuai data) atau tidak setara dengan versi default |

Lonjakan harga ekstrem (default: return harian di atas 50% secara absolut) dicatat sebagai **peringatan** di laporan validasi, bukan error. Crash dan rally besar memang terjadi, jadi keputusan untuk memakai data itu ada di tangan peneliti, tetapi peringatannya tidak boleh hilang.

## Test yang diturunkan dari spesifikasi

Setiap aturan di dokumen ini punya minimal satu test. Test bertanda Hypothesis memakai data harga acak yang dibangkitkan property-based testing.

| Test | Kriteria lulus |
| --- | --- |
| Look-ahead (Hypothesis) | Mengganti semua harga setelah tanggal t dengan nilai acak positif tidak mengubah w\*\_d untuk d ≤ t maupun h\_s untuk s ≤ t+1 |
| Lag eksekusi | Strategi yang pertama kali memberi bobot 1 di tanggal keputusan d menghasilkan transaksi di close d+1 dan bobot non-nol pertama di h\_{d+2} |
| Buy-and-hold tanpa biaya | Dengan `cash_yield = zero`, V\_T / V\_0 = P\_T / P\_1 (dibeli di close 1). Ini menggantikan rumusan "rasio harga akhir/awal" di PRD |
| Monotonisitas biaya (Hypothesis) | Biaya c₂ > c₁ selalu menghasilkan V\_T(c₂) ≤ V\_T(c₁) |
| Bobot pasca-transaksi | Selisih bobot setelah transaksi dengan target ≤ 1e-12; kas ≥ 0; setiap baris `holdings` berjumlah 1 |
| Kesetaraan `signal_all` | Override strategi identik secara eksak dengan versi default |
| Differential vectorized vs event-driven (Hypothesis) | Selisih relatif equity ≤ 1e-10 di setiap tanggal |
| Parity C++ vs Python | Selisih relatif equity ≤ 1e-10 di setiap tanggal |
| Determinisme | Dua run identik menghasilkan hasil yang sama persis dan `run_id` yang sama |
| Normalisasi `run_id` | Default yang dihilangkan dan yang ditulis eksplisit menghasilkan `run_id` sama; mengubah satu parameter apa pun menghasilkan `run_id` berbeda |
| Strategi 100% kas | Dengan `cash_yield = risk_free`, excess return 0 di setiap periode; Sharpe dilaporkan NaN, bukan 0 dan bukan error |
| Metrik vs quantstats | Selisih ≤ 1e-8 pada konvensi yang sama; setiap perbedaan konvensi didokumentasikan |
| Validasi data | Setiap jenis data rusak di bagian Error melempar `DataValidationError` |

## Keputusan terbuka

Pilihan di bawah sudah dipakai sementara di dokumen ini. Masing-masing layak dikunci lewat ADR sebelum M2 selesai.

| Keputusan | Pilihan sementara | Dampak bila diubah |
| --- | --- | --- |
| Mode eksekusi default | `next_close` | `next_open` lebih realistis tapi butuh harga open yang di-adjust dan memecah return periode menjadi dua |
| Imbal hasil kas | `risk_free` | Dengan `zero`, strategi yang sering memegang kas dirugikan, terutama untuk aset IDR yang risk-free rate-nya tinggi |
| Lot dan transaksi minimum | Bobot pecahan, tanpa lot | Lot 100 lembar di IDX membuat hasil dengan modal kecil seperti Rp100 juta berbeda nyata dari bobot pecahan |
| Kalender | Satu kalender bursa per run | Mencampur aset IDX dan AS butuh aturan untuk hari libur yang berbeda |
| Strategi stateful | Tidak didukung | Stop-loss berbasis harga masuk butuh state, sehingga interface strategi harus diubah |
| Dividen | Adjusted close (total return) | Price return + dividen tunai butuh data dividen terpisah |
| Toleransi parity | 1e-10 relatif | Divalidasi ulang setelah implementasi pertama; bisa terlalu ketat atau terlalu longgar |
