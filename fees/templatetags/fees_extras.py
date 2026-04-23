# fees/templatetags/fees_extras.py
# =============================================================================
# Custom template filters for the fees app.
# Load with: {% load fees_extras %}
# =============================================================================

from django import template

register = template.Library()


@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Allows dict lookup by variable key in templates.
    Usage: {{ my_dict|get_item:variable_key }}
    """
    if dictionary is None:
        return ''
    return dictionary.get(str(key), '')


@register.filter
def subtract(value, arg):
    try:
        return int(value) - int(arg)
    except (ValueError, TypeError):
        return 0
