"""Persistência local — tudo é guardado na pasta do projeto (data/).

Esta é a base do sistema de fallback: cada check-in fica gravado em disco como
JSON, XML e .DAT ANTES de qualquer tentativa de submissão. Se o web service
falhar (ou a internet cair), nada se perde e os ficheiros prontos a enviar
ficam disponíveis.

Estrutura:
  data/boletins/   -> 1 JSON por hóspede (dados normalizados + estado)
  data/xml/        -> XML gerado por cada lote
  data/dat/        -> ficheiro .DAT gerado por cada lote
  data/log/        -> registo de envios (envios.log)
  data/sequence.txt-> contador do Numero_Ficheiro
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

from . import dat_generator, xml_generator
from .models import Boletim, UnidadeHoteleira

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
DIR_BOLETINS = os.path.join(DATA, "boletins")
DIR_XML = os.path.join(DATA, "xml")
DIR_DAT = os.path.join(DATA, "dat")
DIR_LOG = os.path.join(DATA, "log")
SEQ_FILE = os.path.join(DATA, "sequence.txt")


def _ensure_dirs() -> None:
    for d in (DIR_BOLETINS, DIR_XML, DIR_DAT, DIR_LOG):
        os.makedirs(d, exist_ok=True)


def proximo_numero_ficheiro() -> int:
    """Lê e incrementa o contador sequencial do Numero_Ficheiro."""
    _ensure_dirs()
    n = 0
    if os.path.exists(SEQ_FILE):
        try:
            n = int(open(SEQ_FILE).read().strip() or "0")
        except ValueError:
            n = 0
    n += 1
    with open(SEQ_FILE, "w") as f:
        f.write(str(n))
    return n


def guardar_boletim(boletim: Boletim, estado: str = "novo") -> str:
    """Grava o boletim como JSON e devolve o id."""
    _ensure_dirs()
    if not boletim.id:
        boletim.id = uuid.uuid4().hex[:12]
    if not boletim.criado_em:
        boletim.criado_em = datetime.now().isoformat(timespec="seconds")

    registo = boletim.to_dict()
    registo["estado"] = estado  # novo | submetido | erro_submissao
    caminho = os.path.join(DIR_BOLETINS, f"{boletim.id}.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(registo, f, ensure_ascii=False, indent=2)
    return boletim.id


def atualizar_estado(boletim_id: str, estado: str, detalhe: str = "") -> None:
    caminho = os.path.join(DIR_BOLETINS, f"{boletim_id}.json")
    if not os.path.exists(caminho):
        return
    with open(caminho, encoding="utf-8") as f:
        registo = json.load(f)
    registo["estado"] = estado
    if detalhe:
        registo["detalhe_submissao"] = detalhe
    registo["atualizado_em"] = datetime.now().isoformat(timespec="seconds")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(registo, f, ensure_ascii=False, indent=2)


def gerar_ficheiros(
    unidade: UnidadeHoteleira,
    boletins: list[Boletim],
    numero_ficheiro: int,
) -> dict:
    """Gera e grava o XML e o .DAT do lote. Devolve os caminhos."""
    _ensure_dirs()
    xml = xml_generator.xml_string(unidade, boletins, numero_ficheiro)
    dat = dat_generator.construir_dat(unidade, boletins, numero_ficheiro)

    nome_dat = dat_generator.nome_ficheiro_dat(unidade, numero_ficheiro)
    nome_xml = nome_dat.replace(".DAT", ".xml")

    caminho_xml = os.path.join(DIR_XML, nome_xml)
    caminho_dat = os.path.join(DIR_DAT, nome_dat)

    with open(caminho_xml, "w", encoding="utf-8") as f:
        f.write(xml)
    with open(caminho_dat, "w", encoding="utf-8") as f:
        f.write(dat)

    return {
        "xml": xml,
        "dat": dat,
        "caminho_xml": caminho_xml,
        "caminho_dat": caminho_dat,
        "nome_xml": nome_xml,
        "nome_dat": nome_dat,
        "numero_ficheiro": numero_ficheiro,
    }


def registar_log(mensagem: str) -> None:
    _ensure_dirs()
    with open(os.path.join(DIR_LOG, "envios.log"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}  {mensagem}\n")
