import re

# Common tech skills to look for in free text
SKILL_PATTERNS = [
    # Frontend
    "react", "reactjs", "react.js", "next.js", "nextjs", "vue", "vuejs",
    "angular", "typescript", "javascript", "html", "css", "tailwind",
    "bootstrap", "redux", "webpack", "vite",
    # Backend
    "node", "nodejs", "node.js", "express", "expressjs", "django",
    "flask", "fastapi", "spring", "laravel", "rails", "ruby",
    "php", "python", "java", "golang", "go", "rust", "c#", ".net",
    # Databases
    "mongodb", "mysql", "postgresql", "postgres", "redis", "sqlite",
    "cassandra", "dynamodb", "firebase", "supabase",
    # Cloud / DevOps
    "aws", "azure", "gcp", "docker", "kubernetes", "k8s", "terraform",
    "ci/cd", "github actions", "jenkins",
    # Tools
    "git", "graphql", "rest", "restful", "api", "microservices",
    "kafka", "rabbitmq", "elasticsearch",
    # Mobile
    "react native", "flutter", "swift", "kotlin", "android", "ios",
]

# Build a single compiled regex for efficiency
_SKILL_REGEX = re.compile(
    r'\b(' + '|'.join(re.escape(s) for s in SKILL_PATTERNS) + r')\b',
    re.IGNORECASE
)


def extract_skills(text: str) -> list[str]:
    """Extract known tech skills from free text (snippet, description)."""
    if not text:
        return []
    matches = _SKILL_REGEX.findall(text)
    # Normalize and deduplicate preserving order
    seen = set()
    result = []
    for m in matches:
        normalized = m.lower()
        if normalized not in seen:
            seen.add(normalized)
            result.append(m)
    return result