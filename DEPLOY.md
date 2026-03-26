# Deploy — AdSpy BR

## Backend → Railway

1. Crie conta em railway.app
2. New Project → Deploy from GitHub → selecione o repo
3. Configure o diretório raiz: `saas/backend`
4. Adicione as variáveis de ambiente (Settings → Variables):
   - SECRET_KEY
   - STRIPE_SECRET_KEY
   - STRIPE_WEBHOOK_SECRET
   - STRIPE_PRICE_PRO
   - STRIPE_PRICE_ELITE
   - FB_APP_ID (opcional)
   - FB_APP_SECRET (opcional)
   - FRONTEND_URL (URL do Vercel depois de fazer o deploy)
5. Railway detecta o Procfile e sobe automaticamente
6. Copie a URL gerada (ex: adspy-backend.up.railway.app)

## Frontend → Vercel

1. Crie conta em vercel.com
2. New Project → Import from GitHub → selecione o repo
3. Configure o diretório raiz: `saas/frontend`
4. Adicione variável de ambiente:
   - VITE_API_URL = https://adspy-backend.up.railway.app
5. Vercel detecta o vercel.json e faz o deploy
6. Atualize FRONTEND_URL no Railway com a URL do Vercel

## Stripe

1. Crie conta em stripe.com
2. Ative modo ao vivo (Live mode)
3. Crie os produtos:
   - Pro: R$97/mês → copie o Price ID → STRIPE_PRICE_PRO
   - Elite: R$197/mês → copie o Price ID → STRIPE_PRICE_ELITE
4. Configure webhook:
   - URL: https://adspy-backend.up.railway.app/stripe/webhook
   - Eventos: checkout.session.completed, customer.subscription.deleted
   - Copie o Signing Secret → STRIPE_WEBHOOK_SECRET

## Domínio customizado (opcional)

- Railway: Settings → Domains → Add custom domain
- Vercel: Settings → Domains → Add domain
