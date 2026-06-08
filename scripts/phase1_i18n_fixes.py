"""Phase 1 i18n fixes: navbar priority strings, Auth0, and unfuzzy corrections."""

from __future__ import annotations

# msgid -> correct Spanish (preserve %(placeholders)s)
PHASE1_FIXES: dict[str, str] = {
    # --- Navbar / auth priority ---
    "or": "o",
    "No account?": "¿No tienes cuenta?",
    "Open forecasts": "Pronósticos abiertos",
    "Open Forecasts": "Pronósticos abiertos",
    "Close menu": "Cerrar menú",
    "Continue with Google": "Continuar con Google",
    "Sign up with Auth0": "Registrarse con Auth0",
    "Auth0 sign-in is not available right now.": "El inicio de sesión con Auth0 no está disponible ahora.",
    "We couldn't complete the Auth0 sign-in. Please try again.": (
        "No pudimos completar el inicio de sesión con Auth0. Inténtalo de nuevo."
    ),
    "Auth0 did not return a valid profile.": "Auth0 no devolvió un perfil válido.",
    "Too many login attempts. Please wait a few minutes and try again.": (
        "Demasiados intentos de inicio de sesión. Espera unos minutos e inténtalo de nuevo."
    ),
    "Too many sign-up attempts from this connection. Please try again later.": (
        "Demasiados intentos de registro desde esta conexión. Inténtalo más tarde."
    ),
    # --- Notifications / email subjects ---
    "%(actor)s published a new forecast": "%(actor)s publicó un pronóstico nuevo",
    "%(actor)s started following you": "%(actor)s empezó a seguirte",
    "%(actor)s upvoted your content": "%(actor)s votó positivamente tu contenido",
    "Your content received a vote": "Tu contenido recibió un voto",
    "%(actor)s invited you to a challenge": "%(actor)s te invitó a un desafío",
    "A challenge event just resolved": "Un evento del desafío se resolvió",
    "%(actor)s accepted your challenge": "%(actor)s aceptó tu desafío",
    "A challenge you joined is complete": "Un desafío al que te uniste ha terminado",
    "%(actor)s replied to your comment": "%(actor)s respondió a tu comentario",
    "%(actor)s mentioned you": "%(actor)s te mencionó",
    "You have a new notification": "Tienes una notificación nueva",
    "Your forecast resolved — see your reputation": "Tu pronóstico se resolvió — mira tu reputación",
    "A market you forecast is closing soon": "Cierra pronto un mercado en el que pronosticaste",
    "Your PredictStamp digest": "Tu resumen de PredictStamp",
    "Your %(days)s-day streak ends tonight": "Tu racha de %(days)s días termina esta noche",
    "Could not send the verification email.": "No se pudo enviar el email de verificación.",
    "Your email address is confirmed.": "Tu dirección de email está confirmada.",
    "Enter a valid email address.": "Introduce una dirección de email válida.",
    "Add an email address to your profile first.": "Añade primero un email a tu perfil.",
    "Please wait a minute before requesting another email.": (
        "Espera un minuto antes de solicitar otro email."
    ),
    "Verification email sent. Check your inbox.": "Email de verificación enviado. Revisa tu bandeja.",
    "This verification link is invalid.": "Este enlace de verificación no es válido.",
    "This verification link has already been used.": "Este enlace de verificación ya se usó.",
    "This verification link has expired. Request a new one.": (
        "Este enlace de verificación caducó. Solicita uno nuevo."
    ),
    # --- Profile / alerts ---
    "Short bio (optional)": "Biografía breve (opcional)",
    "Profile photo": "Foto de perfil",
    "JPEG, PNG, WebP, or GIF. Max 5 MB.": "JPEG, PNG, WebP o GIF. Máx. 5 MB.",
    "Replies to your comments": "Respuestas a tus comentarios",
    "When someone @mentions you": "Cuando alguien te @menciona",
    "When a market you forecast is closing soon": "Cuando cierra pronto un mercado en el que pronosticaste",
    "Browser push notifications": "Notificaciones push del navegador",
    "Get notified when someone replies to one of your comments.": (
        "Recibe una notificación cuando alguien responda a uno de tus comentarios."
    ),
    "Get notified when someone mentions your @username.": (
        "Recibe una notificación cuando alguien mencione tu @usuario."
    ),
    "Profile updated.": "Perfil actualizado.",
    "Invalid target id": "ID de destino no válido",
    "Forecast side": "Lado del pronóstico",
    "Choose Yes or No for this outcome.": "Elige Sí o No para este resultado.",
    "You cannot exit another user's forecast.": "No puedes cerrar el pronóstico de otro usuario.",
    "Add text or poll choices to your post.": "Añade texto u opciones de encuesta a tu publicación.",
    "Invalid poll choice.": "Opción de encuesta no válida.",
    "You can't vote on your own poll.": "No puedes votar en tu propia encuesta.",
    "You can only delete your own posts.": "Solo puedes eliminar tus propias publicaciones.",
    "You can only delete your own comments.": "Solo puedes eliminar tus propios comentarios.",
    # --- Landing / marketing fragments ---
    "Build credibility": "Construye credibilidad",
    "through forecasts": "con pronósticos",
    "Social engagement, separate from credibility.": "Participación social, separada de la credibilidad.",
    "Real markets": "Mercados reales",
    "Live odds from Polymarket — no betting.": "Cuotas en vivo de Polymarket — sin apuestas.",
    "Pick up where you": "Retoma donde",
    "Welcome": "Bienvenido/a",
    "Make your first forecast": "Haz tu primer pronóstico",
    "Forecast this": "Pronostica esto",
    "No open markets right now — check back soon.": "No hay mercados abiertos ahora — vuelve pronto.",
    "Browse all markets": "Explorar todos los mercados",
    "Follow sharp forecasters": "Sigue a predictores destacados",
    "Explore markets": "Explorar mercados",
    "Preview": "Vista previa",
    "Required. Shown as your main name across the platform.": (
        "Obligatorio. Se muestra como tu nombre principal en la plataforma."
    ),
    "Joined %(date)s": "Se unió el %(date)s",
    "Alerts": "Alertas",
    "Verified account": "Cuenta verificada",
    'No users match "%(query)s".': 'Ningún usuario coincide con «%(query)s».',
    "Search users…": "Buscar usuarios…",
    "Search users": "Buscar usuarios",
    "pop": "pop",
    "%(rep)s reputation points on PredictStamp.": "%(rep)s puntos de reputación en PredictStamp.",
    "Level %(lvl)s · %(title)s": "Nivel %(lvl)s · %(title)s",
    "Achievements": "Logros",
    "username": "usuario",
    "Save changes": "Guardar cambios",
    "Hide from user directory": "Ocultarse del directorio de usuarios",
    "When enabled, you won't appear in the public user list or search. Direct profile links and your forecasts and comments still work.": (
        "Si está activado, no aparecerás en la lista pública de usuarios ni en la búsqueda. "
        "Los enlaces directos a tu perfil y tus pronósticos y comentarios siguen funcionando."
    ),
    "Set up your profile": "Configura tu perfil",
    "Step 1 — credentials and email verification.": "Paso 1 — credenciales y verificación de email.",
    "Almost there": "Casi listo",
    "Verify your": "Verifica tu",
    "Resend verification email": "Reenviar email de verificación",
    "Email verification": "Verificación de email",
    "not valid": "no válido",
    "Link expired": "Enlace caducado",
    "Invalid link": "Enlace no válido",
    "You can continue setting up your profile.": "Puedes continuar configurando tu perfil.",
    "Back to verification": "Volver a verificación",
    "Go to profile": "Ir al perfil",
    "Filter events": "Filtrar eventos",
    "Pending vote": "Voto pendiente",
    "No open events left to vote on.": "No quedan eventos abiertos para votar.",
    "You have not voted on any challenge events yet.": "Aún no has votado en ningún evento del desafío.",
    "Liked by <strong>%(name)s</strong>": "Le gusta a <strong>%(name)s</strong>",
    "Disliked by <strong>%(name)s</strong>": "No le gusta a <strong>%(name)s</strong>",
    "Close": "Cerrar",
    "Reactions": "Reacciones",
    "No likes yet.": "Aún no hay likes.",
    "No dislikes yet.": "Aún no hay dislikes.",
    "Resolving soon": "Cierra pronto",
    "information": "información",
    "Jurisdiction": "Jurisdicción",
    "Platform notices": "Avisos de la plataforma",
    "Find top predictors": "Encuentra los mejores predictores",
    "Loading more…": "Cargando más…",
    "Conditions": "Condiciones",
    "No betting or trading": "Sin apuestas ni trading",
    "View Legal information": "Ver información legal",
    "5. Reputation and Popularity": "5. Reputación y popularidad",
    "Recent activity": "Actividad reciente",
    "Open PredictStamp": "Abrir PredictStamp",
    "Manage your alert settings": "Administra tus alertas",
    "View thread": "Ver hilo",
    "Share comment": "Compartir comentario",
    "Share": "Compartir",
    "Share event": "Compartir evento",
    "Event on PredictStamp": "Evento en PredictStamp",
    "Forecast %(title)s on PredictStamp": "Pronostica %(title)s en PredictStamp",
    "Copy link": "Copiar enlace",
    "Place a forecast": "Hacer un pronóstico",
    "Reply posted.": "Respuesta publicada.",
    "Delete comment": "Eliminar comentario",
    "Delete comment?": "¿Eliminar comentario?",
    "You can't vote on your own comment": "No puedes votar tu propio comentario",
    "Remove choice": "Quitar opción",
    "1 day": "1 día",
    "View post": "Ver publicación",
    "%(time)s left": "Quedan %(time)s",
    "Forum navigation": "Navegación del foro",
    "Bookmarks": "Marcadores",
    "Prediction markets": "Mercados de predicción",
    "Explore live events": "Explora eventos en vivo",
    "Community predictions": "Predicciones de la comunidad",
    "Formal forecasts on markets": "Pronósticos formales sobre mercados",
    "Leaderboard rankings": "Rankings",
    "Follow top predictors": "Sigue a los mejores predictores",
    "Popular voices": "Voces populares",
    "Verification record": "Registro de verificación",
    "PredictStamp verification": "Verificación PredictStamp",
    "Signer": "Firmante",
    "Verified record": "Registro verificado",
    "Search results": "Resultados de búsqueda",
    "Search events": "Buscar eventos…",
    "Top outcomes by win probability — price history from Polymarket, updates when you refresh.": (
        "Principales resultados por probabilidad de victoria — historial de precios de Polymarket, "
        "se actualiza al refrescar."
    ),
    "The chart is view-only. Use <strong>Open on Polymarket</strong> above to visit the market — no trading on this platform.": (
        "El gráfico es solo lectura. Usa <strong>Abrir en Polymarket</strong> arriba para visitar "
        "el mercado — sin trading en esta plataforma."
    ),
    "Open positions": "Posiciones abiertas",
    "Your open": "Tus",
    "forecasts": "pronósticos",
    "Active forecasts you can exit now": "Pronósticos activos que puedes cerrar ahora",
    "Unrealized reputation": "Reputación no realizada",
    "Open forecast book": "Libro de pronósticos abiertos",
    "opened %(timesince)s ago": "abierto hace %(timesince)s",
    "Now": "Ahora",
    "Close forecast": "Cerrar pronóstico",
    "No open forecasts right now.": "No tienes pronósticos abiertos ahora.",
    "Challenge event": "Evento del desafío",
    "Posted %(timesince)s ago. You can exit this forecast at the current market price and enter again later.": (
        "Publicado hace %(timesince)s. Puedes cerrar este pronóstico al precio actual del mercado "
        "y volver a participar después."
    ),
    "Exit forecast": "Cerrar pronóstico",
    "All outcomes": "Todos los resultados",
    "Yes %(prob)s%%": "Sí %(prob)s%%",
    "No %(prob)s%%": "No %(prob)s%%",
    "to place your forecast on this event.": "para publicar tu pronóstico en este evento.",
    "Reputation +%(points)s realized on exit": "Reputación +%(points)s al cerrar",
    "Reputation %(points)s realized on exit": "Reputación %(points)s al cerrar",
    "Forecast:": "Pronóstico:",
    "Track record": "Historial",
}

