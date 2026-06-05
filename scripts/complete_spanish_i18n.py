#!/usr/bin/env python3
"""Fill empty Spanish translations and fix known bad entries in django.po."""

from __future__ import annotations

from pathlib import Path

import polib

from achievements_i18n_fixes import ACHIEVEMENTS_I18N_FIXES
from phase1_i18n_fixes import (
    PHASE1_FIXES,
    PHASE1_PLURAL_FIXES,
    PHASE1_UNFUZZY_KEEP_MSGSTR,
    SPANISH_MSGID_FIXES,
)
from phase2_i18n_fixes import (
    PHASE2_BLOCK_PLURAL,
    PHASE2_FIXES,
    PHASE2_PLURAL_FIXES,
)
from phase3_i18n_fixes import PHASE3_FIXES, PHASE3_PLURAL_FIXES
from monetize_i18n_fixes import MONETIZE_I18N_FIXES
from proof_i18n_fixes import (
    PROOF_I18N_BLOCK_FIXES,
    PROOF_I18N_FIXES,
    PROOF_I18N_PLURAL_FIXES,
)

PO_PATH = Path(__file__).resolve().parent.parent / "locale" / "es" / "LC_MESSAGES" / "django.po"

# Phase overrides take precedence over legacy FIXES below.
FIXES: dict[str, str] = {
    **PHASE1_FIXES,
    **PHASE2_FIXES,
    **PHASE3_FIXES,
    **ACHIEVEMENTS_I18N_FIXES,
    **PROOF_I18N_FIXES,
    **MONETIZE_I18N_FIXES,
}
PLURAL_FIXES: dict[str, tuple[str, str]] = {
    **PHASE1_PLURAL_FIXES,
    **PHASE2_PLURAL_FIXES,
    **PHASE3_PLURAL_FIXES,
    **PROOF_I18N_PLURAL_FIXES,
}
BLOCK_FIXES: dict[str, str] = {
    **PROOF_I18N_BLOCK_FIXES,
}

