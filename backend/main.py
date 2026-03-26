"""
AdSpy BR — Backend
FastAPI + SQLite + JWT Auth + Planos

Instalação:
    pip3 install fastapi uvicorn sqlalchemy python-jose[cryptography] passlib[bcrypt] python-multipart

Rodar:
    uvicorn main:app --reload --port 8000
"""

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from typing import Optional
import json

# ─── CONFIG ──────────────────────────────────────────────────────────────────

SECRET_KEY   = "troque-isso-por-uma-chave-segura-em-producao"
ALGORITHM    = "HS256"
TOKEN_EXPIRE = 30  # minutos

DATABASE_URL = "sqlite:///./adspy.db"

PLANOS = {
    "free": {
        "nome": "Free",
        "preco": 0,
        "limite_buscas_dia": 3,
        "limite_resultados": 5,
        "padroes": False,
        "export": False,
    },
    "pro": {
        "nome": "Pro",
        "preco": 97,
        "limite_buscas_dia": 999,
        "limite_resultados": 50,
        "padroes": True,
        "export": True,
    },
    "elite": {
        "nome": "Elite",
        "preco": 197,
        "limite_buscas_dia": 999,
        "limite_resultados": 200,
        "padroes": True,
        "export": True,
    },
}

# ─── BANCO DE DADOS ───────────────────────────────────────────────────────────

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)
Base = declarative_base()


class Usuario(Base):
    __tablename__ = "usuarios"
    id                  = Column(Integer, primary_key=True, index=True)
    email               = Column(String, unique=True, index=True)
    nome                = Column(String)
    senha_hash          = Column(String)
    plano               = Column(String, default="free")
    ativo               = Column(Boolean, default=True)
    criado_em           = Column(DateTime, default=datetime.utcnow)
    buscas_hoje         = Column(Integer, default=0)
    ultima_busca        = Column(String, default="")  # data em string
    stripe_customer_id  = Column(String, default="")
    stripe_sub_id       = Column(String, default="")


