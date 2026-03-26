"""
Stripe Integration — AdSpy BR
Gerencia checkout, webhooks e upgrade de planos

Setup:
    1. Crie conta em stripe.com
    2. Pegue as chaves em: dashboard.stripe.com/apikeys
    3. Crie os produtos/preços no dashboard do Stripe
    4. Configure o webhook: dashboard.stripe.com/webhooks
       - Endpoint: https://seu-backend.com/stripe/webhook
       - Eventos: checkout.session.completed, customer.subscription.deleted
"""

import stripe
from fastapi import APIRouter, Request, HTTPException, Depends
from sqlalchemy.orm import Session
import os

# Importa do main.py
from main import get_db, usuario_atual, Usuario, PLANOS

router = APIRouter(prefix="/stripe", tags=["Stripe"])

# ─── CHAVES (usar variáveis de ambiente em produção) ─────────────────────────

STRIPE_SECRET_KEY      = os.getenv("STRIPE_SECRET_KEY", "sk_test_SUA_CHAVE_AQUI")
STRIPE_WEBHOOK_SECRET  = os.getenv("STRIPE_WEBHOOK_SECRET", "whsec_SUA_CHAVE_WEBHOOK_AQUI")
FRONTEND_URL           = os.getenv("FRONTEND_URL", "http://localhost:3000")

stripe.api_key = STRIPE_SECRET_KEY

# IDs dos preços no Stripe (criar no dashboard e colar aqui)
STRIPE_PRICE_IDS = {
    "pro":   os.getenv("STRIPE_PRICE_PRO",   "price_SEU_ID_PRO"),
    "elite": os.getenv("STRIPE_PRICE_ELITE", "price_SEU_ID_ELITE"),
}


# ─── CRIAR CHECKOUT ───────────────────────────────────────────────────────────

@router.post("/checkout/{plano}")
async def criar_checkout(
    plano: str,
    user: Usuario = Depends(usuario_atual),
    db:   Session = Depends(get_db),
):
    if plano not in ["pro", "elite"]:
        raise HTTPException(400, "Plano inválido")

    price_id = STRIPE_PRICE_IDS.get(plano)
    if not price_id or "SEU_ID" in price_id:
        raise HTTPException(500, "Stripe não configurado. Adicione os PRICE IDs no .env")

    session = stripe.checkout.Session.create(
        payment_method_types=["card"],
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        customer_email=user.email,
        metadata={"user_id": str(user.id), "plano": plano},
        success_url=f"{FRONTEND_URL}?upgrade=success&plano={plano}",
        cancel_url=f"{FRONTEND_URL}?upgrade=cancelled",
    )

    return {"checkout_url": session.url}


# ─── WEBHOOK ─────────────────────────────────────────────────────────────────

@router.post("/webhook")
async def webhook(request: Request, db: Session = Depends(get_db)):
    payload   = await request.body()
    sig       = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except stripe.error.SignatureVerificationError:
        raise HTTPException(400, "Assinatura inválida")

    # Pagamento confirmado → upgrade do plano
    if event["type"] == "checkout.session.completed":
        session  = event["data"]["object"]
        user_id  = int(session["metadata"]["user_id"])
        plano    = session["metadata"]["plano"]
        sub_id   = session.get("subscription")

        user = db.query(Usuario).filter(Usuario.id == user_id).first()
        if user:
            user.plano          = plano
            user.stripe_sub_id  = sub_id or ""
            db.commit()
            print(f"[Stripe] Usuário {user.email} → plano {plano}")

    # Assinatura cancelada → downgrade para free
    if event["type"] == "customer.subscription.deleted":
        sub_id = event["data"]["object"]["id"]
        user   = db.query(Usuario).filter(Usuario.stripe_sub_id == sub_id).first()
        if user:
            user.plano = "free"
            db.commit()
            print(f"[Stripe] Assinatura cancelada → {user.email} voltou para free")

    return {"status": "ok"}


# ─── PORTAL DO CLIENTE (cancelar/mudar plano) ────────────────────────────────

@router.post("/portal")
async def portal_cliente(
    user: Usuario = Depends(usuario_atual),
    db:   Session = Depends(get_db),
):
    if not hasattr(user, "stripe_customer_id") or not user.stripe_customer_id:
        raise HTTPException(400, "Nenhuma assinatura ativa encontrada")

    session = stripe.billing_portal.Session.create(
        customer=user.stripe_customer_id,
        return_url=FRONTEND_URL,
    )
    return {"portal_url": session.url}
