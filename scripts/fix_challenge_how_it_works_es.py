#!/usr/bin/env python3
"""Fix Spanish translations for the challenges how-it-works page."""

from pathlib import Path

import polib

PO_PATH = Path(__file__).resolve().parent.parent / "locale" / "es" / "LC_MESSAGES" / "django.po"

TRANSLATIONS = {
    "How challenges work": "Cómo funcionan los desafíos",
    "How it works": "Cómo funciona",
    "How": "Cómo",
    "How challenges": "Cómo funcionan los",
    "work": "desafíos",
    "challenges work": "funcionan los desafíos",
    "Head-to-head reputation duels with mutual followers on real-world events. No extra bets — your forecasts are the score.": (
        "Duelos de reputación cara a cara con seguidores mutuos en eventos del mundo real. "
        "Sin apuestas extra — tus pronósticos son la puntuación."
    ),
    "Mutual followers": "Seguidores mutuos",
    "You can only challenge people who follow you back.": (
        "Solo puedes desafiar a personas que te siguen de vuelta."
    ),
    "Up to %(max)s events": "Hasta %(max)s eventos",
    "Pick open markets everyone will compete on. The duel ends when all of them resolve.": (
        "Elige mercados abiertos en los que todos competirán. El duelo termina cuando se resuelvan todos."
    ),
    "Highest reputation wins": "Gana quien sume más reputación",
    "Only predictive reputation counts — likes and votes never affect the score.": (
        "Solo cuenta la reputación predictiva — los likes y votos nunca afectan la puntuación."
    ),
    "From invitation to winner": "De la invitación al ganador",
    "Create or get invited": "Crea o recibe una invitación",
    "Someone picks the events and invites opponents. You can accept or decline.": (
        "Alguien elige los eventos e invita oponentes. Puedes aceptar o rechazar."
    ),
    "Challenge goes live": "El desafío se activa",
    "Once everyone has responded, the challenge activates and the clock starts. Group challenges can start when the first invited member accepts.": (
        "Cuando todos han respondido, el desafío se activa y empieza el cronómetro. "
        "Los desafíos de grupo pueden empezar cuando el primer invitado acepta."
    ),
    "Forecast on the events": "Pronostica en los eventos",
    "Publish formal forecasts on the challenge markets — or keep an existing one. See the next section.": (
        "Publica pronósticos formales en los mercados del desafío — o conserva uno que ya tengas. "
        "Mira la siguiente sección."
    ),
    "Markets resolve": "Los mercados se resuelven",
    "When every event in the challenge resolves, we tally final reputation points. The highest total wins; a tie means no single winner.": (
        "Cuando se resuelve cada evento del desafío, sumamos los puntos finales de reputación. "
        "Gana quien tenga más total; un empate significa que no hay ganador único."
    ),
    "Already forecast on a challenge event?": "¿Ya pronosticaste en un evento del desafío?",
    "You do not need to place a new forecast just because an event was added to a challenge.": (
        "No necesitas hacer un pronóstico nuevo solo porque un evento se añadió a un desafío."
    ),
    "Your existing open forecast counts automatically once the challenge is live.": (
        "Tu pronóstico abierto existente cuenta automáticamente cuando el desafío está activo."
    ),
    "If you already have a <strong class=\"text-slate-800 dark:text-slate-200\">pending forecast</strong> on one of the challenge events, it is included in your challenge score immediately — no duplicate pick required.": (
        "Si ya tienes un <strong class=\"text-slate-800 dark:text-slate-200\">pronóstico pendiente</strong> "
        "en uno de los eventos del desafío, se incluye en tu puntuación de inmediato — no hace falta volver a elegir."
    ),
    "While the market is still open, we show <strong class=\"text-slate-800 dark:text-slate-200\">unrealized</strong> reputation (mark-to-market P&amp;L against current odds). When the market resolves or you exit early, those points become <strong class=\"text-slate-800 dark:text-slate-200\">realized</strong>.": (
        "Mientras el mercado sigue abierto, mostramos reputación <strong class=\"text-slate-800 dark:text-slate-200\">no realizada</strong> "
        "(P&amp;L mark-to-market contra las cuotas actuales). Cuando el mercado se resuelve o sales temprano, "
        "esos puntos pasan a ser <strong class=\"text-slate-800 dark:text-slate-200\">realizados</strong>."
    ),
    "<strong class=\"font-medium\">After you accept</strong>, only reputation earned from that moment onward counts toward realized points. Resolutions or early exits that happened before you joined the challenge do not count — but an open forecast you placed earlier still contributes live unrealized points.": (
        "<strong class=\"font-medium\">Después de aceptar</strong>, solo cuenta la reputación ganada desde ese momento "
        "hacia los puntos realizados. Resoluciones o salidas tempranas anteriores a unirte al desafío no cuentan — "
        "pero un pronóstico abierto que hayas hecho antes sigue aportando puntos no realizados en vivo."
    ),
    "How points are calculated": "Cómo se calculan los puntos",
    "Challenges use the same <span class=\"badge-rep\">Reputation</span> rules as the rest of PredictStamp — based on market odds when you forecast, not on votes or popularity.": (
        "Los desafíos usan las mismas reglas de <span class=\"badge-rep\">Reputación</span> que el resto de PredictStamp — "
        "basadas en las cuotas del mercado cuando pronosticas, no en votos ni popularidad."
    ),
    "Points locked in when a market resolves or you exit a forecast early.": (
        "Puntos fijados cuando un mercado se resuelve o sales temprano de un pronóstico."
    ),
    "Live estimate on open markets — updates as odds move.": (
        "Estimación en vivo en mercados abiertos — se actualiza cuando cambian las cuotas."
    ),
    "Your challenge total is <strong class=\"text-slate-800 dark:text-slate-200\">realized + unrealized</strong> across all events in the duel. The leaderboard inside each challenge shows both columns.": (
        "Tu total del desafío es <strong class=\"text-slate-800 dark:text-slate-200\">realizado + no realizado</strong> "
        "en todos los eventos del duelo. La clasificación dentro de cada desafío muestra ambas columnas."
    ),
    'For more examples and edge cases, see the <a href="%(faq_url)s" class="font-medium text-brand-600 hover:underline dark:text-brand-400">FAQ</a>.': (
        'Para más ejemplos y casos límite, consulta las <a href="%(faq_url)s" '
        'class="font-medium text-brand-600 hover:underline dark:text-brand-400">preguntas frecuentes</a>.'
    ),
    "Do I need to bet money or place a special challenge forecast?": (
        "¿Necesito apostar dinero o hacer un pronóstico especial para el desafío?"
    ),
    "<strong class=\"text-slate-800 dark:text-slate-200\">No.</strong> PredictStamp has no wallets or real-money betting. A challenge reuses your normal formal forecasts on the selected events — there is no separate wager.": (
        "<strong class=\"text-slate-800 dark:text-slate-200\">No.</strong> PredictStamp no tiene billeteras ni apuestas con dinero real. "
        "Un desafío reutiliza tus pronósticos formales normales en los eventos seleccionados — no hay una apuesta aparte."
    ),
    "Can I join multiple challenges on the same event?": (
        "¿Puedo unirme a varios desafíos en el mismo evento?"
    ),
    "Yes. One forecast on a market can count toward every active challenge that includes that event.": (
        "Sí. Un pronóstico en un mercado puede contar para cada desafío activo que incluya ese evento."
    ),
    "What are challenge groups?": "¿Qué son los grupos de desafío?",
    "Saved lists of mutual followers for quick invitations. Group challenges can start as soon as the first invited member accepts, instead of waiting for every response.": (
        "Listas guardadas de seguidores mutuos para invitar rápido. Los desafíos de grupo pueden empezar "
        "en cuanto el primer miembro invitado acepta, sin esperar a que todos respondan."
    ),
    "Do upvotes affect my challenge score?": "¿Los votos positivos afectan mi puntuación en el desafío?",
    "No. <span class=\"badge-pop\">Popularity</span> from votes is completely separate. Only reputation from forecasts determines the winner.": (
        "No. La <span class=\"badge-pop\">Popularidad</span> de los votos es completamente independiente. "
        "Solo la reputación de los pronósticos determina al ganador."
    ),
    "Ready to compete?": "¿Listo para competir?",
    "Challenge a mutual follower or respond to a pending invitation.": (
        "Desafía a un seguidor mutuo o responde a una invitación pendiente."
    ),
    "My challenges": "Mis desafíos",
    "Manage challenge groups": "Administrar grupos de desafío",
    "− market %": "− % del mercado",
    "− market %%": "− %% del mercado",
}


def main():
    po = polib.pofile(str(PO_PATH))
    applied = 0
    for entry in po:
        if entry.msgid in TRANSLATIONS:
            entry.msgstr = TRANSLATIONS[entry.msgid]
            if "fuzzy" in entry.flags:
                entry.flags.remove("fuzzy")
            applied += 1
    po.save(str(PO_PATH))
    print(f"Updated {applied} challenge how-it-works translations")


if __name__ == "__main__":
    main()
