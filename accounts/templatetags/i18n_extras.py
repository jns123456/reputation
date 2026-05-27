from django import template

register = template.Library()

LANGUAGE_FLAGS = {
    "en": "🇺🇸",
    "es": "🇪🇸",
}


@register.filter
def language_flag(language_code):
    return LANGUAGE_FLAGS.get(language_code, "🌐")
