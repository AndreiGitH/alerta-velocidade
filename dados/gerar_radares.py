"""Gera dados/radares.csv a partir de fontes oficiais de dados abertos.

Fonte atual:
  - ANTT, conjunto "Radar" (rodovias federais concedidas), licença CC-BY.
    https://dados.antt.gov.br/dataset/radar

Uso:  python dados/gerar_radares.py
"""
import csv
import io
import json
import os
import urllib.request

ANTT_API = "https://dados.antt.gov.br/api/3/action/package_show?id=radar"
SAIDA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "radares.csv")
TIMEOUT = 280  # o portal da ANTT costuma ser lento


def baixar(url):
    req = urllib.request.Request(url, headers={"User-Agent": "AlertaVelocidade/1.0 (dados abertos)"})
    with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
        return r.read()


def numero(s):
    return float(s.strip().replace(",", "."))


def radares_antt():
    pacote = json.loads(baixar(ANTT_API))["result"]
    csvs = [r for r in pacote["resources"] if (r.get("format") or "").upper() == "CSV"]
    # O conjunto ganha um CSV novo por mês; usa o mais recente
    recurso = max(csvs, key=lambda r: r.get("last_modified") or r.get("created") or "")
    print("ANTT:", recurso["url"])
    bruto = baixar(recurso["url"])
    try:
        texto = bruto.decode("utf-8")
    except UnicodeDecodeError:
        texto = bruto.decode("latin-1")

    for l in csv.DictReader(io.StringIO(texto), delimiter=";"):
        if (l.get("situacao") or "").strip().lower() != "ativo":
            continue
        try:
            lat, lon = numero(l["latitude"]), numero(l["longitude"])
        except (KeyError, ValueError):
            continue
        if not (-34 < lat < 6 and -74 < lon < -34):  # fora do Brasil = coordenada inválida
            continue
        try:
            limite = int(numero(l.get("velocidade_leve") or "0"))
        except ValueError:
            limite = 0
        yield {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "limite": limite,
            "rodovia": l.get("rodovia", "").strip(),
            "km": l.get("km_m", "").strip().replace(",", "."),
            "sentido": l.get("sentido", "").strip(),
            "fonte": "ANTT",
        }


def main():
    radares = list(radares_antt())
    # Remove duplicados (mesma posição em ~10 m)
    vistos, unicos = set(), []
    for r in radares:
        chave = (round(r["lat"], 4), round(r["lon"], 4), r["sentido"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(r)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["lat", "lon", "limite", "rodovia", "km", "sentido", "fonte"])
        w.writeheader()
        w.writerows(unicos)
    print(f"{len(unicos)} radares gravados em {SAIDA}")


if __name__ == "__main__":
    main()
