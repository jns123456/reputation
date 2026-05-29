"""Phase 2 i18n: empty PO entries, notification copy, emails, legal, flash messages."""

from __future__ import annotations

# Corrections for notification_tags / dropdown copy damaged in phase 1.
NOTIFICATION_COPY_FIXES: dict[str, str] = {
    "published a forecast on": "publicó un pronóstico en",
    "liked your": "le gustó tu",
    "disliked your": "no le gustó tu",
    "correct": "correcto",
    "was resolved. Your forecast was": "se resolvió. Tu pronóstico fue",
    "reputation points": "puntos de reputación",
    "accepted your challenge": "aceptó tu desafío",
    "sent you a notification": "te envió una notificación",
    "forecast": "pronóstico",
}

PHASE2_FIXES: dict[str, str] = {
    **NOTIFICATION_COPY_FIXES,
    # --- Email / verification (Python + templates) ---
    "Email provider rejected the message. With onboarding@resend.dev you can only send to your Resend account email until you verify a domain.": (
        "El proveedor de email rechazó el mensaje. Con onboarding@resend.dev solo puedes enviar "
        "al email de tu cuenta Resend hasta verificar un dominio."
    ),
    "Email sending is not configured yet. Please contact support or try again later.": (
        "El envío de email aún no está configurado. Contacta soporte o inténtalo más tarde."
    ),
    "Resend test mode blocked the email. Use the development link on this page.": (
        "El modo de prueba de Resend bloqueó el email. Usa el enlace de desarrollo en esta página."
    ),
    "Your email address changed after this link was sent. Request a new verification email.": (
        "Tu email cambió después de enviar este enlace. Solicita un nuevo email de verificación."
    ),
    "Get a reminder before a market you have an open forecast on closes.": (
        "Recibe un recordatorio antes de que cierre un mercado en el que tienes un pronóstico abierto."
    ),
    "Get alerts on this device even when PredictStamp isn't open (requires granting permission).": (
        "Recibe alertas en este dispositivo aunque PredictStamp no esté abierto (requiere permiso)."
    ),
    "We could not email the verification link (Resend test mode). Use the development link on the next page.": (
        "No pudimos enviar el enlace de verificación (modo prueba Resend). "
        "Usa el enlace de desarrollo en la siguiente página."
    ),
    "Your account was created, but we could not send the verification email. Try resending from the next screen.": (
        "Tu cuenta se creó, pero no pudimos enviar el email de verificación. "
        "Reenvíalo desde la siguiente pantalla."
    ),
    "Check your inbox and confirm your email to continue.": (
        "Revisa tu bandeja y confirma tu email para continuar."
    ),
    "Email confirmed for another account. Log in with that account to continue.": (
        "Email confirmado para otra cuenta. Inicia sesión con esa cuenta para continuar."
    ),
    "We sent a verification link to your new email address.": (
        "Enviamos un enlace de verificación a tu nuevo email."
    ),
    "Your email was updated, but we could not send a verification message. Use the resend option on the verification page.": (
        "Tu email se actualizó, pero no pudimos enviar el mensaje de verificación. "
        "Usa reenviar en la página de verificación."
    ),
    "Confirm your email on PredictStamp": "Confirma tu email en PredictStamp",
    # --- Predictions / duplicate forecast ---
    "You already have an open forecast on this challenge event (%(challenges)s). Only one open forecast is allowed per event — exit your current position first. It already counts toward the challenge leaderboard and your global reputation.": (
        "Ya tienes un pronóstico abierto en este evento del desafío (%(challenges)s). "
        "Solo se permite un pronóstico abierto por evento — cierra tu posición actual primero. "
        "Ya cuenta para el ranking del desafío y tu reputación global."
    ),
    "You already have an open forecast on this market. Only one open forecast is allowed per event — exit it before placing another.": (
        "Ya tienes un pronóstico abierto en este mercado. "
        "Solo se permite un pronóstico abierto por evento — ciérralo antes de publicar otro."
    ),
    # --- Alert settings / push ---
    "Push on this device": "Push en este dispositivo",
    "Allow browser notifications so alerts reach you even when PredictStamp is closed.": (
        "Permite notificaciones del navegador para recibir alertas aunque PredictStamp esté cerrado."
    ),
    "Enable push on this device": "Activar push en este dispositivo",
    "Push is enabled on this device.": "Push activado en este dispositivo.",
    "Requesting permission…": "Solicitando permiso…",
    "Push enabled — you are all set.": "Push activado — todo listo.",
    "Permission was not granted.": "No se concedió el permiso.",
    # --- Onboarding ---
    "You're in": "¡Listo!",
    "Reputation is earned by calling real-world markets — no betting, just credibility. Pick a market below to get started.": (
        "La reputación se gana pronosticando mercados reales — sin apuestas, solo credibilidad. "
        "Elige un mercado abajo para empezar."
    ),
    "Popular markets to call": "Mercados populares para pronosticar",
    "Skip for now": "Omitir por ahora",
    # --- Profile ---
    "Level: %(title)s. ": "Nivel: %(title)s. ",
    "%(rep)s reputation · %(pop)s popularity on PredictStamp.": (
        "%(rep)s reputación · %(pop)s popularidad en PredictStamp."
    ),
    "Best: %(best)s days": "Mejor: %(best)s días",
    "Act today to keep it alive!": "¡Actúa hoy para mantenerla!",
    "%(points)s / %(next)s rep": "%(points)s / %(next)s rep",
    "Max level": "Nivel máximo",
    # --- Verify email ---
    "Confirm your email": "Confirma tu email",
    "email address": "dirección de email",
    "We sent a secure link to <strong>%(email)s</strong>. Open it on this device to unlock your account.": (
        "Enviamos un enlace seguro a <strong>%(email)s</strong>. "
        "Ábrelo en este dispositivo para desbloquear tu cuenta."
    ),
    "Check your inbox": "Revisa tu bandeja",
    "The link expires in 48 hours. Check spam if you do not see it.": (
        "El enlace caduca en 48 horas. Revisa spam si no lo ves."
    ),
    "Waiting for confirmation": "Esperando confirmación",
    "Until your email is verified you can only use this page, log out, or request a new link.": (
        "Hasta verificar tu email solo puedes usar esta página, cerrar sesión o pedir un enlace nuevo."
    ),
    "Development shortcut": "Atajo de desarrollo",
    "Resend test mode only emails your account address. In local dev you can confirm with this link:": (
        "El modo prueba de Resend solo envía a tu email de cuenta. En desarrollo local puedes confirmar con este enlace:"
    ),
    "Wrong address?": "¿Email incorrecto?",
    "Log out and sign up again": "Cierra sesión y regístrate de nuevo",
    "Email": "Email",
    "Link": "Enlace",
    "confirmed": "confirmado",
    "You are all set": "Todo listo",
    "Link already used": "Enlace ya usado",
    "Request a fresh verification email from your account.": (
        "Solicita un nuevo email de verificación desde tu cuenta."
    ),
    "Already voted": "Ya votaste",
    # --- Vote reactions preview ---
    "Liked by <strong>%(name1)s</strong> and <strong>%(name2)s</strong>": (
        "Le gusta a <strong>%(name1)s</strong> y <strong>%(name2)s</strong>"
    ),
    "Liked by <strong>%(name1)s</strong>, <strong>%(name2)s</strong> and <strong>%(others)s others</strong>": (
        "Le gusta a <strong>%(name1)s</strong>, <strong>%(name2)s</strong> y <strong>%(others)s más</strong>"
    ),
    "Disliked by <strong>%(name1)s</strong> and <strong>%(name2)s</strong>": (
        "No le gusta a <strong>%(name1)s</strong> y <strong>%(name2)s</strong>"
    ),
    "Disliked by <strong>%(name1)s</strong>, <strong>%(name2)s</strong> and <strong>%(others)s others</strong>": (
        "No le gusta a <strong>%(name1)s</strong>, <strong>%(name2)s</strong> y <strong>%(others)s más</strong>"
    ),
    # --- Forecasts feed ---
    "Feed sort": "Orden del feed",
    "Recent": "Recientes",
    "Hot": "Destacados",
    "Lock in your call before the window closes": "Cierra tu pronóstico antes de que cierre la ventana",
    # --- Legal ---
    "Important information about PredictStamp, the company operating it, and how to contact us.": (
        "Información importante sobre PredictStamp, la empresa que lo opera y cómo contactarnos."
    ),
    "Operator": "Operador",
    "PredictStamp is operated by TAO FACTORY LLC, a Delaware limited liability company.": (
        "PredictStamp es operado por TAO FACTORY LLC, una sociedad de responsabilidad limitada de Delaware."
    ),
    "Delaware, United States": "Delaware, Estados Unidos",
    "Contact": "Contacto",
    "No financial services": "Sin servicios financieros",
    "PredictStamp is a social and reputational platform. It does not offer betting, trading, brokerage, custody, wallets, deposits, or financial settlement services.": (
        "PredictStamp es una plataforma social y de reputación. No ofrece apuestas, trading, "
        "corretaje, custodia, billeteras, depósitos ni liquidaciones financieras."
    ),
    "Terms and conditions": "Términos y condiciones",
    "Use of PredictStamp is subject to our Terms and Conditions.": (
        "El uso de PredictStamp está sujeto a nuestros Términos y Condiciones."
    ),
    "Read Terms & Conditions": "Leer Términos y Condiciones",
    "Forecasts, comments, reputation scores, popularity scores, and market discussions are user-generated social content.": (
        "Pronósticos, comentarios, puntuaciones de reputación y popularidad, y debates de mercados "
        "son contenido social generado por usuarios."
    ),
    "Market data may reference third-party sources. PredictStamp does not control external markets, outcomes, or third-party data availability.": (
        "Los datos de mercado pueden referenciar fuentes de terceros. PredictStamp no controla "
        "mercados externos, resultados ni la disponibilidad de datos de terceros."
    ),
    "Nothing on PredictStamp is financial, investment, legal, tax, or professional advice.": (
        "Nada en PredictStamp es asesoramiento financiero, de inversión, legal, fiscal o profesional."
    ),
    # --- Forecast P&L ---
    "Unrealized reputation if you exited at current market odds. Updates as the market moves.": (
        "Reputación no realizada si cerraras a las cuotas actuales del mercado. Se actualiza con el mercado."
    ),
    "+%(points)s rep if exited now": "+%(points)s rep si cierras ahora",
    "%(points)s rep if exited now": "%(points)s rep si cierras ahora",
    "Break-even if exited now": "Punto de equilibrio si cierras ahora",
    "Your following feed is empty": "Tu feed de seguidos está vacío",
    # --- Terms ---
    "Terms &": "Términos y",
    "Rules for using PredictStamp, a social reputation platform operated by TAO FACTORY LLC.": (
        "Reglas de uso de PredictStamp, plataforma social de reputación operada por TAO FACTORY LLC."
    ),
    "Effective date:": "Fecha de vigencia:",
    "May 28, 2026": "28 de mayo de 2026",
    "These Terms are provided for product clarity and should be reviewed by counsel before launch in production.": (
        "Estos Términos se ofrecen para claridad del producto y deben revisarse con asesoría legal antes del lanzamiento."
    ),
    "A Delaware limited liability company operating PredictStamp.": (
        "Una sociedad de responsabilidad limitada de Delaware que opera PredictStamp."
    ),
    "PredictStamp does not enable wagers, deposits, wallets, trades, custody, financial transactions, or payouts.": (
        "PredictStamp no permite apuestas, depósitos, billeteras, operaciones, custodia, transacciones financieras ni pagos."
    ),
    "1. Acceptance of Terms": "1. Aceptación de los Términos",
    "By accessing or using PredictStamp, you agree to these Terms and Conditions. If you do not agree, do not use the platform.": (
        "Al acceder o usar PredictStamp, aceptas estos Términos y Condiciones. Si no estás de acuerdo, no uses la plataforma."
    ),
    "2. The Service": "2. El Servicio",
    "PredictStamp lets users browse prediction-market-related topics, publish comments, create formal forecasts, participate in social challenges, and build public reputation and popularity records.": (
        "PredictStamp permite explorar temas de mercados de predicción, publicar comentarios, crear pronósticos formales, "
        "participar en desafíos sociales y construir historial público de reputación y popularidad."
    ),
    "3. No Financial Activity": "3. Sin actividad financiera",
    "PredictStamp is not a betting, gambling, trading, brokerage, exchange, custody, wallet, investment advisory, or financial services platform. You cannot deposit funds, place wagers, trade contracts, withdraw funds, or receive payouts through PredictStamp.": (
        "PredictStamp no es una plataforma de apuestas, juego, trading, corretaje, bolsa, custodia, billetera, "
        "asesoría de inversión ni servicios financieros. No puedes depositar fondos, apostar, operar contratos, "
        "retirar fondos ni recibir pagos a través de PredictStamp."
    ),
    "4. User Content and Conduct": "4. Contenido y conducta del usuario",
    "You are responsible for the content you post, including comments, forecasts, reasoning, votes, and profile information. Do not post illegal, misleading, abusive, infringing, spam, or malicious content. We may remove content or restrict accounts that violate these Terms or harm the platform.": (
        "Eres responsable del contenido que publicas, incluidos comentarios, pronósticos, razonamiento, votos e información de perfil. "
        "No publiques contenido ilegal, engañoso, abusivo, infractor, spam o malicioso. Podemos eliminar contenido o "
        "restringir cuentas que violen estos Términos o dañen la plataforma."
    ),
    "Reputation and popularity scores are platform-specific social metrics. They are not money, securities, tokens, credits, rewards, or transferable property, and they have no cash value.": (
        "Las puntuaciones de reputación y popularidad son métricas sociales de la plataforma. "
        "No son dinero, valores, tokens, créditos, recompensas ni propiedad transferible, y no tienen valor en efectivo."
    ),
    "6. Third-Party Data": "6. Datos de terceros",
    "PredictStamp may display or reference third-party market data, links, outcomes, and metadata. Third-party data may be delayed, incomplete, inaccurate, or unavailable. PredictStamp is not responsible for third-party services or content.": (
        "PredictStamp puede mostrar o referenciar datos, enlaces, resultados y metadatos de mercados de terceros. "
        "Esos datos pueden estar retrasados, incompletos, inexactos o no disponibles. "
        "PredictStamp no es responsable de servicios o contenido de terceros."
    ),
    "7. No Advice": "7. Sin asesoramiento",
    "Content on PredictStamp is for informational and social discussion purposes only. It is not financial, investment, legal, tax, or professional advice.": (
        "El contenido en PredictStamp es solo para información y debate social. "
        "No es asesoramiento financiero, de inversión, legal, fiscal ni profesional."
    ),
    "8. Accounts and Availability": "8. Cuentas y disponibilidad",
    "You are responsible for maintaining account security. We may update, suspend, limit, or discontinue any part of the platform at any time, including features, rankings, scoring formulas, and content availability.": (
        "Eres responsable de la seguridad de tu cuenta. Podemos actualizar, suspender, limitar o discontinuar "
        "cualquier parte de la plataforma en cualquier momento, incluidas funciones, rankings, fórmulas de puntuación y disponibilidad de contenido."
    ),
    "9. Contact": "9. Contacto",
    "For questions about these Terms, contact TAO FACTORY LLC at <a href=\"mailto:ops@predictstamp.com\" class=\"font-medium text-brand-600 hover:underline dark:text-brand-400\">ops@predictstamp.com</a>.": (
        "Para preguntas sobre estos Términos, contacta a TAO FACTORY LLC en "
        "<a href=\"mailto:ops@predictstamp.com\" class=\"font-medium text-brand-600 hover:underline dark:text-brand-400\">ops@predictstamp.com</a>."
    ),
    # --- Transactional emails ---
    "%(name)s, here's your daily recap": "%(name)s, aquí está tu resumen diario",
    "What happened on PredictStamp in the last 24 hours.": (
        "Lo que pasó en PredictStamp en las últimas 24 horas."
    ),
    "act today to keep it alive!": "¡actúa hoy para mantenerla!",
    "Hi %(name)s, there's new activity on your PredictStamp account.": (
        "Hola %(name)s, hay actividad nueva en tu cuenta de PredictStamp."
    ),
    "Hi %(name)s — you haven't been active today. Make a forecast, comment, or vote before midnight (UTC) to keep your streak going.": (
        "Hola %(name)s — no has estado activo hoy. Haz un pronóstico, comenta o vota antes de medianoche (UTC) "
        "para mantener tu racha."
    ),
    "Keep my streak alive": "Mantener mi racha",
    # --- Markets / predictions ---
    "Forecast this %(cat)s market and build your reputation on PredictStamp.": (
        "Pronostica este mercado de %(cat)s y construye tu reputación en PredictStamp."
    ),
    "Make your call and build your reputation.": "Haz tu pronóstico y construye tu reputación.",
    "Track reputation P&L on active forecasts, close positions, and re-enter whenever your view changes.": (
        "Sigue el P&L de reputación en pronósticos activos, cierra posiciones y vuelve a entrar cuando cambie tu visión."
    ),
    "Estimated if you closed every open forecast at current market probabilities.": (
        "Estimado si cerraras todos los pronósticos abiertos a las probabilidades actuales del mercado."
    ),
    "Each card compares your entry probability with the current market probability for the same side.": (
        "Cada tarjeta compara tu probabilidad de entrada con la probabilidad actual del mercado para el mismo lado."
    ),
    "Entry": "Entrada",
    "Closing realizes this reputation delta and frees you to forecast again.": (
        "Cerrar realiza este delta de reputación y te permite pronosticar de nuevo."
    ),
    "Browse markets to open a new reputation-only forecast.": (
        "Explora mercados para abrir un nuevo pronóstico solo de reputación."
    ),
    "Challenge event — forecast already placed": "Evento del desafío — pronóstico ya publicado",
    "This market is part of an active challenge. Your forecast will count toward the challenge leaderboard and your global reputation. Only one open forecast is allowed per event.": (
        "Este mercado forma parte de un desafío activo. Tu pronóstico contará para el ranking del desafío "
        "y tu reputación global. Solo se permite un pronóstico abierto por evento."
    ),
}

