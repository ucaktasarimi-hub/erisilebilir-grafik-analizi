import os
import io
import re
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
    img.thumbnail((1024, 1024))
    tampon = io.BytesIO()
    img.save(tampon, format="JPEG", quality=85)
    return base64.b64encode(tampon.getvalue()).decode("utf-8")


def ses_icin_metni_duzenle(metin: str) -> str:
    # Ekrandaki yazıyı bozmadan yalnızca Türkçe seslendirme telaffuzunu netleştirir
    duzenli = metin.replace("*", "").replace("#", "").replace("`", "")
    duzenli = re.sub(r"\b[Xx]\s+ve\s+[Yy]\b", "iks ve ye", duzenli)
    duzenli = re.sub(r"\b[Yy]\s+ve\s+[Xx]\b", "ye ve iks", duzenli)
    duzenli = re.sub(r"\b[Yy]\s*[-–]?\s*(eksen\w*)", r"ye \1", duzenli)
    duzenli = re.sub(r"\b[Xx]\s*[-–]?\s*(eksen\w*)", r"iks \1", duzenli)
    duzenli = re.sub(r"\b[Yy]\s*=", "ye eşittir ", duzenli)
    duzenli = re.sub(r"\b[Xx]\s*=", "iks eşittir ", duzenli)
    duzenli = duzenli.replace(":", ". ")
    duzenli = re.sub(r"\n+", ". ", duzenli)
    duzenli = re.sub(r"\.\s*\.", ".", duzenli)
    return duzenli.strip()


def metni_mp3_yap(metin: str) -> bytes:
    ses_metni = ses_icin_metni_duzenle(metin)
    tts = gTTS(text=ses_metni, lang="tr", slow=False)
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
        "qwen",
        "kimi",
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
        kayitli_model = st.session_state.get("calisan_gorsel_modeli")
        if kayitli_model and (not aktif_ids or kayitli_model in aktif_ids):
            sirali.append(kayitli_model)

        for mid in oncelikli + yedek_liste:
            if mid not in sirali and (not aktif_ids or mid in aktif_ids):
                sirali.append(mid)
        return sirali if sirali else (aktif_ids if aktif_ids else yedek_liste)
    except Exception:
        return yedek_liste


def groq_gorsel_yanit_al(client: Groq, base64_gorsel: str, istem: str, max_tokens: int = 500) -> str:
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
                temperature=0.2,
                max_tokens=max_tokens,
            )
            st.session_state["calisan_gorsel_modeli"] = model_adi
            return yanit.choices[0].message.content
        except Exception as e:
            hatalar.append(f"{model_adi}: {e}")
            continue
    raise RuntimeError("Aktif modellerden yanıt alınamadı:\n" + "\n".join(hatalar))


def groq_metin_yanit_al(client: Groq, istem: str, max_tokens: int = 300) -> str:
    tercih_edilenler = [
        "llama-3.3-70b-versatile",
        "llama-3.1-8b-instant",
        "openai/gpt-oss-20b",
        "openai/gpt-oss-120b",
        "allam-2-7b",
    ]
    haric_tut = ("whisper", "guard", "tts", "orpheus")
    try:
        modeller = client.models.list().data
        aktif_ids = [
            m.id
            for m in modeller
            if getattr(m, "active", True)
            and not any(h in m.id.lower() for h in haric_tut)
        ]
    except Exception:
        aktif_ids = []

    aday_modeller = []
    for mid in tercih_edilenler + aktif_ids:
        if mid not in aday_modeller and (not aktif_ids or mid in aktif_ids):
            aday_modeller.append(mid)

    son_hata = None
    for model
