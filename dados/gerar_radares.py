"""Gera dados/radares.csv a partir de fontes oficiais de dados abertos.

Fontes:
  - ANTT, conjunto "Radar" (rodovias federais concedidas), licença CC-BY.
    https://dados.antt.gov.br/dataset/radar
  - SEINFRA/SIT-Bahia, KML oficial dos radares das rodovias estaduais
    (https://www.ba.gov.br/infraestrutura/12046/mapas). O script baixa o arquivo
    "Mapa-Radar_*.rar" mais recente da página, extrai o KML (precisa do 7-Zip) e
    salva por cima de dados/radares_ba_seinfra.kml.
  - Transalvador (Prefeitura de Salvador), mapa oficial de radares.
    https://transonline.salvador.ba.gov.br/geral_sistema/web/index.php/mapa/mapa-porticos

Se uma fonte falhar, os radares dela da versão anterior de radares.csv são mantidos.

Uso:  python dados/gerar_radares.py
"""
import csv
import html
import io
import json
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
import urllib.request
import xml.etree.ElementTree as ET
from urllib.parse import urljoin

TRANSALVADOR = "https://transonline.salvador.ba.gov.br/geral_sistema/web/index.php/mapa/mapa-porticos"
SEINFRA_MAPAS = "https://www.ba.gov.br/infraestrutura/12046/mapas"
ANTT_API = "https://dados.antt.gov.br/api/3/action/package_show?id=radar"
PASTA = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(PASTA, "radares.csv")
KML_BA = os.path.join(PASTA, "radares_ba_seinfra.kml")
CAMPOS = ["lat", "lon", "limite", "rodovia", "km", "sentido", "fonte"]
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


def sete_zip():
    for c in (shutil.which("7z"), shutil.which("7zz"), r"C:\Program Files\7-Zip\7z.exe"):
        if c and os.path.exists(c):
            return c
    raise RuntimeError("7-Zip não encontrado (necessário para abrir o .rar da SEINFRA)")


def atualizar_kml_bahia():
    """Baixa o mapa de radares mais recente da página da SEINFRA e grava o KML em KML_BA."""
    pagina = baixar(SEINFRA_MAPAS).decode("utf-8", "replace")
    links = re.findall(r'href="([^"]*Mapa-Radar[^"]*\.(?:rar|zip|kmz|kml))"', pagina, re.I)
    if not links:
        raise RuntimeError("link do Mapa-Radar não encontrado na página da SEINFRA")
    url = urljoin(SEINFRA_MAPAS, links[0])
    print("SEINFRA-BA:", url)
    dados = baixar(url)
    ext = url.rsplit(".", 1)[-1].lower()
    with tempfile.TemporaryDirectory() as tmp:
        arquivo = os.path.join(tmp, "mapa." + ext)
        with open(arquivo, "wb") as f:
            f.write(dados)
        if ext == "kml":
            kml = arquivo
        elif ext in ("zip", "kmz"):
            with zipfile.ZipFile(arquivo) as z:
                z.extractall(tmp)
            kml = None
        else:
            subprocess.run([sete_zip(), "x", "-y", "-o" + tmp, arquivo], check=True, capture_output=True)
            kml = None
        if kml is None:
            achados = [os.path.join(r, n) for r, _, ns in os.walk(tmp) for n in ns if n.lower().endswith(".kml")]
            if not achados:
                raise RuntimeError("nenhum .kml dentro de " + url)
            kml = achados[0]
        ET.parse(kml)  # garante que é um KML válido antes de sobrescrever
        shutil.copyfile(kml, KML_BA)


def radares_bahia():
    caminho = KML_BA
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


def anteriores():
    """Radares da versão atual de radares.csv, por fonte (usados se uma fonte falhar)."""
    por_fonte = {}
    if os.path.exists(SAIDA):
        with open(SAIDA, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                por_fonte.setdefault(r["fonte"], []).append(r)
    return por_fonte


def bahia_atualizada():
    atualizar_kml_bahia()
    return radares_bahia()


def main():
    antigos = anteriores()
    fontes = [("ANTT", "federais concedidas", radares_antt),
              ("Transalvador", "Salvador", radares_transalvador),
              ("SEINFRA-BA", "estaduais da Bahia", bahia_atualizada)]
    radares, resumo = [], []
    for nome, descricao, funcao in fontes:
        try:
            lista = list(funcao())
            if not lista:
                raise RuntimeError("nenhum radar lido")
            situacao = "atualizada"
        except Exception as e:
            lista = antigos.get(nome, [])
            situacao = f"FALHOU ({e}); mantidos os dados anteriores"
        radares += lista
        resumo.append((nome, descricao, lista, situacao))

    # Remove duplicados (mesma posição em ~10 m)
    vistos, unicos = set(), []
    for r in radares:
        chave = (round(float(r["lat"]), 4), round(float(r["lon"]), 4), r["sentido"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(r)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS)
        w.writeheader()
        w.writerows(unicos)

    linhas = ["| Fonte | Radares | Situação |", "|---|---:|---|"]
    for nome, descricao, _, situacao in resumo:
        n = sum(1 for r in unicos if r["fonte"] == nome)
        linhas.append(f"| {nome} ({descricao}) | {n} | {situacao} |")
    linhas.append(f"| **Total** | **{len(unicos)}** | |")
    tabela = "\n".join(linhas)
    print(tabela)
    # No GitHub Actions, a tabela aparece no resumo da execução
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as f:
            f.write("## Radares\n\n" + tabela + "\n")


if __name__ == "__main__":
    main()
