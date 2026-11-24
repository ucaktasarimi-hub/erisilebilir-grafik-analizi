import io
import re
import streamlit as st
from google import genai
from google.genai import types
from gtts import gTTS
from PIL import Image
try:
    API_KEY = st.secrets["API_KEY"]
except Exception:
    from gizli_anahtar import API_KEY

# Yapay zeka bağlantısını kuruyoruz
client = genai.Client(api_key=API_KEY.strip())

def bilimsel_metin_duzenle(metin):
    """
    NLP Ön İşleme Katmanı:
    Bilimsel gösterimleri, üslü ifadeleri, birimleri ve matematik sembollerini
    seslendirme motorunun doğru telaffuz edeceği Türkçe metne dönüştürür.
    """
    duzenli = (
        metin.replace("---", "")
        .replace("- ", "")
        .replace("*", "")
        .replace("#", "")
    )

    # Bilimsel gösterim dönüşümleri (Örn: 1e-8 -> 1 çarpı 10 üzeri eksi 8)
    duzenli = re.sub(r"(\d+)\s*[eE]\s*\+?(\d+)", r"\1 çarpı 10 üzeri \2", duzenli)
    duzenli = re.sub(r"(\d+)\s*[eE]\s*-(\d+)", r"\1 çarpı 10 üzeri eksi \2", duzenli)
    duzenli = re.sub(r"10\s*\^\s*-(\d+)", r"10 üzeri eksi \1", duzenli)
    duzenli = re.sub(r"10\s*\^\s*\+?(\d+)", r"10 üzeri \1", duzenli)

    # Fizik ve matematik birimleri
    birim_sozlugu = {
        "m/s²": "metre bölü saniye kare",
        "m/s^2": "metre bölü saniye kare",
        "m/s": "metre bölü saniye",
        "km/h": "kilometre bölü saat",
        "km/sa": "kilometre bölü saat",
        "°C": "santigrat derece",
        "°F": "fahrenhayt derece",
        "cm²": "santimetrekare",
        "m²": "metrekare",
        "cm³": "santimetreküp",
        "m³": "metreküp",
        "x²": "iks kare",
        "x³": "iks küp",
        "y²": "ye kare",
    }
    for sembol, okunus in birim_sozlugu.items():
        duzenli = duzenli.replace(sembol, f" {okunus} ")

    # Matematiksel ve bilimsel semboller
    sembol_sozlugu = {
        "Δ": " delta ",
        "≥": " büyük veya eşittir ",
        "≤": " küçük veya eşittir ",
        "≠": " eşit değildir ",
        "≈": " yaklaşık olarak ",
        "√": " karekök ",
        "π": " pi ",
        "α": " alfa ",
        "β": " beta ",
        "θ": " teta ",
        "Ω": " ohm ",
        "°": " derece ",
        "%": " yüzde ",
    }
    for sembol, okunus in sembol_sozlugu.items():
        duzenli = duzenli.replace(sembol, okunus)

    duzenli = re.sub(r"[ \t]+", " ", duzenli).strip()
    return duzenli

def sese_cevir(metin):
    okunacak_metin = bilimsel_metin_duzenle(metin)
    tts = gTTS(text=okunacak_metin, lang="tr")
    ses_hafiza = io.BytesIO()
    tts.write_to_fp(ses_hafiza)
    ses_hafiza.seek(0)
    return ses_hafiza.read()

def yapay_zekaya_sor(icerik_listesi):
    hizli_modeller = ["gemini-3.8-flash-lite", "gemini-3.8-flash", "gemini-3.5-flash", "gemini-2.5-flash-lite"]
    onceki_basarili = st.session_state.get("calisan_model")
    if onceki_basarili:
        if onceki_basarili in hizli_modeller:
            hizli_modeller.remove(onceki_basarili)
        hizli_modeller.insert(0, onceki_basarili)

    son_hata = ""
    for model_adi in hizli_modeller:
        try:
            cevap = client.models.generate_content(
                model=model_adi,
                contents=icerik_listesi
            )
            st.session_state["calisan_model"] = model_adi
            return cevap.text, ""
        except Exception as hata:
            son_hata = f"{model_adi}: {hata}"
            continue

    if "yedek_modeller" not in st.session_state:
        yedekler = []
        try:
            for m in client.models.list():
                isim = m.name.replace("models/", "")
                if "gemini" in isim and "embedding" not in isim and "imagen" not in isim and "veo" not in isim and isim not in hizli_modeller:
                    yedekler.append(isim)
        except Exception:
            pass
        st.session_state["yedek_modeller"] = yedekler[:5]

    for model_adi in st.session_state["yedek_modeller"]:
        try:
            cevap = client.models.generate_content(
                model=model_adi,
                contents=icerik_listesi
            )
            st.session_state["calisan_model"] = model_adi
            return cevap.text, ""
        except Exception as hata:
            son_hata = f"{model_adi}: {hata}"
            continue

    return None, son_hata

