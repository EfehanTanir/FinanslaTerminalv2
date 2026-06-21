import streamlit as st
import pandas as pd
import feedparser
from textblob import TextBlob
from datetime import datetime, timedelta
import plotly.graph_objects as go
from deep_translator import GoogleTranslator
from tefas import Crawler

# --- 1. SAYFA AYARLARI ---
st.set_page_config(page_title="Finansla PRO Fon Terminali", layout="wide", page_icon="📊", initial_sidebar_state="expanded")

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

st.title("📊 Finansla.net | TEFAS Fon Analiz Terminali")
st.caption("ℹ️ **BİLGİ:** Fon kodunu giriniz örnek: **PHE, TLY, PBR, AAK** | Veriler tefas.gov.tr'nin halka açık kaynağından çekilir.")
st.markdown("---")

# --- 2. ÜST KONTROL PANELİ ---
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    fon_kodu = st.text_input("🔍 Fon Kodu", "PHE")
with col2:
    aralik_secimi = st.selectbox("📅 Periyot", ["1A", "3A", "6A", "1Y", "3Y", "5Y"], index=3)
with col3:
    st.write("")
    st.write("")
    if st.button("Analizi Başlat 🚀"):
        st.rerun()

st.markdown("---")

periyot_map = {
    "1A": 1, "3A": 3, "6A": 6, "1Y": 12, "3Y": 36, "5Y": 60,
}
secilen_ay = periyot_map[aralik_secimi]

# --- 3. TEFAS CRAWLER ---
tefas = Crawler()

# --- FONKSİYONLAR ---
def tarih_formatla(tarih_str):
    try:
        tarih_obj = datetime.strptime(tarih_str[:25], "%a, %d %b %Y %H:%M:%S")
        return tarih_obj.strftime("%d.%m.%Y - %H:%M")
    except: return tarih_str

@st.cache_data(ttl=900)
def fon_verisi_cek(kod, ay):
    bugun = datetime.now()
    baslangic = bugun - timedelta(days=ay * 30 + 5)
    df = tefas.fetch(
        start=baslangic.strftime("%Y-%m-%d"),
        end=bugun.strftime("%Y-%m-%d"),
        name=kod.upper().strip(),
    )
    return df

