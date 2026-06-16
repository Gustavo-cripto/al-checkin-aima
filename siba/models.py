"""Modelos de dados e validação para os Boletins de Alojamento (SIBA).

Campos baseados na especificação oficial do SIBA (esquema BAL.XSD), publicada em
https://siba.ssi.gov.pt/ajuda/modos-de-envio/

Regras de caracteres (conforme spec):
  - Nome / Apelido: [A-Z], [ÇÃÁÀÉÊÍÕÔÓÚ'-] e espaço. Não pode começar por espaço.
  - Documento de identificação: apenas [0-9] e [A-Z].
  - Datas: formato YYYYMMDD.
  - Nacionalidade / País: código de 3 letras (ICAO/ISO-3166 alpha-3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict
from datetime import date, datetime
from typing import Optional


# Tipos de documento aceites pelo SIBA
TIPO_DOC = {
    "P": "Passaporte",
    "B": "Cartão de Cidadão / Bilhete de Identidade",
    "O": "Outro",
}

# Caracteres permitidos em nomes (maiúsculas, acentos PT, apóstrofo, hífen, espaço)
_NOME_OK = set("ABCDEFGHIJKLMNOPQRSTUVWXYZÇÃÁÀÉÊÍÕÔÓÚ'- ")
_DOC_OK = set("0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ")


class ValidationError(ValueError):
    """Erro de validação de um campo do boletim."""


def sanitize_nome(valor: str) -> str:
    """Coloca em maiúsculas e remove caracteres não permitidos em nomes."""
    if valor is None:
        return ""
    v = valor.strip().upper()
    v = "".join(c for c in v if c in _NOME_OK)
    v = re.sub(r"\s+", " ", v).strip()
    return v


def sanitize_documento(valor: str) -> str:
    """Coloca em maiúsculas e mantém apenas [0-9A-Z]."""
    if valor is None:
        return ""
    return "".join(c for c in valor.strip().upper() if c in _DOC_OK)


def _parse_data(valor) -> str:
    """Aceita 'YYYY-MM-DD', 'YYYYMMDD', date/datetime e devolve 'YYYYMMDD'."""
    if valor in (None, ""):
        return ""
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%Y%m%d")
    v = str(valor).strip()
    for fmt in ("%Y-%m-%d", "%Y%m%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(v, fmt).strftime("%Y%m%d")
        except ValueError:
            continue
    raise ValidationError(f"Data inválida: {valor!r} (use YYYY-MM-DD)")


@dataclass
class UnidadeHoteleira:
    """Dados do estabelecimento (cabeçalho). Vêm da configuração, não do hóspede."""

    codigo: str          # NIPC, 9 dígitos
    estabelecimento: str  # número atribuído pelo SEF/AIMA (até 4 dígitos)
    chave_acesso: str    # chave de acesso ao web service (só usada na submissão)
    nome: str
    abreviatura: str
    morada: str
    localidade: str
    codigo_postal: str   # 4 primeiros dígitos
    zona_postal: str     # 3 últimos dígitos
    telefone: str
    nome_contacto: str
    email_contacto: str
    fax: str = ""

    @classmethod
    def from_config(cls, cfg: dict) -> "UnidadeHoteleira":
        u = cfg["unidade_hoteleira"]
        return cls(
            codigo=str(u["codigo"]).strip(),
            estabelecimento=str(u["estabelecimento"]).strip(),
            chave_acesso=str(u.get("chave_acesso", "")).strip(),
            nome=u["nome"].strip(),
            abreviatura=u["abreviatura"].strip(),
            morada=u["morada"].strip(),
            localidade=u["localidade"].strip(),
            codigo_postal=str(u["codigo_postal"]).strip(),
            zona_postal=str(u["zona_postal"]).strip(),
            telefone=str(u["telefone"]).strip(),
            nome_contacto=u["nome_contacto"].strip(),
            email_contacto=u["email_contacto"].strip(),
            fax=str(u.get("fax", "")).strip(),
        )


@dataclass
class Boletim:
    """Um boletim de alojamento = um hóspede."""

    apelido: str
    nacionalidade: str          # 3 letras
    data_nascimento: str        # YYYYMMDD
    documento_identificacao: str
    tipo_documento: str         # P, B ou O
    pais_emissor_documento: str  # 3 letras
    data_entrada: str           # YYYYMMDD
    pais_residencia_origem: str  # 3 letras
    nome: str = ""              # opcional se nome único vai no apelido
    local_nascimento: str = ""  # opcional
    data_saida: str = ""        # opcional
    local_residencia_origem: str = ""  # opcional

    # metadados internos (não vão para o XML SIBA)
    id: str = ""
    criado_em: str = ""

    @classmethod
    def from_form(cls, data: dict) -> "Boletim":
        """Cria e normaliza um boletim a partir do formulário/JSON."""
        b = cls(
            apelido=sanitize_nome(data.get("apelido", "")),
            nome=sanitize_nome(data.get("nome", "")),
            nacionalidade=str(data.get("nacionalidade", "")).strip().upper(),
            data_nascimento=_parse_data(data.get("data_nascimento")),
            local_nascimento=str(data.get("local_nascimento", "")).strip().upper()[:30],
            documento_identificacao=sanitize_documento(
                data.get("documento_identificacao", "")
            ),
            tipo_documento=str(data.get("tipo_documento", "")).strip().upper(),
            pais_emissor_documento=str(
                data.get("pais_emissor_documento", "")
            ).strip().upper(),
            pais_residencia_origem=str(
                data.get("pais_residencia_origem", "")
            ).strip().upper(),
            local_residencia_origem=str(
                data.get("local_residencia_origem", "")
            ).strip().upper()[:30],
            data_entrada=_parse_data(data.get("data_entrada")),
            data_saida=_parse_data(data.get("data_saida")),
        )
        return b

    def validate(self) -> list[str]:
        """Devolve uma lista de erros. Lista vazia = válido."""
        erros: list[str] = []

        if not self.apelido:
            erros.append("Apelido é obrigatório.")
        if len(self.apelido) > 40:
            erros.append("Apelido excede 40 caracteres.")
        if len(self.nome) > 40:
            erros.append("Nome excede 40 caracteres.")

        if len(self.nacionalidade) != 3 or not self.nacionalidade.isalpha():
            erros.append("Nacionalidade tem de ser um código de 3 letras.")
        if len(self.pais_emissor_documento) != 3:
            erros.append("País emissor do documento tem de ter 3 letras.")
        if len(self.pais_residencia_origem) != 3:
            erros.append("País de residência tem de ter 3 letras.")

        if not re.fullmatch(r"\d{8}", self.data_nascimento or ""):
            erros.append("Data de nascimento inválida (YYYYMMDD).")
        elif self.data_nascimento >= datetime.now().strftime("%Y%m%d"):
            erros.append("Data de nascimento tem de ser anterior à data atual.")

        if not re.fullmatch(r"\d{8}", self.data_entrada or ""):
            erros.append("Data de entrada inválida (YYYYMMDD).")

        if self.data_saida:
            if not re.fullmatch(r"\d{8}", self.data_saida):
                erros.append("Data de saída inválida (YYYYMMDD).")
            elif self.data_saida < self.data_entrada:
                erros.append("Data de saída não pode ser anterior à entrada.")

        if not self.documento_identificacao:
            erros.append("Número de documento é obrigatório.")
        if len(self.documento_identificacao) > 16:
            erros.append("Número de documento excede 16 caracteres.")

        if self.tipo_documento not in TIPO_DOC:
            erros.append("Tipo de documento tem de ser P, B ou O.")

        return erros

    def to_dict(self) -> dict:
        return asdict(self)
