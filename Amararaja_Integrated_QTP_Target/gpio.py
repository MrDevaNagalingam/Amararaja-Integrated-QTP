"""Reserved for board-specific GPIO operations once mappings are supplied."""

def require_mapping(name):
    from config import GPIO_MAPPING
    if name not in GPIO_MAPPING:
        raise NotImplementedError("GPIO mapping not configured: " + name)
    return GPIO_MAPPING[name]
