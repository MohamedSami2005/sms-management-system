from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Safely retrieves a key from a dictionary in Django templates.
    Usage: {{ row|get_item:header }}
    """
    if isinstance(dictionary, dict):
        return dictionary.get(key, '')
    return ''
