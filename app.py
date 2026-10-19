import os, json, subprocess, tempfile, time
from pathlib import Path
import streamlit as st
from google import genai
from google.genai import types

st.set_page_config(page_title="IA Cortes TikTok", page_icon="✂️", layout="wide")
st.title("✂️ IA Cortes TikTok")
st.caption("Cortes automáticos para batalhas de presença do TikTok")
st.info("Regra fixa: corte 1 = 1min50s; corte 2 = 2min; corte 3 = todo o restante. A IA cria legendas e hashtags com foco em batalha de presença.")

api_key = os.getenv("GEMINI_API_KEY", "")
try: api_key = st.secrets.get("GEMINI_API_KEY", api_key)
except Exception: pass

with st.sidebar:
    st.header("Regras")
    st.write("Corte 1: 00:00–01:50")
    st.write("Corte 2: 01:50–03:50")
    st.write("Corte 3: 03:50 até o fim")
    st.caption("Vídeos com menos de 3min50s geram apenas os cortes que couberem.")

uploaded = st.file_uploader("Envie o vídeo da batalha de presença", type=["mp4","mov","mpeg","mpg","webm","avi"])
if uploaded:
    st.video(uploaded)
    st.caption(f"{uploaded.name} · {uploaded.size/(1024*1024):.1f} MB")

def duration_of(path):
    r=subprocess.run(["ffprobe","-v","error","-show_entries","format=duration","-of","default=noprint_wrappers=1:nokey=1",str(path)],capture_output=True,text=True,check=True)
    return float(r.stdout.strip())

def parse_json(s):
    s=(s or "").strip()
    if s.startswith("```"):
        s=s.split("\n",1)[1]
        if s.endswith("```"): s=s[:-3]
    return json.loads(s)

if st.button("Gerar cortes + legendas",type="primary",disabled=uploaded is None):
    if not api_key:
        st.error("Configure GEMINI_API_KEY em Streamlit → Settings → Secrets.")
        st.stop()
    workdir=tempfile.mkdtemp(prefix="ia_cortes_")
    src=Path(workdir)/uploaded.name
    src.write_bytes(uploaded.getvalue())
    try:
        subprocess.run(["ffmpeg","-version"],capture_output=True,check=True)
        subprocess.run(["ffprobe","-version"],capture_output=True,check=True)
        dur=duration_of(src)
    except Exception as e:
        st.error(f"FFmpeg/FFprobe indisponível ou vídeo inválido: {e}")
        st.stop()
    segments=[
        {"number":1,"start":0.0,"end":min(110.0,dur)},
        {"number":2,"start":110.0,"end":min(230.0,dur)},
        {"number":3,"start":230.0,"end":dur}
    ]
    segments=[s for s in segments if s["end"]>s["start"]]
    client=genai.Client(api_key=api_key)
    try:
        with st.spinner("Enviando vídeo para a IA..."):
            vf=client.files.upload(file=str(src))
            while getattr(vf,"state",None) and "PROCESSING" in str(vf.state).upper():
                time.sleep(5)
                vf=client.files.get(name=vf.name)
        ranges=[{"number":s["number"],"start_seconds":s["start"],"end_seconds":s["end"]} for s in segments]
        prompt=f"""
Tema obrigatório: batalha de presença do TikTok, duelos ao vivo, torcida, criadores e apoio da audiência.
Analise o vídeo e gere metadados para estes trechos exatos: {json.dumps(ranges)}.
Não invente falas ou acontecimentos. Em caso de dúvida, use texto temático geral.
Para cada corte gere title, caption, hashtags (exatamente cinco hashtags relevantes em português; incluir #BatalhaDePresença e #TikTokLive quando apropriado), onscreen_text (gancho curto para aparecer no meio do vídeo), cover_text (texto curto para capa).
Retorne apenas JSON válido: {{"clips":[{{"number":1,"title":"...","caption":"...","hashtags":["#...","#...","#...","#...","#..."],"onscreen_text":"...","cover_text":"..."}}]}}
Inclua um objeto para cada número solicitado.
"""
        with st.spinner("Criando legendas e hashtags..."):
            res=client.models.generate_content(model="gemini-3.8-flash",contents=[vf,prompt],config=types.GenerateContentConfig(temperature=0.3))
        metadata=parse_json(res.text)
        bynum={int(c.get("number",i+1)):c for i,c in enumerate(metadata.get("clips",[]))}
    except Exception as e:
        st.error("Não consegui analisar o vídeo. Confira a disponibilidade do modelo Gemini e os limites da API.")
        st.caption(f"Detalhe técnico: {e}")
        st.stop()
    st.success(f"Vídeo com {dur/60:.2f} minutos. Criando {len(segments)} cortes.")
    st.session_state["segments"]=segments
    st.session_state["metadata"]=bynum
    st.session_state["workdir"]=workdir
    st.session_state["source"]=str(src)

