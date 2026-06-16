"""Geração do XML dos Boletins de Alojamento conforme o esquema BAL.XSD do SIBA.

Estrutura (campos conforme spec oficial "Modos de Envio"):
  <BoletinsAlojamento>
    <Unidade_Hoteleira> ... </Unidade_Hoteleira>
    <Boletim_Alojamento> ... </Boletim_Alojamento>   (um por hóspede, repetido)
    <Envio> ... </Envio>
  </BoletinsAlojamento>

NOTA: os nomes dos elementos seguem os nomes de campo documentados. Caso o
BAL.XSD oficial use um namespace ou nomes ligeiramente diferentes, ajustar aqui
num único sítio. O conteúdo dos dados está correto e validado.
"""

from __future__ import annotations

from datetime import datetime
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring

from .models import Boletim, UnidadeHoteleira


def _txt(parent: Element, tag: str, valor: str) -> None:
    """Cria <tag>valor</tag> apenas se valor não for vazio."""
    if valor is None or str(valor) == "":
        return
    el = SubElement(parent, tag)
    el.text = str(valor)


def construir_xml(
    unidade: UnidadeHoteleira,
    boletins: list[Boletim],
    numero_ficheiro: int,
    data_movimento: str | None = None,
) -> Element:
    """Constrói a árvore XML dos boletins. Não inclui a chave de acesso."""
    if data_movimento is None:
        data_movimento = datetime.now().strftime("%Y%m%d")

    root = Element("BoletinsAlojamento")

    uh = SubElement(root, "Unidade_Hoteleira")
    _txt(uh, "Codigo_Unidade_Hoteleira", unidade.codigo)
    _txt(uh, "Estabelecimento", unidade.estabelecimento)
    _txt(uh, "Nome", unidade.nome[:40])
    _txt(uh, "Abreviatura", unidade.abreviatura[:15])
    _txt(uh, "Morada", unidade.morada[:40])
    _txt(uh, "Localidade", unidade.localidade[:30])
    _txt(uh, "Codigo_Postal", unidade.codigo_postal)
    _txt(uh, "Zona_Postal", unidade.zona_postal)
    _txt(uh, "Telefone", unidade.telefone)
    _txt(uh, "Fax", unidade.fax)
    _txt(uh, "Nome_Contacto", unidade.nome_contacto[:40])
    _txt(uh, "Email_Contacto", unidade.email_contacto[:140])

    for b in boletins:
        ba = SubElement(root, "Boletim_Alojamento")
        _txt(ba, "Apelido", b.apelido[:40])
        _txt(ba, "Nome", b.nome[:40])
        _txt(ba, "Nacionalidade", b.nacionalidade)
        _txt(ba, "Data_Nascimento", b.data_nascimento)
        _txt(ba, "Local_Nascimento", b.local_nascimento[:30])
        _txt(ba, "Documento_Identificacao", b.documento_identificacao[:16])
        _txt(ba, "Tipo_Documento_Identificacao", b.tipo_documento)
        _txt(ba, "Pais_Emissor_Documento", b.pais_emissor_documento)
        _txt(ba, "Data_Entrada", b.data_entrada)
        _txt(ba, "Data_Saida", b.data_saida)
        _txt(ba, "Pais_Residencia_Origem", b.pais_residencia_origem)
        _txt(ba, "Local_Residencia_Origem", b.local_residencia_origem[:30])

    envio = SubElement(root, "Envio")
    _txt(envio, "Numero_Ficheiro", str(numero_ficheiro))
    _txt(envio, "Data_Movimento", data_movimento)

    return root


def xml_string(
    unidade: UnidadeHoteleira,
    boletins: list[Boletim],
    numero_ficheiro: int,
    data_movimento: str | None = None,
    pretty: bool = True,
) -> str:
    root = construir_xml(unidade, boletins, numero_ficheiro, data_movimento)
    raw = tostring(root, encoding="utf-8")
    if pretty:
        return minidom.parseString(raw).toprettyxml(indent="  ", encoding="utf-8").decode("utf-8")
    return '<?xml version="1.0" encoding="utf-8"?>\n' + raw.decode("utf-8")
