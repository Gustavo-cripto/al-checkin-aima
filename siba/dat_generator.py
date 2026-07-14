"""Geração do ficheiro .DAT (formato de UPLOAD por ficheiro do SIBA).

Formato de registos separados por '|':
  - Registo tipo 0 (cabeçalho): dados da unidade hoteleira
  - Registo tipo 1 (hóspede): um por boletim
  - Registo tipo 9 (sumário): contagem total de registos

Nome do ficheiro: <NIF><Estabelecimento><NumeroFicheiro>.DAT

Serve de SEGUNDA camada de fallback: se o web service falhar, este ficheiro pode
ser carregado manualmente no portal SIBA (Modo de envio: Upload de ficheiro).
"""

from __future__ import annotations

from datetime import datetime

from .models import Boletim, UnidadeHoteleira

TIPO_FICHEIRO = "BA03"


def _campo(valor: str) -> str:
    """Remove o separador '|' de um valor para não corromper o registo."""
    return (str(valor) if valor is not None else "").replace("|", " ")


def construir_dat(
    unidade: UnidadeHoteleira,
    boletins: list[Boletim],
    numero_ficheiro: int,
    data_movimento: str | None = None,
) -> str:
    if data_movimento is None:
        data_movimento = datetime.now().strftime("%Y%m%d")

    linhas: list[str] = []

    # Registo 0 — cabeçalho
    linhas.append("|".join(_campo(c) for c in [
        "0",
        TIPO_FICHEIRO,
        unidade.codigo,
        unidade.estabelecimento,
        unidade.nome[:40],
        unidade.morada[:40],
        unidade.localidade[:30],
        unidade.codigo_postal,
        unidade.zona_postal,
        unidade.telefone,
        unidade.fax,
        unidade.nome_contacto[:40],
        unidade.email_contacto[:140],
    ]))

    # Registos 1 — hóspedes
    for b in boletins:
        linhas.append("|".join(_campo(c) for c in [
            "1",
            b.apelido[:40],
            b.nome[:40],
            b.nacionalidade,
            b.local_nascimento[:40],
            b.data_nascimento,
            b.documento_identificacao[:16],
            b.tipo_documento,
            b.pais_emissor_documento,
            b.pais_residencia_origem,
            b.local_residencia_origem[:30],
            b.data_entrada,
            b.data_saida,
        ]))

    # Registo 9 — fecho: apenas "9|<nº total de registos>" (inclui o próprio
    # registo 9). O portal SIBA rejeita o fecho com mais campos do que este
    # ("Registo de fecho de ficheiro com número de campos inválido").
    numero_registos = len(linhas) + 1
    linhas.append(f"9|{numero_registos}")

    return "\r\n".join(linhas) + "\r\n"


def nome_ficheiro_dat(unidade: UnidadeHoteleira, numero_ficheiro: int) -> str:
    return f"{unidade.codigo}{unidade.estabelecimento}{numero_ficheiro}.DAT"
