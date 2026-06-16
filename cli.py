#!/usr/bin/env python3
"""CLI standalone — gerar e/ou submeter boletins sem a interface web.

Útil para testar, para processar em lote, ou para automatizar via cron.
Só usa biblioteca-padrão (não precisa de Flask).

Exemplos:
  # Gerar XML+DAT a partir de um JSON de hóspedes
  python cli.py gerar hospedes_exemplo.json

  # Gerar e submeter logo ao web service
  python cli.py submeter hospedes_exemplo.json

Formato do JSON de entrada: lista de objetos com os campos do formulário
(apelido, nome, nacionalidade, data_nascimento (YYYY-MM-DD), tipo_documento,
documento_identificacao, pais_emissor_documento, pais_residencia_origem,
data_entrada, data_saida, ...). Ver hospedes_exemplo.json.
"""

from __future__ import annotations

import json
import os
import sys

from siba import storage, submitter
from siba.models import Boletim, UnidadeHoteleira

BASE = os.path.dirname(os.path.abspath(__file__))


def _config() -> dict:
    p = os.path.join(BASE, "config.json")
    if not os.path.exists(p):
        p = os.path.join(BASE, "config.example.json")
        print("[aviso] a usar config.example.json — crie config.json com dados reais.")
    return json.load(open(p, encoding="utf-8"))


def _carregar(path: str) -> list[Boletim]:
    dados = json.load(open(path, encoding="utf-8"))
    if isinstance(dados, dict):
        dados = [dados]
    boletins = []
    for i, d in enumerate(dados, 1):
        b = Boletim.from_form(d)
        erros = b.validate()
        if erros:
            print(f"[erro] hóspede #{i} ({d.get('apelido','?')}): {'; '.join(erros)}")
            sys.exit(1)
        boletins.append(b)
    return boletins


def cmd_gerar(path: str, submeter_tambem: bool = False):
    cfg = _config()
    unidade = UnidadeHoteleira.from_config(cfg)
    boletins = _carregar(path)

    for b in boletins:
        storage.guardar_boletim(b, estado="novo")

    numero = storage.proximo_numero_ficheiro()
    f = storage.gerar_ficheiros(unidade, boletins, numero)
    print(f"✓ {len(boletins)} boletim(ns) gerado(s) — ficheiro nº {numero}")
    print(f"  XML: {f['caminho_xml']}")
    print(f"  DAT: {f['caminho_dat']}")

    if submeter_tambem:
        ws = cfg.get("webservice", {})
        print(f"\n→ A submeter ao web service (ambiente={ws.get('ambiente','teste')})...")
        r = submitter.submeter(
            f["xml"],
            codigo_unidade=unidade.codigo,
            estabelecimento=unidade.estabelecimento,
            chave_acesso=unidade.chave_acesso,
            ambiente=ws.get("ambiente", "teste"),
            soap_namespace=ws.get("soap_namespace", submitter.DEFAULT_NS),
        )
        if r.sucesso:
            print(f"✓ Submetido com sucesso: {r.mensagem}")
        else:
            print(f"✗ Submissão falhou: {r.mensagem}")
            print("  Os ficheiros XML/.DAT acima continuam prontos para upload manual.")


def main():
    if len(sys.argv) < 3 or sys.argv[1] not in ("gerar", "submeter"):
        print(__doc__)
        sys.exit(1)
    cmd_gerar(sys.argv[2], submeter_tambem=(sys.argv[1] == "submeter"))


if __name__ == "__main__":
    main()
