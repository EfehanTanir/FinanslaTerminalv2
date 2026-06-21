"""
Finansla API — piyasa.html'in fetch() ile çağıracağı JSON servisi.
Mevcut app.py'deki (Streamlit) yfinance mantığının aynısını kullanır,
ama HTML render etmez, sadece JSON döner.

Railway'de AYRI bir servis olarak deploy edilir (Streamlit'ten bağımsız).
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import List, Optional
from tefas import Crawler

tefas = Crawler()

app = FastAPI(title="Finansla API", version="1.0")

# --- CORS: finansla.net ve beta.finansla.net'ten gelen isteklere izin ver ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://finansla.net",
        "https://beta.finansla.net",
        "https://www.finansla.net",
    ],
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "status": "ok",
        "service": "Finansla API",
        "endpoints": [
            "/api/hisse/{sembol}",
            "/api/hisseler",
            "/api/fon/{fon_kodu}",
            "/api/fonlar",
            "/api/makro",
        ],
    }


def buyuk_sayi_formatla(sayi):
    if sayi is None:
        return None
    return sayi


def hisse_analiz(sembol: str):
    """app.py'deki hesaplama mantığının JSON versiyonu."""
    ticker = yf.Ticker(sembol)
    veri = ticker.history(period="1y", interval="1d")
    info = ticker.info

    if veri.empty:
        raise HTTPException(status_code=404, detail=f"{sembol} için veri bulunamadı")

    current_price = info.get("currentPrice") or info.get("regularMarketPrice") or float(veri["Close"].iloc[-1])
    previous_close = info.get("previousClose") or info.get("regularMarketPreviousClose")

    if previous_close:
        gunluk_degisim = ((current_price - previous_close) / previous_close) * 100
    elif len(veri) >= 2:
        gunluk_degisim = ((veri["Close"].iloc[-1] - veri["Close"].iloc[-2]) / veri["Close"].iloc[-2]) * 100
    else:
        gunluk_degisim = 0.0

    gunluk_getiri = veri["Close"].pct_change()
    volatilite = gunluk_getiri.std() * (252 ** 0.5) * 100

    # Sharpe oranı (risksiz oran TR için ~%45 politika faizi varsayımıyla, basitleştirilmiş)
    risksiz_oran = 0.45
    yillik_getiri = gunluk_getiri.mean() * 252
    sharpe = (yillik_getiri - risksiz_oran) / (gunluk_getiri.std() * (252 ** 0.5)) if gunluk_getiri.std() > 0 else 0

    # Sortino (sadece negatif getirilerin std'si)
    negatif_getiri = gunluk_getiri[gunluk_getiri < 0]
    downside_std = negatif_getiri.std() * (252 ** 0.5) if len(negatif_getiri) > 0 else 0.0001
    sortino = (yillik_getiri - risksiz_oran) / downside_std if downside_std > 0 else 0

    # VaR %95 (parametrik, günlük)
    var95 = -(1.645 * gunluk_getiri.std() * 100)

    rolling_max = veri["Close"].cummax()
    drawdown = veri["Close"] / rolling_max - 1.0
    max_drawdown = drawdown.min() * 100

    ytd_getiri = ((veri["Close"].iloc[-1] - veri["Close"].iloc[0]) / veri["Close"].iloc[0]) * 100

    return {
        "sembol": sembol.upper(),
        "isim": info.get("longName") or info.get("shortName") or sembol,
        "sektor": info.get("sector", "Bilinmiyor"),
        "fiyat": round(current_price, 2),
        "paraBirimi": info.get("currency", "TRY"),
        "gunlukDegisim": round(gunluk_degisim, 2),
        "hacim": info.get("volume") or info.get("regularMarketVolume"),
        "piyasaDegeri": buyuk_sayi_formatla(info.get("marketCap")),
        "fkOrani": info.get("trailingPE"),
        "temettuVerimi": round((info.get("dividendYield") or 0) * 100, 2),
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "var95": round(var95, 2),
        "volatilite": round(volatilite, 1),
        "maxDrawdown": round(max_drawdown, 1),
        "ytdGetiri": round(ytd_getiri, 1),
        "ellieIkiHaftaAralik": info.get("fiftyTwoWeekRange"),
        "guncellemeZamani": datetime.now().isoformat(),
    }


