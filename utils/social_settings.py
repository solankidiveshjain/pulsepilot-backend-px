"""
Stub module for social media settings required by platform services.
"""

def get_social_media_settings():
    """
    Load social media settings from config/social_media.yml with environment variable substitution.
    """
    import os
    from pathlib import Path
    import yaml

    config_path = Path(__file__).parent.parent / "config" / "social_media.yml"
    text = config_path.read_text()
    text = os.path.expandvars(text)
    settings = yaml.safe_load(text)
    return settings 