# msgid -> natural Spanish (preserve %(placeholders)s)
FIXES.update({
    "How do you want to appear?": "¿Cómo quieres aparecer?",
    "Display name": "Nombre para mostrar",
    "How others will see you": "Cómo te verán los demás",
    "Request verified identity": "Solicitar identidad verificada",
    "Verified accounts get a badge on their profile and posts. Our team reviews requests — no payment required.": (
        "Las cuentas verificadas reciben una insignia en su perfil y publicaciones. "
        "Nuestro equipo revisa las solicitudes — sin pago."
    ),
    "Bio": "Biografía",
    "Choose a pseudonym — it becomes your public name.": "Elige un seudónimo — será tu nombre público.",
    "Pick an alias so others can recognize you without seeing your username.": (
        "Elige un alias para que otros te reconozcan sin ver tu @usuario."
    ),
    "Your account is already verified.": "Tu cuenta ya está verificada.",
    "Your profile is ready. Welcome to PredictStamp!": "Tu perfil está listo. ¡Bienvenido a PredictStamp!",
    "Profile photo updated.": "Foto de perfil actualizada.",
    "Invalid profile photo.": "Foto de perfil no válida.",
    "Forecast exited. You earned +%(points)s reputation.": "Pronóstico cerrado. Ganaste +%(points)s de reputación.",
    "Forecast exited. You realized %(points)s reputation.": "Pronóstico cerrado. Realizaste %(points)s de reputación.",
    "Forecast exited. You can enter again.": "Pronóstico cerrado. Puedes volver a participar.",
    "What's happening?": "¿Qué está pasando?",
    "Polls can't include images.": "Las encuestas no pueden incluir imágenes.",
    "Add at least two poll choices.": "Añade al menos dos opciones.",
    "Polls can have at most four choices.": "Las encuestas pueden tener como máximo cuatro opciones.",
    "Each poll choice must be %(max)s characters or fewer.": "Cada opción debe tener %(max)s caracteres o menos.",
    "This poll has ended.": "Esta encuesta ha terminado.",
    "Predictive accuracy on resolved forecasts.": "Precisión predictiva en pronósticos resueltos.",
    "left off": "lo dejaste",
    "Public": "Público",
    "Your name and @username are visible — best for building reputation under your real identity.": (
        "Tu nombre y @usuario son visibles — ideal para construir reputación con tu identidad real."
    ),
    "Pseudonym": "Seudónimo",
    "Use a creative alias as your main name. @username stays visible on your profile.": (
        "Usa un alias creativo como nombre principal. @usuario sigue visible en tu perfil."
    ),
    "Anonymous": "Anónimo",
    "Hide @username in public posts. Use an alias so people can still recognize you.": (
        "Oculta @usuario en publicaciones. Usa un alias para que otros te reconozcan."
    ),
    "Verified": "Verificado",
    "@username hidden in posts and comments": "@usuario oculto en publicaciones y comentarios",
    "Public alias": "Alias público",
    "e.g. MarketOracle": "p. ej. OráculoMercados",
    "e.g. QuietPredictor": "p. ej. PredictorSilencioso",
    "Your full name or nickname": "Tu nombre completo o apodo",
    "Optional. Falls back to your username if empty.": "Opcional. Si está vacío, se usa tu @usuario.",
    "Required. The only name others see in posts — your @username stays hidden.": (
        "Obligatorio. El único nombre visible en publicaciones — tu @usuario queda oculto."
    ),
    "Your account is verified.": "Tu cuenta está verificada.",
    "Verification review in progress.": "Verificación en revisión.",
    "Change profile photo": "Cambiar foto de perfil",
    "Verification pending": "Verificación pendiente",
    "follower": "seguidor",
    "following": "siguiendo",
    "Find users…": "Buscar usuarios…",
    "Find users": "Buscar usuarios",
    "View users": "Ver usuarios",
    "Show all": "Ver todos",
    "User search results": "Resultados de búsqueda de usuarios",
    'See all results for "%(query)s"': 'Ver todos los resultados de «%(query)s»',
    "Update your email, bio, and how you appear publicly.": "Actualiza tu email, biografía y cómo apareces públicamente.",
    "Your name": "Tu nombre",
    "Basic info": "Información básica",
    "Profile & identity": "Perfil e identidad",
    "Choose how you": "Elige cómo",
    "appear": "aparecer",
    "Step 2 of 2 — pick a public identity, preview how others will see you, and optionally request verification. You can change this anytime in settings.": (
        "Paso 2 de 2 — elige tu identidad pública, previsualiza cómo te verán otros y "
        "opcionalmente solicita verificación. Puedes cambiarlo en ajustes."
    ),
    "Finish setup": "Finalizar configuración",
    "Create your account in seconds. Next, choose how you want to appear publicly.": (
        "Crea tu cuenta en segundos. Después, elige cómo quieres aparecer públicamente."
    ),
    "Step 1 of 2 — credentials only. No payment required.": "Paso 1 de 2 — solo credenciales. Sin pago.",
    "Your @handle on PredictStamp.": "Tu @usuario en PredictStamp.",
    "Password requirements": "Requisitos de contraseña",
    "Continue": "Continuar",
    "Search by name, username, or bio to discover predictors and voices on the platform.": (
        "Busca por nombre, usuario o biografía para descubrir predictores en la plataforma."
    ),
    "Enter at least 2 characters.": "Introduce al menos 2 caracteres.",
    "Enter at least 2 characters to search.": "Introduce al menos 2 caracteres para buscar.",
    "Start typing to find people on PredictStamp.": "Empieza a escribir para encontrar personas en PredictStamp.",
    "The social layer for prediction markets": "La capa social para mercados de predicción",
    "Public predictions and earned reputation for real-world markets.": (
        "Predicciones públicas y reputación ganada en mercados del mundo real."
    ),
    "Public predictions and earned reputation for real-world markets. No betting — just credibility.": (
        "Predicciones públicas y reputación ganada en mercados del mundo real. "
        "Sin apuestas — solo credibilidad."
    ),
    "PredictStamp — The social layer for prediction markets. Popularity ≠ Reputation.": (
        "PredictStamp — La capa social para mercados de predicción. Popularidad ≠ Reputación."
    ),
    "Company": "Empresa",
    "Legal information": "Información legal",
    "Terms & Conditions": "Términos y condiciones",
    "Legal": "Legal",
    "Terms": "Términos",
    "PredictStamp is operated by TAO FACTORY LLC, a Delaware limited liability company. For operational, legal, or partnership inquiries, contact us at <a href=\"mailto:ops@predictstamp.com\" class=\"font-medium text-brand-600 hover:underline dark:text-brand-400\">ops@predictstamp.com</a>.": (
        "PredictStamp es operado por TAO FACTORY LLC, una sociedad de responsabilidad "
        "limitada de Delaware. Para consultas operativas, legales o de alianzas, "
        "contáctanos en <a href=\"mailto:ops@predictstamp.com\" class=\"font-medium "
        "text-brand-600 hover:underline dark:text-brand-400\">ops@predictstamp.com</a>."
    ),
    "The internet has no shortage of opinions. What it lacks is memory. PredictStamp turns predictions into a reputation graph and insight into an asset.": (
        "Internet no le falta opinión. Le falta memoria. PredictStamp convierte "
        "pronósticos en un grafo de reputación y el criterio en un activo."
    ),
    "<strong class=\"text-slate-800 dark:text-white\">PredictStamp</strong> is built around events and outcomes — follow markets, publish theses, debate probabilities, challenge friends, and build a public history of judgment.": (
        "<strong class=\"text-slate-800 dark:text-white\">PredictStamp</strong> se basa "
        "en eventos y resultados — sigue mercados, publica tesis, debate probabilidades, "
        "desafía amigos y construye un historial público de criterio."
    ),
    "Credibility earned through a public history of judgment — not luck, not capital, not hype. PredictStamp secures social intelligence with track record.": (
        "Credibilidad ganada con un historial público de criterio — no suerte, "
        "ni capital, ni hype. PredictStamp respalda la inteligencia social con historial."
    ),
    "Name your challenge and pick opponents.": "Pon nombre al desafío y elige oponentes.",
    "open forecast": "pronóstico abierto",
    "No open events match “%(search_query)s” in this category. Try another keyword.": (
        "Ningún evento abierto coincide con «%(search_query)s» en esta categoría. Prueba otra palabra."
    ),
    "Exited forecast, +%(points)s reputation realized": "Pronóstico cerrado, +%(points)s de reputación realizada",
    "Exited forecast, %(points)s reputation realized": "Pronóstico cerrado, %(points)s de reputación realizada",
    "open match": "partido abierto",
    "Home": "Inicio",
    "More": "Más",
    "Copy link": "Copiar enlace",
    "This can't be undone and will remove your comment from the thread.": (
        "Esta acción no se puede deshacer y eliminará tu comentario del hilo."
    ),
    "Delete": "Eliminar",
    "Choice": "Opción",
    "Poll choice": "Opción de encuesta",
    "Add a choice": "Añadir opción",
    "Poll length": "Duración de la encuesta",
    "3 days": "3 días",
    "7 days": "7 días",
    "Poll": "Encuesta",
    "Welcome to Forum!": "¡Bienvenido al Foro!",
    "Post your reply": "Publica tu respuesta",
    "to reply.": "para responder.",
    "Delete post": "Eliminar publicación",
    "Delete post?": "¿Eliminar publicación?",
    "This can't be undone and will remove your post from the feed.": (
        "Esta acción no se puede deshacer y eliminará tu publicación del feed."
    ),
    "People": "Personas",
    "What's happening": "Qué está pasando",
    "Who to follow": "A quién seguir",
    "Share ideas, debate markets, and connect with fellow predictors.": (
        "Comparte ideas, debate mercados y conecta con otros predictores."
    ),
    "Share your take on markets, events, or the community…": (
        "Comparte tu opinión sobre mercados, eventos o la comunidad…"
    ),
    "Discover": "Descubrir",
    "Suggested voices": "Voces sugeridas",
    "Live prediction events": "Eventos de predicción en vivo",
    "Browse imported Polymarket questions": "Explora preguntas importadas de Polymarket",
    "Formal forecasts with reputation scoring": "Pronósticos formales con puntuación de reputación",
    "Leaderboard by predictive quality": "Ranking por calidad predictiva",
    "Follow proven forecasters": "Sigue a predictores con historial",
    "Discussion": "Debate",
    "Most engaged community members": "Miembros más activos de la comunidad",
    "Back": "Volver",
    "Navigation menu": "Menú de navegación",
    "Menu": "Menú",
    "Signature valid": "Firma válida",
    "Signature mismatch": "Firma no coincide",
    "This record was generated automatically in the background. It proves that PredictStamp recorded this forecast or reputation event without requiring any extra action from the user.": (
        "Este registro se generó automáticamente en segundo plano. Demuestra que PredictStamp "
        "registró este pronóstico o evento de reputación sin acción extra del usuario."
    ),
    "Pick:": "Elección:",
    "UID": "UID",
    "Schema UID": "UID del esquema",
    "Offchain timestamp": "Marca de tiempo offchain",
    "Event timestamp": "Marca de tiempo del evento",
    "Technical payload": "Payload técnico",
    "This forecast has a PredictStamp verification record": "Este pronóstico tiene un registro de verificación PredictStamp",
    "No open events match “%(search_query)s”. Try another keyword or browse by category below.": (
        "Ningún evento abierto coincide con «%(search_query)s». Prueba otra palabra o explora por categoría."
    ),
    "Exited": "Salido",
    "Clear": "Limpiar",
    "Current market probability for your side: %(prob)s%%.": "Probabilidad de mercado actual para tu lado: %(prob)s%%.",
    "Exiting now would realize +%(points)s reputation.": "Salir ahora realizaría +%(points)s de reputación.",
    "Exiting now would realize %(points)s reputation.": "Salir ahora realizaría %(points)s de reputación.",
    "Your active forecast: %(direction)s %(outcome)s. Exit it to enter again later.": (
        "Tu pronóstico activo: %(direction)s %(outcome)s. Ciérralo para volver a participar."
    ),
    "Pick Yes or No on any outcome, then explain your pick below. Reputation-only — no money or trading.": (
        "Elige Sí o No en cualquier resultado y explica tu elección abajo. Solo reputación — sin dinero ni trading."
    ),
    "%(prob)s%% market probability": "%(prob)s%% probabilidad de mercado",
    "Explain your Yes on %(outcome_label)s": "Explica tu Sí en %(outcome_label)s",
    "Explain your No on %(outcome_label)s": "Explica tu No en %(outcome_label)s",
    "%(direction)s %(outcome)s": "%(direction)s %(outcome)s",
    "Cannot predict on a closed or resolved market.": "No puedes pronosticar en un mercado cerrado o resuelto.",
    "You already have a forecast on this market.": "Ya tienes un pronóstico en este mercado.",
    "This prediction cannot be edited.": "Este pronóstico no se puede editar.",
    "Only active forecasts can be exited.": "Solo los pronósticos activos se pueden cerrar.",
    "Cannot exit a forecast after the market has closed.": "No puedes cerrar un pronóstico después de que el mercado cierre.",
    "Cannot edit another user's prediction.": "No puedes editar el pronóstico de otro usuario.",
    "Cannot exit another user's prediction.": "No puedes cerrar el pronóstico de otro usuario.",
    "Users cannot follow themselves.": "No puedes seguirte a ti mismo.",
    "The challenge creator cannot be invited.": "El creador del desafío no puede ser invitado.",
    "Invalid comment": "Comentario no válido",
    "Poll not found": "Encuesta no encontrada",
    "Invalid bookmark target": "Destino de marcador no válido",
    "Missing username": "Falta el nombre de usuario",
    "Link copied!": "¡Enlace copiado!",
    "Copy this link:": "Copia este enlace:",
    "Forecast on PredictStamp": "Pronóstico en PredictStamp",
    "%(name)s on %(title)s": "%(name)s sobre %(title)s",
    "%(time)s ago": "hace %(time)s",
    "Challenge with %(count)s event": "Desafío con %(count)s evento",
    "Challenge with %(count)s events": "Desafío con %(count)s eventos",
    "Resolved": "Resuelto",
    "Exited": "Salido",
    "Void": "Anulado",
    "Invited": "Invitado",
    "Accepted": "Aceptado",
    "Declined": "Rechazado",
    "When someone follows you": "Cuando alguien te sigue",
    "Open": "Abierto",
    "Closed": "Cerrado",
    "1 day left": "Queda 1 día",
    "Rep": "Rep",
    "Pop": "Pop",
    "Global": "Global",
    "Macro": "Macro",
    "Rankings": "Rankings",
    "Social": "Social",
    "incorrect": "incorrecto",
    "Market": "Mercado",
    # --- Challenges (detail, leaderboard, market cards) ---
    "Accept challenge": "Aceptar desafío",
    "You've been challenged! Accept to compete.": "¡Te han desafiado! Acepta para competir.",
    "Highest total reputation score across all challenge events.": (
        "Mayor puntuación total de reputación en todos los eventos del desafío."
    ),
    "Existing open forecasts on these events count immediately — including forecasts placed before the challenge started.": (
        "Los pronósticos abiertos en estos eventos cuentan de inmediato — incluidos los "
        "publicados antes de que empezara el desafío."
    ),
    "Live ranking": "Clasificación en vivo",
    "Leaderboard": "Tabla de posiciones",
    "Realized points come from resolved or closed forecasts. Unrealized points estimate P&L on open challenge events at current market odds — including forecasts you placed before joining the challenge.": (
        "Los puntos realizados provienen de pronósticos resueltos o cerrados. Los no realizados "
        "estiman el P&L en eventos abiertos del desafío según las cuotas actuales — incluidos "
        "los pronósticos que hiciste antes de unirte."
    ),
    "Realized": "Realizado",
    "Unrealized": "No realizado",
    "Combined": "Combinado",
    "Total": "Total",
    "Scores update once all opponents accept and the challenge goes live.": (
        "Las puntuaciones se actualizan cuando todos los oponentes acepten y el desafío comience."
    ),
    "Pending acceptance": "Pendiente de aceptación",
    "No participants yet.": "Aún no hay participantes.",
    "Your forecast": "Tu pronóstico",
    "Placed before this challenge — already in play": (
        "Publicado antes de este desafío — ya cuenta"
    ),
    "Unrealized:": "No realizado:",
    "Counts for challenge + global rep": "Cuenta para el desafío y la rep global",
    "No forecast yet — place one to score": "Sin pronóstico — publica uno para sumar puntos",
    "Challenge invitation": "Invitación al desafío",
    "Pending invitations": "Invitaciones pendientes",
    "No challenges yet.": "Aún no hay desafíos.",
    "Create a": "Crea un",
    "challenge": "desafío",
    "Choose who you want to challenge. You can invite any user on the platform — no mutual follow required.": (
        "Elige a quién quieres desafiar. Puedes invitar a cualquier usuario de la plataforma — no hace falta seguimiento mutuo."
    ),
    "Pick up to %(max)s open events for your challenge.": (
        "Elige hasta %(max)s eventos abiertos para tu desafío."
    ),
    "Challenge details": "Detalles del desafío",
    "Challenge creation steps": "Pasos para crear el desafío",
    "Users": "Usuarios",
    "Events": "Eventos",
    "Select at least one user to challenge.": "Selecciona al menos un usuario para desafiar.",
    "There are no other users on the platform yet. You need at least one opponent to create a challenge.": (
        "Aún no hay otros usuarios en la plataforma. Necesitas al menos un oponente para crear un desafío."
    ),
    "Or pick individual users below.": "O elige usuarios individuales abajo.",
    "No other users on the platform yet.": "Aún no hay otros usuarios en la plataforma.",
    "Opponents": "Oponentes",
    "Select at least one user to continue.": "Selecciona al menos un usuario para continuar.",
    "user(s) selected": "usuario(s) seleccionado(s)",
    "New challenge": "Nuevo desafío",
    "Active": "Activo",
    "Completed": "Completado",
    "Cancelled": "Cancelado",
    "Invited": "Invitado",
    "Accepted": "Aceptado",
    "Declined": "Rechazado",
    "Compete with anyone on the platform on up to 10 events. Highest reputation score wins.": (
        "Compite con cualquier usuario de la plataforma en hasta 10 eventos. Gana quien tenga más reputación."
    ),
    "You cannot challenge @%(username)s.": "No puedes desafiar a @%(username)s.",
    "You cannot add @%(username)s to a group.": "No puedes añadir a @%(username)s a un grupo.",
})

