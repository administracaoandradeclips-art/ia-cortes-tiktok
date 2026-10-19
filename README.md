# IA Cortes TikTok

Protótipo Streamlit para sugerir cortes a partir de vídeo usando a API Gemini.

## Arquivos
- `app.py`: aplicação
- `requirements.txt`: dependências Python
- `packages.txt`: instala FFmpeg no Streamlit Community Cloud

## Configuração
No Streamlit, abra App settings → Secrets e adicione:

```toml
GEMINI_API_KEY = "sua_chave_aqui"
```

Nunca coloque a chave diretamente no código ou em um repositório público.

Este é um protótipo: revise os cortes, tempos, legendas e hashtags antes de publicar. O processamento de vídeos longos pode atingir limites de tamanho, tempo ou cota da API.
