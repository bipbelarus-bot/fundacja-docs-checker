from pathlib import Path
import argparse
import yaml
from extract_docx import extract_docx_text
from extract_pdf import extract_pdf_text
from validators import run_validations
from report import write_reports


def load_rules(path):
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def extract_text(path):
    if path.suffix.lower() == ".docx":
        return extract_docx_text(path)
    if path.suffix.lower() == ".pdf":
        return extract_pdf_text(path)
    return ""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", default="output/report.csv")
    parser.add_argument("--config", default="config/fundacja_rules.yaml")
    args = parser.parse_args()

    input_dir = Path(args.input)
    rules = load_rules(args.config)
    rows = []
    files = [p for p in input_dir.rglob("*") if p.is_file() and p.suffix.lower() in {".docx", ".pdf"}]

    if not files:
        raise SystemExit("No DOCX or PDF files found in input directory")

    for path in sorted(files):
        try:
            text = extract_text(path)
            if not text.strip():
                rows.append({"file": str(path), "check": "text_extraction", "status": "REVIEW", "message": "No text extracted; scanned PDF may require OCR."})
                continue
            for finding in run_validations(str(path), text, rules):
                rows.append(finding.to_dict())
        except Exception as exc:
            rows.append({"file": str(path), "check": "processing", "status": "ERROR", "message": f"{type(exc).__name__}: {exc}"})

    csv_path, xlsx_path = write_reports(rows, args.output)
    print(f"Checked {len(files)} files")
    print(f"CSV: {csv_path}")
    print(f"XLSX: {xlsx_path}")


if __name__ == "__main__":
    main()
