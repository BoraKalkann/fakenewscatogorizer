# Karar Modeli Testleri

Veri: AVeriTeC dev, 500 iddia. Kanıt: insan yazımı soru-cevaplar (gold evidence) → üst sınır.
Kod: `experiments/`. Ham sonuçlar: `experiments/results/`.

## Özet

| Model | Boyut | Sınıf | Doğruluk | Macro F1 |
|---|---|---|---|---|
| Çoğunluk sınıfı ("Refuted") | – | – | %61.0 | – |
| MoritzLaurer/DeBERTa-v3-base-mnli-fever-anli | base | 3 | %52.4* | – |
| ctu-aic/deberta-v3-large-AVeriTeC-nli | large (1.7 GB) | 4 | **%80.2** | **0.680** |

\* 462 iddia üzerinden (3 sınıflı model; 38 "çelişkili" iddia hariç). Çoğunluk sınıfı bu 462'de %66.

## Güven eşiği (kaskad)

| Eşik | MoritzLaurer: kalan / doğruluk | ctu-aic: kalan / doğruluk | ctu-aic: LLM'e giden |
|---|---|---|---|
| 0.0 | %100 / %52.4 | %100 / %80.2 | 0 |
| 0.7 | %85 / %53.4 | %93 / %84.1 | 35 |
| 0.8 | %74 / %54.7 | %90 / %85.9 | 52 |
| 0.9 | %61 / %54.6 | %82 / %90.0 | 92 |
| 0.95 | %51 / %54.5 | %75 / %92.8 | 126 |

## ctu-aic karışıklık tablosu (gerçek → tahmin)

| Gerçek \ Tahmin | Refuted | Supported | NEE | Conflicting |
|---|---|---|---|---|
| Refuted (305) | 256 | 9 | 11 | 29 |
| Supported (122) | 3 | 104 | 1 | 14 |
| NEE (35) | 10 | 1 | 20 | 4 |
| Conflicting (38) | 10 | 6 | 1 | 21 |

## Notlar

| | |
|---|---|
| ctu-aic girdi sırası | iddia → kanıt (ters sırada calibration doğruluğu %72) |
| ctu-aic etiket eşlemesi | LABEL_0=Refuted, 1=Supported, 2=NEE, 3=Conflicting (150 train iddiasıyla belirlendi) |
| ctu-aic train sızıntısı | 150 train iddiasında %100 → train setiyle eğitilmiş; testte train iddiası kullanılmamalı |
| MoritzLaurer ana hata | 305 Refuted'ın 121'i → NEE |
| Seçilen eşik | 0.9 |
| Açık | Web kanıtıyla (gerçek sistem) doğruluk ölçülmedi |
