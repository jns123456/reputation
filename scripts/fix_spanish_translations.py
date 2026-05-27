#!/usr/bin/env python3
"""Fix known bad auto-translations in locale/es/LC_MESSAGES/django.po."""

from pathlib import Path

import polib

PO_PATH = Path(__file__).resolve().parent.parent / "locale" / "es" / "LC_MESSAGES" / "django.po"

# msgid -> natural Spanish (preserve %(placeholders)s)
FIXES = {
    # Hero / brand
    "Proof of Reputation": "Prueba de reputación",
    "The social layer for": "La capa social para",
    "prediction markets": "mercados de predicción",
    "money won": "dinero ganado",
    "We ask a different question:": "Hacemos una pregunta distinta:",
    "What if the most valuable asset was not capital, but": (
        "¿Y si el activo más valioso no fuera el capital, sino"
    ),
    "credibility": "la credibilidad",
    "Start building reputation": "Empieza a construir tu reputación",
    "Explore the thesis": "Conoce la tesis",
    "Scroll down": "Desplázate hacia abajo",
    # About — thesis & proof
    "The shift": "El cambio",
    "From capital to credibility": "Del capital a la credibilidad",
    "Capital": "Capital",
    "Credibility": "Credibilidad",
    "Judgment": "Criterio",
    "Judgment is the entry fee": "El criterio es la entrada",
    "Secures with track record": "Respaldado por historial",
    "Tap to explore": "Toca para explorar",
    "Resolution": "Resolución",
    "The platform": "La plataforma",
    "Demonstrated judgment": "Criterio demostrado",
    "Reputation vs Popularity": "Reputación vs. Popularidad",
    "The platform records both popularity and reputation for every user. They stay independent: popularity measures attention; reputation measures demonstrated judgment.": (
        "La plataforma registra popularidad y reputación para cada usuario. Siguen "
        "siendo independientes: la popularidad mide la atención; la reputación, el "
        "criterio demostrado."
    ),
    "Earned when forecasts resolve. Harder contrarian calls score higher. Upvotes never touch this score.": (
        "Se gana cuando los pronósticos se resuelven. Las predicciones a contracorriente "
        "más difíciles suman más. Los votos a favor no afectan esta puntuación."
    ),
    "Reputation leaderboard": "Ranking de reputación",
    "Popularity leaderboard": "Ranking de popularidad",
    "Leaderboards without betting": "Rankings sin apuestas",
    "Leaderboards": "Rankings",
    "Rankings": "Rankings",
    "How do leaderboards work?": "¿Cómo funcionan los rankings?",
    "We maintain two separate rankings:": "Mantenemos dos rankings separados:",
    "Leaderboard": "Ranking",
    "Popularity Leaderboard": "Ranking de popularidad",
    "Reputation Leaderboard": "Ranking de reputación",
    "Full leaderboard": "Ranking completo",
    "No rankings yet.": "Aún no hay rankings.",
    "Browse challenges": "Ver desafíos",
    "Select events": "Seleccionar eventos",
    "Remove event": "Quitar evento",
    "Search events…": "Buscar eventos…",
    "Send challenge": "Enviar desafío",
    "Optional challenge name": "Nombre del desafío (opcional)",
    "Future": "Futuro",
    "Where credibility": "Donde la credibilidad",
    "compounds": "se acumula",
    "Browse markets": "Explorar mercados",
    "Read the FAQ": "Ver preguntas frecuentes",
    # About nav & domains
    "Intro": "Introducción",
    "Sports": "Deportes",
    "Energy": "Energía",
    "Tech": "Tecnología",
    "Why do you believe this?": "¿Por qué crees esto?",
    "How confident are you?": "¿Qué tan seguro estás?",
    "Did you change your mind?": "¿Cambiaste de opinión?",
    "Were you early or late?": "¿Llegaste temprano o tarde?",
    "Did your reasoning age well?": "¿Tu razonamiento envejeció bien?",
    "Are you right in this domain?": "¿Acertás en este dominio?",
    # Leaderboards / dashboard
    "Predictions": "Predicciones",
    "Top predictors": "Mejores predictores",
    "New challenge": "Nuevo desafío",
    "Challenges": "Desafíos",
    # Awkward machine translations
    "Log in to dislike": "Inicia sesión para dar dislike",
    "Log in to like": "Inicia sesión para dar like",
    "Inicia sesión para que no te guste": "Inicia sesión para dar dislike",
    "Exactitud": "Precisión",
    "Topic expertise": "Experiencia por tema",
    "Early conviction": "Convicción temprana",
    "Bankroll size": "Tamaño del bankroll",
    "Rank by ": "Ranking por ",
    "Become known for %(domain)s — a living map of who has good judgment.": (
        "Destácate en %(domain)s — un mapa vivo de quién tiene buen criterio."
    ),
    "Every forecast captures context — not just yes or no, but why, when, and how confident.": (
        "Cada pronóstico captura contexto: no solo sí o no, sino por qué, cuándo y con qué confianza."
    ),
    "Rewards capital, not necessarily insight": "Premia capital, no necesariamente criterio",
    "Excludes anyone without funds to wager": "Excluye a quien no tiene fondos para apostar",
    "One lucky bet can distort the ranking": "Una apuesta afortunada puede distorsionar el ranking",
    "Accuracy, calibration, early conviction": "Precisión, calibración, convicción temprana",
    "Performance by topic and over time": "Rendimiento por tema y en el tiempo",
    "Open to anyone — judgment is the entry fee": "Abierto a todos — el criterio es la entrada",
    "Profit leaderboard — rewards bankrolls, not necessarily insight.": (
        "Ranking de ganancias: premia bankrolls, no necesariamente criterio."
    ),
    "Judgment leaderboard — earned through resolved forecasts.": (
        "Ranking de criterio: se gana con pronósticos resueltos."
    ),
    "Fantasy sports × Reddit × prediction markets — based on reputation, not betting.": (
        "Fantasy deportes × Reddit × mercados de predicción — por reputación, no por apuestas."
    ),
    "The internet has no shortage of opinions. What it lacks is memory. Proof of "
    "Reputation turns predictions into a reputation graph and insight into an asset.": (
        "Internet no le falta opinión. Le falta memoria. Proof of Reputation convierte "
        "pronósticos en un grafo de reputación y el criterio en un activo."
    ),
    "The most valuable signal is not who speaks the loudest — it is who has been "
    "right over time.": (
        "La señal más valiosa no es quién habla más fuerte, sino quién ha acertado "
        "en el tiempo."
    ),
}


def main() -> None:
    po = polib.pofile(str(PO_PATH))
    updated = 0
    for entry in po:
        if not entry.msgid:
            continue
        fix = FIXES.get(entry.msgid)
        if fix is None and entry.msgid_plural:
            fix = FIXES.get(entry.msgid_plural)
        if fix is None:
            continue
        if entry.msgid_plural:
            # Keep plural forms; only fix if empty or clearly wrong
            if not entry.msgstr_plural.get(0, "").strip():
                entry.msgstr_plural[0] = fix
                updated += 1
        elif entry.msgstr != fix:
            entry.msgstr = fix
            updated += 1
        if "fuzzy" in entry.flags:
            entry.flags.remove("fuzzy")

    po.save(str(PO_PATH))
    print(f"Updated {updated} entries in {PO_PATH}")


if __name__ == "__main__":
    main()
