from django import template
from django.utils.safestring import mark_safe

register = template.Library()


@register.filter
def star_display(rating):
    """Convert a numeric rating to star display string"""
    stars = []
    for i in range(1, 6):
        if rating >= i:
            stars.append(
                '<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px"><path d="m233-120 65-281L80-590l288-25 112-265 112 265 288 25-218 189 65 281-247-149-247 149Z"/></svg>'  # noqa: E501
            )
        elif rating >= i - 0.5:
            stars.append(
                '<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px"><path d="m606-286-33-144 111-96-146-13-58-136v312l126 77ZM233-120l65-281L80-590l288-25 112-265 112 265 288 25-218 189 65 281-247-149-247 149Z"/></svg>'  # noqa: E501
            )
        else:
            stars.append(
                '<svg xmlns="http://www.w3.org/2000/svg" height="24px" viewBox="0 -960 960 960" width="24px"><path d="m354-287 126-76 126 77-33-144 111-96-146-13-58-136-58 135-146 13 111 97-33 143ZM233-120l65-281L80-590l288-25 112-265 112 265 288 25-218 189 65 281-247-149-247 149Zm247-350Z"/></svg>'  # noqa: E501
            )
    return mark_safe("".join(stars))