Base.metadata.create_all(bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ─── AUTH ─────────────────────────────────────────────────────────────────────

pwd_ctx = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2  = OAuth2PasswordBearer(tokenUrl="/auth/login")


def hash_senha(senha: str) -> str:
    return pwd_ctx.hash(senha)


def verificar_senha(senha: str, hash: str) -> bool:
    return pwd_ctx.verify(senha, hash)


def criar_token(data: dict) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + timedelta(minutes=TOKEN_EXPIRE)
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def usuario_atual(token: str = Depends(oauth2), db: Session = Depends(get_db)) -> Usuario:
    erro = HTTPException(status_code=401, detail="Token inválido")
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email   = payload.get("sub")
        if not email:
            raise erro
    except JWTError:
        raise erro

    user = db.query(Usuario).filter(Usuario.email == email).first()
    if not user or not user.ativo:
        raise erro
    return user


# ─── SCHEMAS ─────────────────────────────────────────────────────────────────

class CadastroSchema(BaseModel):
    email: str
    nome:  str
    senha: str


class TokenSchema(BaseModel):
    access_token: str
    token_type:   str
    usuario:      dict


class BuscaSchema(BaseModel):
    termo:  str
    pais:   str = "BR"
    limite: Optional[int] = None


# ─── DADOS DEMO ───────────────────────────────────────────────────────────────

ANUNCIOS_DEMO = [
    {
        "id": "001", "page_name": "FitLife Suplementos", "dias": 570,
        "titulo": "Ver rotina completa",
        "corpo": "Antes: dormia mal, acordava cansada. Depois: energia o dia todo. Veja o que mudei na minha rotina.",
        "formato": "antes_depois", "impressoes_min": 2000000, "impressoes_max": 5000000,
        "gasto_min": 50000, "gasto_max": 100000,
    },
    {
        "id": "002", "page_name": "FitLife Suplementos", "dias": 526,
        "titulo": "Ver transformação completa",
        "corpo": "Antes: 98kg, sem energia, frustrada. Depois: 72kg em 4 meses. Veja o método que ela usou.",
        "formato": "antes_depois", "impressoes_min": 1000000, "impressoes_max": 2000000,
        "gasto_min": 20000, "gasto_max": 50000,
    },
    {
        "id": "003", "page_name": "NutriMax Brasil", "dias": 509,
        "titulo": "Ganhe 20% de desconto hoje",
        "corpo": "Você sabia que 90% das dietas falham por falta do nutriente certo? Descubra o suplemento que está mudando a vida de 50.000 brasileiros.",
        "formato": "antes_depois", "impressoes_min": 500000, "impressoes_max": 1000000,
        "gasto_min": 10000, "gasto_max": 20000,
    },
    {
        "id": "004", "page_name": "NutriMax Brasil", "dias": 479,
        "titulo": "Quero meu kit de transformação",
        "corpo": "Janeiro chegou. Sua transformação começa agora. Kit completo com 3 meses de suplementação por R$197.",
        "formato": "urgencia", "impressoes_min": 300000, "impressoes_max": 700000,
        "gasto_min": 8000, "gasto_max": 15000,
    },
    {
        "id": "005", "page_name": "ProteínaBR", "dias": 31,
        "titulo": "Assistir vídeo do médico",
        "corpo": "Médico revela: o erro que impede você de perder barriga. E como corrigir em 7 dias.",
        "formato": "autoridade", "impressoes_min": 200000, "impressoes_max": 500000,
        "gasto_min": 5000, "gasto_max": 10000,
    },
] * 10  # multiplica para simular mais resultados


# ─── APP ──────────────────────────────────────────────────────────────────────

app = FastAPI(title="AdSpy BR API", version="0.1.0")

# Registra rotas do Stripe
from stripe_integration import router as stripe_router
app.include_router(stripe_router)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth ──

@app.post("/auth/cadastro")
def cadastro(dados: CadastroSchema, db: Session = Depends(get_db)):
    if db.query(Usuario).filter(Usuario.email == dados.email).first():
        raise HTTPException(400, "Email já cadastrado")

    user = Usuario(
        email=dados.email,
        nome=dados.nome,
        senha_hash=hash_senha(dados.senha),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = criar_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer", "usuario": {"nome": user.nome, "plano": user.plano}}


@app.post("/auth/login", response_model=TokenSchema)
def login(form: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(Usuario).filter(Usuario.email == form.username).first()
    if not user or not verificar_senha(form.password, user.senha_hash):
        raise HTTPException(401, "Email ou senha incorretos")

    token = criar_token({"sub": user.email})
    return {"access_token": token, "token_type": "bearer", "usuario": {"nome": user.nome, "plano": user.plano}}


@app.get("/auth/me")
def me(user: Usuario = Depends(usuario_atual)):
    plano_info = PLANOS[user.plano]
    return {
        "id": user.id,
        "nome": user.nome,
        "email": user.email,
        "plano": user.plano,
        "plano_info": plano_info,
        "buscas_hoje": user.buscas_hoje,
    }


# ── Busca ──

@app.post("/buscar")
def buscar(dados: BuscaSchema, user: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    plano = PLANOS[user.plano]

    # Verifica limite de buscas diárias
    hoje = datetime.now().strftime("%Y-%m-%d")
    if user.ultima_busca != hoje:
        user.buscas_hoje  = 0
        user.ultima_busca = hoje

    if user.buscas_hoje >= plano["limite_buscas_dia"]:
        raise HTTPException(429, f"Limite de {plano['limite_buscas_dia']} buscas/dia atingido. Faça upgrade.")

    user.buscas_hoje += 1
    db.commit()

    # Retorna resultados limitados pelo plano
    limite = dados.limite or plano["limite_resultados"]
    limite = min(limite, plano["limite_resultados"])

    from data_source import buscar_anuncios
    resultados = buscar_anuncios(dados.termo, dados.pais, limite)

    resposta = {
        "termo": dados.termo,
        "total": len(resultados),
        "anuncios": resultados,
        "buscas_restantes": plano["limite_buscas_dia"] - user.buscas_hoje,
    }

    if plano["padroes"]:
        resposta["padroes"] = calcular_padroes(resultados)

    return resposta


def calcular_padroes(anuncios: list) -> dict:
    p = {"antes_depois": 0, "urgencia": 0, "autoridade": 0, "prova_social": 0}
    for ad in anuncios:
        t = (ad.get("corpo", "") + " " + ad.get("titulo", "")).lower()
        if any(w in t for w in ["antes", "depois", "transforma"]): p["antes_depois"] += 1
        if any(w in t for w in ["limitado", "hoje", "acaba"]):      p["urgencia"] += 1
        if any(w in t for w in ["médico", "especialista"]):          p["autoridade"] += 1
        if any(w in t for w in ["clientes", "avalia", "estrelas"]):  p["prova_social"] += 1
    return p


# ── Planos ──

@app.get("/planos")
def listar_planos():
    return PLANOS


@app.post("/planos/upgrade")
def upgrade(plano: str, user: Usuario = Depends(usuario_atual), db: Session = Depends(get_db)):
    if plano not in PLANOS:
        raise HTTPException(400, "Plano inválido")
    # Em produção: integrar Stripe aqui antes de mudar o plano
    user.plano = plano
    db.commit()
    return {"mensagem": f"Plano atualizado para {plano}", "plano": PLANOS[plano]}


# ── Health ──

@app.get("/")
def health():
    return {"status": "ok", "versao": "0.1.0"}