# Entries where the existing fuzzy msgstr is already acceptable — only remove fuzzy flag.
PHASE1_UNFUZZY_KEEP_MSGSTR: frozenset[str] = frozenset(
    {
        "Profile photo must be 5 MB or smaller.",
        "Your email is already verified.",
        "Add text, an image, or a poll to your post.",
        "Sorted by soonest closing date. Existing open forecasts count immediately — including forecasts placed before the challenge started.",
        "PredictStamp",
        "<strong class=\"text-slate-800 dark:text-slate-200\">No.</strong> PredictStamp is not a betting, trading, or gambling platform. There are no wallets, deposits, or financial settlements.",
        "Follow forecasters to see their predictions here.",
        "Follow people to see their posts here.",
        "Be the first to share something.",
        "No comments yet — be the first to reply.",
        "View on Polymarket",
        "You can't start a thread on your own post. Reply to comments from others below — or share your post.",
    }
)

PHASE1_PLURAL_FIXES: dict[str, tuple[str, str]] = {
    "%(days)s-day activity streak": (
        "Racha de actividad de %(days)s día",
        "Racha de actividad de %(days)s días",
    ),
    "%(days)s-day streak": (
        "Racha de %(days)s día",
        "Racha de %(days)s días",
    ),
    "Don't lose your %(days)s-day streak": (
        "No pierdas tu racha de %(days)s día",
        "No pierdas tu racha de %(days)s días",
    ),
    "%(counter)s like": ("%(counter)s voto positivo", "%(counter)s votos positivos"),
    "%(counter)s dislike": ("%(counter)s voto negativo", "%(counter)s votos negativos"),
    "%(n)s unread notification": (
        "%(n)s notificación sin leer",
        "%(n)s notificaciones sin leer",
    ),
    "%(n)s open forecast": (
        "%(n)s pronóstico abierto",
        "%(n)s pronósticos abiertos",
    ),
}