def fon_analiz(fon_kodu: str, ay: int = 12):
    """
    TEFAS fonu için fiyat geçmişi çeker, Sharpe/Sortino/VaR/volatilite hesaplar.
    Not: Yeni tefas.gov.tr API'si artık AUM, yatırımcı sayısı ve portföy
    dağılımını döndürmüyor — sadece fiyat serisi var. Risk metrikleri bu
    fiyat serisinden (app.py'deki mantığın aynısıyla) hesaplanıyor.
    """
    fon_kodu = fon_kodu.upper().strip()
    bugun = datetime.now()
    ay_map = {1: 1, 3: 3, 6: 6, 12: 12, 36: 36, 60: 60}
    period_months = ay_map.get(ay, 12)
    baslangic = bugun - timedelta(days=period_months * 30 + 5)

    df = tefas.fetch(
        start=baslangic.strftime("%Y-%m-%d"),
        end=bugun.strftime("%Y-%m-%d"),
        name=fon_kodu,
    )

    if df.empty:
        raise HTTPException(status_code=404, detail=f"{fon_kodu} için veri bulunamadı")

    df = df.sort_values("date").reset_index(drop=True)
    df = df.dropna(subset=["price"])

    if len(df) < 2:
        raise HTTPException(status_code=404, detail=f"{fon_kodu} için yeterli fiyat verisi yok")

    fiyatlar = df["price"].astype(float)
    gunluk_getiri = fiyatlar.pct_change().dropna()

    if gunluk_getiri.empty:
        raise HTTPException(status_code=404, detail=f"{fon_kodu} için getiri hesaplanamadı")

    current_price = float(fiyatlar.iloc[-1])
    onceki_fiyat = float(fiyatlar.iloc[-2]) if len(fiyatlar) >= 2 else current_price
    gunluk_degisim = ((current_price - onceki_fiyat) / onceki_fiyat) * 100 if onceki_fiyat else 0.0

    volatilite = float(gunluk_getiri.std() * (252 ** 0.5) * 100)

    # TR risksiz oran varsayımı (politika faizi yaklaşık)
    risksiz_oran = 0.45
    yillik_getiri = float(gunluk_getiri.mean() * 252)
    std_yillik = float(gunluk_getiri.std() * (252 ** 0.5))
    sharpe = (yillik_getiri - risksiz_oran) / std_yillik if std_yillik > 0 else 0.0

    negatif_getiri = gunluk_getiri[gunluk_getiri < 0]
    downside_std = float(negatif_getiri.std() * (252 ** 0.5)) if len(negatif_getiri) > 1 else 0.0001
    sortino = (yillik_getiri - risksiz_oran) / downside_std if downside_std > 0 else 0.0

    var95 = -(1.645 * float(gunluk_getiri.std()) * 100)

    rolling_max = fiyatlar.cummax()
    drawdown = fiyatlar / rolling_max - 1.0
    max_drawdown = float(drawdown.min() * 100)

    donem_getiri = ((current_price - float(fiyatlar.iloc[0])) / float(fiyatlar.iloc[0])) * 100

    son_satir = df.iloc[-1]

    return {
        "kod": fon_kodu,
        "isim": str(son_satir.get("title") or fon_kodu),
        "fiyat": round(current_price, 6),
        "gunlukDegisim": round(gunluk_degisim, 2),
        "kategoriDerece": int(son_satir["category_rank"]) if pd.notna(son_satir.get("category_rank")) else None,
        "kategoriToplam": int(son_satir["category_total"]) if pd.notna(son_satir.get("category_total")) else None,
        "donemGetiri": round(donem_getiri, 2),
        "donemAy": period_months,
        "sharpe": round(sharpe, 2),
        "sortino": round(sortino, 2),
        "var95": round(var95, 2),
        "volatilite": round(volatilite, 1),
        "maxDrawdown": round(max_drawdown, 1),
        "veriBaslangic": str(df["date"].iloc[0]),
        "veriBitis": str(df["date"].iloc[-1]),
        "kayitSayisi": len(df),
        "guncellemeZamani": datetime.now().isoformat(),
    }


@app.get("/api/fon/{fon_kodu}")
def get_fon(fon_kodu: str, ay: int = Query(12, description="Geriye dönük ay: 1, 3, 6, 12, 36 veya 60")):
    """TEFAS fonu detaylı analiz. Örnek: /api/fon/PHE?ay=12"""
    try:
        return fon_analiz(fon_kodu, ay)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/fonlar")
def get_fonlar(kodlar: str = Query(..., description="Virgülle ayrılmış fon kodları: PHE,TLY,PBR"), ay: int = 12):
    """Birden fazla TEFAS fonunu tek seferde döner. Örnek: /api/fonlar?kodlar=PHE,TLY,PBR"""
    kod_list = [k.strip().upper() for k in kodlar.split(",") if k.strip()]
    sonuc = []
    for kod in kod_list:
        try:
            sonuc.append(fon_analiz(kod, ay))
        except Exception as e:
            sonuc.append({"kod": kod, "hata": str(e)})
    return {"veriler": sonuc, "adet": len(sonuc)}


@app.get("/api/hisse/{sembol}")
@app.get("/api/hisse/{sembol}")
def get_hisse(sembol: str):
    """Tek bir hisse/sembol için detaylı analiz. Örnek: /api/hisse/THYAO.IS"""
    try:
        return hisse_analiz(sembol)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/hisseler")
def get_hisseler(semboller: str = Query(..., description="Virgülle ayrılmış semboller: THYAO.IS,GARAN.IS")):
    """Birden fazla hisseyi tek seferde döner. Örnek: /api/hisseler?semboller=THYAO.IS,GARAN.IS,ASELS.IS"""
    sym_list = [s.strip() for s in semboller.split(",") if s.strip()]
    sonuc = []
    for sym in sym_list:
        try:
            sonuc.append(hisse_analiz(sym))
        except Exception as e:
            sonuc.append({"sembol": sym, "hata": str(e)})
    return {"veriler": sonuc, "adet": len(sonuc)}


@app.get("/api/makro")
def get_makro():
    """BIST100, USD/TL, Altın, BTC gibi makro göstergeler."""
    semboller = {
        "bist100": "XU100.IS",
        "usdtry": "USDTRY=X",
        "eurtry": "EURTRY=X",
        "altin": "GC=F",
        "btc": "BTC-USD",
    }
    sonuc = {}
    for ad, sym in semboller.items():
        try:
            t = yf.Ticker(sym)
            info = t.info
            fiyat = info.get("regularMarketPrice") or info.get("currentPrice")
            degisim = info.get("regularMarketChangePercent", 0)
            sonuc[ad] = {"fiyat": fiyat, "degisimYuzde": round(degisim, 2) if degisim else 0}
        except Exception as e:
            sonuc[ad] = {"hata": str(e)}
    sonuc["guncellemeZamani"] = datetime.now().isoformat()
    return sonuc
