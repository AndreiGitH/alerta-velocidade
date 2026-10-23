"""Gera dados/radares.csv a partir de fontes oficiais de dados abertos.

Fontes:
  - ANTT, conjunto "Radar" (rodovias federais concedidas), licença CC-BY.
    https://dados.antt.gov.br/dataset/radar
  - SEINFRA/SIT-Bahia, KML oficial dos radares das rodovias estaduais
    (https://www.ba.gov.br/infraestrutura/12046/mapas). Baixe o KML novo e salve
    como dados/radares_ba_seinfra.kml para atualizar.
  - Transalvador (Prefeitura de Salvador), mapa oficial de radares.
    https://transonline.salvador.ba.gov.br/geral_sistema/web/index.php/mapa/mapa-porticos

Uso:  python dados/gerar_radares.py
"""
import csv
import html
import io
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET

TRANSALVADOR = "https://transonline.salvador.ba.gov.br/geral_sistema/web/index.php/mapa/mapa-porticos"
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


def radares_transalvador():
    # Mapa oficial de radares da Transalvador: cada marcador do Google Maps traz a
    # posição e, no balão, endereço/sentido, tipo e velocidade.
    bruto = baixar(TRANSALVADOR)
    try:
        s = bruto.decode("utf-8")
    except UnicodeDecodeError:
        s = bruto.decode("latin-1")
    padrao = re.compile(
        r"\"position\":new google\.maps\.LatLng\((-?[\d.]+),\s*(-?[\d.]+)\).*?setContent\('<b><p>(.*?)<br/>.*?<br/><br/>([^<]*)<br/>.*?Velocidade:\s*(\d+)",
        re.S)
    for lat, lon, endereco, tipo, vel in padrao.findall(s):
        lat, lon = float(lat), float(lon)
        if not (-13.1 < lat < -12.7 and -38.7 < lon < -38.2):  # fora de Salvador
            continue
        sentido = ""
        m = re.search(r"/\s*(SENTIDO.*)$", endereco, re.I)
        if m:
            sentido = m.group(1).strip()
            endereco = endereco[:m.start()].strip()
        yield {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "limite": int(vel),
            "rodovia": html.unescape(endereco).strip(),
            "km": "",
            "sentido": html.unescape(sentido),
            "fonte": "Transalvador",
        }


def radares_bahia():
    caminho = os.path.join(os.path.dirname(SAIDA), "radares_ba_seinfra.kml")
    if not os.path.exists(caminho):
        return
    ns = {"k": "http://www.opengis.net/kml/2.2"}
    for pm in ET.parse(caminho).getroot().iter("{http://www.opengis.net/kml/2.2}Placemark"):
        d = {sd.get("name"): (sd.text or "").strip() for sd in pm.iterfind(".//k:SimpleData", ns)}
        try:
            lat, lon = float(d["LATITUDE"]), float(d["LONGITUDE"])
        except (KeyError, ValueError):
            continue
        if not (-19 < lat < -8 and -47 < lon < -37):  # fora da Bahia
            continue
        m = re.search(r"\d+", d.get("VELOCIDADE", ""))
        yield {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "limite": int(m.group()) if m else 0,
            "rodovia": d.get("RODOVIA", "").replace("BA", "BA-", 1) if d.get("RODOVIA", "").startswith("BA") else d.get("RODOVIA", ""),
            "km": d.get("KM", ""),
            "sentido": d.get("MUNICIPIO", "").title(),
            "fonte": "SEINFRA-BA",
        }


def main():
    radares = list(radares_antt())
    ssa = list(radares_transalvador())
    print(f"Transalvador: {len(ssa)} radares")
    radares += ssa
    ba = list(radares_bahia())
    print(f"SEINFRA-BA: {len(ba)} radares")
    radares += ba
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
