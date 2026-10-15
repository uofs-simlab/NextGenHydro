import re

FEATURE = {"basin", "watershed", "catchment", "river", "creek", "fork", "lake"}
STOP = {
    "a", "an", "and", "at", "above", "below", "around", "near", "for", "from", "in", "of", "on", "or",
    "the", "to", "that", "this", "with", "using", "through", "drains", "drain", "gage", "gauge", "usgs",
    "nextgen", "simulation", "outlet", "map", "national", "water", "model", "retrospective", "forcing",
    "hour", "run", "delineate", "noah-owp", "noahowp", "cfe", "pet", "lstm", "sloth", "t-route", "troute",
}
PLACE = r"([A-Za-z][A-Za-z.'-]*(?:\s+[A-Za-z][A-Za-z.'-]*){0,4})"
MONTHS = {
    "January", "February", "March", "April", "May", "June", "July", "August", "September", "October",
    "November", "December",
}


def _clean_place(raw: str) -> str | None:
    words = [word for word in re.split(r"\s+", raw.strip()) if word]
    kept: list[str] = []
    for word in words:
        cleaned = re.sub(r"\.+$", "", re.sub(r"^[^A-Za-z]+|[^A-Za-z'-]+$", "", word))
        if not cleaned:
            continue
        key = cleaned.lower()
        if key == "the" and not kept:
            continue
        if key in STOP:
            return None
        kept.append(cleaned)
    if not any(word.lower() not in FEATURE for word in kept):
        return None
    return " ".join(kept)


def _name_before(text: str, index: int) -> list[str]:
    before = re.split(r"\s+", text[:index].strip())[-4:]
    kept: list[str] = []
    for word in before:
        key = re.sub(r"[^a-z.'-]", "", word.lower())
        if not key or key in STOP:
            kept.clear()
            continue
        kept.append(re.sub(r"[^A-Za-z.'-]", "", word))
    return [word for word in kept if word]


def _leading_place(raw: str) -> str | None:
    kept: list[str] = []
    for word in re.split(r"\s+", raw.strip()):
        cleaned = re.sub(r"\.+$", "", re.sub(r"^[^A-Za-z]+|[^A-Za-z'-]+$", "", word))
        if not cleaned:
            continue
        key = cleaned.lower()
        if not kept and key == "the":
            continue
        if key in STOP or key in FEATURE:
            break
        kept.append(cleaned)
        if len(kept) == 3:
            break
    return " ".join(kept) if kept else None


def place_query_from_sentence(text: str) -> str | None:
    near = re.search(rf"\b(?:near|at|above|below|around)\s+{PLACE}", text, re.I)
    from_near = _leading_place(near.group(1)) if near else None
    if from_near:
        return from_near
    for match in re.finditer(r"\b(basin|watershed|catchment|river|creek)\b", text, re.I):
        kept = _name_before(text, match.start())
        if kept:
            return f"{' '.join(kept)} {match.group(1)}"
    of_place = re.search(rf"\b(?:basin|watershed|catchment|river|creek)\s+(?:of\s+)?(?:the\s+)?{PLACE}", text, re.I)
    from_of = _clean_place(of_place.group(1)) if of_place else None
    if from_of:
        return from_of
    inside = re.search(r"\b(?:in|across)\s+(?:the\s+)?([A-Z][A-Za-z.'-]*(?:\s+[A-Z][A-Za-z.'-]*){0,3})", text)
    if not inside:
        return None
    place = _clean_place(inside.group(1))
    if not place or place in MONTHS:
        return None
    return place
