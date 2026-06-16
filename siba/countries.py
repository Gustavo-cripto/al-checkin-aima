"""Lista de países / códigos de 3 letras para nacionalidade e país emissor.

IMPORTANTE: o SIBA usa a "Lista de Países/Códigos ICAO". A grande maioria coincide
com o ISO 3166-1 alpha-3 (o mesmo que está impresso na zona de leitura óptica dos
passaportes). Esta lista cobre as nacionalidades mais comuns em alojamento local em
Portugal. Para a lista oficial completa, consultar:
  https://siba.ssi.gov.pt/ajuda/  ("Lista de Países/Códigos ICAO")

Para acrescentar/corrigir códigos, basta editar o dicionário PAISES.
"""

from __future__ import annotations

# código -> nome (PT). Ordenado depois por nome no dropdown.
PAISES: dict[str, str] = {
    "PRT": "Portugal",
    "ESP": "Espanha",
    "FRA": "França",
    "GBR": "Reino Unido",
    "IRL": "Irlanda",
    "DEU": "Alemanha",
    "NLD": "Países Baixos",
    "BEL": "Bélgica",
    "LUX": "Luxemburgo",
    "CHE": "Suíça",
    "AUT": "Áustria",
    "ITA": "Itália",
    "POL": "Polónia",
    "CZE": "República Checa",
    "SVK": "Eslováquia",
    "HUN": "Hungria",
    "ROU": "Roménia",
    "BGR": "Bulgária",
    "GRC": "Grécia",
    "DNK": "Dinamarca",
    "SWE": "Suécia",
    "NOR": "Noruega",
    "FIN": "Finlândia",
    "ISL": "Islândia",
    "EST": "Estónia",
    "LVA": "Letónia",
    "LTU": "Lituânia",
    "UKR": "Ucrânia",
    "RUS": "Rússia",
    "TUR": "Turquia",
    "USA": "Estados Unidos",
    "CAN": "Canadá",
    "BRA": "Brasil",
    "MEX": "México",
    "ARG": "Argentina",
    "CHL": "Chile",
    "COL": "Colômbia",
    "URY": "Uruguai",
    "VEN": "Venezuela",
    "AGO": "Angola",
    "MOZ": "Moçambique",
    "CPV": "Cabo Verde",
    "GNB": "Guiné-Bissau",
    "STP": "São Tomé e Príncipe",
    "ZAF": "África do Sul",
    "MAR": "Marrocos",
    "DZA": "Argélia",
    "TUN": "Tunísia",
    "EGY": "Egito",
    "ISR": "Israel",
    "ARE": "Emirados Árabes Unidos",
    "SAU": "Arábia Saudita",
    "IND": "Índia",
    "PAK": "Paquistão",
    "CHN": "China",
    "JPN": "Japão",
    "KOR": "Coreia do Sul",
    "THA": "Tailândia",
    "VNM": "Vietname",
    "PHL": "Filipinas",
    "IDN": "Indonésia",
    "MYS": "Malásia",
    "SGP": "Singapura",
    "AUS": "Austrália",
    "NZL": "Nova Zelândia",
}


def nome_pais(codigo: str) -> str:
    """Devolve o nome do país para um código, ou o próprio código se desconhecido."""
    return PAISES.get((codigo or "").upper(), codigo)


def lista_ordenada() -> list[tuple[str, str]]:
    """Lista de (codigo, nome) ordenada por nome, para preencher dropdowns."""
    return sorted(PAISES.items(), key=lambda kv: kv[1])


def valido(codigo: str) -> bool:
    return (codigo or "").upper() in PAISES
