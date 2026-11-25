"""Gera dados/radares.csv a partir de fontes oficiais de dados abertos.

Fontes:
  - ANTT, conjunto "Radar" (rodovias federais concedidas), licença CC-BY.
    https://dados.antt.gov.br/dataset/radar
  - SEINFRA/SIT-Bahia, KML oficial dos radares das rodovias estaduais
    (https://www.ba.gov.br/infraestrutura/12046/mapas). O script baixa o arquivo
    "Mapa-Radar_*.rar" mais recente da página, extrai o KML (precisa do 7-Zip) e
    salva por cima de dados/radares_ba_seinfra.kml.
  - Transalvador (Prefeitura de Salvador), mapa oficial de radares.
  - Prefeitura de Belo Horizonte, "Fiscalização Eletrônica" (dados abertos, CC-BY), só os
    controladores de velocidade. https://dados.pbh.gov.br/dataset/fiscalizacao-eletronica
  - DNIT, "Controle de Velocidade" (PNCV, dados abertos): rodovias federais sem concessão,
    todo o Brasil. A planilha não traz o limite; usa-se o do ponto do OpenStreetMap que
    estiver a menos de 60 m, quando houver.
    https://servicos.dnit.gov.br/dadosabertos/dataset/controle-de-velocidade
  - OpenStreetMap (colaborativo, NÃO oficial): radares mapeados na Bahia, exceto Salvador
    (que tem a lista oficial da Transalvador), e no Distrito Federal (Brasília e regiões
    administrativas; os dados oficiais do Detran-DF/DER-DF não abrem fora do Brasil) e em Minas Gerais
    e Espírito Santo (DER-MG e DER-ES publicam só rodovia + km, sem coordenadas). Cobre rodovias federais sem concessão
    (DNIT) e cidades sem lista oficial. Pontos a menos de 60 m de um radar oficial são
    ignorados.
  - dados/radares_ssa_extra.csv: redutores e pontos de radar portátil da Transalvador,
    que o site lista só por endereço (coordenadas obtidas no OpenStreetMap, revisadas).
    https://transonline.salvador.ba.gov.br/geral_sistema/web/index.php/mapa/mapa-porticos

Se uma fonte falhar, os radares dela da versão anterior de radares.csv são mantidos.

Uso:  python dados/gerar_radares.py
"""
import csv
import html
import io
import json
import math
import os
import re
import shutil
import subprocess
import tempfile
import time
import zipfile
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from urllib.parse import urljoin

TRANSALVADOR = "https://transonline.salvador.ba.gov.br/geral_sistema/web/index.php/mapa/mapa-porticos"
DNIT_API = "https://servicos.dnit.gov.br/dadosabertos/api/3/action/package_show?id=controle-de-velocidade"
PBH_WFS = ("https://bhmap.pbh.gov.br/v2/api/idebhgeo/wfs?service=WFS&version=2.0.0&request=GetFeature"
           "&typeNames=ide_bhgeo:FISCALIZACAO_ELETRONICA&outputFormat=application/json&srsName=EPSG:4326")
SEINFRA_MAPAS = "https://www.ba.gov.br/infraestrutura/12046/mapas"
ANTT_API = "https://dados.antt.gov.br/api/3/action/package_show?id=radar"
PASTA = os.path.dirname(os.path.abspath(__file__))
SAIDA = os.path.join(PASTA, "radares.csv")
KML_BA = os.path.join(PASTA, "radares_ba_seinfra.kml")
# "atualizado" = data da última edição do ponto (só OpenStreetMap). "fonte" fica sempre por último.
CAMPOS = ["lat", "lon", "limite", "rodovia", "km", "sentido", "atualizado", "fonte"]
TIMEOUT = 280  # o portal da ANTT costuma ser lento


def baixar(url, dados=None, tentativas=3):
    """GET (ou POST, se houver dados) com novas tentativas: os portais oficiais oscilam."""
    for t in range(tentativas):
        try:
            req = urllib.request.Request(url, dados, headers={"User-Agent": "AlertaVelocidade/1.0 (dados abertos)"})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as r:
                return r.read()
        except Exception:
            if t == tentativas - 1:
                raise
            time.sleep(10 * (t + 1))


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
    # Lê um marcador por vez: com uma regex única sobre a página inteira, um marcador
    # com "Velocidade: N/A" fazia a busca seguir para o marcador seguinte e perdia radares.
    for bloco in s.split('"position":new google.maps.LatLng(')[1:]:
        m = re.match(r"\s*(-?[\d.]+),\s*(-?[\d.]+)\)", bloco)
        balao = re.search(r"setContent\('<b><p>(.*?)<br/>.*?Velocidade:\s*([^<]*)<", bloco, re.S)
        if not m or not balao:
            continue
        if "VSOCR" in bloco[:bloco.find("Velocidade:")]:  # câmera de leitura de placas, não mede velocidade
            continue
        vel = re.match(r"\d+", balao.group(2).strip())  # alguns radares vêm com "N/A": limite desconhecido
        lat, lon, endereco, vel = float(m.group(1)), float(m.group(2)), balao.group(1), vel.group() if vel else 0
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


