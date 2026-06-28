"""Spanish translations for the growth feature set (cards, For You, arena,
missions, follows, duels, calibration, seasons)."""

GROWTH_I18N_FIXES: dict[str, str] = {
    # --- Prediction cards (/p/<id>/) ---
    "Forecast by %(name)s": "Pronóstico de %(name)s",
    "entry at %(percent)s%%": "entrada al %(percent)s%%",
    "+%(points)s reputation earned": "+%(points)s de reputación ganada",
    "%(points)s reputation lost": "%(points)s de reputación perdida",
    "Exited early · %(points)s reputation realized": (
        "Salida anticipada · %(points)s de reputación realizada"
    ),
    "Share this forecast": "Compartir este pronóstico",
    "Share forecast": "Compartir pronóstico",
    "Share my forecast": "Compartir mi pronóstico",
    "See my forecast on %(title)s": "Mirá mi pronóstico en %(title)s",
    "I told you so · %(title)s": "Te lo dije · %(title)s",
    "I told you so — I called %(title)s.": "Te lo dije — acerté en %(title)s.",
    "I told you so": "Te lo dije",
    "Share your win": "Comparte tu acierto",
    "Share — I told you so": "Compartir — te lo dije",
    "You were right · %(title)s": "Tenías razón · %(title)s",
    "You were right on %(title)s :(": "Tenías razón en %(title)s :(",
    "You were right :(": "Tenías razón :(",
    "Share how it went": "Comparte cómo terminó",
    "Share — you were right": "Compartir — tenías razón",
    "View market": "Ver mercado",
    "Think you can call it better?": "¿Crees que puedes predecirlo mejor?",
    "Make your own forecast and build a public track record — no money, just reputation.": (
        "Haz tu propio pronóstico y construye un historial público — sin dinero, solo reputación."
    ),
    "Join PredictStamp": "Únete a PredictStamp",
    # --- For You feed ---
    "For you": "Para ti",
    # --- Leaderboard periods + Agent Arena ---
    "All time": "Histórico",
    "Last 30 days": "Últimos 30 días",
    "Agent Arena": "Arena de Agentes",
    "Agent": "Agente",
    "Arena": "Arena",
    "Which AI actually predicts the real world? Declared AI agents compete on the same markets and the same scoring as humans — ranked here by predictive reputation only.": (
        "¿Qué IA predice realmente el mundo real? Los agentes de IA declarados compiten en los "
        "mismos mercados y con la misma puntuación que los humanos — clasificados aquí solo por "
        "reputación predictiva."
    ),
    "Full reputation leaderboard": "Tabla completa de reputación",
    "No AI agents have a scored track record yet.": (
        "Ningún agente de IA tiene todavía un historial puntuado."
    ),
    "Agent Arena — AI agents only": "Arena de Agentes — solo agentes de IA",
    # --- Weekly contest ---
    "Weekly Contest": "Concurso semanal",
    "Weekly": "Concurso",
    "Contest": "Semanal",
    "Absolute prize": "Premio absoluto",
    "Quality prize": "Premio por calidad",
    "Most reputation points earned this week.": "Más puntos de reputación ganados esta semana.",
    "Most reputation points earned this week (min. %(min)s scored forecasts).": (
        "Más puntos de reputación ganados esta semana (mín. %(min)s pronósticos puntuados)."
    ),
    "Best rep / forecast average this week.": "Mejor promedio de rep / pronóstico esta semana.",
    "Best rep / forecast average this week (min. %(min)s scored forecasts).": (
        "Mejor promedio de rep / pronóstico esta semana (mín. %(min)s pronósticos puntuados)."
    ),
    "Week %(week_code)s · %(start)s – %(end)s": "Semana %(week_code)s · %(start)s – %(end)s",
    "Contest week · Sunday %(start)s – Saturday %(end)s": (
        "Semana del concurso · domingo %(start)s – sábado %(end)s"
    ),
    "Starts soon": "Empieza pronto",
    "Live": "En vivo",
    "Prizes are paid off-platform to verified winners after each week ends. PredictStamp does not hold balances or process payments.": (
        "Los premios se pagan fuera de la plataforma a ganadores verificados al cerrar cada semana. "
        "PredictStamp no guarda saldos ni procesa pagos."
    ),
    "Week reputation": "Reputación semanal",
    "No scored forecasts this week yet. Make a forecast to join the contest.": (
        "Aún no hay pronósticos puntuados esta semana. Haz un pronóstico para unirte al concurso."
    ),
    "No qualified players yet — make at least %(min)s scored forecasts this week to join the contest.": (
        "Aún no hay jugadores calificados — haz al menos %(min)s pronósticos puntuados esta semana para unirte al concurso."
    ),
    "Earn reputation points this calendar week. The top absolute scorer wins $%(prize)s — at least %(min)s scored forecasts required.": (
        "Gana puntos de reputación esta semana calendario. El líder absoluto gana $%(prize)s — "
        "se requieren al menos %(min)s pronósticos puntuados."
    ),
    "Best average reputation per scored forecast this week wins $%(prize)s. At least %(min)s scored forecasts required to qualify.": (
        "El mejor promedio de reputación por pronóstico puntuado esta semana gana $%(prize)s. "
        "Se requieren al menos %(min)s pronósticos puntuados para calificar."
    ),
    "Weekly Contest — win $%(prize)s": "Concurso semanal — gana $%(prize)s",
    "Win cash for predictive skill": "Gana dinero por habilidad predictiva",
    "This week (%(start)s – %(end)s) two predictors win $%(prize)s each — at least %(min)s scored forecasts required.": (
        "Esta semana (%(start)s – %(end)s) dos pronosticadores ganan $%(prize)s cada uno — "
        "se requieren al menos %(min)s pronósticos puntuados."
    ),
    "Absolute": "Absoluto",
    "Quality": "Calidad",
    "Most reputation points this week": "Más puntos de reputación esta semana",
    "Best rep / forecast average": "Mejor rep / pronóstico",
    "Compete all week — minimum %(min)s scored forecasts to qualify.": (
        "Compite toda la semana — mínimo %(min)s pronósticos puntuados para calificar."
    ),
    "This week (%(start)s – %(end)s) two predictors win $%(prize)s each: the most absolute reputation points and the best rep / forecast average.": (
        "Esta semana (%(start)s – %(end)s) dos pronosticadores ganan $%(prize)s cada uno: "
        "el de más puntos absolutos de reputación y el de mejor rep / pronóstico."
    ),
    "Make forecasts on open markets — reputation is scored when they resolve.": (
        "Haz pronósticos en mercados abiertos — la reputación se puntúa cuando se resuelven."
    ),
    "No betting or deposits — skill only.": "Sin apuestas ni depósitos — solo habilidad.",
    "View standings": "Ver clasificación",
    "Select week": "Elegir semana",
    "Final": "Finalizada",
    "Week winners": "Ganadores de la semana",
    "Final results for Sunday %(start)s – Saturday %(end)s": (
        "Resultados finales del domingo %(start)s al sábado %(end)s"
    ),
    "+%(points)s rep this week · $%(prize)s prize": (
        "+%(points)s rep esta semana · premio de $%(prize)s"
    ),
    "Rep / forecast %(score)s · $%(prize)s prize": (
        "Rep / pronóstico %(score)s · premio de $%(prize)s"
    ),
    "No winner — nobody met the minimum scored forecasts.": (
        "Sin ganador — nadie alcanzó el mínimo de pronósticos puntuados."
    ),
    "Past winners": "Ganadores anteriores",
    "Official prize winners from completed contest weeks.": (
        "Ganadores oficiales de semanas de concurso completadas."
    ),
    "View week": "Ver semana",
    "Got it": "Entendido",
    "Don't show this message again": "No volver a ver este mensaje",
    # --- Contest earnings / USDT withdrawal ---
    "Contest earnings": "Ganancias del concurso",
    "Cash prizes from the weekly reputation contest. PredictStamp does not hold your funds — USDT is sent manually to your wallet after review.": (
        "Premios en efectivo del concurso semanal de reputación. PredictStamp no custodia tus fondos — "
        "el USDT se envía manualmente a tu wallet tras la revisión."
    ),
    "View weekly contest": "Ver concurso semanal",
    "Available balance": "Saldo disponible",
    "USD equivalent · withdraw as USDT": "Equivalente en USD · retira en USDT",
    "Available balance · $%(earned)s earned from weekly prizes": (
        "Saldo disponible · $%(earned)s ganados en premios semanales"
    ),
    "Withdraw USDT": "Retirar USDT",
    "Lifetime earned": "Total ganado",
    "Pending": "Pendiente",
    "Withdrawn": "Retirado",
    "Request USDT withdrawal": "Solicitar retiro en USDT",
    "Minimum ${{ min }}. Prizes are paid in USDT after manual review — processing usually takes a few business days.": (
        "Mínimo ${{ min }}. Los premios se pagan en USDT tras revisión manual — "
        "el procesamiento suele tardar unos días hábiles."
    ),
    "Amount (USD)": "Monto (USD)",
    "USDT wallet address": "Dirección wallet USDT",
    "We pay prizes in USDT. Double-check your address — transfers cannot be reversed.": (
        "Pagamos los premios en USDT. Revisa bien tu dirección — las transferencias no se pueden revertir."
    ),
    "Submit withdrawal request": "Enviar solicitud de retiro",
    "You have a pending withdrawal request. We will email you when USDT has been sent.": (
        "Tienes una solicitud de retiro pendiente. Te avisaremos por email cuando se envíe el USDT."
    ),
    "Your balance is below the ${{ min }} minimum withdrawal.": (
        "Tu saldo está por debajo del mínimo de retiro de ${{ min }}."
    ),
    "Prize history": "Historial de premios",
    "Week": "Semana",
    "Category": "Categoría",
    "Prize": "Premio",
    "No contest prizes yet. Top the weekly leaderboard to earn cash rewards.": (
        "Aún no tienes premios del concurso. Lidera la tabla semanal para ganar recompensas en efectivo."
    ),
    "Withdrawal requests": "Solicitudes de retiro",
    "Date": "Fecha",
    "Amount": "Monto",
    "Status": "Estado",
    "Address": "Dirección",
    "Withdrawal request submitted. We will send USDT to your address after review.": (
        "Solicitud de retiro enviada. Enviaremos USDT a tu dirección tras la revisión."
    ),
    "Withdrawal requests are not available right now.": (
        "Las solicitudes de retiro no están disponibles en este momento."
    ),
    "Minimum withdrawal is $%(amount)s.": "El retiro mínimo es $%(amount)s.",
    "Amount exceeds your available balance.": "El monto supera tu saldo disponible.",
    "You already have a pending withdrawal request.": "Ya tienes una solicitud de retiro pendiente.",
    "Enter a valid USDT wallet address (0x…).": (
        "Introduce una dirección wallet USDT válida (0x…)."
    ),
    "Contest withdrawals are not available right now.": (
        "Los retiros del concurso no están disponibles en este momento."
    ),
    # --- Weekly contest winner alerts ---
    "You won the weekly contest!": "¡Ganaste el concurso semanal!",
    "Credited to your account": "Acreditado en tu cuenta",
    "Added to your contest earnings balance — withdraw as USDT anytime.": (
        "Sumado a tu saldo de ganancias del concurso — retira en USDT cuando quieras."
    ),
    "View balance & withdraw": "Ver saldo y retirar",
    "We credited $%(amount)s to your contest earnings balance on PredictStamp. Request a USDT withdrawal from your profile whenever you are ready — PredictStamp does not hold funds on-platform.": (
        "Acreditamos $%(amount)s en tu saldo de ganancias del concurso en PredictStamp. "
        "Solicita un retiro en USDT desde tu perfil cuando quieras — PredictStamp no custodia fondos en la plataforma."
    ),
    "We credited $%(amount)s to your contest earnings balance on PredictStamp. You can request a USDT withdrawal from your profile whenever you are ready.": (
        "Acreditamos $%(amount)s en tu saldo de ganancias del concurso en PredictStamp. "
        "Puedes solicitar un retiro en USDT desde tu perfil cuando quieras."
    ),
    "New contest withdrawal request": "Nueva solicitud de retiro del concurso",
    "New contest withdrawal request — %(username)s": "Nueva solicitud de retiro del concurso — %(username)s",
    "A player requested a USDT withdrawal.": "Un jugador solicitó un retiro en USDT.",
    "Player": "Jugador",
    "USDT wallet address": "Dirección wallet USDT",
    "Review the request in Django admin and send USDT manually after verification.": (
        "Revisa la solicitud en Django admin y envía USDT manualmente tras la verificación."
    ),
    "Congratulations — you won $%(prize)s in the weekly reputation contest!": (
        "¡Felicitaciones — ganaste $%(prize)s en el concurso semanal de reputación!"
    ),
    "Category: %(label)s · Week starting %(week)s": (
        "Categoría: %(label)s · Semana que empieza el %(week)s"
    ),
    "Your prize has been credited to your contest earnings balance on PredictStamp. You can request a USDC withdrawal on Base from your profile whenever you are ready.": (
        "Tu premio fue acreditado en tu saldo de ganancias del concurso en PredictStamp. "
        "Puedes solicitar un retiro en USDC en Base desde tu perfil cuando quieras."
    ),
    "View contest earnings:": "Ver ganancias del concurso:",
    "Keep forecasting — a new contest week starts every Sunday.": (
        "Sigue pronosticando — cada domingo empieza una nueva semana del concurso."
    ),
    "Hi %(name)s, congratulations on topping the weekly reputation leaderboard.": (
        "Hola %(name)s, felicitaciones por liderar la tabla semanal de reputación."
    ),
    "Your prize has been added to your contest earnings balance. Request a USDC withdrawal on Base from your profile whenever you are ready — PredictStamp does not hold funds on-platform.": (
        "Tu premio se sumó a tu saldo de ganancias del concurso. Solicita un retiro en USDC en Base "
        "desde tu perfil cuando quieras — PredictStamp no custodia fondos en la plataforma."
    ),
    "A new contest week starts every Sunday. Keep forecasting to defend your spot.": (
        "Cada domingo empieza una nueva semana del concurso. Sigue pronosticando para defender tu puesto."
    ),
    "Absolute reputation leader": "Líder absoluto de reputación",
    "Best rep / forecast average": "Mejor rep / pronóstico",
    "Week %(week)s": "Semana %(week)s",
    "Free to enter — no separate sign-up. Just make forecasts on the platform and you're in.": (
        "Participar es gratis — no hace falta inscribirse por separado. "
        "Solo con hacer pronósticos en la plataforma ya estás dentro."
    ),
    # --- Daily missions ---
    "Daily missions": "Misiones diarias",
    "Popularity points on completion": "Puntos de popularidad al completar",
    "Make a forecast": "Haz un pronóstico",
    "Place one forecast on any open market today.": (
        "Publica un pronóstico en cualquier mercado abierto hoy."
    ),
    "Defend a thesis": "Defiende una tesis",
    "Publish a forecast with written reasoning (100+ characters).": (
        "Publica un pronóstico con razonamiento escrito (100+ caracteres)."
    ),
    "Join a discussion": "Únete a una conversación",
    "Post a comment in any forecast thread.": (
        "Publica un comentario en cualquier hilo de pronósticos."
    ),
    "Curate the feed": "Cura el feed",
    "Vote on three forecasts or comments you find insightful.": (
        "Vota tres pronósticos o comentarios que te parezcan valiosos."
    ),
    # --- Topic follows + market watch ---
    "Following topic": "Siguiendo tema",
    "Follow topic": "Seguir tema",
    "Unknown topic.": "Tema desconocido.",
    "Missing topic": "Falta el tema",
    "Get notified before this market resolves": (
        "Recibe un aviso antes de que este mercado se resuelva"
    ),
    "Watching": "Siguiendo",
    "Watch": "Seguir",
    # --- Duels: H2H + rematch + spectating ---
    "Head to head vs %(name)s: %(wins)sW · %(losses)sL · %(ties)sT": (
        "Cara a cara vs %(name)s: %(wins)sG · %(losses)sP · %(ties)sE"
    ),
    "Rematch": "Revancha",
    "You are spectating this challenge — only participants can forecast for the leaderboard.": (
        "Estás viendo este desafío como espectador — solo los participantes puntúan en la tabla."
    ),
    # --- Profile: calibration + season awards ---
    "Calibration": "Calibración",
    "Hit rate by market-implied entry probability. A well-calibrated forecaster lands near the diagonal — winning ~30%% of 30%% calls and ~90%% of 90%% calls.": (
        "Tasa de acierto según la probabilidad de entrada implícita del mercado. Un pronosticador "
        "bien calibrado queda cerca de la diagonal: acierta ~30%% de sus apuestas al 30%% y ~90%% "
        "de las del 90%%."
    ),
    "Market-implied": "Implícita del mercado",
    "Actual accuracy": "Precisión real",
    "Season awards": "Premios de temporada",
    "Permanent badges for top finishes in quarterly reputation seasons.": (
        "Insignias permanentes por los mejores puestos en las temporadas trimestrales de reputación."
    ),
    "#%(rank)s · Season %(season)s": "#%(rank)s · Temporada %(season)s",
    "%(points)s reputation over %(count_n)s scored forecasts": (
        "%(points)s de reputación en %(count_n)s pronósticos puntuados"
    ),
}
