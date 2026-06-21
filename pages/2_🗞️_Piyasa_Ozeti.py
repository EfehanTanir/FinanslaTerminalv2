import streamlit as st
import pandas as pd
import yfinance as yf
from datetime import datetime, timedelta
from tefas import Crawler

# --- 1. SAYFA AYARLARI ---
st.set_page_config(page_title="Finansla PRO Piyasa Özeti", layout="wide", page_icon="🗞️", initial_sidebar_state="expanded")

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

st.title("🗞️ Finansla.net | Günün Piyasa Özeti")
st.caption("ℹ️ **BİLGİ:** BIST hisseleri ve TEFAS fonlarında günün kazananları/kaybedenleri. Veriler 15 dakikada bir yenilenir.")
st.markdown("---")

tefas = Crawler()

# --- TAKİP LİSTELERİ ---
# Not: Hem yfinance hem TEFAS'ın yeni API'si "tüm piyasayı tek seferde getir"
# desteklemiyor — bu yüzden popüler/likit bir sembol havuzu taranıyor.
BIST_HAVUZU = [
    "THYAO.IS", "GARAN.IS", "ASELS.IS", "EREGL.IS", "SASA.IS",
    "BIMAS.IS", "KCHOL.IS", "AKBNK.IS", "YKBNK.IS", "TUPRS.IS",
    "PGSUS.IS", "FROTO.IS", "TOASO.IS", "SISE.IS", "ARCLK.IS",
    "KOZAL.IS", "TCELL.IS", "SAHOL.IS", "MGROS.IS", "HEKTS.IS",
    "ISCTR.IS", "VAKBN.IS", "HALKB.IS", "TAVHL.IS", "ENKAI.IS",
]

TEFAS_HAVUZU = [
    "PHE", "PBR", "TLY", "AVR", "IJC", "FGS", "FMG", "YAY", "YZG",
    "GUH", "GMC", "GUM", "IOG", "GMF", "GTZ", "TTE", "BHT", "OJT",
    "ZKP", "KEH",
]

# --- FONKSİYONLAR ---
@st.cache_data(ttl=900, show_spinner=False)
def bist_taramasi(semboller):
    sonuc = []
    for sym in semboller:
        try:
            t = yf.Ticker(sym)
            info = t.info
            fiyat = info.get("currentPrice") or info.get("regularMarketPrice")
            degisim = info.get("regularMarketChangePercent")
            hacim = info.get("regularMarketVolume") or info.get("volume")
            isim = info.get("shortName") or sym.replace(".IS", "")
            if fiyat is not None and degisim is not None:
                sonuc.append({
                    "Sembol": sym.replace(".IS", ""),
                    "Şirket": isim,
                    "Fiyat": fiyat,
                    "Değişim %": degisim,
                    "Hacim": hacim or 0,
                })
        except Exception:
            continue
    return pd.DataFrame(sonuc)


@st.cache_data(ttl=900, show_spinner=False)
def tefas_taramasi(kodlar):
    bugun = datetime.now()
    baslangic = bugun - timedelta(days=10)
    sonuc = []
    for kod in kodlar:
        try:
            df = tefas.fetch(
                start=baslangic.strftime("%Y-%m-%d"),
                end=bugun.strftime("%Y-%m-%d"),
                name=kod,
            )
            if df is None or df.empty:
                continue
            df = df.sort_values("date").dropna(subset=["price"])
            if len(df) < 2:
                continue
            son_fiyat = float(df["price"].iloc[-1])
            onceki_fiyat = float(df["price"].iloc[-2])
            degisim = ((son_fiyat - onceki_fiyat) / onceki_fiyat) * 100 if onceki_fiyat else 0.0
            unvan = df["title"].iloc[-1] if "title" in df.columns and pd.notna(df["title"].iloc[-1]) else kod
            sonuc.append({
                "Kod": kod,
                "Fon Adı": unvan,
                "Fiyat": son_fiyat,
                "Değişim %": degisim,
            })
        except Exception:
            continue
    return pd.DataFrame(sonuc)


def renkli_degisim(val):
    if val > 0:
        return f"🟢 +%{val:.2f}"
    elif val < 0:
        return f"🔴 %{val:.2f}"
    return f"⚪ %{val:.2f}"


# --- 2. BIST ÖZETİ ---
with st.spinner("BIST hisseleri taranıyor..."):
    bist_df = bist_taramasi(BIST_HAVUZU)

st.subheader("📈 BIST — Günün Hareketi")

