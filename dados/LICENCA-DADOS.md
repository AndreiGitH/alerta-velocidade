# Licença dos dados de radares

O arquivo [`radares.csv`](radares.csv) junta várias fontes. Cada linha indica a sua na
coluna `fonte`.

| Fonte | Origem | Licença |
|---|---|---|
| `ANTT` | [Dados abertos da ANTT — Radar](https://dados.antt.gov.br/dataset/radar) | Creative Commons Atribuição (CC-BY) |
| `SEINFRA-BA` | [SEINFRA-BA — Mapas](https://www.ba.gov.br/infraestrutura/12046/mapas) | Dado público (Resolução CONTRAN 798/2020) |
| `Transalvador`, `Transalvador (redutor)`, `Transalvador (portátil)` | [Mapa de radares da Transalvador](https://transonline.salvador.ba.gov.br/geral_sistema/web/index.php/mapa/mapa-porticos) | Dado público (Resolução CONTRAN 798/2020) |
| `OpenStreetMap` | [OpenStreetMap](https://www.openstreetmap.org), via Overpass API | **ODbL 1.0** |

## OpenStreetMap

Contém dados **© colaboradores do OpenStreetMap**, disponíveis sob a
[Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1-0/).
Veja <https://www.openstreetmap.org/copyright>.

Como `radares.csv` é uma base de dados derivada que inclui dados do OpenStreetMap, ela é
distribuída sob a **ODbL 1.0**: pode ser usada, copiada e adaptada livremente, desde que
se mantenha este crédito e que versões modificadas distribuídas publicamente continuem
sob a ODbL.

A coluna `atualizado` traz a data da última edição de cada ponto no OpenStreetMap
(colaborativo, não oficial). Radares podem ter sido desativados depois dessa data.
