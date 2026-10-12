import re

from app.models.job import JobRoleCategory


ROLE_PATTERNS: list[tuple[JobRoleCategory, list[re.Pattern[str]]]] = [
    (
        JobRoleCategory.MACHINE_LEARNING,
        [
            re.compile(r"\b(machine\s+learning|ml|ai|artificial\s+intelligence)\b", re.IGNORECASE),
            re.compile(r"\b(data\s+scientist|computer\s+vision|nlp|deep\s+learning)\b", re.IGNORECASE),
        ],
    ),
    (
        JobRoleCategory.DATA,
        [
            re.compile(r"\b(data\s+(engineer|analyst|analytics)|bi\s+analyst|business\s+intelligence)\b", re.IGNORECASE),
            re.compile(r"\b(sql|etl|warehouse|power\s*bi|tableau)\b", re.IGNORECASE),
        ],
    ),
    (
        JobRoleCategory.FULLSTACK,
        [
            re.compile(r"\bfull[\s-]?stack\b", re.IGNORECASE),
            re.compile(r"\b(front[\s-]?end.*back[\s-]?end|back[\s-]?end.*front[\s-]?end)\b", re.IGNORECASE),
        ],
    ),
    (
        JobRoleCategory.FRONTEND,
        [
            re.compile(r"\bfront[\s-]?end\b", re.IGNORECASE),
            re.compile(r"\b(react|vue|angular|javascript|typescript|html|css)\b", re.IGNORECASE),
        ],
    ),
    (
        JobRoleCategory.BACKEND,
        [
            re.compile(r"\bback[\s-]?end\b", re.IGNORECASE),
            re.compile(r"\b(java|python|php|node\.?js|golang|go|ruby|\.net|c#|django|fastapi|spring)\b", re.IGNORECASE),
        ],
    ),
    (
        JobRoleCategory.MOBILE,
        [
            re.compile(r"\b(android|ios|mobile|flutter|react\s+native|swift|kotlin)\b", re.IGNORECASE),
        ],
    ),
    (
        JobRoleCategory.DEVOPS,
        [
            re.compile(r"\b(devops|sre|site\s+reliability|platform\s+engineer)\b", re.IGNORECASE),
            re.compile(r"\b(kubernetes|docker|terraform|aws|azure|gcp|ci/cd)\b", re.IGNORECASE),
        ],
    ),
    (
        JobRoleCategory.QA,
        [
            re.compile(r"\b(qa|quality\s+assurance|test\s+(engineer|automation)|manual\s+tester)\b", re.IGNORECASE),
        ],
    ),
    (
        JobRoleCategory.GAME_DEVELOPMENT,
        [
            re.compile(r"\b(game\s+(developer|programmer|designer|development)|gameplay\s+programmer)\b", re.IGNORECASE),
            re.compile(r"\b(unity|unreal|godot|c\+\+)\b", re.IGNORECASE),
        ],
    ),
    (
        JobRoleCategory.DESIGN,
        [
            re.compile(r"\b(ui/ux|ux|ui|product\s+designer|graphic\s+designer|motion\s+designer)\b", re.IGNORECASE),
            re.compile(r"\b(artist|animator|illustrator|3d\s+modeler|vfx)\b", re.IGNORECASE),
        ],
    ),
    (
        JobRoleCategory.MANAGEMENT,
        [
            re.compile(r"\b(project|product|program)\s+manager\b", re.IGNORECASE),
            re.compile(r"\b(scrum\s+master|team\s+lead|engineering\s+manager|delivery\s+manager)\b", re.IGNORECASE),
        ],
    ),
]


def classify_role(title: str, description: str) -> JobRoleCategory:
    haystack = f"{title}\n{description}"
    for role, patterns in ROLE_PATTERNS:
        if any(pattern.search(haystack) for pattern in patterns):
            return role
    return JobRoleCategory.OTHER
