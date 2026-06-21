# FinanslaTerminal

Finansla.net'in canlı borsa/fon terminali ve API'si. İki ayrı servis içerir, Railway'de
ayrı ayrı deploy edilir.

## Yapı

```
FinanslaTerminal/
├── app.py                 ← Streamlit terminal (finansla.net/terminal) — hisse analizi
├── pages/
│   └── 1_📊_Fonlar.py        ← TEFAS fon analizi sayfası (aynı uygulamada, sol menüde)
├── requirements.txt        ← Streamlit bağımlılıkları (yfinance + tefas-crawler dahil)
├── Procfile                 ← Streamlit başlatma komutu
│
├── api/                     ← JSON API servisi (piyasa.html'in beslendiği yer)
│   ├── api.py
│   ├── requirements.txt
│   └── Procfile
│
└── web/                     ← Frontend (statik HTML, WordPress'e veya doğrudan
    └── piyasa.html              hosting'e yüklenir, /api'ye fetch() atar)
```

## Servisler

### 1. Streamlit Terminal (`app.py` + `pages/`)
Çok sayfalı Streamlit uygulaması:
- **Ana sayfa** (`app.py`): Tek hisse bazlı detaylı analiz. yfinance + plotly + haber akışı.
- **Fonlar sayfası** (`pages/1_📊_Fonlar.py`): TEFAS fonu analizi — fiyat grafiği, Sharpe/Sortino/VaR/volatilite, kategori sırası, ilgili haberler. `tefas-crawler` ile tefas.gov.tr'nin halka açık API'sinden veri çeker.

Streamlit, `pages/` klasöründeki dosyaları otomatik olarak sol menüde sekme yapar — ekstra routing kodu gerekmez.

Railway/Render'da **root servis** olarak deploy edilir (repo kökünden).

### 2. JSON API (`api/`)
`piyasa.html`'in fetch() ile çağırdığı backend. İki veri kaynağı kullanır:

- **BIST hisseleri & makro göstergeler** → `yfinance`
- **TEFAS fonları** → `tefas-crawler` (tefas.gov.tr'nin resmi/halka açık JSON API'si)

Railway'de **ayrı bir servis** olarak deploy edilir; Root Directory ayarı `api` olmalı.

#### Endpoint'ler

| Endpoint | Açıklama |
|---|---|
| `GET /` | Servis durumu + endpoint listesi |
| `GET /api/hisse/{sembol}` | Tek hisse analizi (örn. `THYAO.IS`) |
| `GET /api/hisseler?semboller=A,B,C` | Çoklu hisse |
| `GET /api/fon/{fon_kodu}` | Tek TEFAS fonu analizi (örn. `PHE`) |
| `GET /api/fonlar?kodlar=A,B,C` | Çoklu fon |
| `GET /api/makro` | BIST100, USD/TRY, Altın, BTC |

**Not:** TEFAS'ın 2026'da yenilenen API'si artık fon büyüklüğü (AUM), yatırımcı
sayısı ve portföy dağılımı gibi alanları açık vermiyor — sadece fiyat serisi
sunuyor. Sharpe, Sortino, VaR, volatilite ve max drawdown bu fiyat serisinden
hesaplanıyor.

### 3. Frontend (`web/piyasa.html`)
Karanlık tema, arama/filtre/sıralama destekli piyasa tablosu. Şu an demo verisiyle
çalışıyor; `api/`'deki endpoint'lere `fetch()` ile bağlanacak şekilde güncellenmesi
gerekiyor.

## Deploy (Railway veya Render)

Bu repo **iki ayrı servis** gerektirir (aynı repodan, farklı Root Directory ile):

1. **Terminal servisi** — Root Directory: `/` (varsayılan), Start Command Procfile'dan okunur
2. **API servisi** — Root Directory: `api`

`web/piyasa.html` Railway/Render'a değil, finansla.net'in kendi hosting'ine (cPanel/File
Manager) yüklenir.

## Yasal Uyarı

Burada yer alan bilgiler yatırım tavsiyesi değildir. Tüm veriler halka açık
kaynaklardan (Yahoo Finance, TEFAS) derlenmiştir.