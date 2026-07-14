"""Geração do ficheiro .DAT (formato de UPLOAD por ficheiro do SIBA).

Especificação oficial (SIBA -> Ajuda -> Modos de Envio -> Upload de Ficheiros):
  - O ficheiro tem 3 tipos de registo:
      Tipo 0  -> Registo de Cabeçalho (dados da Unidade Hoteleira)
      Tipo 1  -> Registo de Boletim   (um por hóspede)
      Tipo 9  -> Registo de Resumo    (fecho: total de registos, data, nº série)
  - REGRA-CHAVE: "Os campos terminam todos com um caracter | (pipe)". O pipe é
    TERMINADOR (não separador): cada campo, INCLUINDO o último, é seguido de '|'.
    Ex.: um registo de fecho válido é  9|3|20260714|1|
    (Faltar o '|' final faz o portal contar menos campos e rejeitar com
     "Registo de fecho de ficheiro com número de campos inválido".)

Nome do ficheiro: <NIF><Estabelecimento><NumeroFicheiro>.DAT

Serve de SEGUNDA camada de fallback: se o web service falhar, este ficheiro pode
ser carregado manualmente no portal SIBA (Modo de envio: Upload de ficheiro).
"""

from __future__ import annotations

from datetime import datetime

from .models import Boletim, UnidadeHoteleira

TIPO_FICHEIRO = "BA03"


def _campo(valor: str) -> str:
    """Remove o terminador '|' de um valor para não corromper o registo."""
    return (str(valor) if valor is not None else "").replace("|", " ")


def _registo(campos: list) -> str:
    """Constrói um registo em que CADA campo termina com '|' (incl. o último)."""
    return "".join(f"{_campo(c)}|" for c in campos)


def construir_dat(
    unidade: UnidadeHoteleira,
    boletins: list[Boletim],
    numero_ficheiro: int,
    data_movimento: str | None = None,
) -> str:
    if data_movimento is None:
        data_movimento = datetime.now().strftime("%Y%m%d")

    linhas: list[str] = []

    # Registo 0 — cabeçalho (13 campos)
    linhas.append(_registo([
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

    # Registos 1 — hóspedes (13 campos cada)
    for b in boletins:
        linhas.append(_registo([
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

    # Registo 9 — resumo/fecho (4 campos): tipo, nº total de registos (inclui
    # este), data de geração (AAAAMMDD) e nº de série do ficheiro.
    numero_registos = len(linhas) + 1
    linhas.append(_registo([
        "9",
        str(numero_registos),
        data_movimento,
        str(numero_ficheiro),
    ]))

    return "\r\n".join(linhas) + "\r\n"


def nome_ficheiro_dat(unidade: UnidadeHoteleira, numero_ficheiro: int) -> str:
    return f"{unidade.codigo}{unidade.estabelecimento}{numero_ficheiro}.DAT"
