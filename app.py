import streamlit as st
import yfinance as yf
import feedparser
from textblob import TextBlob
from datetime import datetime
import pandas as pd
import plotly.graph_objects as go
from deep_translator import GoogleTranslator

# --- 1. SAYFA AYARLARI ---
st.set_page_config(page_title="Finansla PRO Terminal V18", layout="wide", page_icon="🦅", initial_sidebar_state="expanded")

st.markdown("""
<style>
@media (max-width: 768px) {
    .block-container {
        padding: 1rem 0.5rem !important;
    }
    div[data-testid="column"] {
        width: 100% !important;
        flex: 1 1 100% !important;
    }
}
</style>
""", unsafe_allow_html=True)

st.title("🦅 Finansla.net | Borsa İstihbarat ve Analiz Terminali")
st.caption("ℹ️ **BİLGİ:** ABD Hisseleri: **AAPL, TSLA** | Borsa İstanbul Hisseleri için Sonuna .IS ekleyiniz örnek: **THYAO.IS, EREGL.IS**")
st.markdown("---")

# --- 2. ÜST KONTROL PANELİ ---
col1, col2, col3, col4, col5 = st.columns([2, 1, 1, 1, 1])
with col1:
    hisse_kodu = st.text_input("🔍 Hisse Sembolü", "NVDA")
with col2:
    aralik_secimi = st.selectbox("📅 Periyot", ["1G", "5G", "1A", "6A", "YTD", "1Y", "5Y"], index=5)
with col3:
    goster_sma20 = st.checkbox("SMA 20", value=True)
    goster_sma50 = st.checkbox("SMA 50", value=True)
with col4:
    goster_bollinger = st.checkbox("Bollinger", value=True)
with col5:
    st.write("")
    st.write("")
    if st.button("Analizi Başlat 🚀"):
        st.rerun()

st.markdown("---")

periyot_map = {
    "1G": "1d", "5G": "5d", "1A": "1mo", "6A": "6mo",
    "YTD": "ytd", "1Y": "1y", "5Y": "5y",
}
secilen_periyot = periyot_map[aralik_secimi]

# --- FONKSİYONLAR ---
def tarih_formatla(tarih_str):
    try:
        tarih_obj = datetime.strptime(tarih_str[:25], "%a, %d %b %Y %H:%M:%S")
        return tarih_obj.strftime("%d.%m.%Y - %H:%M")
    except: return tarih_str

def buyuk_sayi_formatla(sayi):
    if sayi is None: return "Veri Yok"
    if sayi >= 1_000_000_000_000: return f"{sayi/1_000_000_000_000:.2f} Trilyon"
    if sayi >= 1_000_000_000: return f"{sayi/1_000_000_000:.2f} Milyar"
    if sayi >= 1_000_000: return f"{sayi/1_000_000:.2f} Milyon"
    return f"{sayi}"

