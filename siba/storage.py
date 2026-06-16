"""Persistência com dois backends, escolhidos automaticamente:

  * FICHEIRO (local, no teu Mac/tablet): grava em data/ — JSON, XML, .DAT e logs.
    É o comportamento original e a base do fallback "info guardada na pasta".

  * POSTGRES (cloud / Vercel): se existir a variável de ambiente POSTGRES_URL
    (ou DATABASE_URL), os dados vão para uma base de dados Postgres, porque a
    Vercel tem sistema de ficheiros só de leitura. Os XML/.DAT são guardados
    como texto na BD e gerados/servidos a pedido.

A API pública é a mesma nos dois casos, por isso app.py e cli.py não mudam.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime

from . import dat_generator, xml_generator
from .models import Boletim, UnidadeHoteleira

DATABASE_URL = os.environ.get("POSTGRES_URL") or os.environ.get("DATABASE_URL")
USE_DB = bool(DATABASE_URL)

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(BASE, "data")
DIR_BOLETINS = os.path.join(DATA, "boletins")
DIR_XML = os.path.join(DATA, "xml")
DIR_DAT = os.path.join(DATA, "dat")
DIR_LOG = os.path.join(DATA, "log")
SEQ_FILE = os.path.join(DATA, "sequence.txt")


# ---------------------------------------------------------------------------
# Backend POSTGRES
# ---------------------------------------------------------------------------
_DB_READY = False


def _conn():
    import psycopg2  # import tardio: só necessário no modo cloud
    return psycopg2.connect(DATABASE_URL)


def _init_db() -> None:
    global _DB_READY
    if _DB_READY:
        return
    with _conn() as c, c.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS boletins (
                id TEXT PRIMARY KEY,
                dados JSONB NOT NULL,
                estado TEXT NOT NULL DEFAULT 'novo',
                numero_ficheiro INTEGER,
                criado_em TIMESTAMPTZ DEFAULT now(),
                atualizado_em TIMESTAMPTZ
            );
            CREATE TABLE IF NOT EXISTS lotes (
                numero_ficheiro INTEGER PRIMARY KEY,
                nome_xml TEXT, xml TEXT,
                nome_dat TEXT, dat TEXT,
                criado_em TIMESTAMPTZ DEFAULT now()
            );
            CREATE TABLE IF NOT EXISTS logs (
                id SERIAL PRIMARY KEY,
                ts TIMESTAMPTZ DEFAULT now(),
                mensagem TEXT
            );
            CREATE SEQUENCE IF NOT EXISTS siba_numero_ficheiro_seq START 1;
            """
        )
        c.commit()
    _DB_READY = True


# ---------------------------------------------------------------------------
# Backend FICHEIRO
# ---------------------------------------------------------------------------
def _ensure_dirs() -> None:
    for d in (DIR_BOLETINS, DIR_XML, DIR_DAT, DIR_LOG):
        os.makedirs(d, exist_ok=True)


# ---------------------------------------------------------------------------
# API pública
# ---------------------------------------------------------------------------
def proximo_numero_ficheiro() -> int:
    """Devolve o próximo Numero_Ficheiro sequencial."""
    if USE_DB:
        _init_db()
        with _conn() as c, c.cursor() as cur:
            cur.execute("SELECT nextval('siba_numero_ficheiro_seq')")
            n = int(cur.fetchone()[0])
            c.commit()
        return n

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
    """Grava o boletim e devolve o id."""
    if not boletim.id:
        boletim.id = uuid.uuid4().hex[:12]
    if not boletim.criado_em:
        boletim.criado_em = datetime.now().isoformat(timespec="seconds")

    registo = boletim.to_dict()
    registo["estado"] = estado  # novo | submetido | erro_submissao

    if USE_DB:
        _init_db()
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO boletins (id, dados, estado) VALUES (%s, %s, %s) "
                "ON CONFLICT (id) DO UPDATE SET dados = EXCLUDED.dados, "
                "estado = EXCLUDED.estado",
                (boletim.id, json.dumps(registo, ensure_ascii=False), estado),
            )
            c.commit()
        return boletim.id

    _ensure_dirs()
    caminho = os.path.join(DIR_BOLETINS, f"{boletim.id}.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(registo, f, ensure_ascii=False, indent=2)
    return boletim.id


def atualizar_estado(boletim_id: str, estado: str, detalhe: str = "") -> None:
    if USE_DB:
        _init_db()
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "UPDATE boletins SET estado = %s, atualizado_em = now(), "
                "dados = jsonb_set(dados, '{detalhe_submissao}', to_jsonb(%s::text)) "
                "WHERE id = %s",
                (estado, detalhe, boletim_id),
            )
            c.commit()
        return

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
    """Gera o XML e o .DAT do lote e guarda-os. Devolve conteúdo e nomes."""
    xml = xml_generator.xml_string(unidade, boletins, numero_ficheiro)
    dat = dat_generator.construir_dat(unidade, boletins, numero_ficheiro)
    nome_dat = dat_generator.nome_ficheiro_dat(unidade, numero_ficheiro)
    nome_xml = nome_dat.replace(".DAT", ".xml")

    if USE_DB:
        _init_db()
        with _conn() as c, c.cursor() as cur:
            cur.execute(
                "INSERT INTO lotes (numero_ficheiro, nome_xml, xml, nome_dat, dat) "
                "VALUES (%s, %s, %s, %s, %s) ON CONFLICT (numero_ficheiro) DO UPDATE "
                "SET nome_xml=EXCLUDED.nome_xml, xml=EXCLUDED.xml, "
                "nome_dat=EXCLUDED.nome_dat, dat=EXCLUDED.dat",
                (numero_ficheiro, nome_xml, xml, nome_dat, dat),
            )
            c.commit()
        caminho_xml = caminho_dat = None
    else:
        _ensure_dirs()
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


def obter_xml(nome: str) -> str | None:
    """Devolve o conteúdo XML de um lote pelo nome do ficheiro, ou None."""
    if USE_DB:
        _init_db()
        with _conn() as c, c.cursor() as cur:
            cur.execute("SELECT xml FROM lotes WHERE nome_xml = %s", (nome,))
            row = cur.fetchone()
        return row[0] if row else None
    caminho = os.path.join(DIR_XML, nome)
    return open(caminho, encoding="utf-8").read() if os.path.exists(caminho) else None


def obter_dat(nome: str) -> str | None:
    """Devolve o conteúdo .DAT de um lote pelo nome do ficheiro, ou None."""
    if USE_DB:
        _init_db()
        with _conn() as c, c.cursor() as cur:
            cur.execute("SELECT dat FROM lotes WHERE nome_dat = %s", (nome,))
            row = cur.fetchone()
        return row[0] if row else None
    caminho = os.path.join(DIR_DAT, nome)
    return open(caminho, encoding="utf-8").read() if os.path.exists(caminho) else None


def registar_log(mensagem: str) -> None:
    if USE_DB:
        try:
            _init_db()
            with _conn() as c, c.cursor() as cur:
                cur.execute("INSERT INTO logs (mensagem) VALUES (%s)", (mensagem,))
                c.commit()
        except Exception:
            pass  # log nunca deve quebrar o fluxo
        return
    _ensure_dirs()
    with open(os.path.join(DIR_LOG, "envios.log"), "a", encoding="utf-8") as f:
        f.write(f"{datetime.now().isoformat(timespec='seconds')}  {mensagem}\n")
