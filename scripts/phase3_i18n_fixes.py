"""Phase 3 i18n: transactional email templates and JS-adjacent strings."""

from __future__ import annotations

PHASE3_FIXES: dict[str, str] = {
    "PredictStamp product overview video": "Video de presentación de PredictStamp",
    "PredictStamp — The social layer for prediction markets": (
        "PredictStamp — La capa social de los mercados de predicción"
    ),
    "Play video": "Reproducir video",
    "Featured open forecasts": "Pronósticos abiertos destacados",
    "Welcome to PredictStamp": "Bienvenido a PredictStamp",
    "Welcome to PredictStamp!": "¡Bienvenido a PredictStamp!",
    "Hi %(name)s,": "Hola %(name)s,",
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
    "Live": "En vivo",
    "Community forecast feed": "Feed de pronósticos de la comunidad",
    "An account with this email already exists. Try signing in instead.": (
        "Ya existe una cuenta con este email. Prueba iniciar sesión."
    ),
    "Invalid vote": "Voto inválido",
    # --- Password reset flow ---
    "Reset password": "Restablecer contraseña",
    "Account recovery": "Recuperación de cuenta",
    "Forgot your": "¿Olvidaste tu",
    "password?": "contraseña?",
    "Enter the email linked to your account and we'll send you a secure link to choose a new password.": (
        "Ingresa el email vinculado a tu cuenta y te enviaremos un enlace seguro para elegir una nueva contraseña."
    ),
    "Reset your password": "Restablece tu contraseña",
    "We'll email you a one-time reset link.": "Te enviaremos un enlace de un solo uso por email.",
    "Send reset link": "Enviar enlace de restablecimiento",
    "Remembered it?": "¿La recordaste?",
    "Back to login": "Volver al inicio de sesión",
    "Check your email": "Revisa tu email",
    "Check your": "Revisa tu",
    "inbox": "bandeja de entrada",
    "If an account exists with that email, a reset link is on its way.": (
        "Si existe una cuenta con ese email, el enlace de restablecimiento está en camino."
    ),
    "Email sent": "Email enviado",
    "If an account exists with the email you entered, we've sent a password reset link. The link expires after a short time and can be used once.": (
        "Si existe una cuenta con el email que ingresaste, enviamos un enlace para restablecer la contraseña. "
        "El enlace caduca en poco tiempo y solo puede usarse una vez."
    ),
    "Didn't get it? Check your spam folder or try again in a few minutes.": (
        "¿No llegó? Revisa tu carpeta de spam o vuelve a intentarlo en unos minutos."
    ),
    "Choose a new password": "Elige una nueva contraseña",
    "Choose a new": "Elige una nueva",
    "Pick a strong password you haven't used elsewhere.": (
        "Elige una contraseña fuerte que no hayas usado en otro sitio."
    ),
    "Set new password": "Definir nueva contraseña",
    "New password": "Nueva contraseña",
    "Confirm new password": "Confirmar nueva contraseña",
    "Save new password": "Guardar nueva contraseña",
    "This reset link is invalid or has already been used. Request a new one below.": (
        "Este enlace es inválido o ya fue usado. Solicita uno nuevo abajo."
    ),
    "Request a new link": "Solicitar un nuevo enlace",
    "Password updated": "Contraseña actualizada",
    "You're all": "Ya estás",
    "set": "listo",
    "Your password was updated. Sign in with your new credentials.": (
        "Tu contraseña fue actualizada. Inicia sesión con tus nuevas credenciales."
    ),
    "Your new password is active. You can log in now.": (
        "Tu nueva contraseña está activa. Ya puedes iniciar sesión."
    ),
    "Forgot your password?": "¿Olvidaste tu contraseña?",
    "Reset your PredictStamp password": "Restablece tu contraseña de PredictStamp",
    "Too many reset requests. Please wait a while and try again.": (
        "Demasiadas solicitudes de restablecimiento. Espera un momento y vuelve a intentarlo."
    ),
    "Someone requested a password reset for your PredictStamp account. Use this link to choose a new password:": (
        "Alguien solicitó restablecer la contraseña de tu cuenta de PredictStamp. Usa este enlace para elegir una nueva:"
    ),
    "The link can only be used once. If it expires, you can request a new one from the login page.": (
        "El enlace solo puede usarse una vez. Si caduca, puedes solicitar uno nuevo desde la página de inicio de sesión."
    ),
    "If you did not request this, ignore this message — your password will stay the same.": (
        "Si no solicitaste esto, ignora este mensaje: tu contraseña seguirá siendo la misma."
    ),
    # --- OAuth account deletion re-auth ---
    "Email confirmation code": "Código de confirmación por email",
    "Enter the 6-digit code we emailed you.": "Ingresa el código de 6 dígitos que te enviamos por email.",
    "Invalid or expired confirmation code.": "Código de confirmación inválido o caducado.",
    "Email me a code": "Enviarme un código",
    "Please wait a minute before requesting another code.": (
        "Espera un minuto antes de solicitar otro código."
    ),
    "We couldn't send the confirmation email. Try again later.": (
        "No pudimos enviar el email de confirmación. Inténtalo más tarde."
    ),
    "We emailed you a confirmation code. It expires in 15 minutes.": (
        "Te enviamos un código de confirmación por email. Caduca en 15 minutos."
    ),
    "Confirm your PredictStamp account deletion": (
        "Confirma la eliminación de tu cuenta de PredictStamp"
    ),
    "Someone requested to permanently delete your PredictStamp account. Use this code to confirm:": (
        "Alguien solicitó eliminar permanentemente tu cuenta de PredictStamp. Usa este código para confirmar:"
    ),
    "This code expires in %(minutes)s minutes and can only be used once.": (
        "Este código caduca en %(minutes)s minutos y solo puede usarse una vez."
    ),
    "If you did not request this, ignore this message and consider reviewing your account security.": (
        "Si no solicitaste esto, ignora este mensaje y considera revisar la seguridad de tu cuenta."
    ),
    # --- Auth0 linking denial ---
    "We couldn't sign you in: your identity provider has not verified this email address. Verify it there, or sign in with your password.": (
        "No pudimos iniciar tu sesión: tu proveedor de identidad no verificó esta dirección de email. "
        "Verifícala allí o inicia sesión con tu contraseña."
    ),
    "Your open forecasts": "Tus pronósticos abiertos",
    "Formal predictions from the community — each card compares entry odds with the current market and live reputation P&L.": (
        "Pronósticos formales de la comunidad: cada tarjeta compara las probabilidades de entrada "
        "con el mercado actual y el P&L de reputación en vivo."
    ),
    # --- MCP agent discoverability ---
    "MCP tokens": "Tokens MCP",
    "Connect this agent": "Conectar este agente",
    "Create MCP tokens so Cursor or other AI tools can read markets and submit forecasts on your behalf.": (
        "Crea tokens MCP para que Cursor u otras herramientas de IA lean mercados "
        "y publiquen pronósticos en tu nombre."
    ),
    "Manage MCP tokens": "Gestionar tokens MCP",
}

PHASE3_PLURAL_FIXES: dict[str, tuple[str, str]] = {}
