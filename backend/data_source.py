"""
Data Source — AdSpy BR
Camada de abstração para fonte de dados.
Usa API do Facebook se configurada, senão usa dados demo.

Adicione no .env:
    FB_APP_ID=seu_app_id
    FB_APP_SECRET=seu_app_secret
"""

import os
import requests
from datetime import datetime, timezone

FB_APP_ID     = os.getenv("FB_APP_ID", "")
FB_APP_SECRET = os.getenv("FB_APP_SECRET", "")

_fb_token_cache = {"token": None, "expires": None}


# ─── FACEBOOK AD LIBRARY API ─────────────────────────────────────────────────

def obter_token_fb() -> str | None:
    """Gera App Token do Facebook (cache de 1h)."""
    if not FB_APP_ID or not FB_APP_SECRET:
        return None

    agora = datetime.now(timezone.utc).timestamp()
    if _fb_token_cache["token"] and _fb_token_cache["expires"] > agora:
        return _fb_token_cache["token"]

    resp = requests.get(
        "https://graph.facebook.com/oauth/access_token",
        params={
            "client_id": FB_APP_ID,
            "client_secret": FB_APP_SECRET,
            "grant_type": "client_credentials",
        },
        timeout=10,
    )
    if resp.status_code != 200:
        return None

    token = resp.json().get("access_token")
    _fb_token_cache["token"]   = token
    _fb_token_cache["expires"] = agora + 3600
    return token


def buscar_facebook(termo: str, pais: str, limite: int) -> list[dict]:
    """Busca anúncios via Facebook Ad Library API."""
    token = obter_token_fb()
    if not token:
        return []

    resp = requests.get(
        "https://graph.facebook.com/v19.0/ads_archive",
        params={
            "access_token": token,
            "search_terms": termo,
            "ad_reached_countries": pais,
            "ad_type": "ALL",
            "ad_active_status": "ACTIVE",
            "limit": limite,
            "fields": "id,page_name,ad_delivery_start_time,ad_delivery_stop_time,"
                      "ad_creative_bodies,ad_creative_link_titles,ad_snapshot_url,"
                      "impressions,spend,currency",
        },
        timeout=15,
    )

    if resp.status_code != 200:
        return []

    raw = resp.json().get("data", [])
    return [normalizar_fb(ad) for ad in raw]


def normalizar_fb(ad: dict) -> dict:
    """Converte formato da API do Facebook para o formato interno."""
    inicio = ad.get("ad_delivery_start_time", "")
    fim    = ad.get("ad_delivery_stop_time")
    dias   = 0

    fmt = "%Y-%m-%dT%H:%M:%S%z"
    try:
        dt_i = datetime.strptime(inicio, fmt)
        dt_f = datetime.strptime(fim, fmt) if fim else datetime.now(timezone.utc)
        dias = (dt_f - dt_i).days
    except Exception:
        pass

    corpos  = ad.get("ad_creative_bodies") or [""]
    titulos = ad.get("ad_creative_link_titles") or [""]
    corpo   = corpos[0] if corpos else ""
    titulo  = titulos[0] if titulos else ""
    imp     = ad.get("impressions", {})
    gasto   = ad.get("spend", {})

    return {
        "id":             ad.get("id", ""),
        "page_name":      ad.get("page_name", "Desconhecida"),
        "dias":           dias,
        "titulo":         titulo,
        "corpo":          corpo,
        "formato":        detectar_formato(corpo + " " + titulo),
        "impressoes_min": int(imp.get("lower_bound", 0) or 0),
        "impressoes_max": int(imp.get("upper_bound", 0) or 0),
        "gasto_min":      int(gasto.get("lower_bound", 0) or 0),
        "gasto_max":      int(gasto.get("upper_bound", 0) or 0),
        "url":            ad.get("ad_snapshot_url", ""),
    }


