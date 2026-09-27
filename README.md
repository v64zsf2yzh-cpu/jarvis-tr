# JARVIS v2

Sıfırdan eğitilen Türkçe kişisel asistan (Iron Man / Jarvis tarzı).

## Yenilikler

- Daha büyük Türkçe niyet veri seti
- Unigram + bigram özellikler
- 3 gizli katmanlı NumPy MLP (ağırlıklar rastgele başlar, harici LLM yok)
- **Öğretme paneli**: soru → cevap ekle
- **Yeniden eğit**: öğretilerle birlikte modeli sıfırdan güncelle
- Çeviri sözlüğü, birim dönüşümü, şifre üretimi, yazı araçları, yazı-tura / zar

## Kurulum

```bash
pip install -r requirements.txt
python train.py      # veri setini yaz + sıfırdan eğit
python app.py        # http://localhost:5050
```

## Öğretme

Sohbette:
```text
öğret favori rengim ne | Mavi
yeniden eğit
```

veya arayüzdeki öğretme paneli + **Yeniden eğit** düğmesi.

## Dürüst sınır

Bu bir GPT-ölçeği dil modeli değildir. Sıfırdan eğitilen şey **Türkçe anlama beyni** (niyet sınıflandırıcı) + sizin öğrettiğiniz bilgi bankasıdır. Her cümleyi üreten trilyon-parametreli LLM için ayrı, çok büyük hesaplama gerekir.
