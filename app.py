import os, io, re, base64
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
        temiz = str(key).strip().strip('"').strip("'")
        if temiz.startswith("gsk_"):
            return temiz
    except ImportError:
        pass
    return ""

def gorseli_base64_yap(dosya) -> str:
    img = Image.open(dosya).convert("RGB")
    img.thumbnail((1024, 1024))
    tampon = io.BytesIO()
    img.save(tampon, format="JPEG", quality=85)
    return base64.b64encode(tampon.getvalue()).decode("utf-8")

def metni_mp3_yap(metin: str) -> bytes:
    d = metin.replace("*", "").replace("#", "").replace("`", "")
    d = re.sub(r"\b[Xx]\s+ve\s+[Yy]\b", "iks ve ye", d)
    d = re.sub(r"\b[Yy]\s+ve\s+[Xx]\b", "ye ve iks", d)
    d = re.sub(r"\b[Yy]\s*[-–]?\s*(eksen\w*)", r"ye \1", d)
    d = re.sub(r"\b[Xx]\s*[-–]?\s*(eksen\w*)", r"iks \1", d)
    d = re.sub(r"\b[Yy]\s*=", "ye eşittir ", d)
    d = re.sub(r"\b[Xx]\s*=", "iks eşittir ", d)
    d = re.sub(r"\.\s*\.", ".", re.sub(r"\n+", ". ", d.replace(":", ". "))).strip()
    tampon = io.BytesIO()
    gTTS(text=d, lang="tr", slow=False).write_to_fp(tampon)
    tampon.seek(0)
    return tampon.read()

def aktif_modelleri_getir(client: Groq, haric: tuple) -> list[str]:
    try:
        return [
            m.id for m in client.models.list().data
            if getattr(m, "active", True) and not any(h in m.id.lower() for h in haric)
        ]
    except Exception:
        return []

def groq_gorsel_yanit_al(client: Groq, b64: str, istem: str, max_tokens: int = 500) -> str:
    yedek = ["meta-llama/llama-4-scout-17b-16e-instruct", "meta-llama/llama-4-maverick-17b-128e-instruct"]
    etiketler = ("vision", "scout", "maverick", "-vl", "vl-", "pixtral", "llava", "multimodal", "llama-4", "gemma-3", "qwen", "kimi")
    aktif = aktif_modelleri_getir(client, ("whisper", "guard", "tts", "orpheus", "distil"))
    oncelikli = [m for m in aktif if any(e in m.lower() for e in etiketler)]
    adaylar = []
    kayitli = st.session_state.get("calisan_gorsel_modeli")
    for m in ([kayitli] if kayitli else []) + oncelikli + yedek:
        if m and m not in adaylar and (not aktif or m in aktif):
            adaylar.append(m)
    hatalar = []
    for model_adi in (adaylar or aktif or yedek):
        try:
            yanit = client.chat.completions.create(
                model=model_adi,
                messages=[{"role": "user", "content": [
                    {"type": "text", "text": istem},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ]}],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            st.session_state["calisan_gorsel_modeli"] = model_adi
            return yanit.choices[0].message.content
        except Exception as e:
            hatalar.append(f"{model_adi}: {e}")
    raise RuntimeError("Aktif modellerden yanıt alınamadı:\n" + "\n".join(hatalar))

def groq_metin_yanit_al(client: Groq, istem: str, max_tokens: int = 280) -> str:
    tercih = ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "openai/gpt-oss-20b", "openai/gpt-oss-120b", "allam-2-7b"]
    aktif = aktif_modelleri_getir(client, ("whisper", "guard", "tts", "orpheus"))
    adaylar = []
    for m in tercih + aktif:
        if m not in adaylar and (not aktif or m in aktif):
            adaylar.append(m)
    son_hata = None
    for model_adi in adaylar:
        try:
            yanit = client.chat.completions.create(
                model=model_adi,
                messages=[{"role": "user", "content": istem}],
                temperature=0.2,
                max_tokens=max_tokens,
            )
            return yanit.choices[0].message.content
        except Exception as e:
            son_hata = e
    raise RuntimeError(f"Metin modelinden yanıt alınamadı: {son_hata}")

