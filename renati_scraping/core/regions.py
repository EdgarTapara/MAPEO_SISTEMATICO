from __future__ import annotations

from .normalize import normalize_for_match


UNIVERSITY_REGION_PATTERNS: dict[str, str] = {
    "amazonas": "Amazonas",
    "arequipa": "Arequipa",
    "ayacucho": "Ayacucho",
    "cajamarca": "Cajamarca",
    "callao": "Callao",
    "cusco": "Cusco",
    "huancavelica": "Huancavelica",
    "huanuco": "Huanuco",
    "ica": "Ica",
    "jauja": "Junin",
    "junin": "Junin",
    "la libertad": "La Libertad",
    "lambayeque": "Lambayeque",
    "lima": "Lima",
    "loreto": "Loreto",
    "madre de dios": "Madre de Dios",
    "moquegua": "Moquegua",
    "pasco": "Pasco",
    "piura": "Piura",
    "puno": "Puno",
    "san martin": "San Martin",
    "tacna": "Tacna",
    "tumbes": "Tumbes",
    "ucayali": "Ucayali",
    "cesar vallejo": "La Libertad",
    "catolica del peru": "Lima",
    "pacifico": "Lima",
    "san ignacio de loyola": "Lima",
    "san marcos": "Lima",
    "cayetano heredia": "Lima",
    "esan": "Lima",
    "ricardo palma": "Lima",
    "senor de sipan": "Lambayeque",
    "toribio rodriguez de mendoza": "Amazonas",
}


def infer_region(university: str) -> str:
    normalized = normalize_for_match(university)
    for pattern, region in UNIVERSITY_REGION_PATTERNS.items():
        if pattern in normalized:
            return region
    return ""
