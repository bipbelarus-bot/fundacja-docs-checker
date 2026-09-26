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


def _basename(file_name: str) -> str:
    return file_name.rsplit("/", 1)[-1]


def check_identifiers(file_name: str, text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    f = rules["fundacja"]
    patterns = {
        "krs": r"\bKRS(?:\s*(?:nr|numer))?\s*[:#-]?\s*(\d{10})\b",
        "nip": r"\bNIP\s*[:#-]?\s*(\d{10})\b",
        "regon": r"\bREGON\s*[:#-]?\s*(\d{9})\b",
    }
    for key, label in [("krs", "KRS"), ("nip", "NIP"), ("regon", "REGON")]:
        expected = str(f.get(key, "")).strip()
        if not expected:
            continue
        if expected in text:
            findings.append(Finding(file_name, label, "OK", f"Znaleziono poprawny {label}: {expected}"))
            continue
        match = re.search(patterns[key], text, re.I)
        if match:
            found = match.group(1)
            findings.append(Finding(file_name, label, "WARN", f"Wykryto {label} {found}, oczekiwano: {expected}"))
    return findings


def check_name(file_name: str, text: str, rules: dict) -> list[Finding]:
    expected = str(rules["fundacja"].get("name", "")).strip()
    if not expected:
        return []
    if _norm(expected) in _norm(text):
        return [Finding(file_name, "fundacja_name", "OK", "Nazwa Fundacji zgodna z konfiguracją.")]
    explicit = re.search(r"(?im)^\s*(?:nazwa\s+fundacji|fundacja)\s*[:\-]\s*(.+?)\s*$", text)
    if explicit:
        return [Finding(file_name, "fundacja_name", "REVIEW", f"Jawnie podana nazwa wymaga weryfikacji: {explicit.group(1).strip()}")]
    return []


def check_seat_and_address(file_name: str, text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    f = rules["fundacja"]
    seat = str(f.get("current_seat", "")).strip()
    address = str(f.get("current_address", "")).strip()

    if seat:
        seat_statement = re.search(r"siedzib[ąa]\s+fundacji\s+(?:jest|pozostaje)\s+([^\n.]+)", text, re.I)
        seat_field = re.search(r"(?im)^\s*siedziba\s*$", text)
        if seat_statement:
            findings.append(Finding(file_name, "seat", "OK" if seat.lower() in seat_statement.group(1).lower() else "WARN", f"Siedziba oczekiwana: {seat}"))
        elif seat_field:
            nearby = text[seat_field.end():seat_field.end() + 250]
            findings.append(Finding(file_name, "seat", "OK" if seat.lower() in nearby.lower() else "REVIEW", f"Pole siedziby wymaga zgodności z: {seat}"))

    address_configured = bool(address) and "UZUPEŁNIJ" not in address.upper()
    if address_configured:
        if _norm(address) in _norm(text):
            findings.append(Finding(file_name, "address", "OK", f"Znaleziono aktualny adres: {address}"))
        else:
            explicit_address = re.search(r"(?im)^\s*(?:adres|adres\s+rejestrowy)\s*$", text)
            if explicit_address:
                findings.append(Finding(file_name, "address", "REVIEW", f"Dokument zawiera pole adresu; oczekiwany aktualny adres: {address}"))
    return findings


def check_placeholders(file_name: str, text: str, rules: dict) -> list[Finding]:
    if "CHECKLISTA" in _basename(file_name).upper():
        return []
    findings: list[Finding] = []
    for marker in rules.get("placeholders", []):
        if marker.lower() in text.lower():
            findings.append(Finding(file_name, "placeholder", "ERROR", f"Pozostał niewypełniony placeholder: {marker}"))
    if not findings:
        findings.append(Finding(file_name, "placeholder", "OK", "Nie znaleziono skonfigurowanych placeholderów."))
    return findings


def check_board_resolution_reference(file_name: str, text: str, rules: dict) -> list[Finding]:
    f = rules.get("fundacja", {})
    expected_number = str(f.get("board_resolution_number", "")).strip()
    expected_date = str(f.get("board_resolution_date", "")).strip()
    if not expected_number and not expected_date:
        return []
    if not re.search(r"uchwa[łl](?:a|y|ę)\s+zarz[ąa]du", text, re.I):
        return []

    findings: list[Finding] = []
    if expected_number:
        ref = re.search(r"uchwa[łl](?:a|y|ę)\s+zarz[ąa]du(?:\s+fundacji)?\s+nr\s+([^\s,;]+(?:\s+UZUPEŁNIENIA\])?)", text, re.I)
        if ref:
            found_number = ref.group(1).strip().rstrip(".")
            status = "OK" if expected_number.lower() == found_number.lower() else "ERROR"
            message = f"Numer uchwały Zarządu zgodny: {expected_number}" if status == "OK" else f"Numer uchwały Zarządu niespójny: '{found_number}', oczekiwano '{expected_number}'"
            findings.append(Finding(file_name, "board_resolution_reference", status, message))

    if expected_date:
        date_ref = re.search(r"uchwa[łl](?:a|y|ę)\s+zarz[ąa]du(?:\s+fundacji)?\s+nr\s+[^\n,;]+?\s+z\s+dnia\s+([^\n,;–-]+)", text, re.I)
        if date_ref:
            found_date = date_ref.group(1).strip().rstrip(".")
            accepted = {_norm(expected_date.rstrip(".")), "7.07.2026 r", "07.07.2026 r", "7.07.2026", "07.07.2026"}
            status = "OK" if _norm(found_date) in accepted else "ERROR"
            message = f"Data uchwały Zarządu zgodna: {expected_date}" if status == "OK" else f"Data uchwały Zarządu niespójna: '{found_date}', oczekiwano '{expected_date}'"
            findings.append(Finding(file_name, "board_resolution_date", status, message))
    return findings


def check_procedure_dates(file_name: str, text: str, rules: dict) -> list[Finding]:
    """Check explicit references to the first Council meeting date."""
    expected = str(rules.get("fundacja", {}).get("first_meeting_date", "")).strip()
    if not expected:
        return []
    findings: list[Finding] = []
    # Capture phrases such as: "zwołanie posiedzenia ... na dzień 6 października 2026 r."
    match = re.search(r"zwołani[ea]\s+posiedzenia\s+Rady\s+Fundacji\s+na\s+dzień\s+([^\n.]+(?:2026\s*r\.?)?)", text, re.I)
    if match:
        found = match.group(1).strip().rstrip(".")
        if _norm(found) != _norm(expected.rstrip(".")):
            findings.append(Finding(file_name, "first_meeting_date", "ERROR", f"Niespójna data pierwszego posiedzenia: '{found}', oczekiwano '{expected}'"))
        else:
            findings.append(Finding(file_name, "first_meeting_date", "OK", f"Data pierwszego posiedzenia zgodna: {expected}"))
    return findings


def check_resolution_data(file_name: str, text: str) -> list[Finding]:
    findings: list[Finding] = []
    name = _basename(file_name)
    head = text[:2500]
    is_resolution = bool(
        re.search(r"(?:^|[_\-\s])UCHWA[ŁL]A(?:[_\-\s.]|$)", name, re.I)
        or re.search(r"^\s*UCHWA[ŁL]A\b", head, re.I | re.M)
        or re.search(r"\bUCHWA[ŁL]A\s+(?:RADY|ZARZ[ĄA]DU|FUNDATOR(?:A|ÓW)?|NR)\b", head, re.I)
    )
    is_project = "PROJEKT" in head.upper()

    if is_resolution:
        number_patterns = [
            r"\buchwa[łl]a\s+(?:nr\s*)?[A-Za-z]*\s*\d+[A-Za-z]?(?:[/\-.]\d+){1,3}\b",
            r"\bnr\s+\d+[A-Za-z]?(?:[/\-.]\d+){1,3}\b",
        ]
        has_number = any(re.search(p, head, re.I) for p in number_patterns)
        if has_number:
            findings.append(Finding(file_name, "resolution_number", "OK", "Wykryto numer uchwały."))
        elif not is_project:
            findings.append(Finding(file_name, "resolution_number", "REVIEW", "Dokument jest uchwałą, ale nie wykryto standardowego numeru."))

    is_template = (
        "PROCEDURA" in name.upper()
        or "DOKUMENT PROCEDURALNY" in head.upper()
        or "DOKUMENT WYPEŁNIA SIĘ DOPIERO" in head.upper()
    )
    if not is_template:
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
    findings += check_board_resolution_reference(file_name, text, rules)
    findings += check_procedure_dates(file_name, text, rules)
    findings += check_resolution_data(file_name, text)
    findings += check_statute_references(file_name, text)
    return findings