# --- 3. HESAPLAMA MOTORU ---
try:
    ticker = yf.Ticker(hisse_kodu)
    kullanilan_interval = "1d"
    if secilen_periyot == "1d": kullanilan_interval = "15m"
    elif secilen_periyot == "5d": kullanilan_interval = "60m"

    veri = ticker.history(period=secilen_periyot, interval=kullanilan_interval)
    info = ticker.info

    if not veri.empty:
        # --- İNDİKATÖRLER ---
        if len(veri) > 20:
            veri['SMA20'] = veri['Close'].rolling(window=20).mean()
            veri['STD'] = veri['Close'].rolling(window=20).std()
            veri['Upper'] = veri['SMA20'] + (veri['STD'] * 2)
            veri['Lower'] = veri['SMA20'] - (veri['STD'] * 2)
        else:
            veri['SMA20'] = None; veri['Upper'] = None; veri['Lower'] = None

        if len(veri) > 50:
            veri['SMA50'] = veri['Close'].rolling(window=50).mean()
        else:
            veri['SMA50'] = None

        delta = veri['Close'].diff()
        gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
        rs = gain / loss
        veri['RSI'] = 100 - (100 / (1 + rs))

        # --- KRİTİK HESAPLAMALAR ---
        current_price = info.get('currentPrice') or info.get('regularMarketPrice') or veri['Close'].iloc[-1]
        previous_close = info.get('previousClose') or info.get('regularMarketPreviousClose')

        if previous_close:
            gunluk_degisim = ((current_price - previous_close) / previous_close) * 100
        else:
            if len(veri) >= 2:
                gunluk_degisim = ((veri['Close'].iloc[-1] - veri['Close'].iloc[-2]) / veri['Close'].iloc[-2]) * 100
            else:
                gunluk_degisim = 0.0

        if secilen_periyot == "1d":
            donemsel_getiri = gunluk_degisim
        else:
            donem_basi_fiyat = veri['Close'].iloc[0]
            donem_sonu_fiyat = veri['Close'].iloc[-1]
            donemsel_getiri = ((donem_sonu_fiyat - donem_basi_fiyat) / donem_basi_fiyat) * 100

        getiri_renk = "green" if donemsel_getiri > 0 else "red"
        getiri_ikon = "🚀" if donemsel_getiri > 0 else "🔻"

        gunluk_getiri = veri['Close'].pct_change()
        volatilite = gunluk_getiri.std() * (252 ** 0.5) * 100

        rolling_max = veri['Close'].cummax()
        drawdown = veri['Close'] / rolling_max - 1.0
        max_drawdown = drawdown.min() * 100

        trend_yonu = "NÖTR ⚪"
        trend_farki = "%0.0"
        if veri['SMA50'] is not None and not pd.isna(veri['SMA50'].iloc[-1]):
            sma50_son = veri['SMA50'].iloc[-1]
            if current_price > sma50_son:
                trend_yonu = "YÜKSELİŞ 🐂"
                trend_farki = f"%{((current_price - sma50_son) / sma50_son) * 100:.1f} (Güçlü)"
            else:
                trend_yonu = "DÜŞÜŞ 🐻"
                trend_farki = f"-%{((sma50_son - current_price) / sma50_son) * 100:.1f} (Zayıf)"

        # --- EKRAN TASARIMI ---
        k1, k2, k3, k4, k5 = st.columns(5)
        para_birimi = info.get('currency', '$')

        if gunluk_degisim < 0:
            delta_str = f"-%{abs(gunluk_degisim):.2f} (Günlük)"
        else:
            delta_str = f"%{gunluk_degisim:.2f} (Günlük)"

        k1.metric("Fiyat", f"{para_birimi}{current_price:.2f}", delta_str)

        rsi_val = veri['RSI'].iloc[-1] if not pd.isna(veri['RSI'].iloc[-1]) else 50
        k2.metric("RSI Gücü", f"{rsi_val:.1f}", "30-70 Normal")
        k3.metric("Oynaklık (Risk)", f"%{volatilite:.1f}", "Volatilite")
        k4.metric("Max Kayıp", f"%{max_drawdown:.1f}", "Zirveden Dip")
        k5.metric("Genel Trend", trend_yonu, trend_farki)

        st.markdown("---")
        st.subheader("📊 Temel Analiz Karnesi")
        t1, t2, t3, t4, t5 = st.columns(5)

        piyasa_degeri = buyuk_sayi_formatla(info.get('marketCap'))
        fk_orani = info.get('trailingPE', 'Yok')
        hedef_fiyat = info.get('targetMeanPrice', 'Yok')
        temettu = info.get('dividendYield', 0)
        sektor = info.get('sector', 'Bilinmiyor')

        temettu_yuzde = f"%{temettu*100:.2f}" if temettu else "Yok"

        potansiyel = "Nötr"
        if isinstance(hedef_fiyat, (int, float)) and hedef_fiyat > current_price:
            fark = ((hedef_fiyat - current_price) / current_price) * 100
            potansiyel = f"%{fark:.1f} Potansiyel 🚀"
        elif isinstance(hedef_fiyat, (int, float)):
            fark = ((hedef_fiyat - current_price) / current_price) * 100
            potansiyel = f"%{fark:.1f} Düşüş Beklentisi"

        t1.metric("Piyasa Değeri", f"{para_birimi}{piyasa_degeri}", "Büyüklük")
        t2.metric("F/K Oranı", f"{fk_orani}", "Değerleme")
        t3.metric("Analist Hedefi", f"{para_birimi}{hedef_fiyat}", potansiyel)
        t4.metric("Temettü", temettu_yuzde, "Kâr Payı")
        t5.metric("Sektör", sektor, info.get('industry', ''))

        with st.expander(f"🏢 {hisse_kodu.upper()} Şirket Profili (Türkçe)"):
            ozet_eng = info.get('longBusinessSummary', 'Bilgi yok.')
            try: ozet_tr = GoogleTranslator(source='auto', target='tr').translate(ozet_eng)
            except: ozet_tr = ozet_eng
            st.write(ozet_tr)
            st.caption(f"CEO: {info.get('companyOfficers', [{}])[0].get('name', 'Bilinmiyor')}")

        st.subheader(f"📉 Fiyat Grafiği ({aralik_secimi}) | Dönemsel Getiri: :{getiri_renk}[{getiri_ikon} %{donemsel_getiri:.2f}]")

        fig = go.Figure()
        fig.add_trace(go.Candlestick(x=veri.index, open=veri['Open'], high=veri['High'], low=veri['Low'], close=veri['Close'], name='Fiyat'))

        if goster_sma20 and veri['SMA20'] is not None:
            fig.add_trace(go.Scatter(x=veri.index, y=veri['SMA20'], line=dict(color='orange', width=1), name='SMA 20'))
        if goster_sma50 and veri['SMA50'] is not None:
            fig.add_trace(go.Scatter(x=veri.index, y=veri['SMA50'], line=dict(color='blue', width=1), name='SMA 50'))
        if goster_bollinger and veri['Upper'] is not None:
            fig.add_trace(go.Scatter(x=veri.index, y=veri['Upper'], line=dict(color='gray', width=0.5, dash='dot'), name='Üst Bant'))
            fig.add_trace(go.Scatter(x=veri.index, y=veri['Lower'], line=dict(color='gray', width=0.5, dash='dot'), name='Alt Bant'))

        fig.update_layout(height=600, xaxis_rangeslider_visible=True, template="plotly_dark", title=f"{hisse_kodu.upper()} ({aralik_secimi})")
        st.plotly_chart(fig, use_container_width=True)

        if len(veri) > 15:
            st.line_chart(veri['RSI'])
        else:
            st.info("⚠️ RSI için yeterli veri yok.")

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.info("🧠 **Teknik Görünüm:**")
            rsi = veri['RSI'].iloc[-1] if not pd.isna(veri['RSI'].iloc[-1]) else 50
            if rsi < 30: st.write("• RSI: Aşırı Satım (UCUZ).")
            elif rsi > 70: st.write("• RSI: Aşırı Alım (PAHALI).")
            else: st.write("• RSI: Nötr.")

            if trend_yonu == "YÜKSELİŞ 🐂": st.write("• Trend: YUKARI")
            else: st.write("• Trend: AŞAĞI veya YATAY")

        with c2:
            st.warning("⚖️ **Temel Değerleme:**")
            if isinstance(fk_orani, (int, float)):
                if fk_orani < 15: st.write("• Fiyat/Kazanç: Düşük (Ucuz).")
                elif fk_orani > 50: st.write("• Fiyat/Kazanç: Yüksek (Pahalı).")
                else: st.write("• Fiyat/Kazanç: Makul.")
            else: st.write("• Veri yok.")

        st.markdown("---")
        simdi = datetime.now()
        ay_isimleri = {1:'Ocak',2:'Şubat',3:'Mart',4:'Nisan',5:'Mayıs',6:'Haziran',7:'Temmuz',8:'Ağustos',9:'Eylül',10:'Ekim',11:'Kasım',12:'Aralık'}
        st.subheader(f"📰 Güncel Haberler ({ay_isimleri[simdi.month]} {simdi.year})")

        rss_url = f"https://news.google.com/rss/search?q={hisse_kodu}+stock+news&hl=en-US&gl=US&ceid=US:en"
        feed = feedparser.parse(rss_url)

        if feed.entries:
            cols = st.columns(2)
            counter = 0
            for entry in feed.entries:
                try:
                    pub = entry.published_parsed
                    if pub.tm_year < simdi.year or (pub.tm_year == simdi.year and pub.tm_mon < simdi.month): continue
                except: continue

                if counter >= 6: break

                try: baslik_tr = GoogleTranslator(source='auto', target='tr').translate(entry.title)
                except: baslik_tr = entry.title

                try: skor = TextBlob(entry.title).sentiment.polarity
                except: skor = 0

                if skor > 0.05: renk, ikon = "green", "🟢"
                elif skor < -0.05: renk, ikon = "red", "🔴"
                else: renk, ikon = "gray", "⚪"

                with cols[counter % 2]:
                    with st.container(border=True):
                        st.markdown(f"**{baslik_tr}**")
                        st.caption(f"🕒 {tarih_formatla(entry.published)}")
                        st.markdown(f":{renk}[{ikon} Etki: {skor:.2f}]")
                        st.markdown(f"[Oku 🔗]({entry.link})")
                counter += 1

            if counter == 0: st.info("Bu ay önemli haber yok.")
        else: st.warning("Haber kaynağına erişilemedi.")
    else: st.error("Veri bulunamadı.")