PLURAL_FIXES.update({
    "%(days)s day left": ("Queda %(days)s día", "Quedan %(days)s días"),
    "%(days)s days left": ("Queda %(days)s día", "Quedan %(days)s días"),
    "Ended %(past)s day ago": ("Terminó hace %(past)s día", "Terminó hace %(past)s días"),
    "Ended %(past)s days ago": ("Terminó hace %(past)s día", "Terminó hace %(past)s días"),
    "\n          You have %(counter)s new alert\n          ": (
        "\n          Tienes %(counter)s alerta nueva\n          ",
        "\n          Tienes %(counter)s alertas nuevas\n          ",
    ),
    "\n          You have %(counter)s new alerts\n          ": (
        "\n          Tienes %(counter)s alerta nueva\n          ",
        "\n          Tienes %(counter)s alertas nuevas\n          ",
    ),
    "follower": ("seguidor", "seguidores"),
    "followers": ("seguidor", "seguidores"),
    "following": ("siguiendo", "siguiendo"),
    "%(counter)s event": ("%(counter)s evento", "%(counter)s eventos"),
    "%(counter)s events": ("%(counter)s evento", "%(counter)s eventos"),
    "%(counter)s participants": ("%(counter)s participante", "%(counter)s participantes"),
    "+%(counter)s more outcome": ("+%(counter)s resultado más", "+%(counter)s resultados más"),
    "+%(counter)s more outcomes": ("+%(counter)s resultado más", "+%(counter)s resultados más"),
    "+ %(counter)s reply": ("+ %(counter)s respuesta", "+ %(counter)s respuestas"),
    "+ %(counter)s replies": ("+ %(counter)s respuesta", "+ %(counter)s respuestas"),
    "open forecast": ("pronóstico abierto", "pronósticos abiertos"),
    "open forecasts": ("pronóstico abierto", "pronósticos abiertos"),
    "%(counter)s forecast": ("%(counter)s pronóstico", "%(counter)s pronósticos"),
    "%(counter)s result": ("%(counter)s resultado", "%(counter)s resultados"),
    "%(counter)s forecasts": ("%(counter)s pronóstico", "%(counter)s pronósticos"),
    "open match": ("partido abierto", "partidos abiertos"),
    "open matches": ("partido abierto", "partidos abiertos"),
    "%(counter)s vote · Final results": (
        "%(counter)s voto · Resultados finales",
        "%(counter)s votos · Resultados finales",
    ),
    "%(counter)s votes · Final results": (
        "%(counter)s voto · Resultados finales",
        "%(counter)s votos · Resultados finales",
    ),
    "%(counter)s vote": ("%(counter)s voto", "%(counter)s votos"),
    "%(counter)s votes": ("%(counter)s voto", "%(counter)s votos"),
    "\n            %(counter)s open event matches “%(search_query)s”\n          ": (
        "\n            %(counter)s evento abierto coincide con «%(search_query)s»\n          ",
        "\n            %(counter)s eventos abiertos coinciden con «%(search_query)s»\n          ",
    ),
    "\n            %(counter)s open events match “%(search_query)s”\n          ": (
        "\n            %(counter)s evento abierto coincide con «%(search_query)s»\n          ",
        "\n            %(counter)s eventos abiertos coinciden con «%(search_query)s»\n          ",
    ),
})