PHASE2_PLURAL_FIXES: dict[str, tuple[str, str]] = {
    "%(counter)s like — view who liked": (
        "%(counter)s voto positivo — ver quién votó",
        "%(counter)s votos positivos — ver quién votó",
    ),
    "%(counter)s dislike — view who disliked": (
        "%(counter)s voto negativo — ver quién votó en contra",
        "%(counter)s votos negativos — ver quién votó en contra",
    ),
}

# Multiline blocktrans with HTML — singular/plural share structure.
_CHALLENGE_ALERT_SINGULAR = (
    "\n        Your open forecast on this event already counts for <strong>%(counter)s</strong> "
    "active challenge and your global reputation — even if you placed it before the challenge started. "
    "You cannot open a second position on the same event.\n        "
)
_CHALLENGE_ALERT_PLURAL = (
    "\n        Your open forecast on this event already counts for <strong>%(counter)s</strong> "
    "active challenges and your global reputation — even if you placed it before they started. "
    "You cannot open a second position on the same event.\n        "
)
_CHALLENGE_ALERT_ES_SINGULAR = (
    "\n        Tu pronóstico abierto en este evento ya cuenta para <strong>%(counter)s</strong> "
    "desafío activo y tu reputación global — incluso si lo publicaste antes de que empezara el desafío. "
    "No puedes abrir una segunda posición en el mismo evento.\n        "
)
_CHALLENGE_ALERT_ES_PLURAL = (
    "\n        Tu pronóstico abierto en este evento ya cuenta para <strong>%(counter)s</strong> "
    "desafíos activos y tu reputación global — incluso si lo publicaste antes de que empezaran. "
    "No puedes abrir una segunda posición en el mismo evento.\n        "
)

PHASE2_BLOCK_PLURAL: dict[str, tuple[str, str]] = {
    _CHALLENGE_ALERT_SINGULAR: (_CHALLENGE_ALERT_ES_SINGULAR, _CHALLENGE_ALERT_ES_PLURAL),
}
