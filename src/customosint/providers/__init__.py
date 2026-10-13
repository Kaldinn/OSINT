"""Built-in provider registry."""

from .base import Provider
from .email import HIBPProvider, HoleheProvider
from .public import (
    GHuntProvider,
    GitHubProvider,
    GravatarProvider,
    KeybaseProvider,
    SpiderFootProvider,
)
from .username import MaigretProvider, SherlockProvider


def built_in_providers() -> list[Provider]:
    providers: list[Provider] = [
        MaigretProvider(),
        SherlockProvider(),
        HoleheProvider(),
        HIBPProvider(),
        GitHubProvider(),
        GravatarProvider(),
        KeybaseProvider(),
        GHuntProvider(),
        SpiderFootProvider(),
    ]
    return providers


__all__ = ["Provider", "built_in_providers"]