# --- ARAYÜZ BAŞLANGICI ---
st.title("Erişilebilir Grafik Analiz Arayüzü")
st.write("Görme engelli öğrenciler için sesli ve etkileşimli teknik grafik yorumlama asistanı")

# Sesli Kullanım Rehberi
if st.button("Uygulama Kullanım Rehberini Sesli Dinle"):
    rehber_metni = (
        "Bu sayfada üç kolay adım bulunur. "
        "Birinci adımda bilgisayarınızdan veya telefonunuzdan analiz edilecek grafik fotoğrafını seçip yükleyin. "
        "İkinci adımda detaylı öğretim veya hızlı özet modunu seçip Grafiği Analiz Et butonuna basarak sesli açıklamayı dinleyebilir ve ses dosyası olarak indirebilirsiniz. "
        "Üçüncü adımda ise sayfanın altındaki mikrofon simgesine basarak merak ettiğiniz tüm soruları sesli olarak sorabilirsiniz."
    )
    st.session_state["rehber_ses"] = sese_cevir(rehber_metni)

if st.session_state.get("rehber_ses"):
    st.audio(st.session_state["rehber_ses"], format="audio/mp3", autoplay=True)

st.divider()

# 1. Bilgisayardan grafik seçme kutusu
st.subheader("1. Adım: İncelenecek Grafiği Yükleyin")
yuklenen_grafik = st.file_uploader("Analiz edilecek grafik fotoğrafını seçin", type=["jpg", "jpeg", "png"])

