from __future__ import annotations

import re
import unicodedata


def clean_text(value: str | None) -> str:
    if not value:
        return ""
    return re.sub(r"\s+", " ", value).strip()


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text.lower()).strip("-")
    return text or "renati"


def normalize_for_match(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return re.sub(r"\s+", " ", text.lower()).strip()


def map_degree(value: str | None) -> str:
    normalized = normalize_for_match(value)
    if not normalized:
        return ""
    mapping = {
        "bachelorthesis": "Bachiller",
        "bachelor thesis": "Bachiller",
        "professionaltitle": "Licenciatura/Titulo profesional",
        "professionaltitlethesis": "Licenciatura/Titulo profesional",
        "masterthesis": "Maestria",
        "master thesis": "Maestria",
        "doctoralthesis": "Doctorado",
        "doctoral thesis": "Doctorado",
        "bachiller": "Bachiller",
        "titulo profesional": "Licenciatura/Titulo profesional",
        "tituloprofesional": "Licenciatura/Titulo profesional",
        "licenciado": "Licenciatura/Titulo profesional",
        "maestro": "Maestria",
        "master": "Maestria",
        "doctor": "Doctorado",
        "segundaespecialidad": "Segunda especialidad",
        "segunda especialidad": "Segunda especialidad",
    }
    compact = normalized.replace("#", " ").replace("/", " ")
    for key, label in mapping.items():
        if key in compact:
            return label
    return value or ""


def map_access_type(value: str | None) -> str:
    normalized = normalize_for_match(value)
    if not normalized:
        return ""
    if "acceso abierto" in normalized or "openaccess" in normalized or "open access" in normalized:
        return "Acceso abierto"
    if "restrictedaccess" in normalized or "restricted access" in normalized or "acceso restringido" in normalized:
        return "Acceso restringido"
    if "embargoedaccess" in normalized or "embargo" in normalized:
        return "Embargado"
    if "tesis" in normalized:
        return "Tesis"
    if "trabajoacademico" in normalized or "trabajo academico" in normalized:
        return "Trabajo academico"
    if "trabajoinvestigacion" in normalized or "trabajo investigacion" in normalized:
        return "Trabajo de investigacion"
    if "suficienciaprofesional" in normalized or "suficiencia profesional" in normalized:
        return "Trabajo de suficiencia profesional"
    return value or ""
