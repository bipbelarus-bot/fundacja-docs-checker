from __future__ import annotations

import re
from dataclasses import dataclass, asdict
from pathlib import Path
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
        if expected in text:
            findings.append(Finding(file_name, label, "OK", f"Znaleziono poprawny {label}: {expected}"))
        else:
            findings.append(Finding(file_name, label, "WARN", f"Nie znaleziono oczekiwanego {label}: {expected}"))
    return findings


def check_name(file_name: str, text: str, rules: dict) -> list[Finding]:
    expected = rules["fundacja"].get("name", "").strip()
    if not expected:
        return []
    if _norm(expected) in _norm(text):
        return [Finding(file_name, "fundacja_name", "OK", "Nazwa Fundacji zgodna z konfiguracją.")]
    return [Finding(file_name, "fundacja_name", "WARN", "Nie znaleziono pełnej oczekiwanej nazwy Fundacji.")]


def check_seat_and_address(file_name: str, text: str, rules: dict) -> list[Finding]:
    findings: list[Finding] = []
    f = rules["fundacja"]
    seat = str(f.get("current_seat", "")).strip()
    address = str(f.get("current_address", "")).strip()
    if seat:
        findings.append(Finding(file_name, "seat", "OK" if seat.lower() in text.lower() else "WARN", f"Siedziba oczekiwana: {seat}"))
    if address and "UZUPEŁNIJ" not in address.upper():
        findings.append(Finding(file_name, "address", "OK" if _norm(address) in _norm(text) else "WARN", f"Adres oczekiwany: {address}"))
    else:
        findings.append(Finding(file_name, "address", "REVIEW", "Aktualny pełny adres nie jest jeszcze skonfigurowany."))
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
    if re.search(r"uchwa[łl]a\s+(?:nr\s*)?\d+[/\-]\d{2,4}", text, re.I):
        findings.append(Finding(file_name, "resolution_number", "OK", "Wykryto numer uchwały."))
    elif "uchwa" in text.lower():
        findings.append(Finding(file_name, "resolution_number", "REVIEW", "Dokument wygląda na uchwałę, ale nie wykryto standardowego numeru."))

    date_patterns = [r"\b\d{1,2}[.\-/]\d{1,2}[.\-/]\d{4}\b", r"\b\d{1,2}\s+[a-ząćęłńóśźż]+\s+\d{4}\s*r?\.?\b"]
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