def linhas_xlsx(bruto):
    """Linhas da 1ª aba de um .xlsx (sem depender de bibliotecas externas)."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    with zipfile.ZipFile(io.BytesIO(bruto)) as z:
        textos = []
        if "xl/sharedStrings.xml" in z.namelist():
            textos = ["".join(t.text or "" for t in si.iter(ns + "t"))
                      for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        aba = sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
        for linha in ET.fromstring(z.read(aba)).iter(ns + "row"):
            celulas = {}
            for c in linha.iter(ns + "c"):
                v = c.find(ns + "v")
                x = v.text if v is not None else "".join(t.text or "" for t in c.iter(ns + "t"))
                if c.get("t") == "s" and x:
                    x = textos[int(x)]
                celulas[re.match("[A-Z]+", c.get("r")).group()] = (x or "").strip()
            yield celulas


def radares_dnit():
    recursos = json.loads(baixar(DNIT_API))["result"]["resources"]
    # Cada edição é um arquivo novo, com mês e ano no nome: ..._07_2026.xlsx
    edicoes = []
    for r in recursos:
        m = re.search(r"(\d{2})_(\d{4})\.xlsx$", r["url"])
        if m:
            edicoes.append((m.group(2), m.group(1), r["url"]))
    ano, mes, url = max(edicoes)
    print("DNIT:", url)
    linhas = linhas_xlsx(baixar(url))
    colunas = {nome: letra for letra, nome in next(linhas).items()}
    for l in linhas:
        campo = lambda nome: l.get(colunas[nome], "")
        m = re.fullmatch(r"\s*(-?[\d.,]+)\s*/\s*(-?[\d.,]+)\s*", campo("Coordenadas (Lat/Long)"))
        if not m:
            continue
        lat, lon = numero(m.group(1)), numero(m.group(2))
        if not (-34 < lat < 6 and -74 < lon < -34):  # fora do Brasil = coordenada inválida
            continue
        try:
            km = f"{numero(campo('Km')):.2f}"
        except ValueError:
            km = ""
        yield {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "limite": 0,  # a planilha não informa
            "rodovia": f"BR-{campo('Rodovia')} ({campo('UF')})",
            "km": km,
            "sentido": "",
            # Sem data de início: provavelmente ainda em instalação quando a planilha saiu
            "fonte": "DNIT" if campo("Início Operação") else "DNIT (sem data de início)",
        }


def radares_bh():
    # Um registro por faixa: junta os que estão na mesma posição com o mesmo limite
    vistos = set()
    for f in json.loads(baixar(PBH_WFS))["features"]:
        p = f["properties"]
        # Fora: detectores de avanço de semáforo, conversão proibida e faixa exclusiva
        if not (p.get("DESC_TIPO_CONTROLADOR_TRANSITO") or "").startswith("Controlador Eletr"):
            continue
        lon, lat = f["geometry"]["coordinates"][:2]
        if not (-20.1 < lat < -19.7 and -44.1 < lon < -43.8):  # fora de Belo Horizonte
            continue
        limite = int(p.get("VELOCIDADE_REGULAMENTAR") or 0)
        if not 10 <= limite <= 120:  # erro de digitação na origem (ex.: 260): limite desconhecido
            limite = 0
        chave = (round(lat, 4), round(lon, 4), limite)
        if chave in vistos:
            continue
        vistos.add(chave)
        yield {
            "lat": round(lat, 6),
            "lon": round(lon, 6),
            "limite": limite,
            "rodovia": (p.get("DESC_LOC_CONTROLADOR_TRANSITO") or "").strip(),
            "km": "",
            "sentido": (p.get("SENTIDO") or "").strip(),
            "fonte": "PBH",
        }


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


# Servidores Overpass, tentados em ordem (o principal costuma ficar lotado)
OVERPASS = ["https://overpass-api.de/api/interpreter",
            "https://overpass.private.coffee/api/interpreter",
            "https://maps.mail.ru/osm/tools/overpass/api/interpreter"]


def radares_osm():
    # Bahia (exceto Salvador, que tem lista oficial) + Distrito Federal (Brasília e regiões administrativas)
    # + Minas Gerais e Espírito Santo (DER-MG e DER-ES só publicam rodovia + km, sem coordenadas)
    q = ('[out:json][timeout:180];area["ISO3166-2"="BR-BA"]->.ba;'
         'area["name"="Salvador"]["admin_level"="8"]->.ssa;area["ISO3166-2"="BR-DF"]->.df;'
         'area["ISO3166-2"="BR-MG"]->.mg;area["ISO3166-2"="BR-ES"]->.es;'
         '((node(area.ba)[highway=speed_camera]; - node(area.ssa)[highway=speed_camera];);'
         'node(area.df)[highway=speed_camera];node(area.mg)[highway=speed_camera];'
         'node(area.es)[highway=speed_camera];);out meta;')
    dados = urllib.parse.urlencode({"data": q}).encode()
    erro = None
    for servidor in OVERPASS:
        try:
            resposta = json.loads(baixar(servidor, dados))
            elementos = resposta["elements"]
            # Consulta interrompida vem com HTTP 200, lista parcial e um "remark"
            if resposta.get("remark") or not elementos:
                raise RuntimeError(resposta.get("remark") or "resposta vazia")
            # Servidor de reserva pode estar meses atrasado: usá-lo apagaria radares recentes
            base = resposta["osm3s"]["timestamp_osm_base"]
            idade = datetime.now(timezone.utc) - datetime.fromisoformat(base.replace("Z", "+00:00"))
            if idade.days > 7:
                raise RuntimeError(f"mapa desatualizado ({base})")
            break
        except Exception as e:
            erro = e
    else:
        raise RuntimeError(f"Overpass indisponível: {erro}")
    for e in elementos:
        t = e.get("tags", {})
        m = re.search(r"\d+", t.get("maxspeed", ""))
        yield {
            "lat": round(e["lat"], 6),
            "lon": round(e["lon"], 6),
            "limite": int(m.group()) if m else 0,
            "rodovia": t.get("name", "") or t.get("ref", ""),
            "km": "",
            "sentido": "",
            "atualizado": e.get("timestamp", "")[:10],
            "fonte": "OpenStreetMap",
        }


def perto(a, b, metros):
    dy = (float(a["lat"]) - float(b["lat"])) * 110540
    dx = (float(a["lon"]) - float(b["lon"])) * 111320 * math.cos(math.radians(float(a["lat"])))
    return dx * dx + dy * dy < metros * metros


def radares_extras():
    caminho = os.path.join(PASTA, "radares_ssa_extra.csv")
    if not os.path.exists(caminho):
        return []
    with open(caminho, encoding="utf-8") as f:
        return list(csv.DictReader(l for l in f if not l.startswith("#")))


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
              ("SEINFRA-BA", "estaduais da Bahia", bahia_atualizada),
              ("PBH", "Belo Horizonte", radares_bh),
              ("DNIT", "federais sem concessão", radares_dnit),
              ("OpenStreetMap", "Bahia exceto Salvador + Distrito Federal + Minas Gerais + Espírito Santo, não oficial", radares_osm)]
    radares, resumo = [], []
    for nome, descricao, funcao in fontes:
        try:
            lista = list(funcao())
            if nome == "DNIT":  # só o que as outras fontes oficiais (com limite) não cobrem
                lista = [r for r in lista if not any(perto(r, o, 60) for o in radares)]
                limites = {(o["lat"], o["lon"]): o["limite"] for f in antigos if f.startswith("DNIT") for o in antigos[f]}
                for r in lista:  # limite já aproveitado do OpenStreetMap em execução anterior
                    r["limite"] = int(limites.get((str(r["lat"]), str(r["lon"])), 0))
            if nome == "OpenStreetMap":  # só o que as fontes oficiais não cobrem
                restantes = []
                for r in lista:
                    vizinhos = [o for o in radares if perto(r, o, 60)]
                    for o in vizinhos:
                        if o["fonte"].startswith("DNIT") and r["limite"]:
                            o["limite"] = r["limite"]
                    if not vizinhos:
                        restantes.append(r)
                lista = restantes
            if not lista and nome != "OpenStreetMap":
                raise RuntimeError("nenhum radar lido")
            situacao = "atualizada"
        except Exception as e:
            lista = [r for f in antigos if f == nome or (nome == "DNIT" and f.startswith("DNIT")) for r in antigos[f]]
            situacao = f"FALHOU ({e}); mantidos os dados anteriores"
        radares += lista
        resumo.append((nome, descricao, lista, situacao))

    extras = radares_extras()
    radares += extras
    for nome in sorted({r["fonte"] for r in extras}):
        resumo.append((nome, "endereços revisados", None, "arquivo radares_ssa_extra.csv"))

    # Remove duplicados (mesma posição em ~10 m)
    vistos, unicos = set(), []
    for r in radares:
        chave = (round(float(r["lat"]), 4), round(float(r["lon"]), 4), r["sentido"])
        if chave not in vistos:
            vistos.add(chave)
            unicos.append(r)
    with open(SAIDA, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=CAMPOS, extrasaction="ignore")
        w.writeheader()
        w.writerows(unicos)

    linhas = ["| Fonte | Radares | Situação |", "|---|---:|---|"]
    for nome, descricao, _, situacao in resumo:
        n = sum(1 for r in unicos if r["fonte"] == nome or (nome == "DNIT" and r["fonte"].startswith("DNIT")))
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
