# Veri Setleri Raporu

## 1. Wikipedia Perennial Sources (`dataset/wp_rsp.csv`)

| | |
|---|---|
| Kaynak | 497 |
| Alan adı (tekil) | 756 |
| Alan adı olmayan kaynak | 7 |
| Sürüm | 1378772250 (2026-10-09) |

| Karar | Kaynak |
|---|---|
| Güvenilir | 156 |
| Güvenilmez | 149 |
| Uzlaşı yok | 110 |
| Yasaklanmış | 56 |
| Kara liste | 25 |
| Çoklu | 1 |

| Son tartışma | Kaynak |
|---|---|
| ≤ 2019 | 108 |
| 2020–2022 | 176 |
| ≥ 2023 | 213 |

## 2. Lin 2023 site puanları (`dataset/lin2023_*.csv`)

| | |
|---|---|
| Site | 11.520 |
| Puan aralığı | 0–1 |
| Ortalama | 0.547 |
| Çeyrekler (Q1 / medyan / Q3) | 0.379 / 0.582 / 0.694 |
| Puan < 0.4 | 3.155 |
| Puan ≥ 0.8 | 1.264 |
| Bozuk satır (yol / tire) | 50 |
| Wikipedia ile ortak site | 361 |
| Son güncelleme | 2023-09 |

## 3. AVeriTeC (`dataset/averitec/`)

| | Eğitim | Geliştirme |
|---|---|---|
| İddia | 3.068 | 500 |
| Yanlış | 1.742 | 305 |
| Doğru | 849 | 122 |
| Yeterli kanıt yok | 282 | 35 |
| Çelişkili / seçici | 195 | 38 |
| Hiciv kaynaklı | 111 | 10 |
| İddia uzunluğu (medyan / maks. kelime) | 15 / 73 | 16 / 66 |
| İddia başına soru (medyan) | 2 | 2 |

| İddia tipi | Eğitim | Geliştirme |
|---|---|---|
| Olay / özellik | 1.772 | 307 |
| Sayısal | 1.035 | 119 |
| Nedensellik | 353 | 54 |
| Alıntı | 295 | 69 |
| Tutum | 238 | 29 |

| Yıl (eğitim) | İddia |
|---|---|
| 2020 | 1.411 |
| 2019 | 1.375 |
| 2018 ve öncesi | ~170 |

Geliştirme setinin tamamı 2020.

Tür modeli için etiketlenecek (yanlış + çelişkili, eğitim): **1.937 iddia**

## 4. Temel model

| | |
|---|---|
| Model | microsoft/deberta-v3-base |
| Boyut | ~700 MB |

## Bağlantılar

- https://en.wikipedia.org/wiki/Wikipedia:Reliable_sources/Perennial_sources
- https://github.com/hauselin/domain-quality-ratings
- https://github.com/MichSchli/AVeriTeC
- https://huggingface.co/microsoft/deberta-v3-base
