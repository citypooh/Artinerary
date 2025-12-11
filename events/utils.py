import string

# Base62 alphabet: a-z, A-Z, 0-9 (62 characters total)
BASE62_ALPHABET = string.ascii_letters + string.digits


def base62_encode(num: int) -> str:
    """
    Encode a positive integer to a Base62 string.
    
    Args:
        num: Positive integer (e.g., event.id)
        
    Returns:
        Base62 encoded string (e.g., 'Xk9mP2')
        
    Raises:
        ValueError: If num is not a positive integer
    """
    if num <= 0:
        raise ValueError("ID must be a positive integer")
    
    base = len(BASE62_ALPHABET)
    chars = []
    while num > 0:
        num, rem = divmod(num, base)
        chars.append(BASE62_ALPHABET[rem])
    
    return ''.join(reversed(chars))


def base62_decode(code: str) -> int:
    """
    Decode a Base62 string back to integer.
    
    Args:
        code: Base62 encoded string (e.g., 'Xk9mP2')
        
    Returns:
        Original integer ID
        
    Raises:
        ValueError: If code contains invalid characters
    """
    base = len(BASE62_ALPHABET)
    num = 0
    for ch in code:
        try:
            value = BASE62_ALPHABET.index(ch)
        except ValueError:
            raise ValueError("Invalid character in Base62 code")
        num = num * base + value
    return num


def get_event_share_code(event_or_id):
    """
    Get the stateless share code for an event.
    
    Args:
        event_or_id: Either an Event instance or integer event ID
        
    Returns:
        Base62 encoded share code string
    """
    if hasattr(event_or_id, 'id'):
        # Event instance
        event_id = event_or_id.id
    else:
        # Assume integer ID
        event_id = event_or_id
    
    return base62_encode(event_id)

