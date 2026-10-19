import os
import json
import subprocess
import tempfile
import time
from pathlib import Path

import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="IA Cortes TikTok", page_icon="✂️", layout="wide")

st.title("✂️ IA Cortes TikTok")
st.caption("Envie um vídeo, encontre momentos interessantes e prepare cortes para publicar.")

st.info(
    "Protótipo de teste: a IA sugere momentos promissores, mas não garante viralização. "
    "Confira todos os cortes antes de publicar."
)

api_key = os.getenv("GEMINI_API_KEY", "")
try:
    if not api_key:
        api_key = st.secrets["GEMINI_API_KEY"]
except Exception:
    api_key = api_key or ""

with st.sidebar:
    st.header("Configurações")
    max_clip = st.slider("Duração máxima de cada corte (segundos)", 30, 120, 120, 15)
    max_clips = st.slider("Quantidade máxima de cortes", 1, 10, 5)
    st.caption("Para o primeiro teste, use um vídeo curto de 5 a 10 minutos.")

uploaded = st.file_uploader("Envie um vídeo", type=["mp4", "mov", "mpeg", "mpg", "webm", "avi"])
if uploaded:
    st.video(uploaded)
    st.write(f"Arquivo: **{uploaded.name}** · {uploaded.size / (1024*1024):.1f} MB")

if st.button("Analisar vídeo e gerar cortes", type="primary", disabled=uploaded is None):
    if not api_key:
        st.error("Falta configurar GEMINI_API_KEY em Streamlit → Settings → Secrets.")
        st.stop()

    workdir = tempfile.mkdtemp(prefix="ia_cortes_")
    input_path = Path(workdir) / uploaded.name
    input_path.write_bytes(uploaded.getvalue())

    # Verify ffmpeg exists before starting the expensive AI call.
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, check=True)
    except Exception:
        st.error("O FFmpeg não está disponível. Confira se o arquivo packages.txt contém 'ffmpeg' e se o app foi reiniciado.")
        st.stop()

    client = genai.Client(api_key=api_key)

    try:
        with st.spinner("Enviando vídeo para o Gemini..."):
            video_file = client.files.upload(file=str(input_path))
            while getattr(video_file, "state", None) and str(video_file.state).upper().endswith("PROCESSING"):
                time.sleep(5)
                video_file = client.files.get(name=video_file.name)

        prompt = f"""
Analise este vídeo para encontrar até {max_clips} trechos que possam funcionar como vídeos curtos para TikTok.
Priorize momentos com começo e fim compreensíveis: histórias, humor, reações, discussões, frases fortes ou acontecimentos surpreendentes.
Não invente acontecimentos. Os tempos devem corresponder ao vídeo. Cada corte deve durar no máximo {max_clip} segundos.
Evite trechos sem contexto; quando possível inclua alguns segundos antes da fala ou acontecimento principal.
Responda SOMENTE com JSON válido neste formato:
{{
  "clips": [
    {{
      "start": 12.5,
      "end": 82.0,
      "title": "título curto",
      "reason": "por que esse trecho pode interessar",
      "caption": "legenda curta para a publicação",
      "hashtags": ["#tag1", "#tag2", "#tag3", "#tag4", "#tag5"],
      "onscreen_text": "frase curta para aparecer no meio do vídeo",
      "cover_text": "texto curto para a capa"
    }}
  ]
}}
Os tempos start/end devem ser números em segundos. Inclua exatamente cinco hashtags relevantes por corte.
"""
        with st.spinner("O Gemini está analisando o conteúdo..."):
            response = client.models.generate_content(
                model="gemini-3.8-flash",
                contents=[video_file, prompt],
                config=types.GenerateContentConfig(temperature=0.2),
            )

        raw = response.text or ""
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
        data = json.loads(raw)
        clips = data.get("clips", [])
        if not clips:
            st.warning("A IA não encontrou cortes neste vídeo. Tente outro vídeo.")
            st.stop()

        st.session_state["clips_data"] = clips
        st.session_state["clips_dir"] = workdir
        st.session_state["clips_source"] = str(input_path)
        st.success(f"A IA sugeriu {len(clips)} cortes. Confira os tempos e baixe os arquivos abaixo.")

    except json.JSONDecodeError:
        st.error("A resposta da IA não veio no formato esperado. Tente novamente com outro vídeo.")
        st.code(raw[:3000] if "raw" in locals() else "Sem resposta")
    except Exception as exc:
        st.error("Não foi possível analisar o vídeo. Confira a chave, os limites da API e tente novamente.")
        st.caption(f"Detalhe técnico: {exc}")