def detectar_formato(texto: str) -> str:
    t = texto.lower()
    if any(w in t for w in ["antes", "depois", "transforma", "perdi", "emagreci"]):
        return "antes_depois"
    if any(w in t for w in ["médico", "especialista", "cientific", "comprova"]):
        return "autoridade"
    if any(w in t for w in ["limitado", "hoje", "acaba", "oferta", "desconto"]):
        return "urgencia"
    if any(w in t for w in ["clientes", "avalia", "estrelas", "depoimento"]):
        return "prova_social"
    return "outros"


# ─── DADOS DEMO ───────────────────────────────────────────────────────────────

DEMO = [
    {"id":"d1","page_name":"FitLife Suplementos","dias":570,"titulo":"Ver rotina completa","corpo":"Antes: dormia mal, acordava cansada. Depois: energia o dia todo.","formato":"antes_depois","impressoes_min":2000000,"impressoes_max":5000000,"gasto_min":50000,"gasto_max":100000,"url":"#"},
    {"id":"d2","page_name":"FitLife Suplementos","dias":526,"titulo":"Ver transformação completa","corpo":"Antes: 98kg, sem energia. Depois: 72kg em 4 meses.","formato":"antes_depois","impressoes_min":1000000,"impressoes_max":2000000,"gasto_min":20000,"gasto_max":50000,"url":"#"},
    {"id":"d3","page_name":"NutriMax Brasil","dias":509,"titulo":"Ganhe 20% de desconto hoje","corpo":"Você sabia que 90% das dietas falham por falta do nutriente certo?","formato":"antes_depois","impressoes_min":500000,"impressoes_max":1000000,"gasto_min":10000,"gasto_max":20000,"url":"#"},
    {"id":"d4","page_name":"NutriMax Brasil","dias":479,"titulo":"Quero meu kit de transformação","corpo":"Kit completo com 3 meses de suplementação por R$197. Oferta limitada.","formato":"urgencia","impressoes_min":300000,"impressoes_max":700000,"gasto_min":8000,"gasto_max":15000,"url":"#"},
    {"id":"d5","page_name":"ProteínaBR","dias":31,"titulo":"Assistir vídeo do médico","corpo":"Médico revela: o erro que impede você de perder barriga em 7 dias.","formato":"autoridade","impressoes_min":200000,"impressoes_max":500000,"gasto_min":5000,"gasto_max":10000,"url":"#"},
    {"id":"d6","page_name":"VidaSaúde","dias":320,"titulo":"2.000 avaliações 5 estrelas","corpo":"Nossos clientes perderam em média 8kg no primeiro mês. Veja depoimentos reais.","formato":"prova_social","impressoes_min":800000,"impressoes_max":1500000,"gasto_min":15000,"gasto_max":30000,"url":"#"},
    {"id":"d7","page_name":"BioNutri","dias":280,"titulo":"Desconto de 40% só hoje","corpo":"Últimas 50 unidades com frete grátis. Oferta acaba à meia-noite.","formato":"urgencia","impressoes_min":400000,"impressoes_max":900000,"gasto_min":12000,"gasto_max":25000,"url":"#"},
    {"id":"d8","page_name":"FitLife Suplementos","dias":410,"titulo":"Aprovado por nutricionistas","corpo":"Especialistas em nutrição indicam nosso produto como o mais completo do mercado.","formato":"autoridade","impressoes_min":600000,"impressoes_max":1200000,"gasto_min":18000,"gasto_max":35000,"url":"#"},
]


# ─── FUNÇÃO PRINCIPAL ─────────────────────────────────────────────────────────

def buscar_anuncios(termo: str, pais: str = "BR", limite: int = 20) -> list[dict]:
    """
    Tenta buscar dados reais do Facebook.
    Se não configurado ou falhar, retorna dados demo.
    """
    if FB_APP_ID and FB_APP_SECRET:
        resultados = buscar_facebook(termo, pais, limite)
        if resultados:
            return resultados[:limite]
        print("[DataSource] API do Facebook falhou, usando demo.")

    # Filtra demo pelo termo (simula busca)
    demo = DEMO * (limite // len(DEMO) + 1)
    return demo[:limite]
