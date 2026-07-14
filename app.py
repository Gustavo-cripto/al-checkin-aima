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

# max_hospedes: lotação para comunicação — B e C até 4; restantes até 2.
APARTAMENTOS = {
    "C": {"estabelecimento": "0", "chave_acesso": "257585029368", "nome": "Apartamento C", "max_hospedes": 4},
    "B": {"estabelecimento": "1", "chave_acesso": "257586504456", "nome": "Apartamento B", "max_hospedes": 4},
    "E": {"estabelecimento": "2", "chave_acesso": "257588717088", "nome": "Apartamento E", "max_hospedes": 2},
    "F": {"estabelecimento": "3", "chave_acesso": "257590929720", "nome": "Apartamento F", "max_hospedes": 2},
    "I": {"estabelecimento": "4", "chave_acesso": "257593142352", "nome": "Apartamento I", "max_hospedes": 2},
    "H": {"estabelecimento": "5", "chave_acesso": "257594617440", "nome": "Apartamento H", "max_hospedes": 2},
    "G": {"estabelecimento": "6", "chave_acesso": "257929477806", "nome": "Apartamento G", "max_hospedes": 2},
    "J": {"estabelecimento": "7", "chave_acesso": "257932431834", "nome": "Apartamento J", "max_hospedes": 2},
    "D": {"estabelecimento": "8", "chave_acesso": "258189983535", "nome": "Apartamento D", "max_hospedes": 2},
}

# Campos pessoais recolhidos por hóspede (as datas de estadia são partilhadas).
CAMPOS_HOSPEDE = [
    "nome_completo", "data_nascimento", "local_nascimento", "nacionalidade",
    "tipo_documento", "documento_identificacao", "pais_emissor_documento",
    "pais_residencia_origem", "local_residencia_origem",
]


def gerar_pdf_boletins(boletins: list, apt_nome: str = "") -> bytes:
    """Gera um PDF legível com os dados de todos os hóspedes (um por tabela)."""
    from reportlab.lib.pagesizes import A4
    from reportlab.lib import colors
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm
    import io

    buf = io.BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, topMargin=2*cm, bottomMargin=2*cm,
                            leftMargin=2*cm, rightMargin=2*cm)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle('title', parent=styles['Heading1'], fontSize=16,
                                 textColor=colors.HexColor('#1f7a8c'), spaceAfter=6)
    sub_style = ParagraphStyle('sub', parent=styles['Normal'], fontSize=9,
                               textColor=colors.grey, spaceAfter=12)
    hosp_style = ParagraphStyle('hosp', parent=styles['Heading2'], fontSize=12,
                                textColor=colors.HexColor('#1f7a8c'), spaceBefore=10, spaceAfter=4)

    def fmt_data(d):
        if d and len(d) == 8:
            return f"{d[6:8]}/{d[4:6]}/{d[0:4]}"
        return d or "—"

    subtitulo = ("Apartamento: " + apt_nome + " · " if apt_nome else "")
    story = [
        Paragraph("White Sand Apartments — Boletim de Check-in", title_style),
        Paragraph(f"{subtitulo}{len(boletins)} hóspede(s) · Documento gerado automaticamente", sub_style),
    ]

    for i, boletim in enumerate(boletins, start=1):
        campos = [
            ("Apelido", boletim.apelido),
            ("Nome próprio", boletim.nome or "—"),
            ("Data de nascimento", fmt_data(boletim.data_nascimento)),
            ("Local de nascimento", boletim.local_nascimento or "—"),
            ("Nacionalidade", boletim.nacionalidade),
            ("Tipo de documento", boletim.tipo_documento),
            ("Nº do documento", boletim.documento_identificacao),
            ("País emissor", boletim.pais_emissor_documento),
            ("País de residência", boletim.pais_residencia_origem),
            ("Local de residência", boletim.local_residencia_origem or "—"),
            ("Data de entrada", fmt_data(boletim.data_entrada)),
            ("Data de saída", fmt_data(boletim.data_saida) if boletim.data_saida else "—"),
        ]
        table_data = [[Paragraph(f"<b>{k}</b>", styles['Normal']),
                       Paragraph(str(v), styles['Normal'])] for k, v in campos]
        table = Table(table_data, colWidths=[6*cm, 11*cm])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#f0fafb')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#e2e8f0')),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
        ]))
        titulo_hosp = f"Hóspede {i}: {boletim.nome} {boletim.apelido}".strip()
        story.append(Paragraph(titulo_hosp, hosp_style))
        story.append(table)

    story.append(Spacer(1, 1*cm))
    story.append(Paragraph("Dados comunicados à AIMA (SIBA) conforme lei portuguesa.", styles['Normal']))
    doc.build(story)
    return buf.getvalue()