# Reputation ranking (points per scored forecast)
PHASE1_FIXES.update(
    {
        "Rep / forecast": "Rep / pronóstico",
        "Scored": "Puntuados",
        "Ranked by average reputation per scored forecast — total points shown for reference. Not social popularity.": (
            "Clasificación por reputación media por pronóstico puntuado — los puntos totales se muestran como referencia. No es popularidad social."
        ),
        "Top predictors in this category — ranked by average reputation per scored forecast.": (
            "Mejores pronosticadores en esta categoría — clasificados por reputación media por pronóstico puntuado."
        ),
        "Average across %(scored)s scored forecasts.": (
            "Media en %(scored)s pronósticos puntuados."
        ),
        "Following · %(name)s": "Siguiendo · %(name)s",
        "%(name)s's profile": "Perfil de %(name)s",
        "No followers yet for %(name)s.": "Todavía no hay seguidores para %(name)s.",
        "%(name)s is not following anyone yet.": "%(name)s aún no sigue a nadie.",
        "%(count)s people": "%(count)s personas",
        "Group: %(group_name)s": "Grupo: %(group_name)s",
        "Closed %(closed_date)s": "Cerrado %(closed_date)s",
        "Entered %(entry_date)s": "Registrado %(entry_date)s",
        "Relative ranking": "Ranking relativo",
        "Absolute ranking": "Ranking absoluto",
        "Average reputation per scored forecast.": "Reputación media por pronóstico puntuado.",
        "Total reputation points from all scored forecasts.": "Puntos totales de reputación de todos los pronósticos puntuados.",
        "Relative ranking by average reputation per scored forecast — rewards predictive quality. Not social popularity.": (
            "Ranking relativo por reputación media por pronóstico puntuado — premia la calidad predictiva. No es popularidad social."
        ),
        "Absolute ranking by total reputation points — rewards sustained forecasting. Not social popularity.": (
            "Ranking absoluto por puntos totales de reputación — premia el volumen sostenido de pronósticos. No es popularidad social."
        ),
        "Top predictors in this category — ranked by total reputation points.": (
            "Mejores pronosticadores en esta categoría — clasificados por puntos totales de reputación."
        ),
        "Sort by rep per forecast, highest first": "Ordenar por rep / pronóstico, mayor primero",
        "Sort by accuracy, highest first": "Ordenar por precisión, mayor primero",
        "Average reputation per scored forecast. Only users with more than %(min)s scored forecasts qualify for ranking.": (
            "Reputación media por pronóstico puntuado. Solo califican quienes tienen más de %(min)s pronósticos puntuados."
        ),
        "More than %(min)s scored forecasts required to qualify for relative ranking.": (
            "Se requieren más de %(min)s pronósticos puntuados para calificar en el ranking relativo."
        ),
    }
)

# Legacy Spanish msgid (migrate to English source string in code).
SPANISH_MSGID_FIXES: dict[str, str] = {
    "Confirma tu email en PredictStamp": "Confirma tu email en PredictStamp",
}