if not bist_df.empty:
    k1, k2, k3 = st.columns(3)
    yukselen = (bist_df["Değişim %"] > 0).sum()
    dusen = (bist_df["Değişim %"] < 0).sum()
    ort_degisim = bist_df["Değişim %"].mean()

    k1.metric("Yükselen", f"{yukselen} hisse", "Pozitif")
    k2.metric("Düşen", f"{dusen} hisse", "Negatif")
    k3.metric("Ortalama Değişim", f"%{ort_degisim:.2f}", f"{len(bist_df)} hisse taranıyor")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**🚀 En Çok Yükselenler**")
        en_yuksek = bist_df.sort_values("Değişim %", ascending=False).head(5)
        for _, row in en_yuksek.iterrows():
            with st.container(border=True):
                cc1, cc2 = st.columns([2, 1])
                cc1.markdown(f"**{row['Sembol']}** — {row['Şirket']}")
                cc1.caption(f"₺{row['Fiyat']:.2f}")
                cc2.markdown(f"### {renkli_degisim(row['Değişim %'])}")

    with c2:
        st.markdown("**🔻 En Çok Düşenler**")
        en_dusuk = bist_df.sort_values("Değişim %", ascending=True).head(5)
        for _, row in en_dusuk.iterrows():
            with st.container(border=True):
                cc1, cc2 = st.columns([2, 1])
                cc1.markdown(f"**{row['Sembol']}** — {row['Şirket']}")
                cc1.caption(f"₺{row['Fiyat']:.2f}")
                cc2.markdown(f"### {renkli_degisim(row['Değişim %'])}")

    with st.expander("📋 Taranan Tüm BIST Hisseleri"):
        goster_df = bist_df.copy()
        goster_df["Fiyat"] = goster_df["Fiyat"].apply(lambda x: f"₺{x:.2f}")
        goster_df["Değişim %"] = goster_df["Değişim %"].apply(lambda x: f"%{x:.2f}")
        goster_df["Hacim"] = goster_df["Hacim"].apply(lambda x: f"{x:,.0f}")
        st.dataframe(goster_df.sort_values("Değişim %", ascending=False), use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ BIST verisi şu anda çekilemedi. Birkaç dakika sonra tekrar deneyin (Yahoo Finance rate limit olabilir).")

st.markdown("---")

# --- 3. TEFAS ÖZETİ ---
st.subheader("🏦 TEFAS — Günün Fon Hareketi")

with st.spinner("TEFAS fonları taranıyor..."):
    tefas_df = tefas_taramasi(TEFAS_HAVUZU)

if not tefas_df.empty:
    k1, k2, k3 = st.columns(3)
    yukselen_f = (tefas_df["Değişim %"] > 0).sum()
    dusen_f = (tefas_df["Değişim %"] < 0).sum()
    ort_degisim_f = tefas_df["Değişim %"].mean()

    k1.metric("Yükselen Fon", f"{yukselen_f} fon", "Pozitif")
    k2.metric("Düşen Fon", f"{dusen_f} fon", "Negatif")
    k3.metric("Ortalama Değişim", f"%{ort_degisim_f:.2f}", f"{len(tefas_df)} fon taranıyor")

    c1, c2 = st.columns(2)

    with c1:
        st.markdown("**🚀 En Çok Yükselen Fonlar**")
        en_yuksek_f = tefas_df.sort_values("Değişim %", ascending=False).head(5)
        for _, row in en_yuksek_f.iterrows():
            with st.container(border=True):
                cc1, cc2 = st.columns([2, 1])
                cc1.markdown(f"**{row['Kod']}**")
                cc1.caption(row["Fon Adı"][:50] + ("…" if len(row["Fon Adı"]) > 50 else ""))
                cc2.markdown(f"### {renkli_degisim(row['Değişim %'])}")

    with c2:
        st.markdown("**🔻 En Çok Düşen Fonlar**")
        en_dusuk_f = tefas_df.sort_values("Değişim %", ascending=True).head(5)
        for _, row in en_dusuk_f.iterrows():
            with st.container(border=True):
                cc1, cc2 = st.columns([2, 1])
                cc1.markdown(f"**{row['Kod']}**")
                cc1.caption(row["Fon Adı"][:50] + ("…" if len(row["Fon Adı"]) > 50 else ""))
                cc2.markdown(f"### {renkli_degisim(row['Değişim %'])}")

    with st.expander("📋 Taranan Tüm TEFAS Fonları"):
        goster_df_f = tefas_df.copy()
        goster_df_f["Fiyat"] = goster_df_f["Fiyat"].apply(lambda x: f"₺{x:.4f}")
        goster_df_f["Değişim %"] = goster_df_f["Değişim %"].apply(lambda x: f"%{x:.2f}")
        st.dataframe(goster_df_f.sort_values("Değişim %", ascending=False), use_container_width=True, hide_index=True)
else:
    st.warning("⚠️ TEFAS verisi şu anda çekilemedi. Birkaç dakika sonra tekrar deneyin.")

st.markdown("---")
st.caption("💡 İpucu: Belirli bir hisse veya fonu detaylı incelemek için sol menüden ilgili sayfaya geçin.")

# --- 4. YASAL UYARI VE FOOTER ---
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