def enviar_email_checkin(boletins: list, apt_nome: str, nome_xml: str, xml: str,
                         nome_dat: str = "", dat: str = "") -> None:
    """Envia email com PDF/XML/DAT em anexo via Resend. Silencioso em caso de erro."""
    import base64
    api_key = os.environ.get("RESEND_API_KEY")
    app.logger.warning("DEBUG key prefix: %s", (api_key or "")[:8])
    if not api_key:
        app.logger.warning("RESEND_API_KEY não configurado — email não enviado")
        return
    if not boletins:
        return
    principal = boletins[0]
    try:
        linhas_hospedes = "".join(
            f"""<tr>
  <td style="padding:5px 16px 5px 0;color:#666;white-space:nowrap">Hóspede {i}</td>
  <td style="padding:5px 0"><b>{b.apelido}, {b.nome}</b> · {b.nacionalidade}
      · {b.tipo_documento} {b.documento_identificacao}</td></tr>"""
            for i, b in enumerate(boletins, start=1)
        )
        corpo = f"""
<h2 style="font-family:sans-serif;color:#1f2a37">Novo Check-in — White Sand Apartments</h2>
<p style="font-family:sans-serif;font-size:14px;color:#1f2a37">
  <b>{apt_nome or '—'}</b> · {len(boletins)} hóspede(s)
  · Entrada {principal.data_entrada} · Saída {principal.data_saida or '—'}</p>
<table style="font-family:sans-serif;border-collapse:collapse;font-size:14px">
  {linhas_hospedes}
  <tr><td style="padding:5px 16px 5px 0;color:#666">Ficheiro XML</td>
      <td style="padding:5px 0">{nome_xml}</td></tr>
</table>
<div style="font-family:sans-serif;margin-top:16px;padding:12px 16px;background:#eaf7f9;border-left:4px solid #1f7a8c;border-radius:4px">
  📎 <b>Ficheiro para o portal AIMA:</b> {nome_dat or '—'}<br>
  <span style="color:#555;font-size:13px">Um só ficheiro com todos os hóspedes.
  Carregar em siba.ssi.gov.pt &rarr; &Aacute;rea Reservada &rarr; Entrega de Boletins &rarr; Carregamento de Ficheiros</span>
</div>
<p style="font-family:sans-serif;color:#aaa;font-size:11px;margin-top:24px">
  Enviado automaticamente · White Sand Apartments AL Check-in
</p>
"""
        xml_b64 = base64.b64encode(xml.encode("utf-8")).decode("ascii")
        pdf_bytes = gerar_pdf_boletins(boletins, apt_nome)
        pdf_b64 = base64.b64encode(pdf_bytes).decode("ascii")
        nome_pdf = nome_xml.replace(".xml", ".pdf")
        sufixo = f" +{len(boletins) - 1}" if len(boletins) > 1 else ""
        payload = json.dumps({
            "from": "onboarding@resend.dev",
            "to": [NOTIFY_EMAIL],
            "subject": f"✅ Check-in {apt_nome}: {principal.apelido}, {principal.nome}{sufixo} ({principal.data_entrada})",
            "html": corpo,
            "attachments": [
                {"filename": nome_pdf, "content": pdf_b64},
                {"filename": nome_xml, "content": xml_b64},
                *(
                    [{"filename": nome_dat, "content": base64.b64encode(dat.encode("utf-8")).decode("ascii")}]
                    if nome_dat and dat else []
                ),
            ],
        }).encode()
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "WhiteSandApartments/1.0",
            },
        )
        urllib.request.urlopen(req, timeout=10)
        app.logger.info("Email enviado para %s (%s)", NOTIFY_EMAIL, nome_xml)
    except Exception as exc:
        body = getattr(exc, 'read', lambda: b'')()
        app.logger.warning("Email não enviado: %s | body: %s", exc, body)


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
    apt = request.args.get("apt", "")
    apto = APARTAMENTOS.get(apt, {})
    return render_template(
        "index.html",
        paises=lista_ordenada(),
        tipos_doc=TIPO_DOC,
        apt=apt,
        apt_nome=apto.get("nome", ""),
        max_hospedes=apto.get("max_hospedes", 4),
        hospedes=[{}],
    )


