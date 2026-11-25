import os
import io
import base64
import streamlit as st
from PIL import Image
from gtts import gTTS
from groq import Groq

st.set_page_config(page_title="Erişilebilir Grafik Asistanı", layout="centered")


def get_groq_api_key() -> str:
    try:
        if "GROQ_API_KEY" in st.secrets:
            return str(st.secrets["GROQ_API_KEY"]).strip().strip('"').strip("'")
    except Exception:
        pass

    env_key = os.environ.get("GROQ_API_KEY", "").strip().strip('"').strip("'")
    if env_key:
        return env_key

    try:
        import gizli_anahtar
        key = getattr(gizli_anahtar, "GROQ_API_KEY", "") or getattr(gizli_anahtar, "API_KEY", "")
        temiz_key = str(key).strip().strip('"').strip("'")
        if temiz_key.startswith("gsk_"):
            return temiz_key
    except ImportError:
        pass

    return ""


def gorseli_base64_yap(yuklenen_dosya) -> str:
    img = Image.open(yuklenen_dosya).convert("RGB")
    img.thumbnail((1200, 1200))
    tampon = io.BytesIO()
    img.save(tampon, format="JPEG", quality=85)
    return base64.b64encode(tampon.getvalue()).decode("utf-8")


def metni_mp3_yap(metin: str) -> bytes:
    temiz_metin = metin.replace("*", "").replace("#", "").replace("`", "")
    tts = gTTS(text=temiz_metin, lang="tr")
    ses_tamponu = io.BytesIO()
    tts.write_to_fp(ses_tamponu)
    ses_tamponu.seek(0)
    return ses_tamponu.read()


def aktif_gorsel_modellerini_bul(client: Groq) -> list[str]:
    yedek_liste = [
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "meta-llama/llama-4-maverick-17b-128e-instruct",
    ]
    gorsel_etiketleri = (
        "vision",
        "scout",
        "maverick",
        "-vl",
        "vl-",
        "pixtral",
        "llava",
        "multimodal",
        "llama-4",
        "gemma-3",
    )
    haric_tut = ("whisper", "guard", "tts", "orpheus", "distil")
    try:
        modeller = client.models.list().data
        aktif_ids = [
            m.id
            for m in modeller
            if getattr(m, "active", True)
            and not any(h in m.id.lower() for h in haric_tut)
        ]
        oncelikli = [
            mid
            for mid in aktif_ids
            if any(etiket in mid.lower() for etiket in gorsel_etiketleri)
        ]
        sirali = []
        for mid in oncelikli + yedek_liste:
            if mid not in sirali and (not aktif_ids or mid in aktif_ids):
                sirali.append(mid)
        return sirali if sirali else (aktif_ids if aktif_ids else yedek_liste)
    except Exception:
        return yedek_liste


def groq_gorsel_yanit_al(client: Groq, base64_gorsel: str, istem: str) -> str:
    aday_modeller = aktif_gorsel_modellerini_bul(client)
    hatalar = []
    for model_adi in aday_modeller:
        try:
            yanit = client.chat.completions.create(
                model=model_adi,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": istem},
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/jpeg;base64,{base64_gorsel}"
                                },
                            },
                        ],
                    }
                ],
                temperature=0.3,
            )
            return yanit.choices[0].message.content
        except Exception as e:
            hatalar.append(f"{model_adi}: {e}")
            continue
    raise RuntimeError("Aktif modellerden yanıt alınamadı:\n" + "\n".join(hatalar))


def sesi_metne_cevir(client: Groq, ses_dosyasi) -> str:
    transkript = client.audio.transcriptions.create(
        file=("soru.wav", ses_dosyasi.getvalue()),
        model="whisper-large-v3-turbo",
        language="tr",
    )
    return transkript.text


api_key = get_groq_api_key()
if not api_key:
    st.error("GROQ_API_KEY bulunamadı. Lütfen Streamlit Secrets ayarlarına anahtarınızı ekleyin.")
    st.stop()

client = Groq(api_key=api_key)

st.title("Erişilebilir Grafik Analiz Arayüzü")
st.write("Görme engelli öğrenciler için sesli ve etkileşimli teknik grafik yorumlama asistanı")

if st.button("Uygulama Kullanım Rehberini Sesli Dinle"):
    rehber_metni = (
        "Erişilebilir Grafik Analiz Arayüzüne hoş geldiniz. "
        "Birinci adımda incelemek istediğiniz grafik veya geometri görselini yükleyin. "
        "İkinci adımda detaylı öğretim modu veya hızlı özet modunu seçip Grafiği Analiz Et düğmesine basın. "
        "Oluşturulan açıklamayı ekrandan dinleyebilir veya MP3 dosyası olarak cihazınıza indirebilirsiniz. "
        "Üçüncü adımda ise mikrofon düğmesine basarak grafik hakkında sesli soru sorabilirsiniz."
    )
    rehber_mp3 = metni_mp3_yap(rehber_metni)
    st.audio(rehber_mp3, format="audio/mp3")
    st.download_button(
        label="Kullanım Rehberini MP3 İndir",
        data=rehber_mp3,
        file_name="kullanim_rehberi.mp3",
        mime="audio/mp3",
    )

st.divider()

st.header("1. Adım: İncelenecek Grafiği Yükleyin")
yuklenen_gorsel = st.file_uploader(
    "Analiz edilecek grafik fotoğrafını seçin",
    type=["jpg", "jpeg", "png"],
)