if "clips_data" in st.session_state:
    clips = st.session_state["clips_data"]
    workdir = st.session_state["clips_dir"]
    input_path = st.session_state["clips_source"]
    st.divider()
    st.header("Seus cortes sugeridos")

    for i, clip in enumerate(clips, start=1):
        try:
            start = max(0.0, float(clip["start"]))
            end = float(clip["end"])
        except (KeyError, TypeError, ValueError):
            st.warning(f"Corte {i}: tempos inválidos; ignorado.")
            continue

        if end <= start:
            st.warning(f"Corte {i}: o tempo final precisa ser maior que o inicial.")
            continue
        if end - start > 120:
            end = start + 120

        safe_title = "".join(c if c.isalnum() or c in "-_" else "_" for c in str(clip.get("title", f"corte_{i}")))[:45]
        output_path = Path(workdir) / f"corte_{i}_{safe_title}.mp4"
        cover_path = Path(workdir) / f"capa_{i}_{safe_title}.jpg"

        with st.expander(f"Corte {i}: {clip.get('title', 'Momento interessante')} ({int(end-start)} s)", expanded=True):
            st.write(f"**Por que foi escolhido:** {clip.get('reason', 'Momento sugerido pela IA.')}")
            st.write(f"**Legenda:** {clip.get('caption', '')}")
            hashtags = clip.get("hashtags", [])
            if isinstance(hashtags, list):
                st.write("**Hashtags:** " + " ".join(str(x) for x in hashtags[:5]))
            st.write(f"**Texto no meio do vídeo:** {clip.get('onscreen_text', '')}")
            st.write(f"**Texto sugerido para capa:** {clip.get('cover_text', '')}")
            st.caption(f"Trecho original: {start:.1f}s – {end:.1f}s. Confira se o contexto está correto.")

            if not output_path.exists():
                cmd = [
                    "ffmpeg", "-y", "-ss", str(start), "-i", input_path,
                    "-t", str(end-start), "-c:v", "libx264", "-preset", "veryfast",
                    "-c:a", "aac", "-movflags", "+faststart", str(output_path)
                ]
                result = subprocess.run(cmd, capture_output=True, text=True)
                if result.returncode != 0:
                    st.error("Não foi possível criar este corte.")
                    st.caption(result.stderr[-800:])
                    continue

            st.video(str(output_path))
            if not cover_path.exists():
                cover_cmd = [
                    "ffmpeg", "-y", "-ss", str(max(0, (end-start)/2)), "-i", str(output_path),
                    "-frames:v", "1", "-q:v", "2", str(cover_path)
                ]
                subprocess.run(cover_cmd, capture_output=True)
            if cover_path.exists():
                st.image(str(cover_path), caption="Imagem de capa (quadro do vídeo; texto sugerido acima)", width=260)
                st.download_button(
                    f"Baixar capa {i}", data=cover_path.read_bytes(),
                    file_name=cover_path.name, mime="image/jpeg", key=f"cover_{i}"
                )
            st.download_button(
                f"Baixar corte {i}", data=output_path.read_bytes(),
                file_name=output_path.name, mime="video/mp4", key=f"clip_{i}"
            )
            package_text = (
                f"TÍTULO: {clip.get('title','')}\n"
                f"LEGENDA: {clip.get('caption','')}\n"
                f"HASHTAGS: {' '.join(str(x) for x in hashtags[:5]) if isinstance(hashtags, list) else hashtags}\n"
                f"TEXTO NO VÍDEO: {clip.get('onscreen_text','')}\n"
                f"TEXTO DA CAPA: {clip.get('cover_text','')}\n"
            )
            st.download_button(
                f"Baixar informações {i} (.txt)", data=package_text,
                file_name=f"informacoes_corte_{i}.txt", mime="text/plain", key=f"info_{i}"
            )