def _split_nome(nome_completo: str) -> tuple[str, str]:
    """Separa 'nome completo' em (nome próprio, apelido) para o boletim AIMA."""
    partes = nome_completo.strip().upper().split()
    if len(partes) >= 2:
        return " ".join(partes[:-1]), partes[-1]
    return "", (partes[0] if partes else "")


@app.route("/checkin", methods=["POST"])
def checkin():
    cfg = carregar_config()
    unidade = UnidadeHoteleira.from_config(cfg)

    # Apartamento vem do campo hidden (lido do URL ?apt=X)
    apto_key = request.form.get("apartamento", "")
    apto = APARTAMENTOS.get(apto_key)
    apt_nome = APARTAMENTOS.get(apto_key, {}).get("nome", "")
    max_hospedes = APARTAMENTOS.get(apto_key, {}).get("max_hospedes", 4)
    if apto:
        unidade.estabelecimento = apto["estabelecimento"]
        unidade.chave_acesso = apto["chave_acesso"]
        unidade.nome = f"WHITE SAND APARTMENTS - {apto['nome'].upper()}"

    # Datas de estadia — partilhadas por todos os hóspedes da reserva
    data_entrada = request.form.get("data_entrada", "")
    data_saida = request.form.get("data_saida", "")

    # Ler os campos de cada hóspede como listas paralelas (arrays do formulário)
    valores = {c: request.form.getlist(c) for c in CAMPOS_HOSPEDE}
    n_blocos = max((len(v) for v in valores.values()), default=0)

    hospedes_raw: list[dict] = []   # para repor no formulário em caso de erro
    boletins: list[Boletim] = []
    erros: list[str] = []

    for i in range(n_blocos):
        def get(campo):
            lst = valores[campo]
            return lst[i] if i < len(lst) else ""

        nome_completo = get("nome_completo").strip()
        if not nome_completo:
            continue  # bloco de hóspede vazio -> ignorado

        raw = {c: get(c) for c in CAMPOS_HOSPEDE}
        hospedes_raw.append(raw)

        nome, apelido = _split_nome(nome_completo)
        boletim = Boletim.from_form({
            "apelido": apelido,
            "nome": nome,
            "data_nascimento": get("data_nascimento"),
            "local_nascimento": get("local_nascimento"),
            "nacionalidade": get("nacionalidade"),
            "tipo_documento": get("tipo_documento"),
            "documento_identificacao": get("documento_identificacao"),
            "pais_emissor_documento": get("pais_emissor_documento"),
            "pais_residencia_origem": get("pais_residencia_origem"),
            "local_residencia_origem": get("local_residencia_origem"),
            "data_entrada": data_entrada,
            "data_saida": data_saida,
        })
        for e in boletim.validate():
            erros.append(f"Hóspede {len(boletins) + 1}: {e}")
        boletins.append(boletim)

    if not boletins:
        erros.insert(0, "Preencha os dados de pelo menos um hóspede.")

    if erros:
        return render_template(
            "index.html",
            paises=lista_ordenada(),
            tipos_doc=TIPO_DOC,
            apt=apto_key,
            apt_nome=apt_nome,
            max_hospedes=max_hospedes,
            hospedes=hospedes_raw or [{}],
            datas={"data_entrada": data_entrada, "data_saida": data_saida},
            erros=erros,
        ), 400

    # 1) Guardar SEMPRE primeiro (fallback garantido)
    for boletim in boletins:
        storage.guardar_boletim(boletim, estado="novo")

    # 2) Gerar UM XML + UM .DAT com todos os hóspedes
    numero = storage.proximo_numero_ficheiro()
    ficheiros = storage.gerar_ficheiros(unidade, boletins, numero)
    nomes = ", ".join(f"{b.apelido} {b.nome}".strip() for b in boletins)
    storage.registar_log(
        f"check-in {apt_nome} [{len(boletins)} hóspede(s): {nomes}] "
        f"-> ficheiro nº {numero} ({ficheiros['nome_xml']})"
    )

    # Notificação por email (silenciosa se não configurado)
    enviar_email_checkin(
        boletins, apt_nome, ficheiros["nome_xml"], ficheiros["xml"],
        ficheiros["nome_dat"], ficheiros["dat"],
    )

    return render_template(
        "sucesso.html",
        boletins=boletins,
        boletim=boletins[0],
        n_hospedes=len(boletins),
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
