"""Phase 3 i18n: transactional email templates and JS-adjacent strings."""

from __future__ import annotations

PHASE3_FIXES: dict[str, str] = {
    "Welcome to PredictStamp": "Bienvenido a PredictStamp",
    "Welcome to PredictStamp!": "¡Bienvenido a PredictStamp!",
    "Hi %(name)s, thanks for joining PredictStamp.": "Hola %(name)s, gracias por unirte a PredictStamp.",
    "PredictStamp is the social layer for prediction markets: debate real-world events, publish formal forecasts, and build credibility when markets resolve. No betting, no wallets.": (
        "PredictStamp es la capa social de los mercados de predicción: debatí eventos del mundo real, "
        "publicá pronósticos formales y construí credibilidad cuando los mercados se resuelven. "
        "Sin apuestas, sin wallets."
    ),
    "Earned when your resolved forecasts are correct. Measures your predictive quality over time.": (
        "Se gana cuando tus pronósticos resueltos son correctos. Mide tu calidad predictiva a lo largo del tiempo."
    ),
    "Driven by votes and debate. Independent from reputation — you can be popular without being accurate.": (
        "Impulsada por votos y debate. Es independiente de la reputación: podés ser popular sin ser preciso."
    ),
    "Browse open markets, make your first forecast, and follow top predictors to learn from the community.": (
        "Explorá mercados abiertos, hacé tu primer pronóstico y seguí a predictores destacados para aprender de la comunidad."
    ),
    "Explore PredictStamp": "Explorar PredictStamp",
    "Questions? Reply to this email or visit the platform anytime.": (
        "¿Preguntas? Respondé a este email o visitá la plataforma cuando quieras."
    ),
    "Confirm email": "Confirmar email",
    "Hi %(name)s, confirm your email address to finish creating your PredictStamp account.": (
        "Hola %(name)s, confirma tu dirección de email para terminar de crear tu cuenta en PredictStamp."
    ),
    "This link expires in %(hours)s hours and can only be used once.": (
        "Este enlace expira en %(hours)s horas y solo puede usarse una vez."
    ),
    "If the button does not work, copy and paste this URL into your browser:": (
        "Si el botón no funciona, copia y pega esta URL en tu navegador:"
    ),
    "You receive this email because you enabled email alerts on PredictStamp.": (
        "Recibís este email porque activaste alertas por email en PredictStamp."
    ),
    "Manage alerts": "Administrar alertas",
    "You receive this email because you signed up on PredictStamp.": (
        "Recibís este email porque te registraste en PredictStamp."
    ),
    # welcome.txt
    "PredictStamp is the social layer for prediction markets: a place to debate real-world events, publish formal forecasts, and build reputation when markets resolve.": (
        "PredictStamp es la capa social de los mercados de predicción: un lugar para debatir eventos del "
        "mundo real, publicar pronósticos formales y construir reputación cuando los mercados se resuelven."
    ),
    "What you can do:": "Qué puedes hacer:",
    "Browse markets imported from sources like Polymarket (no real-money betting).": (
        "Explorar mercados importados de fuentes como Polymarket (sin apostar dinero real)."
    ),
    "Publish formal forecasts with your reasoning.": "Publicar pronósticos formales con tu razonamiento.",
    "Comment, debate, and follow other predictors.": "Comentar, debatir y seguir a otros predictores.",
    "Earn Reputation when you are right (predictive quality) and Popularity when your content gets engagement.": (
        "Ganar Reputación cuando aciertas (calidad predictiva) y Popularidad cuando tu contenido genera engagement."
    ),
    "Two scores, independent:": "Dos puntuaciones, independientes:",
    "Reputation: measures the historical quality of your resolved forecasts.": (
        "Reputación: mide la calidad histórica de tus pronósticos resueltos."
    ),
    "Popularity: measures votes, replies, and social visibility.": (
        "Popularidad: mide votos, respuestas y visibilidad social."
    ),
    "PredictStamp is not a betting house: there are no wallets, deposits, or real-money trading.": (
        "PredictStamp no es una casa de apuestas: no hay wallets, depósitos ni trading con dinero real."
    ),
    "Get started:": "Empieza aquí:",
    "If you did not create an account, you can ignore this message.": (
        "Si no creaste una cuenta, puedes ignorar este mensaje."
    ),
    "Confirm your email address to finish creating your PredictStamp account.": (
        "Confirma tu dirección de email para terminar de crear tu cuenta en PredictStamp."
    ),
    "price": "precio",
}

PHASE3_PLURAL_FIXES: dict[str, tuple[str, str]] = {}
