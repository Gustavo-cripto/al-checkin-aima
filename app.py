"""Aplicação web de check-in de hóspedes -> Boletins de Alojamento (SIBA/AIMA).

Fluxo:
  1. O hóspede preenche o formulário no telemóvel/tablet.
  2. Ao submeter, os dados são validados, GUARDADOS em disco (JSON) e é gerado
     logo o XML (BAL.XSD) e o .DAT — antes de qualquer envio. (fallback garantido)
  3. O recepcionista pode descarregar o XML/.DAT, ou carregar em "Submeter à AIMA"
     que tenta o envio automático pelo web service WSSIBA.
  4. Se o envio falhar, os ficheiros continuam prontos para upload manual no portal.

Arrancar:
  pip install -r requirements.txt
  python app.py
  Abrir http://<ip-do-pc>:8000 no tablet/telemóvel (mesma rede Wi-Fi).
"""

from __future__ import annotations

import json
import os

from flask import (
    Flask, abort, render_template, request, send_from_directory, url_for,
)

from siba import storage, submitter
from siba.countries import lista_ordenada
from siba.models import TIPO_DOC, Boletim, UnidadeHoteleira

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)


def carregar_config() -> dict:
    """Carrega config.json (ou config.example.json com aviso)."""
    cfg_path = os.path.join(BASE, "config.json")
    if not os.path.exists(cfg_path):
        cfg_path = os.path.join(BASE, "config.example.json")
        app.logger.warning(
            "config.json não encontrado — a usar config.example.json. "
            "Crie config.json com os dados reais do estabelecimento."
        )
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    return render_template(
        "index.html",
        paises=lista_ordenada(),
        tipos_doc=TIPO_DOC,
    )


@app.route("/checkin", methods=["POST"])
def checkin():
    cfg = carregar_config()
    unidade = UnidadeHoteleira.from_config(cfg)

    boletim = Boletim.from_form(request.form.to_dict())
    erros = boletim.validate()
    if erros:
        return render_template(
            "index.html",
            paises=lista_ordenada(),
            tipos_doc=TIPO_DOC,
            erros=erros,
            valores=request.form.to_dict(),
        ), 400

    # 1) Guardar SEMPRE primeiro (fallback garantido)
    boletim_id = storage.guardar_boletim(boletim, estado="novo")

    # 2) Gerar XML + .DAT
    numero = storage.proximo_numero_ficheiro()
    ficheiros = storage.gerar_ficheiros(unidade, [boletim], numero)
    storage.registar_log(
        f"check-in {boletim_id} {boletim.apelido} {boletim.nome} "
        f"-> ficheiro nº {numero} ({ficheiros['nome_xml']})"
    )

    return render_template(
        "sucesso.html",
        boletim=boletim,
        numero=numero,
        nome_xml=ficheiros["nome_xml"],
        nome_dat=ficheiros["nome_dat"],
        envio_auto=cfg.get("webservice", {}).get("ativo", False),
    )


@app.route("/submeter", methods=["POST"])
def submeter():
    cfg = carregar_config()
    unidade = UnidadeHoteleira.from_config(cfg)
    ws = cfg.get("webservice", {})

    nome_xml = request.form.get("nome_xml", "")
    caminho = os.path.join(storage.DIR_XML, nome_xml)
    if not nome_xml or not os.path.exists(caminho):
        abort(404)
    xml = open(caminho, encoding="utf-8").read()

    resultado = submitter.submeter(
        xml,
        codigo_unidade=unidade.codigo,
        estabelecimento=unidade.estabelecimento,
        chave_acesso=unidade.chave_acesso,
        ambiente=ws.get("ambiente", "teste"),
        soap_namespace=ws.get("soap_namespace", submitter.DEFAULT_NS),
    )
    storage.registar_log(
        f"submissão {nome_xml} ambiente={ws.get('ambiente')} "
        f"sucesso={resultado.sucesso} -> {resultado.mensagem}"
    )

    return render_template(
        "resultado_submissao.html",
        resultado=resultado,
        nome_xml=nome_xml,
        nome_dat=nome_xml.replace(".xml", ".DAT"),
    )


@app.route("/download/xml/<path:nome>")
def download_xml(nome):
    return send_from_directory(storage.DIR_XML, nome, as_attachment=True)


@app.route("/download/dat/<path:nome>")
def download_dat(nome):
    return send_from_directory(storage.DIR_DAT, nome, as_attachment=True)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    # host 0.0.0.0 -> acessível a partir do tablet/telemóvel na mesma rede
    app.run(host="0.0.0.0", port=port, debug=True)