# --- 4. HESAPLAMA MOTORU ---
try:
    veri = fon_verisi_cek(fon_kodu, secilen_ay)

    if veri is not None and not veri.empty:
        veri = veri.sort_values("date").reset_index(drop=True)
        veri = veri.dropna(subset=["price"])

        if len(veri) < 2:
            st.warning("⚠️ Bu fon için yeterli fiyat verisi bulunamadı. Farklı bir periyot deneyin.")
            st.stop()

        veri["fiyat"] = veri["price"].astype(float)

        # --- İNDİKATÖRLER ---
        if len(veri) > 20:
            veri["SMA20"] = veri["fiyat"].rolling(window=20).mean()
        else:
            veri["SMA20"] = None

        if len(veri) > 50:
            veri["SMA50"] = veri["fiyat"].rolling(window=50).mean()
        else:
            veri["SMA50"] = None

        gunluk_getiri = veri["fiyat"].pct_change()

        # --- KRİTİK HESAPLAMALAR ---
        current_price = float(veri["fiyat"].iloc[-1])
        onceki_fiyat = float(veri["fiyat"].iloc[-2]) if len(veri) >= 2 else current_price
        gunluk_degisim = ((current_price - onceki_fiyat) / onceki_fiyat) * 100 if onceki_fiyat else 0.0

        donem_basi_fiyat = float(veri["fiyat"].iloc[0])
        donemsel_getiri = ((current_price - donem_basi_fiyat) / donem_basi_fiyat) * 100

        getiri_renk = "green" if donemsel_getiri > 0 else "red"
        getiri_ikon = "🚀" if donemsel_getiri > 0 else "🔻"

        volatilite = gunluk_getiri.std() * (252 ** 0.5) * 100

        risksiz_oran = 0.45  # TR politika faizi yaklaşık varsayımı
        yillik_getiri = gunluk_getiri.mean() * 252
        std_yillik = gunluk_getiri.std() * (252 ** 0.5)
        sharpe = (yillik_getiri - risksiz_oran) / std_yillik if std_yillik > 0 else 0

        negatif_getiri = gunluk_getiri[gunluk_getiri < 0]
        downside_std = negatif_getiri.std() * (252 ** 0.5) if len(negatif_getiri) > 1 else 0.0001
        sortino = (yillik_getiri - risksiz_oran) / downside_std if downside_std > 0 else 0

        var95 = -(1.645 * gunluk_getiri.std() * 100)

        rolling_max = veri["fiyat"].cummax()
        drawdown = veri["fiyat"] / rolling_max - 1.0
        max_drawdown = drawdown.min() * 100

        trend_yonu = "NÖTR ⚪"
        trend_farki = "%0.0"
        if veri["SMA50"] is not None and not pd.isna(veri["SMA50"].iloc[-1]):
            sma50_son = veri["SMA50"].iloc[-1]
            if current_price > sma50_son:
                trend_yonu = "YÜKSELİŞ 🐂"
                trend_farki = f"%{((current_price - sma50_son) / sma50_son) * 100:.1f} (Güçlü)"
            else:
                trend_yonu = "DÜŞÜŞ 🐻"
                trend_farki = f"-%{((sma50_son - current_price) / sma50_son) * 100:.1f} (Zayıf)"

        kategori_derece = veri["category_rank"].iloc[-1] if "category_rank" in veri.columns and pd.notna(veri["category_rank"].iloc[-1]) else None
        kategori_toplam = veri["category_total"].iloc[-1] if "category_total" in veri.columns and pd.notna(veri["category_total"].iloc[-1]) else None
        fon_unvan = veri["title"].iloc[-1] if "title" in veri.columns and pd.notna(veri["title"].iloc[-1]) else fon_kodu.upper()

        # --- EKRAN TASARIMI ---
        st.subheader(f"🏦 {fon_unvan}")

        k1, k2, k3, k4, k5 = st.columns(5)

        delta_str = f"%{gunluk_degisim:.2f} (Günlük)" if gunluk_degisim >= 0 else f"-%{abs(gunluk_degisim):.2f} (Günlük)"
        k1.metric("Fiyat", f"₺{current_price:.4f}", delta_str)
        k2.metric("Sharpe Oranı", f"{sharpe:.2f}", "Risk-Getiri")
        k3.metric("Oynaklık (Risk)", f"%{volatilite:.1f}", "Volatilite")
        k4.metric("Max Kayıp", f"%{max_drawdown:.1f}", "Zirveden Dip")
        k5.metric("Genel Trend", trend_yonu, trend_farki)

        st.markdown("---")
        st.subheader("📊 Risk & Getiri Karnesi")
        t1, t2, t3, t4, t5 = st.columns(5)

        t1.metric("Sortino Oranı", f"{sortino:.2f}", "İndirim Riski")
        t2.metric("VaR %95 (Günlük)", f"%{var95:.2f}", "Olası Kayıp")
        t3.metric("Dönemsel Getiri", f"%{donemsel_getiri:.2f}", aralik_secimi)
        if kategori_derece is not None and kategori_toplam is not None:
            t4.metric("Kategori Sırası", f"{int(kategori_derece)} / {int(kategori_toplam)}", "Kategori İçi")
        else:
            t4.metric("Kategori Sırası", "Veri Yok", "")
        t5.metric("Veri Aralığı", f"{len(veri)} gün", f"{aralik_secimi}")

        st.subheader(f"📉 Fiyat Grafiği ({aralik_secimi}) | Dönemsel Getiri: :{getiri_renk}[{getiri_ikon} %{donemsel_getiri:.2f}]")

        fig = go.Figure()
        fig.add_trace(go.Scatter(x=veri["date"], y=veri["fiyat"], line=dict(color="#4F9CF9", width=2), name="Fiyat", fill="tozeroy", fillcolor="rgba(79,156,249,0.08)"))

        if veri["SMA20"] is not None:
            fig.add_trace(go.Scatter(x=veri["date"], y=veri["SMA20"], line=dict(color="orange", width=1), name="SMA 20"))
        if veri["SMA50"] is not None:
            fig.add_trace(go.Scatter(x=veri["date"], y=veri["SMA50"], line=dict(color="purple", width=1), name="SMA 50"))

        fig.update_layout(height=550, template="plotly_dark", title=f"{fon_kodu.upper()} ({aralik_secimi})")
        st.plotly_chart(fig, use_container_width=True)

        st.markdown("---")
        c1, c2 = st.columns(2)
        with c1:
            st.info("🧠 **Risk Görünümü:**")
            if sharpe > 1: st.write("• Sharpe: Riske göre güçlü getiri.")
            elif sharpe > 0: st.write("• Sharpe: Pozitif ama zayıf risk-ayarlı getiri.")
            else: st.write("• Sharpe: Risksiz orana göre zayıf performans.")

            if trend_yonu == "YÜKSELİŞ 🐂": st.write("• Trend: YUKARI")
            else: st.write("• Trend: AŞAĞI veya YATAY")

        with c2:
            st.warning("⚖️ **Volatilite Değerlendirmesi:**")
            if volatilite < 12: st.write("• Oynaklık: Düşük (görece istikrarlı).")
            elif volatilite < 25: st.write("• Oynaklık: Orta seviye.")
            else: st.write("• Oynaklık: Yüksek (dikkatli pozisyon büyüklüğü önerilir).")

        # --- 5. HABERLER ---
        st.markdown("---")
        simdi = datetime.now()
        ay_isimleri = {1:'Ocak',2:'Şubat',3:'Mart',4:'Nisan',5:'Mayıs',6:'Haziran',7:'Temmuz',8:'Ağustos',9:'Eylül',10:'Ekim',11:'Kasım',12:'Aralık'}
        st.subheader(f"📰 TEFAS & Fon Piyasası Haberleri ({ay_isimleri[simdi.month]} {simdi.year})")

        haber_sorgusu = f"{fon_unvan} TEFAS fon"
        rss_url = f"https://news.google.com/rss/search?q={haber_sorgusu}&hl=tr-TR&gl=TR&ceid=TR:tr"
        feed = feedparser.parse(rss_url)

        if feed.entries:
            cols = st.columns(2)
            counter = 0
            for entry in feed.entries:
                if counter >= 6: break

                try: baslik_tr = GoogleTranslator(source="auto", target="tr").translate(entry.title)
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

            if counter == 0:
                st.info("Bu fon için güncel haber bulunamadı.")
        else:
            st.warning("Haber kaynağına erişilemedi veya bu fon için haber bulunamadı.")

    else:
        st.error(f"'{fon_kodu.upper()}' kodlu fon için veri bulunamadı. Fon kodunu kontrol edin.")

except Exception as e:
    st.error(f"Hata: {e}")

# --- 6. YASAL UYARI VE FOOTER ---
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

st.caption("© 2025 Finansla.net | Tüm Hakları Saklıdır. | Efehan Tanırgan Efehan@finansla.net")
