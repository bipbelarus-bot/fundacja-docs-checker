# fundacja-docs-checker

Инструмент для автоматической технической проверки документов Fundacji перед внутренним утверждением и подачей в KRS.

## Что проверяет

- KRS, NIP, REGON
- название Fundacji
- siedziba и адрес
- даты и номера uchwał
- ссылки на § Statutu
- наличие слов-плейсхолдеров и незаполненных полей
- базовую согласованность документов
- наличие обязательных элементов в протоколах и uchwałach

## Важно

Этот проект выполняет техническую и формальную проверку. Он не заменяет юридическую проверку актуального Statutu, компетенций органов, quorum, większości głosów и действующего законодательства.

## Структура

- `config/fundacja_rules.yaml` — эталонные реквизиты и правила
- `src/` — Python-код проверки
- `notebooks/Fundacja_Docs_Checker_Colab.ipynb` — запуск в Google Colab
- `templates/` — место для универсальных шаблонов
- `output/` — результаты проверки

## Быстрый запуск

```bash
pip install -r requirements.txt
python src/check_documents.py --input ./documents --output ./output/report.csv
```

Для Google Colab откройте `notebooks/Fundacja_Docs_Checker_Colab.ipynb`.