def soruya_cevap_uret(client: Groq, b64: str, soru: str, gecmis: list[dict]) -> str:
    baglam = ""
    if gecmis:
        satirlar = [f"Önceki Soru: {k['soru']}\nÖnceki Yanıt: {k['cevap']}" for k in gecmis[-3:]]
        baglam = "Önceki konuşma bağlamı (devam sorusuysa dikkate al):\n" + "\n".join(satirlar) + "\n\n"
    temel = (
        "Selamlama veya rol yapma cümleleri kullanma; "
        "ilk cümleden itibaren doğrudan sorunun cevabını kısa, açık ve sesli okumaya uygun Türkçe ile ver.\n\n"
    )
    try:
        return groq_gorsel_yanit_al(client, b64, "Yüklenen ders grafiğine bakarak soruyu yanıtla. " + temel + baglam + f"Yeni Soru: {soru}", 280)
    except Exception:
        analiz = st.session_state.get("analiz_sonucu", "")
        if not analiz:
            raise
        return groq_metin_yanit_al(client, "Aşağıdaki grafik analizine göre soruyu yanıtla. " + temel + f"Analiz:\n{analiz}\n\n" + baglam + f"Yeni Soru: {soru}", 280)

def sesi_metne_cevir(client: Groq, ses_dosyasi) -> str:
    return client.audio.transcriptions.create(
        file=("soru.wav", ses_dosyasi.getvalue()), model="whisper-large-v3-turbo", language="tr"
    ).text

api_key = get_groq_api_key()
if not api_key:
    st.error("GROQ_API_KEY bulunamadı. Lütfen Streamlit Secrets ayarlarına anahtarınızı ekleyin.")
    st.stop()

client = Groq(api_key=api_key)
st.title("Erişilebilir Grafik Analiz Arayüzü")
st.write("Görme engelli öğrenciler için sesli ve etkileşimli teknik grafik yorumlama asistanı")

if st.button("Uygulama Kullanım Rehberini Sesli Dinle"):
    rehber = (
        "Erişilebilir Grafik Analiz Arayüzüne hoş geldiniz. "
        "Birinci adımda cihazınızdan bir ders grafiği seçebilir veya kamerayla fotoğraf çekebilirsiniz. "
        "İkinci adımda anlatım modunu seçip Grafiği Analiz Et düğmesine basın; açıklama otomatik okunmaya başlar. "
        "Üçüncü adımda mikrofona dokunup sorunuzu söyleyip durdurduğunuzda yanıt otomatik seslendirilir."
    )
    rehber_mp3 = metni_mp3_yap(rehber)
    st.audio(rehber_mp3, format="audio/mp3", autoplay=True)
    st.download_button("Kullanım Rehberini MP3 İndir", rehber_mp3, "kullanim_rehberi.mp3", "audio/mp3")

st.divider()
st.header("1. Adım: İncelenecek Grafiği Ekleyin")
yontem = st.radio("Görsel ekleme yöntemini seçin:", ["Cihazdan Dosya Yükle", "Kamera ile Fotoğraf Çek"], horizontal=True)
if yontem == "Cihazdan Dosya Yükle":
    gorsel = st.file_uploader("Analiz edilecek ders grafiği veya şekil fotoğrafını seçin", type=["jpg", "jpeg", "png"])
else:
    gorsel = st.camera_input("Ders kitabındaki veya kağıttaki grafiğin fotoğrafını çekin")