except Exception as e: st.error(f"Hata: {e}")

# --- 7. YASAL UYARI VE FOOTER ---
st.markdown("---")
st.subheader("⚖️ Yasal Uyarı & Sorumluluk Reddi")
with st.container(border=True):
    st.markdown("""
**Yasal Uyarı**

Burada yer alan yatırım bilgi, yorum ve tavsiyeleri **yatırım danışmanlığı kapsamında değildir.** Yatırım danışmanlığı hizmeti; aracı kurumlar, portföy yönetim şirketleri, mevduat kabul etmeyen bankalar ile müşteri arasında imzalanacak yatırım danışmanlığı sözleşmesi çerçevesinde sunulmaktadır.

**Finansla**, yetkili kuruluşların yetkilendirdiği bir platform değildir; sadece piyasa hareketlerini analiz etmenizi ve örnek çalışmaları görmenizi sağlar. Burada yer alan yorum ve tavsiyeler, yorum ve tavsiyede bulunanların kişisel görüşlerine dayanmaktadır. Bu görüşler, mali durumunuz ile risk ve getiri tercihlerinize uygun olmayabilir. Bu nedenle, sadece burada yer alan bilgilere dayanılarak yatırım kararı verilmesi, beklentilerinize uygun sonuçlar doğurmayabilir.
""")
    st.markdown("""
**Sorumluluk Reddi**

İşbu platformda yer alan bilgi, rapor ve yorumların hazırlanmasında kullanılan yöntemler veya sunulan görüşler, hiçbir yatırımcının veya müşterinin özel ihtiyaçlarına yönelik değildir. Ayrıca **Finansla** ve çalışanlarının; işbu platformda yer alan bilgi, öngörü ve tahminler dolayısıyla ortaya çıkabilecek doğrudan veya dolaylı zararlarla ilgili herhangi bir sorumluluğu bulunmamaktadır.

Bu platformda yer alan bilgiler, güvenilir olduğuna inanılan kaynaklardan derlenmiş olmakla birlikte, **Finansla** bu bilgilerin doğruluğunu ve bütünlüğünü garanti etmez. Bilgi, rapor ve tavsiyelerde yer alan işlem ve tahminler ile **Finansla** yöneticilerinin veya çalışanlarının, doğrudan veya dolaylı olarak aynı veya farklı doğrultuda şahsi pozisyonları bulunabilir.

**Finansla** platformu içinde bulunan hiçbir bilgi; yatırım tavsiyesi, yatırım olanağı veya yatırım fırsatı olarak değerlendirilmemelidir. Yatırımcı, vereceği kararlardan bizzat kendisi sorumludur. Bu siteyi ziyaret etmenizle birlikte, bu sorumluluk reddi beyanını kabul etmiş sayılırsınız.
""")

st.caption("© 2026 Finansla.net | Tüm Hakları Saklıdır. | Efehan Tanırgan Efehan@finansla.net")