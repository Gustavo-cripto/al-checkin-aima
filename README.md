# AL Check-in de clientes para AIMA

Sistema de check-in para Alojamento Local que recolhe os dados do hóspede,
gera o **Boletim de Alojamento** no formato oficial **SIBA/AIMA** e o submete
automaticamente — com **fallback garantido** se o envio automático falhar.

## O que faz

1. **Formulário de check-in** — o hóspede preenche no telemóvel/tablet (mobile-first).
2. **Gerador automático** — assim que o hóspede submete, gera logo:
   - o **XML** (esquema `BAL.XSD` do SIBA) — com botão de download;
   - o ficheiro **`.DAT`** (formato de upload manual do portal) — 2.ª camada de fallback.
3. **Submissão automática ("robô")** — em vez de automatizar cliques no portal
   (frágil), usa o **web service oficial WSSIBA** (`EntregaBoletinsAlojamento`),
   que é a forma mais fiável e foi por isso a escolhida.
4. **Fallback** — **tudo é guardado em disco antes de qualquer envio**. Se o web
   service falhar, o XML e o `.DAT` ficam prontos para upload manual, e os dados
   do hóspede permanecem em `data/boletins/`.

## Estrutura

```
app.py                  Aplicação web (Flask)
cli.py                  Gerar/submeter por linha de comandos (sem Flask)
config.example.json     Modelo de configuração (copiar para config.json)
hospedes_exemplo.json   Exemplo de entrada para o CLI
siba/
  models.py             Modelos + validação dos campos
  countries.py          Lista de países / códigos de 3 letras
  xml_generator.py      Geração do XML (BAL.XSD)
  dat_generator.py      Geração do ficheiro .DAT
  submitter.py          Submissão pelo web service WSSIBA (SOAP)
  storage.py            Persistência em data/ (fallback)
templates/ static/      Interface web
data/                   Boletins (JSON), XML, .DAT e logs gerados
```

## Instalação e arranque

```bash
cd "AL Check-in de clientes para AIMA"
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp config.example.json config.json   # e preencher com os dados reais
python app.py
```

Abrir no PC: `http://localhost:8000`
No tablet/telemóvel (mesma rede Wi-Fi): `http://<IP-DO-PC>:8000`

> O núcleo (XML/.DAT/web service) usa **só a biblioteca-padrão**. O `cli.py`
> funciona sem instalar nada: `python3 cli.py gerar hospedes_exemplo.json`.

## Configuração (`config.json`)

| Campo | Descrição |
|-------|-----------|
| `unidade_hoteleira.codigo` | NIPC (9 dígitos) |
| `unidade_hoteleira.estabelecimento` | Nº de estabelecimento atribuído pela AIMA |
| `unidade_hoteleira.chave_acesso` | Chave de acesso ao web service SIBA |
| `webservice.ativo` | `true` liga o botão de submissão automática |
| `webservice.ambiente` | `teste` ou `producao` |
| `webservice.soap_namespace` | Namespace SOAP (confirmar no WSDL) |

## Pontos a confirmar antes de produção

Estes valores vêm da especificação oficial mas devem ser confirmados com a
AIMA/SIBA para o seu estabelecimento, porque a chave e os endpoints são
específicos:

- **Chave de acesso e nº de estabelecimento** — fornecidos pela AIMA.
- **`soap_namespace`** do web service — confirmar em
  `https://siba.sef.pt/baws/boletinsalojamento.asmx?wsdl`.
- **Lista de países/códigos ICAO** — `siba/countries.py` cobre os mais comuns;
  a lista oficial completa está em <https://siba.ssi.gov.pt/ajuda/>.
- **Nomes dos elementos XML** — seguem os campos documentados; se o `BAL.XSD`
  oficial usar nomes/namespace diferentes, ajustar em `siba/xml_generator.py`.

## Especificação de referência

Campos baseados em "Modos de Envio" do SIBA:
<https://siba.ssi.gov.pt/ajuda/modos-de-envio/>

- Web service: `EntregaBoletinsAlojamento(UnidadeHoteleira, Estabelecimento, ChaveAcesso, Boletins)` — `Boletins` = XML em Base64.
- Endpoints: testes `https://siba.sef.pt/bawsdev/...`, produção `https://siba.sef.pt/baws/...`.
- Tipos de documento: `P` (passaporte), `B` (cartão de cidadão/BI), `O` (outro).
- Datas no formato `YYYYMMDD`; nacionalidade/país em código de 3 letras.

## Privacidade (RGPD)

`config.json` e a pasta `data/` (dados pessoais dos hóspedes) estão no
`.gitignore` e **não devem ser versionados nem partilhados**.