if "segments" in st.session_state:
    st.header("Cortes prontos para revisar")
    for seg in st.session_state["segments"]:
        n=seg["number"]; start=seg["start"]; end=seg["end"]
        meta=st.session_state["metadata"].get(n,{})
        work=st.session_state["workdir"]
        out=Path(work)/f"corte_{n}.mp4"; cover=Path(work)/f"capa_{n}.jpg"
        if not out.exists():
            r=subprocess.run(["ffmpeg","-y","-ss",str(start),"-i",st.session_state["source"],"-t",str(end-start),"-c:v","libx264","-preset","veryfast","-c:a","aac","-movflags","+faststart",str(out)],capture_output=True,text=True)
            if r.returncode:
                st.error(f"Falha no corte {n}: {r.stderr[-500:]}")
                continue
        title=meta.get("title",f"Batalha de presença — corte {n}")
        caption=meta.get("caption","Quem levou essa batalha de presença? Comenta aí!")
        tags=meta.get("hashtags",["#BatalhaDePresença","#TikTokLive","#TikTokBrasil","#AoVivo","#FYP"])
        if not isinstance(tags,list): tags=["#BatalhaDePresença","#TikTokLive","#TikTokBrasil","#AoVivo","#FYP"]
        tags=tags[:5]
        onscreen=meta.get("onscreen_text","Quem levou essa batalha?")
        cover_text=meta.get("cover_text","BATALHA DE PRESENÇA")
        with st.expander(f"Corte {n} · {start:.0f}s–{end:.0f}s · {(end-start)/60:.2f} min",expanded=True):
            st.subheader(title); st.video(str(out))
            st.write("**Legenda:**",caption)
            st.write("**Hashtags:**"," ".join(tags))
            st.write("**Frase no meio do vídeo:**",onscreen)
            st.write("**Texto sugerido para capa:**",cover_text)
            if not cover.exists():
                subprocess.run(["ffmpeg","-y","-ss",str((end-start)/2),"-i",str(out),"-frames:v","1","-q:v","2",str(cover)],capture_output=True)
            if cover.exists():
                st.image(str(cover),caption="Quadro extraído do vídeo",width=260)
                st.download_button(f"Baixar capa {n}",cover.read_bytes(),file_name=f"capa_corte_{n}.jpg",mime="image/jpeg",key=f"cap{n}")
            st.download_button(f"Baixar vídeo {n}",out.read_bytes(),file_name=f"batalha_presenca_corte_{n}.mp4",mime="video/mp4",key=f"vid{n}")
            bundle=f"TÍTULO: {title}\nLEGENDA: {caption}\nHASHTAGS: {' '.join(tags)}\nTEXTO NO VÍDEO: {onscreen}\nTEXTO DA CAPA: {cover_text}\n"
            st.download_button(f"Baixar informações {n}",bundle,file_name=f"informacoes_corte_{n}.txt",mime="text/plain",key=f"info{n}")
