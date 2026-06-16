"""Submissão automática dos boletins pelo web service oficial WSSIBA — o "robô".

Em vez de automatizar cliques no portal (frágil e quebra a cada mudança do site),
usamos o web service SOAP oficial do SIBA:

  Método: EntregaBoletinsAlojamento(UnidadeHoteleira, Estabelecimento,
                                    ChaveAcesso, Boletins) As String
  Boletins = conteúdo XML (BAL.XSD) codificado em Base64

Endpoints (conforme spec oficial):
  Testes:    https://siba.sef.pt/bawsdev/boletinsalojamento.asmx
  Produção:  https://siba.sef.pt/baws/boletinsalojamento.asmx

Só usa biblioteca-padrão (urllib). Não há dependências externas.

NOTA: o namespace SOAP do serviço (SOAP_NS) deve ser confirmado no WSDL
(.../boletinsalojamento.asmx?wsdl). O valor por defeito é o típico de serviços
.asmx; é configurável em config.json -> webservice.soap_namespace.
"""

from __future__ import annotations

import base64
import urllib.request
from xml.etree import ElementTree as ET

ENDPOINTS = {
    "teste": "https://siba.sef.pt/bawsdev/boletinsalojamento.asmx",
    "producao": "https://siba.sef.pt/baws/boletinsalojamento.asmx",
}
DEFAULT_NS = "http://siba.sef.pt/"  # confirmar no WSDL


class ResultadoSubmissao:
    def __init__(self, sucesso: bool, mensagem: str, resposta_raw: str = ""):
        self.sucesso = sucesso
        self.mensagem = mensagem
        self.resposta_raw = resposta_raw

    def __repr__(self) -> str:
        return f"<ResultadoSubmissao sucesso={self.sucesso} msg={self.mensagem!r}>"


def _envelope(ns: str, codigo: str, estabelecimento: str,
              chave: str, boletins_b64: str) -> bytes:
    return (
        '<?xml version="1.0" encoding="utf-8"?>'
        '<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">'
        "<soap:Body>"
        f'<EntregaBoletinsAlojamento xmlns="{ns}">'
        f"<UnidadeHoteleira>{codigo}</UnidadeHoteleira>"
        f"<Estabelecimento>{estabelecimento}</Estabelecimento>"
        f"<ChaveAcesso>{chave}</ChaveAcesso>"
        f"<Boletins>{boletins_b64}</Boletins>"
        "</EntregaBoletinsAlojamento>"
        "</soap:Body>"
        "</soap:Envelope>"
    ).encode("utf-8")


def submeter(
    xml_boletins: str,
    *,
    codigo_unidade: str,
    estabelecimento: str,
    chave_acesso: str,
    ambiente: str = "teste",
    soap_namespace: str = DEFAULT_NS,
    timeout: int = 30,
) -> ResultadoSubmissao:
    """Submete o XML dos boletins ao web service WSSIBA.

    Devolve sempre um ResultadoSubmissao (nunca lança) para que o chamador possa
    cair no fallback de forma controlada.
    """
    endpoint = ENDPOINTS.get(ambiente, ENDPOINTS["teste"])
    boletins_b64 = base64.b64encode(xml_boletins.encode("utf-8")).decode("ascii")
    corpo = _envelope(soap_namespace, codigo_unidade, estabelecimento,
                      chave_acesso, boletins_b64)

    req = urllib.request.Request(
        endpoint,
        data=corpo,
        headers={
            "Content-Type": "text/xml; charset=utf-8",
            "SOAPAction": f'"{soap_namespace}EntregaBoletinsAlojamento"',
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except Exception as exc:  # rede, timeout, HTTP error, etc.
        return ResultadoSubmissao(False, f"Falha de comunicação: {exc}", "")

    # A resposta do método vem dentro de <EntregaBoletinsAlojamentoResult>.
    resultado = _extrair_resultado(raw)
    if resultado is None:
        return ResultadoSubmissao(False, "Resposta inesperada do servidor", raw)

    # Convenção SIBA: resposta começa por código; "0" / "OK" = sucesso.
    sucesso = resultado.strip().upper().startswith(("0", "OK", "SUCESSO"))
    return ResultadoSubmissao(sucesso, resultado.strip(), raw)


def _extrair_resultado(raw: str) -> str | None:
    try:
        root = ET.fromstring(raw)
    except ET.ParseError:
        return None
    for el in root.iter():
        tag = el.tag.split("}")[-1]
        if tag == "EntregaBoletinsAlojamentoResult":
            return el.text or ""
    return None
