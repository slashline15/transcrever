import os
from notion_client import Client

# Esperado pelo código Python (notion_sync.py)
EXPECTED_PROPERTIES = {
    "Title": "title",
    "Data": "date",
    "Duração": "number",
    "Custo": "number",
    "Modelo": "select",
    "Status": "select",
}

def fetch_notion_db_structure(token, database_id):
    client = Client(auth=token)
    db = client.databases.retrieve(database_id=database_id)
    props = db["properties"]
    structure = {name: prop["type"] for name, prop in props.items()}
    return structure

def compare_structures(expected, actual):
    report = []
    matched = []
    # Checa campos esperados
    for field, type_expected in expected.items():
        type_actual = actual.get(field)
        if type_actual is None:
            report.append(f"❌ Campo ausente no Notion: '{field}' (esperado: {type_expected})")
        elif type_actual != type_expected:
            report.append(f"❌ Tipo divergente em '{field}': esperado '{type_expected}', obtido '{type_actual}'")
        else:
            matched.append(f"✅ '{field}' OK ({type_expected})")
    # Extras desconhecidos
    for field in set(actual) - set(expected):
        report.append(f"⚠️ Campo extra não reconhecido no Notion: '{field}' (tipo {actual[field]})")
    return matched, report

def main():
    token = os.getenv("NOTION_TOKEN")
    db_id = os.getenv("NOTION_TRANSCRIPTIONS_DB")
    if not token or not db_id:
        print("Configure NOTION_TOKEN e NOTION_TRANSCRIPTIONS_DB no ambiente")
        return

    real_structure = fetch_notion_db_structure(token, db_id)
    matched, report = compare_structures(EXPECTED_PROPERTIES, real_structure)
    print("Comparação estrutura Notion vs esperado:")
    for line in matched:
        print(line)
    print("---")
    for line in report:
        print(line)
    if report:
        print("ATENÇÃO: Inconsistências encontradas na estrutura do banco Notion!")
    else:
        print("Estrutura do banco Notion está de acordo com o esperado.")

if __name__ == "__main__":
    main()