if yuklenen_grafik is not None:
    if st.session_state.get("son_grafik") != yuklenen_grafik.name:
        st.session_state["son_grafik"] = yuklenen_grafik.name
        st.session_state["analiz_metni"] = None
        st.session_state["analiz_ses"] = None
        st.session_state["sohbet_gecmisi"] = []
        st.session_state["son_cevap_ses"] = None
        st.session_state["son_ses_sorusu"] = None

    gorsel = Image.open(yuklenen_grafik)
    st.image(gorsel, caption="Yüklenen Görsel")

    kucuk_gorsel = gorsel.copy()
    kucuk_gorsel.thumbnail((1024, 1024))

    # 2. Anlatım Modu ve Ana Grafik Analizi
    st.subheader("2. Adım: Anlatım Modunu Seçin ve Yorumlayın")
    anlatim_modu = st.radio(
        "Anlatım derinliğini belirleyin:",
        ["Detaylı Öğretim Modu (4 Adımlı Analiz)", "Hızlı Özet Modu (Kısa ve Net)"],
        horizontal=True
    )

    if st.button("Grafiği Analiz Et"):
        with st.spinner("Görsel inceleniyor, lütfen bekleyin..."):
            if anlatim_modu == "Hızlı Özet Modu (Kısa ve Net)":
                mod_talimati = """
                DURUM A - Görsel bir veri grafiği veya tablo ise:
                4 başlık açmadan, grafiğin neyi gösterdiğini, eksen değişkenlerini, en kritik değişimi ve temel bilimsel sonucunu toplam 3 kısa ve net cümlede özetle.
                """
            else:
                mod_talimati = """
                DURUM A - Görsel bir veri grafiği veya tablo ise (çizgi, sütun, pasta, dağılım grafiği vb.):
                Şu 4 adımı sırayla uygula:
                1. Grafiğin Türü ve Başlığı: Bu nasıl bir grafik ve neyi gösteriyor?
                2. Eksenler ve Birimler: Yatay (X) ve dikey (Y) eksenlerde hangi değişkenler ve birimler var?
                3. Genel Eğilim ve Kritik Noktalar: Değerler nasıl değişiyor (artış, azalış, sabit kalma) ve en yüksek/en düşük noktalar nereler?
                4. Bilimsel Yorum: Bu grafikten çıkarılması gereken temel bilimsel sonuç nedir?
                """

            yonerge = f"""
            Sen görme engelli lise öğrencileri için teknik grafikleri ve ders şemalarını yorumlayan bir erişilebilirlik asistanısın.
            Kesinlikle 'Merhaba', 'Merhaba öğrencim', 'Sevgili öğrencim' gibi selamlama, hitap veya giriş cümleleri kullanma. Doğrudan sonuca başla ve ekstra kapanış cümlesi ekleme.
            Ekran okuyucu programlarla uyumlu, sade, nesnel ve anlaşılır bir dil kullan. Karmaşık semboller, yıldızlar veya ayırıcı çizgiler kullanma.

            Önce yüklenen görselin türünü belirle ve şu üç kuraldan uygun olanını uygula:

            {mod_talimati}

            DURUM B - Görsel bir ders şeması veya geometrik şekil ise (geometri çizimi, elektrik devresi, kuvvet diyagramı, biyoloji şeması vb.):
            Eksen aramaya çalışma. Bunun yerine şeklin veya şemanın türünü, üzerindeki tüm harf, açı, ölçü ve etiketleri, parçaların birbirine göre konumunu ve bilimsel/matematiksel anlamını açıkla.

            DURUM C - Görsel herhangi bir grafik, tablo, geometrik şekil veya ders şeması içermeyen günlük bir fotoğraf ise (manzara, insan, eşya vb.):
            Görseli betimlemeye çalışma. Yalnızca şu cümleyi yaz: "Yüklenen görsel bir grafik veya ders şeması değildir. Lütfen analiz için matematik, fen veya teknik bir grafik yükleyin."
            """
            cevap_metni, son_hata = yapay_zekaya_sor([yonerge, kucuk_gorsel])

            if cevap_metni:
                st.session_state["analiz_metni"] = cevap_metni
                st.session_state["analiz_ses"] = None
                st.session_state["sohbet_gecmisi"] = []
            else:
                st.warning("Yapay zeka sunucularında şu an yoğunluk var. Lütfen birkaç saniye bekleyip tekrar deneyin.")
                st.caption(f"Teknik bilgi: {son_hata}")

    if st.session_state.get("analiz_metni"):
        st.write(st.session_state["analiz_metni"])

        if st.button("Analizi Sesli Dinle"):
            with st.spinner("Ses dosyası hazırlanıyor..."):
                st.session_state["analiz_ses"] = sese_cevir(st.session_state["analiz_metni"])

        if st.session_state.get("analiz_ses"):
            st.audio(st.session_state["analiz_ses"], format="audio/mp3", autoplay=True)
            st.download_button(
                label="Ses Kaydını İndir (.mp3)",
                data=st.session_state["analiz_ses"],
                file_name="grafik_analizi.mp3",
                mime="audio/mp3"
            )

        # 3. Bağlamı Hatırlayan Sesli ve Yazılı Soru-Cevap
        st.divider()
        st.subheader("3. Adım: Grafik Hakkında Sesli Soru Sor")
        st.write("Mikrofona basıp sorunuzu söyleyin. Asistan önceki konuşmalarınızı hatırlayarak sorunuzu yanıtlar ve sesli okur.")

        sesli_soru = st.audio_input("Sorunuzu kaydetmek için mikrofona basın")

        if sesli_soru is not None:
            ses_verisi = sesli_soru.getvalue()
            if ses_verisi != st.session_state.get("son_ses_sorusu"):
                st.session_state["son_ses_sorusu"] = ses_verisi
                with st.spinner("Sesli sorunuz dinleniyor ve önceki bilgilerle birlikte değerlendiriliyor..."):
                    ses_turu = sesli_soru.type if sesli_soru.type else "audio/wav"
                    ses_parcasi = types.Part.from_bytes(data=ses_verisi, mime_type=ses_turu)

                    gecmis_ozeti = "\n".join(
                        [f"Soru: {s}\nCevap: {c}" for s, c in st.session_state["sohbet_gecmisi"]]
                    )
                    sesli_yonerge = f"""
                    Sen görme engelli lise öğrencileri için teknik grafikleri ve ders şemalarını yorumlayan bir erişilebilirlik asistanısın.
                    Kesinlikle 'Merhaba', 'Merhaba öğrencim', 'Sevgili öğrencim' gibi selamlama, hitap veya giriş cümleleri kullanma; doğrudan sorunun cevabıyla başla ve ekstra kapanış cümlesi ekleme.
                    Görselin genel özeti: {st.session_state['analiz_metni']}
                    Önceki soru-cevap geçmişi:
                    {gecmis_ozeti}

                    Ekteki ses kaydında kullanıcının yeni sorusu bulunuyor.
                    Önceki konuşmaları da dikkate alarak, ekran okuyucu uyumlu, yıldız veya ayırıcı çizgi kullanmadan sade, net ve doğrudan bir Türkçe cevap ver.
                    """
                    soru_yaniti, hata_detay = yapay_zekaya_sor([sesli_yonerge, kucuk_gorsel, ses_parcasi])
                    if soru_yaniti:
                        st.session_state["sohbet_gecmisi"].append(("Sesli Soru", soru_yaniti))
                        st.session_state["son_cevap_ses"] = sese_cevir(soru_yaniti)
                    else:
                        st.warning("Şu an sesli sorunuza cevap üretilemedi, lütfen tekrar deneyin.")

        with st.expander("Alternatif: Soruyu Yazarak Sormak İsterseniz"):
            ogrenci_sorusu = st.text_input("Grafikle ilgili sorunuzu yazın")
            if st.button("Yazılı Soruyu Cevapla"):
                if ogrenci_sorusu.strip():
                    with st.spinner("Sorunuz inceleniyor..."):
                        gecmis_ozeti = "\n".join(
                            [f"Soru: {s}\nCevap: {c}" for s, c in st.session_state["sohbet_gecmisi"]]
                        )
                        soru_yonergesi = f"""
                        Sen görme engelli lise öğrencileri için teknik grafikleri ve ders şemalarını yorumlayan bir erişilebilirlik asistanısın.
                        Kesinlikle 'Merhaba', 'Merhaba öğrencim', 'Sevgili öğrencim' gibi selamlama, hitap veya giriş cümleleri kullanma; doğrudan sorunun cevabıyla başla ve ekstra kapanış cümlesi ekleme.
                        Görselin genel özeti: {st.session_state['analiz_metni']}
                        Önceki soru-cevap geçmişi:
                        {gecmis_ozeti}

                        Kullanıcının yeni sorusu: {ogrenci_sorusu}
                        Önceki konuşmaları da dikkate alarak, ekran okuyucu uyumlu, yıldız veya ayırıcı çizgi kullanmadan sade, net ve doğrudan bir Türkçe cevap ver.
                        """
                        soru_yaniti, hata_detay = yapay_zekaya_sor([soru_yonergesi, kucuk_gorsel])
                        if soru_yaniti:
                            st.session_state["sohbet_gecmisi"].append((ogrenci_sorusu, soru_yaniti))
                            st.session_state["son_cevap_ses"] = sese_cevir(soru_yaniti)
                        else:
                            st.warning("Şu an cevap üretilemedi, lütfen tekrar deneyin.")
                else:
                    st.info("Lütfen önce yukarıdaki kutuya bir soru yazın.")

        # Sohbet geçmişini ve en son cevabın ses oynatıcısını göster
        if st.session_state.get("sohbet_gecmisi"):
            st.subheader("Soru - Cevap Geçmişi")
            for idx, (soru_m, cevap_m) in enumerate(st.session_state["sohbet_gecmisi"], 1):
                st.markdown(f"**{idx}. Soru ({soru_m}):** {cevap_m}")

            if st.session_state.get("son_cevap_ses"):
                st.audio(st.session_state["son_cevap_ses"], format="audio/mp3", autoplay=True)
