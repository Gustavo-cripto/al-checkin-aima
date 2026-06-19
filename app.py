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
import urllib.request

from flask import (
    Flask, Response, abort, render_template, request, url_for,
)

from siba import storage, submitter
from siba.countries import lista_ordenada
from siba.models import TIPO_DOC, Boletim, UnidadeHoteleira

BASE = os.path.dirname(os.path.abspath(__file__))
app = Flask(__name__)


NOTIFY_EMAIL = "azulequatorial@outlook.com"

APARTAMENTOS = {
    "C": {"estabelecimento": "0", "chave_acesso": "257585029368", "nome": "Apartamento C"},
    "B": {"estabelecimento": "1", "chave_acesso": "257586504456", "nome": "Apartamento B"},
    "E": {"estabelecimento": "2", "chave_acesso": "257588717088", "nome": "Apartamento E"},
    "F": {"estabelecimento": "3", "chave_acesso": "257590929720", "nome": "Apartamento F"},
    "I": {"estabelecimento": "4", "chave_acesso": "257593142352", "nome": "Apartamento I"},
    "H": {"estabelecimento": "5", "chave_acesso": "257594617440", "nome": "Apartamento H"},
    "G": {"estabelecimento": "6", "chave_acesso": "257929477806", "nome": "Apartamento G"},
    "J": {"estabelecimento": "7", "chave_acesso": "257932431834", "nome": "Apartamento J"},
    "D": {"estabelecimento": "8", "chave_acesso": "258189983535", "nome": "Apartamento D"},
}


def enviar_email_checkin(boletim: Boletim, nome_xml: str, xml: str) -> None:
    """Envia email com XML em anexo via Resend. Silencioso em caso de erro."""
    import base64
    api_key = os.environ.get("RESEND_API_KEY")
    if not api_key:
        app.logger.warning("RESEND_API_KEY não configurado — email não enviado")
        return
    try:
        corpo = f"""
<h2 style="font-family:sans-serif;color:#1f2a37">Novo Check-in — White Sand Apartments</h2>
<table style="font-family:sans-serif;border-collapse:collapse;font-size:14px">
  <tr><td style="padding:5px 16px 5px 0;color:#666;white-space:nowrap">Hóspede</td>
      <td style="padding:5px 0"><b>{boletim.apelido}, {boletim.nome}</b></td></tr>
  <tr><td style="padding:5px 16px 5px 0;color:#666">Nascimento</td>
      <td style="padding:5px 0">{boletim.data_nascimento}</td></tr>
  <tr><td style="padding:5px 16px 5px 0;color:#666">Nacionalidade</td>
      <td style="padding:5px 0">{boletim.nacionalidade}</td></tr>
  <tr><td style="padding:5px 16px 5px 0;color:#666">Documento</td>
      <td style="padding:5px 0">{boletim.tipo_documento} · {boletim.documento_identificacao}</td></tr>
  <tr><td style="padding:5px 16px 5px 0;color:#666">Check-in</td>
      <td style="padding:5px 0">{boletim.data_entrada}</td></tr>
  <tr><td style="padding:5px 16px 5px 0;color:#666">Check-out</td>
      <td style="padding:5px 0">{boletim.data_saida or '—'}</td></tr>
  <tr><td style="padding:5px 16px 5px 0;color:#666">Ficheiro XML</td>
      <td style="padding:5px 0">{nome_xml}</td></tr>
</table>
<p style="font-family:sans-serif;color:#aaa;font-size:11px;margin-top:24px">
  Enviado automaticamente · White Sand Apartments AL Check-in
</p>
"""
        xml_b64 = base64.b64encode(xml.encode("utf-8")).decode("ascii")
        payload = json.dumps({
            "from": "checkin@resend.dev",
            "to": [NOTIFY_EMAIL],
            "subject": f"✅ Check-in: {boletim.apelido}, {boletim.nome} ({boletim.data_entrada})",
            "html": corpo,
            "attachments": [
                {
                    "filename": nome_xml,
                    "content": xml_b64,
                }
            ],
        }).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        urllib.request.urlopen(req, timeout=10)
        app.logger.info("Email enviado para %s (%s)", NOTIFY_EMAIL, nome_xml)
    except Exception as exc:
        app.logger.warning("Email não enviado: %s", exc)


def carregar_config() -> dict:
    """Carrega a configuração.

    Ordem de prioridade:
      1. variável de ambiente SIBA_CONFIG_JSON (usada na cloud/Vercel);
      2. config.json (local);
      3. config.example.json (com aviso).
    """
    env_cfg = os.environ.get("SIBA_CONFIG_JSON")
    if env_cfg:
        return json.loads(env_cfg)

    cfg_path = os.path.join(BASE, "config.json")
    if not os.path.exists(cfg_path):
        cfg_path = os.path.join(BASE, "config.example.json")
        app.logger.warning(
            "config.json não encontrado — a usar config.example.json. "
            "Defina SIBA_CONFIG_JSON ou crie config.json com os dados reais."
        )
    with open(cfg_path, encoding="utf-8") as f:
        return json.load(f)


@app.route("/")
def index():
    return render_template(
        "index.html",
        paises=lista_ordenada(),
        tipos_doc=TIPO_DOC,
        apartamentos=APARTAMENTOS,
    )


@app.route("/checkin", methods=["POST"])
def checkin():
    cfg = carregar_config()
    unidade = UnidadeHoteleira.from_config(cfg)

    # Sobrepor estabelecimento e chave conforme o apartamento selecionado
    apto_key = request.form.get("apartamento", "")
    apto = APARTAMENTOS.get(apto_key)
    if apto:
        unidade.estabelecimento = apto["estabelecimento"]
        unidade.chave_acesso = apto["chave_acesso"]
        unidade.nome = f"WHITE SAND APARTMENTS - {apto['nome'].upper()}"

    boletim = Boletim.from_form(request.form.to_dict())
    erros = boletim.validate()
    if not apto_key:
        erros = (erros or []) + ["Selecione o apartamento."]
    if erros:
        return render_template(
            "index.html",
            paises=lista_ordenada(),
            tipos_doc=TIPO_DOC,
            apartamentos=APARTAMENTOS,
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

    # Notificação por email (silenciosa se não configurado)
    enviar_email_checkin(boletim, ficheiros["nome_xml"], ficheiros["xml"])

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
    xml = storage.obter_xml(nome_xml) if nome_xml else None
    if xml is None:
        abort(404)

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
    conteudo = storage.obter_xml(nome)
    if conteudo is None:
        abort(404)
    return Response(
        conteudo,
        mimetype="application/xml",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


@app.route("/download/dat/<path:nome>")
def download_dat(nome):
    conteudo = storage.obter_dat(nome)
    if conteudo is None:
        abort(404)
    return Response(
        conteudo,
        mimetype="text/plain",
        headers={"Content-Disposition": f'attachment; filename="{nome}"'},
    )


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8000"))
    # host 0.0.0.0 -> acessível a partir do tablet/telemóvel na mesma rede
    app.run(host="0.0.0.0", port=port, debug=True)