if gorsel is not None:
    kimlik = f"{getattr(gorsel, 'name', 'gorsel')}_{getattr(gorsel, 'size', 0)}"
    if st.session_state.get("son_dosya") != kimlik:
        st.session_state["son_dosya"] = kimlik
        for k in ("analiz_sonucu", "analiz_mp3", "kapsam_disi", "uyari_mp3", "son_islenen_ses", "soru_gecmisi", "otomatik_cal"):
            st.session_state.pop(k, None)

    st.image(gorsel, caption="Seçilen Görsel", use_container_width=True)
    b64_gorsel = gorseli_base64_yap(gorsel)

    st.header("2. Adım: Anlatım Modunu Seçin ve Yorumlayın")
    mod = st.radio("Anlatım derinliğini belirleyin:", ["Detaylı Öğretim Modu (4 Adımlı Analiz)", "Hızlı Özet Modu (Kısa ve Net)"])
    kapsam = (
        "ÖNCE GÖRSELİN KAPSAMINI KONTROL ET:\n"
        "- Bu görsel bir ders materyali mi? (Matematik/fen grafiği, veri tablosu, geometrik şekil, teknik şema, devre, harita veya şekilli sınav sorusu)\n"
        "- Eğer ders materyali DEĞİLSE (insan, özçekim, manzara, eşya, hayvan, yiyecek vb.) başka HİÇBİR ŞEY YAZMA ve yalnızca şu kelimeyi döndür: KAPSAM_DISI\n\n"
        "EĞER DERS MATERYALİ İSE:\n"
        "- 'Merhaba', 'Hoş geldin', 'Ben senin öğretmeninim' gibi selamlama veya rol yapma cümleleri KULLANMA.\n"
        "- İlk cümlede doğrudan bu görselin ne grafiği, tablosu veya şekli olduğunu söyle.\n"
    )

    if st.button("Grafiği Analiz Et"):
        if mod.startswith("Detaylı"):
            istem = kapsam + (
                "Ardından akıcı ve sesli okumaya uygun Türkçe ile 4 adımda kısa ve öz detaylandır:\n"
                "1. Görselin Tanımı: Grafiğin, tablonun veya şeklin ne olduğunu ve konusunu belirt.\n"
                "2. Eksenler ve Bileşenler: Yatay X ekseni ve dikey Y ekseninin adlarını, birimlerini veya geometrik elemanları açıkla.\n"
                "3. Veri Eğilimi ve Kritik Noktalar: Artış, azalış, tepe, dip, açı, kenar ve kesişimleri sayısal değerleriyle aktar.\n"
                "4. Temel Sonuç: Bu görselden çıkarılması gereken ana bilgiyi özetle."
            )
        else:
            istem = kapsam + "Ardından 2-3 cümlede en önemli sayısal değerleri ve ana sonucu sade bir Türkçe ile özetle."

        with st.spinner("Görsel kontrol ediliyor ve analiz hazırlanıyor..."):
            try:
                yanit = groq_gorsel_yanit_al(client, b64_gorsel, istem, 520)
                if "KAPSAM_DISI" in yanit.strip().upper():
                    st.session_state["kapsam_disi"] = True
                    st.session_state.pop("analiz_sonucu", None)
                    uyari = "Bu görsel bir ders grafiği, veri tablosu, harita veya geometrik şekil olarak algılanmadı. Lütfen bir eğitim materyali yükleyin."
                    st.session_state["uyari_mp3"] = metni_mp3_yap(uyari)
                    st.session_state["otomatik_cal"] = "uyari"
                else:
                    st.session_state["kapsam_disi"] = False
                    st.session_state["analiz_sonucu"] = yanit
                    st.session_state["analiz_mp3"] = metni_mp3_yap(yanit)
                    st.session_state["otomatik_cal"] = "analiz"
            except Exception as hata:
                st.error(f"Analiz sırasında bir sorun oluştu: {hata}")

    if st.session_state.get("kapsam_disi"):
        st.warning("Bu görsel bir ders grafiği, veri tablosu, harita veya geometrik şekil olarak algılanmadı. Lütfen bir eğitim materyali yükleyin.")
        oto = st.session_state.get("otomatik_cal") == "uyari"
        if oto:
            st.session_state.pop("otomatik_cal", None)
        st.audio(st.session_state["uyari_mp3"], format="audio/mp3", autoplay=oto)

    elif "analiz_sonucu" in st.session_state:
        st.subheader("Grafik Açıklaması")
        st.write(st.session_state["analiz_sonucu"])
        oto = st.session_state.get("otomatik_cal") == "analiz"
        if oto:
            st.session_state.pop("otomatik_cal", None)
        st.audio(st.session_state["analiz_mp3"], format="audio/mp3", autoplay=oto)
        st.download_button("Analizi MP3 Olarak İndir", st.session_state["analiz_mp3"], "grafik_analizi.mp3", "audio/mp3")

        st.divider()
        st.header("3. Adım: Grafik Hakkında Soru Sorun")
        sesli_soru = st.audio_input("Mikrofona dokunun, sorunuzu söyleyin ve kaydı durdurun (otomatik yanıtlanır ve okunur)")

        if sesli_soru is not None:
            ses_id = hash(sesli_soru.getvalue())
            if st.session_state.get("son_islenen_ses") != ses_id:
                with st.spinner("Sesli sorunuz algılanıyor ve yanıt hazırlanıyor..."):
                    try:
                        soru = sesi_metne_cevir(client, sesli_soru).strip()
                        if soru:
                            gecmis = st.session_state.setdefault("soru_gecmisi", [])
                            cevap = soruya_cevap_uret(client, b64_gorsel, soru, gecmis)
                            gecmis.append({"soru": soru, "cevap": cevap, "mp3": metni_mp3_yap(cevap)})
                            st.session_state["son_islenen_ses"] = ses_id
                            st.session_state["otomatik_cal"] = "cevap"
                    except Exception as hata:
                        st.error(f"Sesli soru yanıtlanırken bir sorun oluştu: {hata}")

        with st.expander("Mikrofon yerine yazılı soru sormak için tıklayın"):
            yazili = st.text_input("Sorunuzu buraya yazın:")
            if st.button("Yazılı Soruyu Yanıtla"):
                if not yazili.strip():
                    st.warning("Lütfen bir soru yazın.")
                else:
                    with st.spinner("Sorunuz yanıtlanıyor..."):
                        try:
                            gecmis = st.session_state.setdefault("soru_gecmisi", [])
                            cevap = soruya_cevap_uret(client, b64_gorsel, yazili.strip(), gecmis)
                            gecmis.append({"soru": yazili.strip(), "cevap": cevap, "mp3": metni_mp3_yap(cevap)})
                            st.session_state["otomatik_cal"] = "cevap"
                        except Exception as hata:
                            st.error(f"Soru yanıtlanırken bir sorun oluştu: {hata}")

        gecmis = st.session_state.get("soru_gecmisi", [])
        if gecmis:
            guncel = gecmis[-1]
            st.info(f"Son Soru: {guncel['soru']}")
            st.write(guncel["cevap"])
            oto = st.session_state.get("otomatik_cal") == "cevap"
            if oto:
                st.session_state.pop("otomatik_cal", None)
            st.audio(guncel["mp3"], format="audio/mp3", autoplay=oto)
            st.download_button("Son Yanıtı MP3 İndir", guncel["mp3"], "son_yanit.mp3", "audio/mp3", key="son_yanit_mp3")

            if len(gecmis) > 1:
                oncekiler = gecmis[:-1]
                with st.expander(f"Önceki Sorular ve Yanıtlar ({len(oncekiler)})"):
                    for idx, kayit in enumerate(oncekiler, start=1):
                        st.markdown(f"**{idx}. Soru:** {kayit['soru']}")
                        st.write(kayit["cevap"])
                        st.audio(kayit["mp3"], format="audio/mp3", autoplay=False)
                        st.download_button(
                            f"{idx}. Yanıtı MP3 İndir",
                            kayit["mp3"],
                            f"soru_yaniti_{idx}.mp3",
                            "audio/mp3",
                            key=f"gecmis_mp3_{idx}",
                        )
                        if idx < len(oncekiler):
                            st.divider()
# SON
