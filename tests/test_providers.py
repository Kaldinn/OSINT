from customosint.models import Entity, EntityType
from customosint.providers.public import GitHubProvider, GravatarProvider, SpiderFootProvider


def test_github_normalization():
    seed = Entity(EntityType.USERNAME, "octocat", "octocat")
    result = GitHubProvider().normalize({"login": "octocat", "html_url": "https://github.com/octocat", "location": "Internet"}, seed)
    assert result.entities[0].type == EntityType.GITHUB_ACCOUNT
    assert result.relationships[0].confidence == .72


def test_gravatar_normalization():
    seed = Entity(EntityType.EMAIL, "a@example.com", "a@example.com")
    result = GravatarProvider().normalize({"profile_url": "https://gravatar.com/a", "display_name": "A"}, seed)
    assert result.entities[0].type == EntityType.SOCIAL_PROFILE
    assert result.relationships[0].relation == "HAS_PROFILE"


def test_spiderfoot_normalization_is_low_confidence():
    seed = Entity(EntityType.EMAIL, "a@example.com", "a@example.com")
    result = SpiderFootProvider().normalize([{"type": "INTERNET_NAME", "data": "example.com"}], seed)
    assert result.entities[0].confidence == .45