if yuklenen_gorsel is not None:
    st.image(yuklenen_gorsel, caption="Yüklenen Görsel", use_container_width=True)
    base64_gorsel = gorseli_base64_yap(yuklenen_gorsel)

    st.header("2. Adım: Anlatım Modunu Seçin ve Yorumlayın")
    anlatim_modu = st.radio(
        "Anlatım derinliğini belirleyin:",
        [
            "Detaylı Öğretim Modu (4 Adımlı Analiz)",
            "Hızlı Özet Modu (Kısa ve Net)",
        ],
    )

    if st.button("Grafiği Analiz Et"):
        if anlatim_modu.startswith("Detaylı"):
            istem = (
                "Görme engelli öğrenciler için teknik grafikleri, tabloları ve şekilleri doğrudan betimle. "
                "KESİNLİKLE 'Merhaba', 'Hoş geldin', 'Ben senin öğretmeninim', 'Geometri öğretmeninim' gibi "
                "selamlama, rol yapma veya tanıtım cümleleri kurma. "
                "İlk cümlede doğrudan bu görselin ne grafiği veya ne şekli olduğunu net bir şekilde söyle "
                "(örneğin: 'Bu görsel, ... gösteren bir sütun grafiğidir.' veya 'Bu görsel, ... içeren bir geometrik şekildir.'). "
                "Ardından akıcı, anlaşılır ve sesli okumaya uygun Türkçe ile şu 4 adımda detaylandır:\n"
                "1. Görselin Tanımı: Grafiğin, tablonun veya şeklin tam olarak ne olduğunu ve konusunu belirt.\n"
                "2. Eksenler ve Bileşenler: X ve Y eksenlerinin adlarını, birimlerini, renkleri veya geometrik elemanları tek tek açıkla.\n"
                "3. Veri Eğilimi ve Kritik Noktalar: Artış, azalış, tepe, dip, açı, kenar ve kesişim noktalarını sayısal değerleriyle aktar.\n"
                "4. Temel Sonuç: Bu görselden çıkarılması gereken ana bilgiyi özetle."
            )
        else:
            istem = (
                "Görme engelli öğrenciler için bu görseli doğrudan özetle. "
                "KESİNLİKLE 'Merhaba', 'Ben senin öğretmeninim' gibi selamlama veya tanıtım cümlesi kurma. "
                "İlk cümlede doğrudan bu görselin ne grafiği veya ne şekli olduğunu söyle, "
                "ardından 2-3 cümlede en önemli sayısal değerleri ve ana sonucu sesli dinlemeye uygun sade bir Türkçe ile aktar."
            )

        with st.spinner("Grafik analiz ediliyor ve ses dosyası hazırlanıyor..."):
            try:
                analiz_metni = groq_gorsel_yanit_al(client, base64_gorsel, istem)
                st.session_state["analiz_sonucu"] = analiz_metni
                st.session_state["analiz_mp3"] = metni_mp3_yap(analiz_metni)
            except Exception as hata:
                st.error(f"Analiz sırasında bir sorun oluştu: {hata}")

    if "analiz_sonucu" in st.session_state:
        st.subheader("Grafik Açıklaması")
        st.write(st.session_state["analiz_sonucu"])
        st.audio(st.session_state["analiz_mp3"], format="audio/mp3")
        st.download_button(
            label="Analizi MP3 Olarak İndir",
            data=st.session_state["analiz_mp3"],
            file_name="grafik_analizi.mp3",
            mime="audio/mp3",
        )

        st.divider()
        st.header("3. Adım: Grafik Hakkında Soru Sorun")
        sesli_soru = st.audio_input("Mikrofona tıklayıp sorunuzu sesli sorun")
        yazili_soru = st.text_input("Veya sorunuzu buraya yazın:")

        if st.button("Soruyu Yanıtla"):
            soru_metni = yazili_soru.strip()
            with st.spinner("Sorunuz yanıtlanıyor..."):
                try:
                    if sesli_soru is not None and not soru_metni:
                        soru_metni = sesi_metne_cevir(client, sesli_soru)
                        st.info(f"Anlaşılan Sorunuz: {soru_metni}")

                    if not soru_metni:
                        st.warning("Lütfen mikrofonla bir soru kaydedin veya metin kutusuna yazın.")
                    else:
                        soru_istemi = (
                            "Yüklenen bu grafiğe veya şekle bakarak soruyu doğrudan yanıtla. "
                            "KESİNLİKLE 'Merhaba', 'Tabii ki', 'Ben senin öğretmeninim' gibi giriş veya selamlama cümleleri kullanma; "
                            "ilk cümleden itibaren doğrudan sorunun cevabını açık, net ve sesli okumaya uygun Türkçe ile ver.\n\n"
                            f"Soru: {soru_metni}"
                        )
                        cevap_metni = groq_gorsel_yanit_al(client, base64_gorsel, soru_istemi)
                        cevap_mp3 = metni_mp3_yap(cevap_metni)
                        st.write(cevap_metni)
                        st.audio(cevap_mp3, format="audio/mp3")
                        st.download_button(
                            label="Yanıtı MP3 Olarak İndir",
                            data=cevap_mp3,
                            file_name="soru_yaniti.mp3",
                            mime="audio/mp3",
                        )
                except Exception as hata:
                    st.error(f"Soru yanıtlanırken bir sorun oluştu: {hata}")