def apply_fixes() -> tuple[int, int, int]:
    po = polib.pofile(str(PO_PATH))
    updated = 0
    unfuzzied = 0
    remaining_empty = 0

    for entry in po:
        if entry.msgid in SPANISH_MSGID_FIXES:
            entry.msgstr = SPANISH_MSGID_FIXES[entry.msgid]
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            updated += 1
            continue

        if entry.msgid in PHASE1_UNFUZZY_KEEP_MSGSTR and entry.msgstr.strip():
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
                unfuzzied += 1
            continue

        if (
            "fuzzy" in entry.flags
            and entry.msgid not in FIXES
            and not (entry.msgid_plural and entry.msgid in PLURAL_FIXES)
            and entry.msgstr.strip()
        ):
            # Leftover fuzzy with a non-empty msgstr: activate it rather than fall back to English.
            entry.flags.remove("fuzzy")
            unfuzzied += 1

    for entry in po:
        if entry.msgid == "Challenge with %(count)s event" and entry.msgid_plural:
            entry.msgstr_plural = {
                0: "Desafío con %(count)s evento",
                1: "Desafío con %(count)s eventos",
            }
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            updated += 1
            continue

        if entry.msgid in FIXES:
            entry.msgstr = FIXES[entry.msgid]
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            updated += 1
            continue

        if entry.msgid in BLOCK_FIXES:
            entry.msgstr = BLOCK_FIXES[entry.msgid]
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            updated += 1
            continue

        if entry.msgid_plural and entry.msgid in PLURAL_FIXES:
            singular, plural = PLURAL_FIXES[entry.msgid]
            entry.msgstr_plural = {0: singular, 1: plural}
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            updated += 1
            continue

        if entry.msgid_plural and entry.msgid in PHASE2_BLOCK_PLURAL:
            singular, plural = PHASE2_BLOCK_PLURAL[entry.msgid]
            entry.msgstr_plural = {0: singular, 1: plural}
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            updated += 1
            continue

        if entry.msgid and not entry.msgstr.strip() and not entry.msgid_plural:
            remaining_empty += 1

    po.save(str(PO_PATH))
    return updated, unfuzzied, remaining_empty


def main() -> None:
    updated, unfuzzied, remaining = apply_fixes()
    print(
        f"Updated {updated} translation(s), unfuzzied {unfuzzied}. "
        f"Remaining empty singular entries: {remaining}."
    )


if __name__ == "__main__":
    main()
