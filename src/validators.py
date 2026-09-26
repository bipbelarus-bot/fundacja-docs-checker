from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Finding:
    file: str
    check: str
    status: str
    message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _norm(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def check_identifiers(file_name: str, text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    f = rules["fundacja"]
    for key, label in [("krs", "KRS"), ("nip", "NIP"), ("regon", "REGON")]:
        expected = str(f.get(key, "")).strip()
        if not expected:
            continue
        field_present = re.search(rf"\b{re.escape(label)}\b", text, re.I) is not None
        value_present = expected in text
        if not field_present and not value_present:
            continue
        if value_present:
            findings.append(Finding(file_name, label, "OK", f"Znaleziono poprawny {label}: {expected}"))
        else:
            findings.append(Finding(file_name, label, "WARN", f"Dokument zawiera pole {label}, ale nie znaleziono oczekiwanej wartości: {expected}"))
    return findings


def check_name(file_name: str, text: str, rules: dict) -> list[Finding]:
    expected = rules["fundacja"].get("name", "").strip()
    if not expected:
        return []
    normalized = _norm(text)
    if _norm(expected) in normalized:
        return [Finding(file_name, "fundacja_name", "OK", "Nazwa Fundacji zgodna z konfiguracją.")]
    if "fundacja" in normalized:
        return [Finding(file_name, "fundacja_name", "REVIEW", "Dokument odnosi się do Fundacji, ale nie znaleziono pełnej skonfigurowanej nazwy.")]
    return []


def check_seat_and_address(file_name: str, text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    f = rules["fundacja"]
    seat = str(f.get("current_seat", "")).strip()
    address = str(f.get("current_address", "")).strip()
    normalized = _norm(text)
    if seat and "siedzib" in normalized:
        findings.append(Finding(file_name, "seat", "OK" if seat.lower() in text.lower() else "WARN", f"Siedziba oczekiwana: {seat}"))
    address_configured = bool(address) and "UZUPEŁNIJ" not in address.upper()
    if address_configured and ("adres" in normalized or _norm(address) in normalized):
        findings.append(Finding(file_name, "address", "OK" if _norm(address) in normalized else "REVIEW", f"Adres oczekiwany: {address}"))
    return findings


def check_placeholders(file_name: str, text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    for marker in rules.get("placeholders", []):
        if marker.lower() in text.lower():
            findings.append(Finding(file_name, "placeholder", "ERROR", f"Pozostał niewypełniony placeholder: {marker}"))
    if not findings:
        findings.append(Finding(file_name, "placeholder", "OK", "Nie znaleziono skonfigurowanych placeholderów."))
    return findings


def check_resolution_data(file_name: str, text: str) -> list[Finding]:
    findings: list[Finding] = []

    # Numer uchwały sprawdzamy tylko wtedy, gdy sam dokument wygląda jak uchwała.
    # Samo wspomnienie słowa „uchwała” w protokole, checkliście czy załączniku
    # nie powinno generować REVIEW.
    name = file_name.rsplit("/", 1)[-1]
    head = text[:2500]
    is_resolution = bool(
        re.search(r"(?:^|[_\-\s])UCHWA[ŁL]A(?:[_\-\s.]|$)", name, re.I)
        or re.search(r"^\s*UCHWA[ŁL]A\b", head, re.I | re.M)
        or re.search(r"\bUCHWA[ŁL]A\s+(?:RADY|ZARZ[ĄA]DU|FUNDATOR(?:A|ÓW)?|NR)\b", head, re.I)
    )

    if is_resolution:
        number_patterns = [
            r"\buchwa[łl]a\s+(?:nr\s*)?[A-Za-z]*\s*\d+[A-Za-z]?(?:[/\-]\d+){1,3}\b",
            r"\bnr\s+\d+[A-Za-z]?(?:[/\-]\d+){1,3}\b",
        ]
        if any(re.search(p, head, re.I) for p in number_patterns):
            findings.append(Finding(file_name, "resolution_number", "OK", "Wykryto numer uchwały."))
        else:
            findings.append(Finding(file_name, "resolution_number", "REVIEW", "Dokument jest uchwałą, ale nie wykryto standardowego numeru."))

    months = r"(?:stycznia|lutego|marca|kwietnia|maja|czerwca|lipca|sierpnia|wrze[śs]nia|pa[źz]dziernika|listopada|grudnia)"
    date_patterns = [
        r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4}\b",
        rf"\b\d{{1,2}}\s+{months}\s+\d{{4}}(?:\s*r(?:oku)?\.?|\s*roku)?\b",
        r"\b\d{4}[.\-/]\d{1,2}[.\-/]\d{1,2}\b",
    ]
    if any(re.search(p, text, re.I) for p in date_patterns):
        findings.append(Finding(file_name, "date", "OK", "Wykryto datę."))
    else:
        findings.append(Finding(file_name, "date", "REVIEW", "Nie wykryto daty w standardowym formacie."))
    return findings


def check_statute_references(file_name: str, text: str) -> list[Finding]:
    if re.search(r"§\s*\d+", text):
        return [Finding(file_name, "statute_reference", "OK", "Wykryto odwołanie do paragrafu Statutu.")]
    if "statut" in text.lower():
        return [Finding(file_name, "statute_reference", "REVIEW", "Jest odniesienie do Statutu, ale bez wykrytego numeru paragrafu.")]
    return []


def run_validations(file_name: str, text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    findings += check_identifiers(file_name, text, rules)
    findings += check_name(file_name, text, rules)
    findings += check_seat_and_address(file_name, text, rules)
    findings += check_placeholders(file_name, text, rules)
    findings += check_resolution_data(file_name, text)
    findings += check_statute_references(file_name, text)
    return findings
