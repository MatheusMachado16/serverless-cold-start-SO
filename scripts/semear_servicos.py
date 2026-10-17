#!/usr/bin/env python3
"""Semeia ScyllaDB (A1) e Minio (A2), gera os eventos de entrada e atualiza configs/ambiente_local.json.

Usa o próprio input.py do SeBS (entrada `small` de A1; imagem de A2), para manter a mesma carga.
Requer: serviços no ar (scripts/servicos.sh up) e `pip install boto3 minio pillow`.
Roda fora da medição. É idempotente para a tabela/bucket, mas gera novos IDs de carrinho a cada execução.
"""
import hashlib
import importlib.util
import json
import subprocess
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
AMB = RAIZ / "configs/ambiente_local.json"
TABELA = "cold-start-shopping-cart"
BUCKET = "cold-start"


def ip(nome):
    return subprocess.run(["docker", "inspect", "-f", "{{.NetworkSettings.IPAddress}}", nome],
                          capture_output=True, text=True, check=True).stdout.strip()


def carregar_input(bench):
    spec = importlib.util.spec_from_file_location("inp_" + bench.split("/")[-1], RAIZ / "benchmarks" / bench / "input.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def semear_a1(end):
    import boto3
    ddb = boto3.resource("dynamodb", endpoint_url=f"http://{end}", region_name="None",
                         aws_access_key_id="None", aws_secret_access_key="None")
    try:
        ddb.create_table(TableName=TABELA, BillingMode="PAY_PER_REQUEST",
                         AttributeDefinitions=[{"AttributeName": "cart_id", "AttributeType": "S"},
                                               {"AttributeName": "product_id", "AttributeType": "S"}],
                         KeySchema=[{"AttributeName": "cart_id", "KeyType": "HASH"},
                                    {"AttributeName": "product_id", "KeyType": "RANGE"}]).wait_until_exists()
    except Exception as e:  # tabela já existe
        print("  tabela:", type(e).__name__)
    tabela = ddb.Table(TABELA)

    def nosql_upload(benchmark, table, data, primary, secondary=None):
        item = dict(data)
        for k in (primary, secondary):
            if k:
                item[k[0]] = k[1]
        tabela.put_item(Item=item)

    inp = carregar_input("100.webapps/130.crud-api")
    ev = inp.generate_input(None, "small", None, None, None, None, nosql_upload)
    (RAIZ / "configs/eventos").mkdir(exist_ok=True)
    (RAIZ / "configs/eventos/a1_small.json").write_text(json.dumps(ev, indent=2))
    print("  A1: evento small gravado (carrinho com 4 itens)")


def semear_a2(end, usuario, senha, sebs_dir):
    import minio
    cli = minio.Minio(end, access_key=usuario, secret_key=senha, secure=False)
    if not cli.bucket_exists(BUCKET):
        cli.make_bucket(BUCKET)
    dados = Path(sebs_dir).expanduser() / "benchmarks-data/200.multimedia/210.thumbnailer"
    jpgs = sorted(dados.glob("*.jpg"))
    assert jpgs, f"nenhum .jpg em {dados}"

    def upload(idx, key, caminho):
        cli.fput_object(BUCKET, f"input/{key}", caminho)

    inp = carregar_input("200.multimedia/210.thumbnailer")
    ev = inp.generate_input(str(dados), "small", BUCKET, ["input"], ["output"], upload, None)
    alvo = dados / ev["object"]["key"]
    (RAIZ / "configs/eventos/a2.json").write_text(json.dumps(ev, indent=2))
    (RAIZ / "configs/eventos/a2.meta.json").write_text(json.dumps(
        {"imagem": alvo.name, "sha256": hashlib.sha256(alvo.read_bytes()).hexdigest(), "bytes": alvo.stat().st_size,
         "redimensionamento": [ev["object"]["width"], ev["object"]["height"]]}, indent=2))
    print(f"  A2: {len(jpgs)} imagens enviadas; alvo {alvo.name}")


def main():
    amb = json.loads(AMB.read_text())
    s_ip, m_ip = ip("cs-scylla"), ip("cs-minio")
    semear_a1(f"{s_ip}:8000")
    semear_a2(f"{m_ip}:9000", "coldstart", "coldstart-secret", amb["sebs_dir"])
    amb["env_por_workload"]["A1"].update(NOSQL_STORAGE_ENDPOINT=f"{s_ip}:8000", NOSQL_STORAGE_TABLE_shopping_cart=TABELA)
    amb["env_por_workload"]["A2"].update(MINIO_ADDRESS=f"{m_ip}:9000")
    AMB.write_text(json.dumps(amb, indent=2, ensure_ascii=False) + "\n")
    print("ambiente_local.json atualizado.")


if __name__ == "__main__":
    main()
