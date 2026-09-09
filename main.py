import os
from datetime import date, datetime, timedelta
from pathlib import Path
import hashlib
import re
import sqlite3
import unicodedata
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

try:
    import transferegovpy as tg
except Exception:
    tg = None
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates


# ============================================================
# CONFIGURAÇÃO
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = Path(
    os.getenv(
        "CAMINHO_BANCO",
        str(BASE_DIR / "radar.db"),
    )
)

app = FastAPI(title="Radar Investe São Carlos")

app.mount(
    "/static",
    StaticFiles(directory=BASE_DIR / "static"),
    name="static",
)

templates = Jinja2Templates(directory=BASE_DIR / "templates")

AREAS = [
    "Comércio",
    "Startup/Inovação",
    "Indústria",
]

PUBLICOS = [
    "Prefeitura",
    "Empresas",
    "Startups",
    "Todos",
]

TIPOS = [
    "Recurso para Prefeitura",
    "Equipamento/Infraestrutura",
    "Programa estratégico",
    "Recurso para empresas",
    "Recurso para startups",
    "Financiamento para Prefeitura",
    "Financiamento para empresas",
]


STATUS_CAPTACAO = [
    "Encontrada",
    "Analisar edital",
    "Preparar proposta",
    "Inscrição enviada",
    "Aguardando resultado",
    "Aprovada",
    "Não aderente",
    "Encerrada",
]

FONTES = {
    "MINISTERIO_CIDADES": (
        "https://www.gov.br/cidades/pt-br/acesso-a-informacao/"
        "participacao-social/editais-de-chamamento-publico"
    ),
    "SEMIL": "https://semil.sp.gov.br/editais/",
    "INVESTSP_EXPORTA": "https://investsp.org.br/exportasp/",
    "INVESTSP_CREATIVE": "https://investsp.org.br/creativesp-edicao-2026/",
    "INVESTSP_DISCOVER": "https://investsp.org.br/discover-sp/",
    "CNPQ_ABERTAS": "https://www.gov.br/cnpq/pt-br/chamadas/abertas-para-submissao",
    "BNDES_FINEM": "https://www.bndes.gov.br/wps/portal/site/home/financiamento/bndes-finem",
    "BNDES_INOVACAO": "https://www.bndes.gov.br/wps/portal/site/home/financiamento/produto/bndes-inovacao",
    "BNDES_MPME": "https://www.bndes.gov.br/wps/portal/site/home/financiamento/produto/bndes-credito-pequenas-e-medias-empresas",
    "SP_PRODUZ": "https://spproduz.sp.gov.br/",
    "MEMP_EDITAIS": "https://www.gov.br/memp/pt-br/acesso-a-informacao/editais",
    "SDE_SP_EDITAIS": "https://www.desenvolvimentoeconomico.sp.gov.br/DesenvolvimentoEconomico/transparencia/editais_e_deliberacoes",
    "TRANSFEREGOV_PROGRAMAS": "https://cadastro.transferegov.sistema.gov.br/ep-atos-prep-web/atos-prep/programa/consulta",
    "MEMP_ACTS": "https://www.gov.br/memp/pt-br/acesso-a-informacao/instrumento-e-parcerias/acordos-de-cooperacao-tecnica-acts",
    "MEMP_PORTARIAS": "https://www.gov.br/memp/pt-br/acesso-a-informacao/institucional/atos-normativos/portarias",
    "SDE_ORCAMENTO_2026": "https://portal.fazenda.sp.gov.br/servicos/orcamento/Documents/LOA/%28PLOA%202026%29%20Projeto%20de%20Lei%201036%20de%2030_09_2025_VOL%202.pdf",
    "FINEP_ABERTAS": "https://www.finep.gov.br/chamadas-publicas?situacao=aberta&tFonte=0",
    "FINEP_PRORROGACOES_2026": "https://faleconosco.finep.gov.br/web/guest/w/aten%C3%A7%C3%A3o-novos-prazos",
    "NOVO_PAC": "https://www.gov.br/cidades/pt-br/novo-pac-selecoes-2026",
    "TRANSFEREGOV_API": "https://api-publica.transferegov.gestao.gov.br/",
    "TRANSFEREGOV_DOWNLOADS": "https://api-publica.transferegov.gestao.gov.br/downloads",
    "TRANSFEREGOV_PARcerias": "https://parcerias.transferegov.sistema.gov.br/",
    "TRANSFEREGOV_CONSULTA": (
        "https://discricionarias.transferegov.sistema.gov.br/"
        "voluntarias/ForwardAction.do?Pwd=guest&Usr=guest"
        "&modulo=programa&path=%2FConsultarPrograma%2FConsultarPrograma.do"
    ),
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 RadarInvesteSaoCarlos/4.0"
    )
}

TERMOS_BLOQUEADOS = [
    "base industrial de defesa",
    "armamento",
    "armamentos",
    "munição",
    "munições",
    "arma de fogo",
]

TERMOS_PREFEITURA = [
    "municipio",
    "municipios",
    "prefeitura",
    "prefeituras",
    "administracao municipal",
    "ente municipal",
    "entes municipais",
    "governo municipal",
    "poder executivo municipal",
]

TERMOS_INTERESSE = [
    "desenvolvimento economico",
    "desenvolvimento empresarial",
    "comercio",
    "varejo",
    "empreendedorismo",
    "empreendedor",
    "microempresa",
    "pequena empresa",
    "industria",
    "industrial",
    "desenvolvimento industrial",
    "infraestrutura industrial",
    "distrito industrial",
    "parque industrial",
    "reindustrializacao",
    "manufatura avancada",
    "industria 4.0",
    "eficiencia energetica",
    "descarbonizacao industrial",
    "distrito industrial",
    "arranjo produtivo",
    "cadeia produtiva",
    "inovacao",
    "tecnologia",
    "transformacao digital",
    "economia criativa",
    "parque tecnologico",
    "ecossistema de inovacao",
    "hub de inovacao",
    "centro de inovacao",
    "laboratorio de inovacao",
    "inovacao aberta",
    "cidade inteligente",
    "govtech",
    "incubadora",
    "startup",
    "competitividade",
    "produtividade",
    "exportacao",
    "internacionalizacao",
    "qualificacao profissional",
    "capacitacao empresarial",
    "infraestrutura",
    "energia",
    "mobilidade",
    "turismo",
    "saneamento",
    "residuos",
    "clima",
    "urbanismo",
]

TERMOS_EXCLUIR_LICITACAO = [
    "pregao",
    "pregão",
    "dispensa de licitacao",
    "dispensa de licitação",
    "inexigibilidade",
    "registro de precos",
    "registro de preços",
    "contratacao de empresa",
    "contratação de empresa",
    "aquisicao",
    "aquisição",
]


# ============================================================
# BANCO
# ============================================================

def conexao():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def coluna_existe(conn, tabela, coluna):
    cols = conn.execute(f"PRAGMA table_info({tabela})").fetchall()
    return any(c["name"] == coluna for c in cols)


def inicializar_banco():
    with conexao() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS oportunidades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                area TEXT NOT NULL,
                orgao TEXT,
                valor REAL,
                data_final TEXT,
                publico TEXT,
                requisitos TEXT,
                link TEXT,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        migracoes = {
            "fonte": "TEXT",
            "external_id": "TEXT",
            "atualizado_em": "TEXT",
            "motivo_sao_carlos": "TEXT",
            "tipo_oportunidade": "TEXT",
            "prazo_texto": "TEXT",
            "verificado_em": "TEXT",
            "status_captacao": "TEXT",
            "responsavel_captacao": "TEXT",
            "observacoes_captacao": "TEXT",
            "data_status_captacao": "TEXT",
            "prazo_interno": "TEXT",
            "contrapartida": "TEXT",
            "documentos_necessarios": "TEXT",
            "despesas_elegiveis": "TEXT",
            "projeto_relacionado_manual": "TEXT",
            "valor_pretendido": "REAL",
        }

        for coluna, tipo in migracoes.items():
            if not coluna_existe(conn, "oportunidades", coluna):
                conn.execute(
                    f"ALTER TABLE oportunidades ADD COLUMN {coluna} {tipo}"
                )

        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_oportunidades_external_id
            ON oportunidades(external_id)
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS projetos_prefeitura (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nome TEXT NOT NULL,
                area TEXT NOT NULL,
                descricao TEXT,
                valor_estimado REAL,
                termos_busca TEXT,
                responsavel TEXT,
                fontes_monitoradas TEXT,
                status TEXT NOT NULL DEFAULT 'Buscando recurso',
                ativo INTEGER NOT NULL DEFAULT 1,
                criado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        if not coluna_existe(conn, "projetos_prefeitura", "fontes_monitoradas"):
            conn.execute(
                """
                ALTER TABLE projetos_prefeitura
                ADD COLUMN fontes_monitoradas TEXT
                """
            )

        # Primeiro projeto municipal do Radar
        existe_onibus = conn.execute(
            """
            SELECT id
            FROM projetos_prefeitura
            WHERE nome = ?
            LIMIT 1
            """,
            ("Ônibus da Ciência",),
        ).fetchone()

        if not existe_onibus:
            conn.execute(
                """
                INSERT INTO projetos_prefeitura
                (
                    nome,
                    area,
                    descricao,
                    valor_estimado,
                    termos_busca,
                    responsavel,
                    fontes_monitoradas,
                    status,
                    ativo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    "Ônibus da Ciência",
                    "Startup/Inovação",
                    (
                        "Veículo itinerante de ciência, tecnologia, educação "
                        "e inovação para circular por bairros, escolas, "
                        "universidades, polos de tecnologia e ambientes de inovação."
                    ),
                    800000.0,
                    (
                        "popularização da ciência, divulgação científica, "
                        "educação científica, ciência itinerante, laboratório móvel, "
                        "museu de ciência, STEM, inclusão digital, cultura científica, "
                        "tecnologia educacional, feira de ciências, inovação educacional"
                    ),
                    "Diretoria de Startup/Inovação",
                    (
                        "CNPq/MCTI; Finep/FNDCT; MEC; FAPESP; Transferegov; "
                        "Governo do Estado de São Paulo; Ministério das Cidades; BNDES; SP Produz"
                    ),
                    "Buscando recurso",
                ),
            )

        existe_industria = conn.execute(
            """
            SELECT id
            FROM projetos_prefeitura
            WHERE nome = ?
            LIMIT 1
            """,
            ("São Carlos Indústria Competitiva",),
        ).fetchone()

        if not existe_industria:
            conn.execute(
                """
                INSERT INTO projetos_prefeitura
                (
                    nome,
                    area,
                    descricao,
                    valor_estimado,
                    termos_busca,
                    responsavel,
                    fontes_monitoradas,
                    status,
                    ativo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    "São Carlos Indústria Competitiva",
                    "Indústria",
                    (
                        "Programa municipal para fortalecimento da indústria, "
                        "modernização de distritos e áreas industriais, melhoria "
                        "de infraestrutura, produtividade, qualificação, transição "
                        "energética, inovação industrial e atração de investimentos."
                    ),
                    3000000.0,
                    (
                        "desenvolvimento industrial, infraestrutura industrial, "
                        "distrito industrial, parque industrial, arranjo produtivo, "
                        "cadeia produtiva, produtividade industrial, competitividade, "
                        "manufatura avançada, indústria 4.0, eficiência energética, "
                        "descarbonização industrial, economia circular, logística, "
                        "qualificação profissional, atração de investimentos"
                    ),
                    "Diretoria de Indústria",
                    (
                        "SDE/SP; Transferegov; MDIC; Governo do Estado de São Paulo; "
                        "Ministério das Cidades; SEMIL/SP; SP Produz; BNDES"
                    ),
                    "Buscando recurso",
                ),
            )

        existe_inova = conn.execute(
            """
            SELECT id
            FROM projetos_prefeitura
            WHERE nome = ?
            LIMIT 1
            """,
            ("São Carlos Inova",),
        ).fetchone()

        if not existe_inova:
            conn.execute(
                """
                INSERT INTO projetos_prefeitura
                (
                    nome,
                    area,
                    descricao,
                    valor_estimado,
                    termos_busca,
                    responsavel,
                    fontes_monitoradas,
                    status,
                    ativo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    "São Carlos Inova",
                    "Startup/Inovação",
                    (
                        "Programa municipal para fortalecer o ecossistema de inovação, "
                        "startups, parques e polos tecnológicos, transformação digital, "
                        "inovação aberta, govtech, laboratórios, incubação e conexão "
                        "entre Prefeitura, universidades e empresas."
                    ),
                    2000000.0,
                    (
                        "ecossistema de inovação, hub de inovação, centro de inovação, "
                        "parque tecnológico, incubadora, startup, inovação aberta, "
                        "govtech, cidade inteligente, transformação digital, laboratório "
                        "de inovação, inclusão digital, tecnologia educacional, "
                        "empreendedorismo inovador, ambientes de inovação"
                    ),
                    "Diretoria de Startup/Inovação",
                    (
                        "MCTI/CNPq; Finep/FNDCT; Transferegov; SDE/SP; FAPESP; "
                        "Governo do Estado de São Paulo; MEC; Centro Paula Souza"
                    ),
                    "Buscando recurso",
                ),
            )

        existe_comercio_forte = conn.execute(
            """
            SELECT id
            FROM projetos_prefeitura
            WHERE nome = ?
            LIMIT 1
            """,
            ("São Carlos Comércio Forte",),
        ).fetchone()

        if not existe_comercio_forte:
            conn.execute(
                """
                INSERT INTO projetos_prefeitura
                (
                    nome,
                    area,
                    descricao,
                    valor_estimado,
                    termos_busca,
                    responsavel,
                    fontes_monitoradas,
                    status,
                    ativo
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)
                """,
                (
                    "São Carlos Comércio Forte",
                    "Comércio",
                    (
                        "Programa municipal para fortalecimento e modernização "
                        "do comércio local, com foco em competitividade, "
                        "qualificação, transformação digital, acesso a mercados, "
                        "revitalização de corredores comerciais e melhoria "
                        "do ambiente de negócios."
                    ),
                    1500000.0,
                    (
                        "desenvolvimento do comércio local, fortalecimento do comércio, "
                        "desenvolvimento econômico municipal, revitalização comercial, "
                        "corredores comerciais, varejo, micro e pequenas empresas, "
                        "ambiente de negócios, acesso a mercados, qualificação empresarial, "
                        "empreendedorismo local, economia criativa, feiras de negócios, "
                        "mercado municipal, centro de empreendedorismo, formalização, "
                        "desburocratização, sala do empreendedor, desenvolvimento territorial, "
                        "inclusão produtiva, transformação digital, comércio de bairro"
                    ),
                    "Diretoria de Comércio",
                    (
                        "MEMP; Transferegov; MDIC; Governo do Estado de São Paulo; "
                        "Secretaria de Desenvolvimento Econômico de SP; Sebrae-SP; "
                        "Desenvolve SP; Ministério das Cidades"
                    ),
                    "Buscando recurso",
                ),
            )

        conn.execute(
            """
            UPDATE projetos_prefeitura
            SET fontes_monitoradas = COALESCE(
                NULLIF(fontes_monitoradas, ''),
                ?
            )
            WHERE nome = ?
            """,
            (
                (
                    "CNPq/MCTI; Finep/FNDCT; MEC; FAPESP; Transferegov; "
                    "Governo do Estado de São Paulo; Ministério das Cidades; BNDES; SP Produz"
                ),
                "Ônibus da Ciência",
            ),
        )

        conn.execute(
            """
            UPDATE oportunidades
            SET status_captacao = 'Encontrada'
            WHERE status_captacao IS NULL OR status_captacao = ''
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS metas_captacao (
                id INTEGER PRIMARY KEY CHECK (id = 1),
                meta_anual REAL NOT NULL DEFAULT 5000000,
                atualizado_em TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS radar_config (
                chave TEXT PRIMARY KEY,
                valor TEXT
            )
            """
        )

        conn.execute(
            """
            INSERT OR IGNORE INTO metas_captacao (id, meta_anual)
            VALUES (1, 5000000)
            """
        )

        conn.commit()


@app.on_event("startup")
def startup():
    inicializar_banco()


# ============================================================
# AUXILIARES
# ============================================================

def normalizar(txt: str) -> str:
    txt = unicodedata.normalize("NFKD", txt or "")
    txt = "".join(
        c for c in txt
        if not unicodedata.combining(c)
    )
    return re.sub(r"\s+", " ", txt).strip().lower()


def parse_data_br(texto: str):
    texto = texto or ""

    datas = re.findall(
        r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b",
        texto,
    )

    if datas:
        d, m, a = datas[-1]
        try:
            return date(int(a), int(m), int(d))
        except ValueError:
            pass

    meses = {
        "janeiro": 1,
        "fevereiro": 2,
        "marco": 3,
        "abril": 4,
        "maio": 5,
        "junho": 6,
        "julho": 7,
        "agosto": 8,
        "setembro": 9,
        "outubro": 10,
        "novembro": 11,
        "dezembro": 12,
    }

    nt = normalizar(texto)

    achados = re.findall(
        (
            r"\b(\d{1,2})\s+de\s+"
            r"(janeiro|fevereiro|marco|abril|maio|junho|"
            r"julho|agosto|setembro|outubro|novembro|dezembro)"
            r"\s+de\s+(\d{4})\b"
        ),
        nt,
    )

    if achados:
        d, mes, a = achados[-1]
        try:
            return date(int(a), meses[mes], int(d))
        except ValueError:
            pass

    return None


def extrair_prazo_aberto(texto: str):
    hoje = date.today()
    texto = re.sub(r"\s+", " ", texto or "").strip()

    padroes = [
        r"(?:inscri(?:cao|ção|coes|ções)|propostas?|adesao|adesão|habilitacao|habilitação).{0,180}?(\d{1,2}/\d{1,2}/\d{4})",
        r"(?:ate|até).{0,40}?(\d{1,2}/\d{1,2}/\d{4})",
        r"(\d{1,2}/\d{1,2}/\d{4}).{0,120}?(?:inscri(?:cao|ção|coes|ções)|propostas?|adesao|adesão)",
    ]

    candidatas = []

    for padrao in padroes:
        for data_txt in re.findall(
            padrao,
            texto,
            flags=re.IGNORECASE,
        ):
            d = parse_data_br(data_txt)
            if d:
                candidatas.append(d)

    futuras = [d for d in candidatas if d >= hoje]

    if futuras:
        return max(futuras)

    return None


def extrair_valor(texto: str):
    n = normalizar(texto or "")

    m = re.search(
        r"r\$\s*([\d.,]+)\s*"
        r"(bilh(?:ao|oes)|milh(?:ao|oes)|mil)?",
        n,
    )

    if not m:
        return None

    raw = m.group(1)
    sufixo = m.group(2) or ""

    try:
        if "," in raw and "." in raw:
            num = float(raw.replace(".", "").replace(",", "."))
        elif "," in raw:
            num = float(raw.replace(",", "."))
        else:
            num = (
                float(raw.replace(".", ""))
                if raw.count(".") > 1
                else float(raw)
            )
    except ValueError:
        return None

    if sufixo.startswith("bilh"):
        num *= 1_000_000_000
    elif sufixo.startswith("milh"):
        num *= 1_000_000
    elif sufixo == "mil":
        num *= 1_000

    return num


def classificar_area(nome: str, texto: str):
    n = normalizar(f"{nome} {texto}")

    if any(
        t in n
        for t in [
            "startup",
            "inovacao",
            "tecnolog",
            "digital",
            "parque tecnologico",
    "ecossistema de inovacao",
    "hub de inovacao",
    "centro de inovacao",
    "laboratorio de inovacao",
    "inovacao aberta",
    "cidade inteligente",
    "govtech",
            "incubadora",
        ]
    ):
        return "Startup/Inovação"

    if any(
        t in n
        for t in [
            "industr",
            "manufatura",
            "produtiv",
            "maquina",
            "equipamento",
            "energia",
            "bioeconom",
            "mobilidade",
        ]
    ):
        return "Indústria"

    return "Comércio"


def classificar_publico(texto: str):
    n = normalizar(texto)

    if any(t in n for t in TERMOS_PREFEITURA):
        return "Prefeitura"

    if "startup" in n and "empresa" not in n:
        return "Startups"

    if any(
        t in n
        for t in [
            "empresa",
            "empresas",
            "cooperativa",
            "ict",
            "industria",
        ]
    ):
        return "Empresas"

    return "Todos"


def motivo_sao_carlos(publico: str, area: str):
    if publico == "Prefeitura":
        return (
            "Prioridade máxima: São Carlos pode potencialmente participar "
            "como município/prefeitura. Confirmar os critérios do edital."
        )

    if publico == "Empresas":
        return f"Pode beneficiar empresas de São Carlos na área de {area}."

    if publico == "Startups":
        return (
            "Pode beneficiar startups e o ecossistema de inovação "
            "de São Carlos."
        )

    return "Oportunidade relacionada ao desenvolvimento econômico local."


def tem_interesse_sao_carlos(texto: str):
    n = normalizar(texto)
    return any(normalizar(t) in n for t in TERMOS_INTERESSE)


def parece_licitacao_compra(texto: str):
    n = normalizar(texto)
    return any(normalizar(t) in n for t in TERMOS_EXCLUIR_LICITACAO)


def bloqueado(texto: str):
    n = normalizar(texto)
    return any(normalizar(t) in n for t in TERMOS_BLOQUEADOS)


def external_id(fonte: str, nome: str, link: str):
    base = f"{fonte}|{normalizar(nome)}|{link or ''}"
    return hashlib.sha1(base.encode("utf-8")).hexdigest()


def salvar_oportunidade(item):
    ext = external_id(
        item["fonte"],
        item["nome"],
        item.get("link", ""),
    )

    motivo = item.get(
        "motivo_sao_carlos"
    ) or motivo_sao_carlos(
        item["publico"],
        item["area"],
    )

    with conexao() as conn:
        conn.execute(
            """
            INSERT INTO oportunidades
            (
                nome,
                area,
                orgao,
                valor,
                data_final,
                publico,
                requisitos,
                link,
                fonte,
                external_id,
                atualizado_em,
                motivo_sao_carlos,
                tipo_oportunidade,
                prazo_texto,
                verificado_em
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?)

            ON CONFLICT(external_id)
            DO UPDATE SET
                area = excluded.area,
                orgao = excluded.orgao,
                valor = COALESCE(excluded.valor, oportunidades.valor),
                data_final = excluded.data_final,
                publico = excluded.publico,
                requisitos = excluded.requisitos,
                link = excluded.link,
                fonte = excluded.fonte,
                motivo_sao_carlos = excluded.motivo_sao_carlos,
                tipo_oportunidade = excluded.tipo_oportunidade,
                prazo_texto = excluded.prazo_texto,
                verificado_em = excluded.verificado_em,
                atualizado_em = CURRENT_TIMESTAMP
            """,
            (
                item["nome"],
                item["area"],
                item["orgao"],
                item.get("valor"),
                item.get("data_final") or "",
                item["publico"],
                item["requisitos"],
                item.get("link", ""),
                item["fonte"],
                ext,
                motivo,
                item.get("tipo_oportunidade", "Programa estratégico"),
                item.get("prazo_texto", ""),
                item.get("verificado_em", date.today().isoformat()),
            ),
        )

        conn.commit()


# ============================================================
# COLETOR GENÉRICO PARA PREFEITURAS
# ============================================================

def coletar_links_municipais(
    url_lista: str,
    fonte: str,
    orgao: str,
    limite_links: int = 30,
):
    r = requests.get(
        url_lista,
        timeout=20,
        headers=HEADERS,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")

    hoje = date.today()
    candidatos = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        titulo = re.sub(
            r"\s+",
            " ",
            " ".join(a.stripped_strings),
        ).strip()

        if len(titulo) < 12:
            continue

        link = urljoin(url_lista, a["href"])

        chave = (normalizar(titulo), link)

        if chave in vistos:
            continue

        vistos.add(chave)

        n_titulo = normalizar(titulo)

        if not any(
            termo in n_titulo
            for termo in [
                "edital",
                "chamamento",
                "selecao",
                "seleção",
                "programa",
            ]
        ):
            continue

        if parece_licitacao_compra(titulo):
            continue

        candidatos.append((titulo, link))

        if len(candidatos) >= limite_links:
            break

    itens = []

    for titulo, link in candidatos:
        try:
            rd = requests.get(
                link,
                timeout=15,
                headers=HEADERS,
            )
            rd.raise_for_status()
        except Exception:
            continue

        sd = BeautifulSoup(rd.text, "html.parser")

        texto = re.sub(
            r"\s+",
            " ",
            sd.get_text(" ", strip=True),
        ).strip()

        if bloqueado(titulo + " " + texto):
            continue

        if parece_licitacao_compra(titulo + " " + texto[:1500]):
            continue

        n_texto = normalizar(texto)

        if not any(
            normalizar(t) in n_texto
            for t in TERMOS_PREFEITURA
        ):
            continue

        if not tem_interesse_sao_carlos(titulo + " " + texto):
            continue

        prazo = extrair_prazo_aberto(texto)

        if not prazo or prazo < hoje:
            continue

        area = classificar_area(titulo, texto)

        valor = extrair_valor(texto)

        tipo = (
            "Recurso para Prefeitura"
            if valor
            else "Programa estratégico"
        )

        itens.append(
            {
                "nome": titulo[:300],
                "area": area,
                "orgao": orgao,
                "valor": valor,
                "data_final": prazo.isoformat(),
                "prazo_texto": "",
                "publico": "Prefeitura",
                "requisitos": (
                    "Município/prefeitura aparece como público elegível. "
                    "Consulte o edital para confirmar documentos, "
                    "contrapartida e forma de inscrição."
                ),
                "link": link,
                "fonte": fonte,
                "motivo_sao_carlos": (
                    "Prioridade Prefeitura: o edital menciona municípios "
                    "ou prefeituras e o prazo identificado ainda está aberto."
                ),
                "tipo_oportunidade": tipo,
            }
        )

    return itens


# ============================================================
# FONTES PRIORITÁRIAS
# ============================================================

def coletar_ministerio_cidades():
    return coletar_links_municipais(
        FONTES["MINISTERIO_CIDADES"],
        "Ministério das Cidades",
        "Ministério das Cidades",
    )


def coletar_semil():
    return coletar_links_municipais(
        FONTES["SEMIL"],
        "SEMIL/SP",
        "Governo do Estado de São Paulo / SEMIL",
    )


def coletar_transferegov():
    return []


# ============================================================
# INVESTSP — PROGRAMAS ABERTOS / ESTRATÉGICOS
# ============================================================

def coletar_investsp():
    """
    InvestSP com filtro estrito para São Carlos.

    Só entra no Radar aquilo que a página oficial atual permite
    considerar aberto e aplicável ao município/empresas locais.

    Regras atuais:
    - Discover SP NÃO entra: a página oficial informa participação
      de empresas da cidade de São Paulo.
    - Exporta SP NÃO entra enquanto a página continuar se referindo
      apenas à turma do 1º semestre de 2026.
    - CreativeSP entra quando a página oficial disser explicitamente
      que há inscrições abertas para missões de 2026.
    """

    itens = []
    hoje = date.today()

    # --------------------------------------------------------
    # CreativeSP 2026
    # --------------------------------------------------------
    url = FONTES["INVESTSP_CREATIVE"]

    try:
        r = requests.get(
            url,
            timeout=20,
            headers=HEADERS,
        )
        r.raise_for_status()

        soup = BeautifulSoup(
            r.text,
            "html.parser",
        )

        texto = re.sub(
            r"\s+",
            " ",
            soup.get_text(" ", strip=True),
        ).strip()

        n = normalizar(texto)

        if "inscricoes abertas para as missoes de 2026" in n:
            # Missões futuras listadas na página oficial em setembro/2026.
            futuras = [
                ("Feira do Livro de Frankfurt", date(2026, 10, 7)),
                ("Womex", date(2026, 10, 21)),
                ("Ventana Sur", date(2026, 11, 30)),
            ]

            futuras = [
                nome
                for nome, inicio in futuras
                if inicio >= hoje
            ]

            if futuras:
                itens.append(
                    {
                        "nome": "CreativeSP – Missões internacionais 2026",
                        "area": "Comércio",
                        "orgao": "InvestSP",
                        "valor": None,
                        "data_final": "",
                        "prazo_texto": (
                            "Inscrições abertas – missões futuras em 2026"
                        ),
                        "publico": "Empresas",
                        "requisitos": (
                            "A página oficial informa inscrições abertas para "
                            "as missões de 2026. Missões futuras listadas: "
                            + ", ".join(futuras)
                            + ". Consulte o chamamento e o formulário oficial "
                            "para confirmar setor, documentos e prazo específico."
                        ),
                        "link": url,
                        "fonte": "InvestSP",
                        "motivo_sao_carlos": (
                            "Pode beneficiar empresas de São Carlos ligadas "
                            "à economia criativa e à internacionalização."
                        ),
                        "tipo_oportunidade": "Programa estratégico",
                        "verificado_em": hoje.isoformat(),
                    }
                )

    except Exception as e:
        print(
            "AVISO INVESTSP CreativeSP:",
            f"{type(e).__name__}: {e}",
        )

    # --------------------------------------------------------
    # Exporta SP
    # --------------------------------------------------------
    # A página oficial atual ainda menciona explicitamente a turma
    # do 1º semestre de 2026. Como hoje já é setembro/2026, não
    # tratamos essa chamada como aberta até a página ser atualizada.
    #
    # Discover SP também não entra: a página oficial informa que o
    # programa viabiliza a participação de empresas da cidade de São Paulo.

    return itens


# ============================================================
# SDE/SP — DESENVOLVIMENTO ECONÔMICO E MUNICÍPIOS
# ============================================================

def coletar_sde_sp():
    """
    Monitora a página oficial da Secretaria de Desenvolvimento Econômico
    do Estado de São Paulo.

    Regra conservadora:
    - só entra oportunidade com prazo futuro identificado;
    - município/prefeitura deve aparecer explicitamente como elegível;
    - prioriza comércio, desenvolvimento econômico, empreendedorismo,
      produtividade, qualificação, cadeias produtivas e desenvolvimento regional;
    - resultados, homologações e fases encerradas não entram.
    """

    url = FONTES["SDE_SP_EDITAIS"]

    r = requests.get(
        url,
        timeout=25,
        headers=HEADERS,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    hoje = date.today()

    candidatos = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        titulo = re.sub(
            r"\s+",
            " ",
            " ".join(a.stripped_strings),
        ).strip()

        if len(titulo) < 12:
            continue

        n_titulo = normalizar(titulo)

        if not any(
            termo in n_titulo
            for termo in [
                "edital",
                "fomento",
                "chamamento",
                "selecao",
                "seleção",
                "programa",
            ]
        ):
            continue

        if any(
            termo in n_titulo
            for termo in [
                "resultado",
                "homologacao",
                "homologação",
                "recurso",
                "alteracao do cronograma",
                "alteração do cronograma",
            ]
        ):
            continue

        link = urljoin(url, a["href"])

        chave = (n_titulo, link)
        if chave in vistos:
            continue

        vistos.add(chave)
        candidatos.append((titulo, link))

        if len(candidatos) >= 40:
            break

    itens = []

    for titulo, link in candidatos:
        try:
            rd = requests.get(
                link,
                timeout=18,
                headers=HEADERS,
            )
            rd.raise_for_status()

            sd = BeautifulSoup(rd.text, "html.parser")
            conteudo = re.sub(
                r"\s+",
                " ",
                sd.get_text(" ", strip=True),
            ).strip()
        except Exception:
            continue

        n = normalizar(conteudo)

        if not any(
            normalizar(t) in n
            for t in TERMOS_PREFEITURA
        ):
            continue

        if not any(
            termo in n
            for termo in [
                "desenvolvimento economico",
                "comercio",
                "empreendedorismo",
                "microempresa",
                "pequena empresa",
                "produtividade",
                "competitividade",
                "cadeia produtiva",
                "desenvolvimento regional",
                "qualificacao",
                "inclusao produtiva",
                "arranjo produtivo",
            ]
        ):
            continue

        prazo = extrair_prazo_aberto(conteudo)

        if not prazo or prazo < hoje:
            continue

        area = classificar_area(titulo, conteudo)

        itens.append(
            {
                "nome": titulo[:300],
                "area": area,
                "orgao": "Secretaria de Desenvolvimento Econômico do Estado de São Paulo",
                "valor": extrair_valor(conteudo),
                "data_final": prazo.isoformat(),
                "prazo_texto": "",
                "publico": "Prefeitura",
                "requisitos": (
                    "Oportunidade identificada em fonte oficial da Secretaria "
                    "de Desenvolvimento Econômico de SP com menção a município/"
                    "prefeitura. Confirmar documentação, contrapartida e forma de adesão."
                ),
                "link": link,
                "fonte": "SDE/SP",
                "motivo_sao_carlos": (
                    "Pode apoiar políticas municipais de desenvolvimento econômico, "
                    "comércio, empreendedorismo ou desenvolvimento regional."
                ),
                "tipo_oportunidade": "Recurso para Prefeitura",
                "verificado_em": hoje.isoformat(),
            }
        )

    return itens


# ============================================================
# MEMP — EMPREENDEDORISMO, COMÉRCIO E DESENVOLVIMENTO LOCAL
# ============================================================

def coletar_memp():
    """
    Monitora a página oficial de editais do Ministério do Empreendedorismo.

    Regra rígida:
    - só marca como Prefeitura quando município/prefeitura/ente municipal
      aparece explicitamente como participante/proponente;
    - editais exclusivos para OSC, empresas, artesãos ou pessoas físicas
      não entram como captação municipal;
    - precisa haver prazo futuro identificável;
    - precisa ter relação com comércio, micro e pequenas empresas,
      ambiente de negócios, empreendedorismo ou desenvolvimento territorial.
    """

    url = FONTES["MEMP_EDITAIS"]

    r = requests.get(
        url,
        timeout=20,
        headers=HEADERS,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    texto_pagina = re.sub(
        r"\s+",
        " ",
        soup.get_text(" ", strip=True),
    ).strip()

    hoje = date.today()
    itens = []

    # A página é uma tabela/lista. Vamos analisar blocos que contenham
    # "EDITAL" e tentar identificar o respectivo link oficial.
    for row in soup.find_all(["tr", "p", "div"]):
        bloco = re.sub(
            r"\s+",
            " ",
            row.get_text(" ", strip=True),
        ).strip()

        if len(bloco) < 40:
            continue

        n = normalizar(bloco)

        if "edital" not in n:
            continue

        if not any(
            termo in n
            for termo in [
                "microempresa",
                "microempresas",
                "empresa de pequeno porte",
                "empresas de pequeno porte",
                "ambiente de negocios",
                "empreendedorismo",
                "desenvolvimento territorial",
                "inclusao socioprodutiva",
                "comercio",
                "acesso a mercados",
                "desburocratizacao",
                "inovacao empresarial",
            ]
        ):
            continue

        # Exclui editais claramente não municipais.
        if any(
            termo in n
            for termo in [
                "organizacoes da sociedade civil",
                "organizacao da sociedade civil",
                "oscs",
                "osc ",
                "mestre artesao",
                "mestra artesa",
                "tradutores",
                "interpretes publicos",
            ]
        ):
            continue

        # Município precisa aparecer explicitamente.
        if not any(
            normalizar(t) in n
            for t in TERMOS_PREFEITURA
        ):
            continue

        prazo = extrair_prazo_aberto(bloco)

        if not prazo or prazo < hoje:
            continue

        links = row.find_all("a", href=True)

        link = url
        for a in links:
            candidato = urljoin(url, a["href"])
            if candidato.startswith("http"):
                link = candidato
                break

        nome = bloco[:260]

        itens.append(
            {
                "nome": nome,
                "area": "Comércio",
                "orgao": (
                    "Ministério do Empreendedorismo, "
                    "da Microempresa e da Empresa de Pequeno Porte"
                ),
                "valor": extrair_valor(bloco),
                "data_final": prazo.isoformat(),
                "prazo_texto": "",
                "publico": "Prefeitura",
                "requisitos": (
                    "Edital do MEMP com indicação de participação municipal. "
                    "Confirmar no documento oficial a forma de submissão, "
                    "contrapartida, documentos e despesas elegíveis."
                ),
                "link": link,
                "fonte": "MEMP",
                "motivo_sao_carlos": (
                    "Potencial fonte para políticas municipais de comércio, "
                    "empreendedorismo, ambiente de negócios ou desenvolvimento territorial."
                ),
                "tipo_oportunidade": "Recurso para Prefeitura",
                "verificado_em": hoje.isoformat(),
            }
        )

    # deduplicação
    unicos = []
    vistos = set()

    for item in itens:
        chave = normalizar(item["nome"])
        if chave in vistos:
            continue
        vistos.add(chave)
        unicos.append(item)

    return unicos


# ============================================================
# TRANSFEREGOV — TRANSFERÊNCIAS ESPECIAIS PARA SÃO CARLOS
# ============================================================

def coletar_transferegov_especiais():
    """
    Consulta a API pública oficial de Transferências Especiais.

    Objetivo:
    acompanhar recursos/emendas destinados diretamente ao Município
    de São Carlos. Isso NÃO substitui ainda o coletor de programas
    discricionários abertos, cuja nova API está em implantação.

    Usa o pacote transferegovpy, que valida nomes de filtros contra
    o esquema oficial da API.
    """

    if tg is None:
        raise RuntimeError(
            "Pacote transferegovpy não instalado. "
            "Execute: pip install -r requirements.txt"
        )

    # Beneficiários é uma tabela pequena; filtramos localmente.
    beneficiarios = tg.get(
        "especiais",
        "beneficiarios_especiais",
        limit=10000,
    )

    if beneficiarios is None or len(beneficiarios) == 0:
        return []

    registros = beneficiarios.to_dict("records")

    ids = []

    for b in registros:
        nome = normalizar(str(b.get("nome_beneficiario") or ""))
        uf = str(b.get("uf_beneficiario") or "").upper().strip()

        if uf != "SP":
            continue

        if "sao carlos" not in nome:
            continue

        if "municipio" not in nome:
            continue

        if b.get("id_beneficiario") is not None:
            ids.append(b.get("id_beneficiario"))

    if not ids:
        return []

    itens = []

    for id_beneficiario in ids:
        planos = tg.get(
            "especiais",
            "planos_acao_especiais",
            id_beneficiario=id_beneficiario,
            limit=500,
        )

        if planos is None or len(planos) == 0:
            continue

        for p in planos.to_dict("records"):
            # Preferimos planos recentes.
            ano = None

            for campo in [
                "ano_plano_acao",
                "aa_ano_plano_acao",
                "ano_emenda_plano_acao",
            ]:
                valor_ano = p.get(campo)
                if valor_ano:
                    try:
                        ano = int(valor_ano)
                        break
                    except Exception:
                        pass

            if ano and ano < date.today().year:
                continue

            valor_custeio = float(
                p.get("valor_custeio_plano_acao") or 0
            )
            valor_investimento = float(
                p.get("valor_investimento_plano_acao") or 0
            )
            valor_total = valor_custeio + valor_investimento

            situacao = str(
                p.get("situacao_plano_acao") or "Situação não informada"
            )

            parlamentar = str(
                p.get("nome_parlamentar_emenda_plano_acao") or ""
            ).strip()

            id_plano = p.get("id_plano_acao")

            nome = "Transferência Especial – São Carlos"

            if parlamentar:
                nome += f" – {parlamentar}"

            requisitos = (
                f"Plano de ação Transferegov: {id_plano}. "
                f"Situação atual: {situacao}. "
                "Recurso de transferência especial destinado ao Município; "
                "acompanhar plano de trabalho, execução e eventuais pendências."
            )

            itens.append(
                {
                    "nome": nome[:300],
                    "area": "Comércio",
                    "orgao": "Transferegov / Transferência Especial",
                    "valor": valor_total or None,
                    "data_final": "",
                    "prazo_texto": "Recurso destinado — acompanhar execução",
                    "publico": "Prefeitura",
                    "requisitos": requisitos,
                    "link": FONTES["TRANSFEREGOV_API"],
                    "fonte": "Transferegov Especial",
                    "motivo_sao_carlos": (
                        "Transferência especial identificada diretamente para "
                        "o Município de São Carlos na API oficial."
                    ),
                    "tipo_oportunidade": "Programa estratégico",
                    "verificado_em": date.today().isoformat(),
                }
            )

    return itens


# ============================================================
# NOVO PAC — SELEÇÕES PARA MUNICÍPIOS
# ============================================================

def coletar_novo_pac():
    """
    Varre as modalidades oficiais do Novo PAC Seleções 2026.

    Regras:
    - município/prefeitura precisa aparecer como elegível;
    - ignora páginas de resultado/homologação;
    - classifica financiamento separado de repasse;
    - se não houver prazo final explícito, mantém como programa estratégico
      e não como oportunidade aberta com prazo inventado.
    """

    raiz = FONTES["NOVO_PAC"]

    r = requests.get(
        raiz,
        timeout=25,
        headers=HEADERS,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    candidatos = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        titulo = re.sub(
            r"\s+",
            " ",
            " ".join(a.stripped_strings),
        ).strip()

        link = urljoin(raiz, a["href"])

        if not titulo or len(titulo) < 5:
            continue

        if "/novo-pac-selecoes-2026/" not in link:
            continue

        n_titulo = normalizar(titulo)

        if any(
            termo in n_titulo
            for termo in [
                "resultado",
                "selecionadas",
                "habilitadas",
                "arquivos",
            ]
        ):
            continue

        if link in vistos:
            continue

        vistos.add(link)
        candidatos.append((titulo, link))

    itens = []

    for titulo, link in candidatos[:30]:
        try:
            rd = requests.get(
                link,
                timeout=18,
                headers=HEADERS,
            )
            rd.raise_for_status()
        except Exception:
            continue

        sd = BeautifulSoup(rd.text, "html.parser")
        conteudo = re.sub(
            r"\s+",
            " ",
            sd.get_text(" ", strip=True),
        ).strip()

        n = normalizar(conteudo)

        if not any(
            termo in n
            for termo in [
                "municipios",
                "municipio",
                "entes publicos",
                "setor publico",
            ]
        ):
            continue

        if any(
            termo in n
            for termo in [
                "propostas selecionadas",
                "resultado final",
                "selecao encerrada",
                "inscricoes encerradas",
            ]
        ):
            continue

        # O Novo PAC pode ser repasse ou financiamento.
        eh_financiamento = any(
            termo in n
            for termo in [
                "operacoes de credito",
                "operação de crédito",
                "operacao de credito",
                "recursos onerosos",
                "fgts",
                "financiamento",
                "emprestimo",
            ]
        )

        prazo = extrair_prazo_aberto(conteudo)

        codigo_programa = ""
        m_codigo = re.search(
            r"PROGRAMA\s+(\d{10,})",
            conteudo,
            flags=re.IGNORECASE,
        )
        if m_codigo:
            codigo_programa = m_codigo.group(1)

        area = classificar_area(titulo, conteudo)

        # PAC é essencialmente infraestrutura/urbano; quando a classificação
        # genérica cair em Comércio, mantemos Comércio apenas se houver
        # aderência a desenvolvimento econômico/mercado/centro urbano.
        if area == "Comércio" and any(
            termo in n
            for termo in [
                "mobilidade",
                "saneamento",
                "residuos",
                "drenagem",
                "urbanizacao",
                "infraestrutura",
            ]
        ):
            area = "Indústria"

        tipo = (
            "Financiamento para Prefeitura"
            if eh_financiamento
            else "Recurso para Prefeitura"
        )

        prazo_texto = ""
        data_final = ""

        if prazo:
            data_final = prazo.isoformat()
        else:
            prazo_texto = "Seleção/programa oficial — verificar inscrição vigente"

        requisitos = (
            "Municípios aparecem como proponentes ou beneficiários na página oficial. "
            "Consulte a modalidade para confirmar enquadramento, documentação e cronograma."
        )

        if codigo_programa:
            requisitos += f" Código Transferegov identificado: {codigo_programa}."

        itens.append(
            {
                "nome": f"Novo PAC – {titulo}"[:300],
                "area": area,
                "orgao": "Governo Federal / Novo PAC",
                "valor": extrair_valor(conteudo),
                "data_final": data_final,
                "prazo_texto": prazo_texto,
                "publico": "Prefeitura",
                "requisitos": requisitos,
                "link": link,
                "fonte": "Novo PAC",
                "motivo_sao_carlos": (
                    "Modalidade do Novo PAC com participação municipal prevista. "
                    "Avaliar aderência aos projetos de São Carlos."
                ),
                "tipo_oportunidade": tipo,
                "verificado_em": date.today().isoformat(),
            }
        )

    return itens


# ============================================================
# CNPq / MCTI — CHAMADAS ABERTAS
# ============================================================

def coletar_cnpq():
    """
    Consulta a página oficial de chamadas abertas do CNPq.

    Só entram chamadas com prazo futuro identificado e relação
    com ciência, tecnologia, inovação, empreendedorismo ou
    educação científica. A Prefeitura só é marcada como elegível
    quando município/prefeitura aparece explicitamente no texto.
    """

    url = FONTES["CNPQ_ABERTAS"]

    r = requests.get(
        url,
        timeout=20,
        headers=HEADERS,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    hoje = date.today()

    candidatos = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        nome = re.sub(
            r"\s+",
            " ",
            " ".join(a.stripped_strings),
        ).strip()

        if len(nome) < 20:
            continue

        n_nome = normalizar(nome)

        if not any(
            termo in n_nome
            for termo in ["chamada", "chamamento", "edital"]
        ):
            continue

        link = urljoin(url, a["href"])

        if "gov.br/cnpq" not in link:
            continue

        if link in vistos:
            continue

        vistos.add(link)
        candidatos.append((nome, link))

        if len(candidatos) >= 30:
            break

    itens = []

    for nome, link in candidatos:
        try:
            rd = requests.get(
                link,
                timeout=15,
                headers=HEADERS,
            )
            rd.raise_for_status()
        except Exception:
            continue

        sd = BeautifulSoup(rd.text, "html.parser")

        texto = re.sub(
            r"\s+",
            " ",
            sd.get_text(" ", strip=True),
        ).strip()

        n_texto = normalizar(texto)

        if bloqueado(nome + " " + texto):
            continue

        if not any(
            termo in n_texto
            for termo in [
                "inovacao",
                "tecnologia",
                "ciencia",
                "cientifica",
                "empreendedorismo",
                "empresa",
                "educacao",
                "popularizacao",
                "divulgacao cientifica",
                "evento",
            ]
        ):
            continue

        prazo = None

        m = re.search(
            r"inscri(?:coes|ções)\s*:\s*"
            r"\d{1,2}/\d{1,2}/\d{4}\s+a\s+"
            r"(\d{1,2}/\d{1,2}/\d{4})",
            texto,
            flags=re.IGNORECASE,
        )

        if m:
            prazo = parse_data_br(m.group(1))

        if not prazo:
            prazo = extrair_prazo_aberto(texto)

        if not prazo or prazo < hoje:
            continue

        publico = classificar_publico(texto)

        if publico == "Todos":
            if "empresa" in n_texto or "empresas" in n_texto:
                publico = "Empresas"

        area = classificar_area(nome, texto)

        tipo = (
            "Recurso para Prefeitura"
            if publico == "Prefeitura"
            else (
                "Recurso para empresas"
                if publico == "Empresas"
                else "Programa estratégico"
            )
        )

        itens.append(
            {
                "nome": nome[:300],
                "area": area,
                "orgao": "CNPq / MCTI",
                "valor": extrair_valor(texto),
                "data_final": prazo.isoformat(),
                "publico": publico,
                "requisitos": (
                    "Chamada aberta identificada no portal oficial do CNPq. "
                    "Consulte a página específica para confirmar proponente, "
                    "documentação, orçamento e forma de submissão."
                ),
                "link": link,
                "fonte": "CNPq/MCTI",
                "motivo_sao_carlos": motivo_sao_carlos(
                    publico,
                    area,
                ),
                "tipo_oportunidade": tipo,
            }
        )

    return itens


# ============================================================
# DESENVOLVE SP
# ============================================================

def coletar_desenvolvesp():
    hoje = date.today()

    oportunidades = [
        {
            "nome": "Chamada Pública 01/2026 – Máquinas e Equipamentos",
            "area": "Indústria",
            "orgao": "Desenvolve SP",
            "valor": None,
            "data_final": "2027-04-28",
            "prazo_texto": "",
            "publico": "Empresas",
            "requisitos": (
                "Seleção de parceiros privados do setor de máquinas e "
                "equipamentos. Consulte o edital para os documentos "
                "de habilitação."
            ),
            "link": (
                "https://www.desenvolvesp.com.br/institucional/"
                "parcerias/inscricoes-abertas/"
                "chamada-publica-01-2026-maq-equip-setor-privado/"
            ),
            "fonte": "Desenvolve SP",
            "motivo_sao_carlos": (
                "Pode beneficiar indústrias e empresas do setor de máquinas "
                "e equipamentos instaladas em São Carlos."
            ),
            "tipo_oportunidade": "Programa estratégico",
        },
        {
            "nome": "Chamamento Público 01/2026 – Parcerias Institucionais",
            "area": "Comércio",
            "orgao": "Desenvolve SP",
            "valor": None,
            "data_final": "2027-03-11",
            "prazo_texto": "",
            "publico": "Empresas",
            "requisitos": (
                "Voltado a entidades institucionais sem fins lucrativos, "
                "como associações e entidades de classe com atuação no "
                "Estado de São Paulo."
            ),
            "link": (
                "https://www.desenvolvesp.com.br/institucional/"
                "parcerias/inscricoes-abertas/"
                "chamamento-publico-01-2026-parcerias-institucionais/"
            ),
            "fonte": "Desenvolve SP",
            "motivo_sao_carlos": (
                "Pode interessar a associações e entidades empresariais "
                "que atuam no município de São Carlos."
            ),
            "tipo_oportunidade": "Programa estratégico",
        },
    ]

    return [
        item
        for item in oportunidades
        if datetime.strptime(
            item["data_final"],
            "%Y-%m-%d",
        ).date() >= hoje
    ]


# ============================================================
# FINEP / FNDCT — CHAMADAS ABERTAS PARA EMPRESAS
# ============================================================

def _prazo_finep(texto: str, nome: str):
    """
    Lê o prazo exibido na chamada e aplica, quando necessário,
    prorrogações oficiais publicadas pela Finep em 2026.
    """
    hoje = date.today()

    prazos_prorrogados_2026 = {
        "saude / empresas": date(2026, 9, 18),
        "mobilidade sustentavel": date(2026, 9, 25),
        "conhecimento brasil": date(2026, 9, 11),
        # Base Industrial de Defesa não entra no Radar:
        # o filtro de conteúdo bloqueado a exclui.
        "base industrial de defesa": date(2026, 10, 2),
    }

    n_nome = normalizar(nome)

    for chave, prazo in prazos_prorrogados_2026.items():
        if chave in n_nome and prazo >= hoje:
            return prazo

    m = re.search(
        r"Prazo\s+para\s+envio\s+de\s+propostas\s+at[eé]\s*:\s*"
        r"(\d{1,2}/\d{1,2}/\d{4})",
        texto,
        flags=re.IGNORECASE,
    )

    if m:
        prazo = parse_data_br(m.group(1))
        if prazo and prazo >= hoje:
            return prazo

    return extrair_prazo_aberto(texto)


def coletar_finep():
    """
    Coleta chamadas abertas na página oficial da Finep.

    Regras:
    - somente chamadas com prazo futuro;
    - exclui chamadas de conteúdo bloqueado;
    - prioriza subvenção/apoio a empresas e startups;
    - não transforma chamada empresarial em recurso da Prefeitura.
    """

    url = FONTES["FINEP_ABERTAS"]

    r = requests.get(
        url,
        timeout=25,
        headers=HEADERS,
    )
    r.raise_for_status()

    soup = BeautifulSoup(r.text, "html.parser")
    hoje = date.today()

    candidatos = []
    vistos = set()

    for a in soup.find_all("a", href=True):
        nome = re.sub(
            r"\s+",
            " ",
            " ".join(a.stripped_strings),
        ).strip()

        if len(nome) < 18:
            continue

        n_nome = normalizar(nome)

        if not any(
            termo in n_nome
            for termo in [
                "finep",
                "selecao publica",
                "seleção pública",
                "chamada",
                "subvencao",
                "subvenção",
            ]
        ):
            continue

        link = urljoin(url, a["href"])

        if "finep.gov.br" not in link:
            continue

        chave = (n_nome, link)
        if chave in vistos:
            continue

        vistos.add(chave)
        candidatos.append((nome, link))

        if len(candidatos) >= 50:
            break

    itens = []

    for nome, link in candidatos:
        # Tenta obter o texto da página individual.
        texto = ""
        try:
            rd = requests.get(
                link,
                timeout=18,
                headers=HEADERS,
            )
            rd.raise_for_status()
            sd = BeautifulSoup(rd.text, "html.parser")
            texto = re.sub(
                r"\s+",
                " ",
                sd.get_text(" ", strip=True),
            ).strip()
        except Exception:
            # Ainda podemos tentar usar o texto do cartão/lista.
            pass

        if not texto:
            # Procura o bloco pai do link na página de listagem.
            a_match = soup.find(
                "a",
                href=lambda h: h and urljoin(url, h) == link,
            )

            if a_match:
                bloco = a_match
                for _ in range(5):
                    if not bloco.parent:
                        break
                    bloco = bloco.parent
                    bloco_txt = re.sub(
                        r"\s+",
                        " ",
                        bloco.get_text(" ", strip=True),
                    ).strip()

                    if "Prazo para envio" in bloco_txt:
                        texto = bloco_txt
                        break

        if not texto:
            continue

        completo = f"{nome} {texto}"

        if bloqueado(completo):
            continue

        prazo = _prazo_finep(texto, nome)

        if not prazo or prazo < hoje:
            continue

        n_texto = normalizar(texto)

        publico = "Empresas"
        if "startup" in n_texto and "empresas" not in n_texto:
            publico = "Startups"

        area = classificar_area(nome, texto)

        # Finep Mais Inovação e chamadas de subvenção são apoio
        # não reembolsável quando a página assim indica.
        if (
            "subvencao economica" in n_texto
            or "subvenção econômica" in texto.lower()
        ):
            tipo = (
                "Recurso para startups"
                if publico == "Startups"
                else "Recurso para empresas"
            )
            natureza = (
                "Subvenção econômica / recurso não reembolsável, "
                "conforme regulamento da chamada."
            )
        else:
            tipo = "Programa estratégico"
            natureza = (
                "Chamada pública da Finep. Consulte o regulamento "
                "para confirmar a natureza do apoio."
            )

        valor = extrair_valor(texto)

        itens.append(
            {
                "nome": nome[:300],
                "area": area,
                "orgao": "Finep / MCTI / FNDCT",
                "valor": valor,
                "data_final": prazo.isoformat(),
                "prazo_texto": "",
                "publico": publico,
                "requisitos": (
                    natureza
                    + " Verifique porte da empresa, TRL, contrapartida, "
                    "itens financiáveis e documentos exigidos."
                ),
                "link": link,
                "fonte": "Finep/FNDCT",
                "motivo_sao_carlos": (
                    "Pode beneficiar empresas e startups de São Carlos "
                    "com projetos de inovação enquadrados na chamada."
                ),
                "tipo_oportunidade": tipo,
                "verificado_em": hoje.isoformat(),
            }
        )

    # Remove duplicados por nome normalizado, mantendo o primeiro.
    unicos = []
    nomes = set()

    for item in itens:
        chave = normalizar(item["nome"])
        if chave in nomes:
            continue
        nomes.add(chave)
        unicos.append(item)

    return unicos


# ============================================================
# BNDES — FINANCIAMENTO PARA PREFEITURA E EMPRESAS
# ============================================================

def coletar_bndes():
    """
    Linhas permanentes/ativas do BNDES que podem interessar a São Carlos.

    São FINANCIAMENTOS, não transferências não reembolsáveis.
    Por isso aparecem separados no Radar e não entram automaticamente
    como recurso compatível do Ônibus da Ciência.
    """

    hoje = date.today().isoformat()

    return [
        {
            "nome": "BNDES Finem – Crédito para projetos",
            "area": "Indústria",
            "orgao": "BNDES",
            "valor": None,
            "data_final": "",
            "prazo_texto": "Linha disponível – sem prazo único de encerramento",
            "publico": "Prefeitura",
            "requisitos": (
                "Financiamento para projetos de investimento públicos ou privados. "
                "Entidades e órgãos públicos podem solicitar. Para estados e "
                "municípios, a participação do BNDES pode chegar a 90% do valor "
                "total do projeto, limitada aos itens financiáveis. Consulte as "
                "condições, valor mínimo, garantias e capacidade de pagamento."
            ),
            "link": FONTES["BNDES_FINEM"],
            "fonte": "BNDES",
            "motivo_sao_carlos": (
                "Pode financiar projetos estruturantes municipais, mas é crédito "
                "reembolsável e deve ser analisado separadamente de editais de repasse."
            ),
            "tipo_oportunidade": "Financiamento para Prefeitura",
            "verificado_em": hoje,
        },
        {
            "nome": "BNDES Finem – Crédito Inovação Direto",
            "area": "Startup/Inovação",
            "orgao": "BNDES",
            "valor": None,
            "data_final": "",
            "prazo_texto": "Linha disponível – sem prazo único de encerramento",
            "publico": "Prefeitura",
            "requisitos": (
                "Financiamento direto para investimentos em inovação. "
                "Empresas, fundações, associações, cooperativas e entidades "
                "ou órgãos públicos podem solicitar. A página oficial informa "
                "valor mínimo de financiamento de R$ 20 milhões."
            ),
            "link": FONTES["BNDES_INOVACAO"],
            "fonte": "BNDES",
            "motivo_sao_carlos": (
                "Pode ser relevante para projetos municipais de inovação de maior "
                "porte. Não é adequado ao Ônibus da Ciência de R$ 800 mil pela "
                "regra atual de valor mínimo."
            ),
            "tipo_oportunidade": "Financiamento para Prefeitura",
            "verificado_em": hoje,
        },
        {
            "nome": "BNDES Crédito Pequenas e Médias Empresas",
            "area": "Indústria",
            "orgao": "BNDES",
            "valor": None,
            "data_final": "",
            "prazo_texto": "Linha disponível – sem prazo único de encerramento",
            "publico": "Empresas",
            "requisitos": (
                "Crédito para micro, pequenas e médias empresas e empresários "
                "individuais. Pode apoiar manutenção e geração de empregos, "
                "sujeito à análise da instituição financeira credenciada."
            ),
            "link": FONTES["BNDES_MPME"],
            "fonte": "BNDES",
            "motivo_sao_carlos": (
                "Pode apoiar empresas de São Carlos que buscam crédito para "
                "crescimento, produtividade e manutenção de empregos."
            ),
            "tipo_oportunidade": "Financiamento para empresas",
            "verificado_em": hoje,
        },
    ]


# ============================================================
# SP PRODUZ — CADEIAS PRODUTIVAS LOCAIS
# ============================================================

def coletar_sp_produz():
    """
    Monitora a página oficial do SP Produz.

    A edição 2026 já está em fases de resultado/habilitação, então
    não inserimos automaticamente edital como aberto só porque ele
    permanece publicado. Quando a página voltar a anunciar inscrições
    abertas com prazo futuro, este coletor poderá ser ampliado.
    """
    return []


# ============================================================
# ATUALIZAÇÃO
# ============================================================

def limpar_vencidas():
    hoje = date.today().isoformat()

    with conexao() as conn:
        qtd = conn.execute(
            """
            DELETE FROM oportunidades
            WHERE data_final IS NOT NULL
              AND data_final != ''
              AND data_final < ?
            """,
            (hoje,),
        ).rowcount

        conn.commit()

    return qtd


def atualizar_fontes():
    resultado = {
        "incluidas_ou_atualizadas": 0,
        "fontes": {},
        "erros": [],
    }

    coletores = [
        ("Ministério das Cidades", coletar_ministerio_cidades),
        ("MEMP", coletar_memp),
        ("SDE/SP", coletar_sde_sp),
        ("SEMIL/SP", coletar_semil),
        ("Transferegov", coletar_transferegov),
        ("Transferegov Especial", coletar_transferegov_especiais),
        ("Novo PAC", coletar_novo_pac),
        ("InvestSP", coletar_investsp),
        ("CNPq/MCTI", coletar_cnpq),
        ("Finep/FNDCT", coletar_finep),
        ("BNDES", coletar_bndes),
        ("SP Produz", coletar_sp_produz),
        ("Desenvolve SP", coletar_desenvolvesp),
    ]

    fontes_preservar_se_zero = {
        "Transferegov",
        "Transferegov Especial",
        "Novo PAC",
    }

    for nome, coletor in coletores:
        try:
            itens = coletor()

            if nome not in fontes_preservar_se_zero:
                with conexao() as conn:
                    conn.execute(
                        "DELETE FROM oportunidades WHERE fonte = ?",
                        (nome,),
                    )
                    conn.commit()

            for item in itens:
                salvar_oportunidade(item)

            resultado["fontes"][nome] = len(itens)
            resultado["incluidas_ou_atualizadas"] += len(itens)

        except Exception as e:
            resultado["fontes"][nome] = 0

            erro = f"{nome}: {type(e).__name__}: {e}"
            resultado["erros"].append(erro)

            print("ERRO COLETOR:", erro)

    resultado["vencidas_removidas"] = limpar_vencidas()

    with conexao() as conn:
        conn.execute(
            """
            INSERT INTO radar_config (chave, valor)
            VALUES ('ultima_atualizacao', ?)
            ON CONFLICT(chave)
            DO UPDATE SET valor = excluded.valor
            """,
            (datetime.now().isoformat(timespec="seconds"),),
        )
        conn.commit()

    return resultado


# ============================================================
# PROJETOS MUNICIPAIS E COMPATIBILIDADE
# ============================================================

def listar_projetos_prefeitura():
    with conexao() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM projetos_prefeitura
            WHERE ativo = 1
            ORDER BY nome
            """
        ).fetchall()

    return [dict(r) for r in rows]


def termos_do_projeto(projeto):
    termos = []

    for termo in (projeto.get("termos_busca") or "").split(","):
        termo = normalizar(termo.strip())
        if termo:
            termos.append(termo)

    # Nome e descrição também ajudam na compatibilidade
    termos.extend(
        [
            normalizar(projeto.get("nome") or ""),
            normalizar(projeto.get("area") or ""),
        ]
    )

    return [t for t in termos if t]


def calcular_compatibilidade(projeto, oportunidade):
    texto = normalizar(
        " ".join(
            [
                oportunidade.get("nome") or "",
                oportunidade.get("area") or "",
                oportunidade.get("orgao") or "",
                oportunidade.get("requisitos") or "",
                oportunidade.get("motivo_sao_carlos") or "",
                oportunidade.get("tipo_oportunidade") or "",
            ]
        )
    )

    termos = termos_do_projeto(projeto)
    encontrados = [t for t in termos if t and t in texto]

    mesma_area = oportunidade.get("area") == projeto.get("area")
    prefeitura = oportunidade.get("publico") == "Prefeitura"

    # Financiamentos aparecem no Radar, mas não são sugeridos
    # automaticamente como "recurso compatível" do projeto municipal.
    # Para projetos como o Ônibus da Ciência, priorizamos editais,
    # transferências e programas de apoio.
    tipo = oportunidade.get("tipo_oportunidade") or ""
    if tipo.startswith("Financiamento"):
        return {
            "score": 0,
            "nivel": "Baixa",
            "termos": [],
        }

    # Uma oportunidade municipal genérica não deve combinar com todo
    # projeto da Prefeitura. Precisa haver afinidade temática.
    if not encontrados and not mesma_area:
        return {
            "score": 0,
            "nivel": "Baixa",
            "termos": [],
        }

    score = 0

    if prefeitura:
        score += 35

    if mesma_area:
        score += 25

    score += min(40, len(encontrados) * 8)

    if score >= 60:
        nivel = "Alta"
    elif score >= 40:
        nivel = "Média"
    else:
        nivel = "Baixa"

    return {
        "score": score,
        "nivel": nivel,
        "termos": encontrados[:6],
    }


def vincular_oportunidades_a_projetos(oportunidades, projetos):
    vinculos = {}

    for projeto in projetos:
        encontrados = []

        for oportunidade in oportunidades:
            comp = calcular_compatibilidade(
                projeto,
                oportunidade,
            )

            # Para projeto da Prefeitura, mostramos somente
            # oportunidades de Prefeitura com compatibilidade mínima.
            if (
                oportunidade.get("publico") == "Prefeitura"
                and comp["score"] >= 40
            ):
                encontrados.append(
                    {
                        "oportunidade": oportunidade,
                        "compatibilidade": comp,
                    }
                )

        encontrados.sort(
            key=lambda x: (
                -x["compatibilidade"]["score"],
                x["oportunidade"].get("data_final") or "9999-12-31",
            )
        )

        vinculos[projeto["id"]] = encontrados[:5]

    return vinculos


# ============================================================
# FICHA DE CAPTAÇÃO
# ============================================================

def sugerir_prazo_interno(data_final: str):
    """
    Sugere prazo interno 10 dias antes do prazo oficial.
    Nunca grava automaticamente: serve como recomendação visual.
    """
    if not data_final:
        return ""

    try:
        prazo = datetime.strptime(data_final, "%Y-%m-%d").date()
    except Exception:
        return ""

    sugerido = prazo - timedelta(days=10)
    hoje = date.today()

    if sugerido < hoje:
        sugerido = hoje

    return sugerido.isoformat()


# ============================================================
# PRIORIZAÇÃO PARA CAPTAÇÃO MUNICIPAL
# ============================================================

def calcular_prioridade_municipal(oportunidade, projetos):
    """
    Pontuação simples de 0 a 100 para ordenar oportunidades de captação.

    A pontuação favorece:
    - Prefeitura explicitamente elegível;
    - recurso/apoio não reembolsável;
    - prazo aberto;
    - valor identificado;
    - compatibilidade com projeto municipal cadastrado;
    - fonte oficial monitorada.
    """

    score = 0
    motivos = []

    publico = oportunidade.get("publico") or ""
    tipo = oportunidade.get("tipo_oportunidade") or ""
    fonte = oportunidade.get("fonte") or ""

    if publico == "Prefeitura":
        score += 40
        motivos.append("Prefeitura elegível")

    if not tipo.startswith("Financiamento"):
        score += 20
        motivos.append("não é financiamento")

    if oportunidade.get("data_final"):
        score += 10
        motivos.append("prazo definido")
    elif oportunidade.get("prazo_texto"):
        score += 5
        motivos.append("programa ativo")

    if oportunidade.get("valor"):
        score += 10
        motivos.append("valor identificado")

    melhor_projeto = None
    melhor_comp = 0

    for projeto in projetos:
        comp = calcular_compatibilidade(
            projeto,
            oportunidade,
        )

        if comp["score"] > melhor_comp:
            melhor_comp = comp["score"]
            melhor_projeto = projeto

    if melhor_comp >= 60:
        score += 20
        motivos.append("alta compatibilidade com projeto municipal")
    elif melhor_comp >= 40:
        score += 10
        motivos.append("compatível com projeto municipal")

    # Fontes oficiais e estratégicas da Prefeitura.
    fontes_prioritarias = {
        "Ministério das Cidades",
        "MEMP",
        "SDE/SP",
        "CNPq/MCTI",
        "Transferegov",
        "SEMIL/SP",
        "Desenvolve SP",
        "SP Produz",
        "BNDES",
    }

    if fonte in fontes_prioritarias:
        score += 5

    score = min(score, 100)

    if score >= 80:
        nivel = "Muito alta"
    elif score >= 60:
        nivel = "Alta"
    elif score >= 40:
        nivel = "Média"
    else:
        nivel = "Baixa"

    return {
        "score": score,
        "nivel": nivel,
        "motivos": motivos,
        "projeto": melhor_projeto,
        "compatibilidade_projeto": melhor_comp,
    }


# ============================================================
# RADAR ESTRATÉGICO — NÃO CONFUNDIR COM INSCRIÇÃO ABERTA
# ============================================================

def listar_fontes_estrategicas():
    """
    Itens que merecem acompanhamento da Prefeitura, mas NÃO são
    contabilizados como oportunidade aberta.

    Categorias:
    - Programa / articulação: programa municipal ou cooperação que pode
      exigir contato/adesão, sem inscrição pública aberta confirmada.
    - Recurso potencial: existência de ação orçamentária, diretriz ou
      dotação que pode originar transferência futura.
    """

    return [
        {
            "nome": "Integra MEMP",
            "categoria": "Programa / articulação",
            "area": "Comércio",
            "orgao": "MEMP",
            "status": "Verificar possibilidade de adesão para São Carlos",
            "descricao": (
                "O MEMP firmou em 2026 acordos com municípios para implantação "
                "do Integra MEMP, com plataforma de desenvolvimento econômico, "
                "capacitação, mobilização de empreendedores e articulação institucional."
            ),
            "projeto_relacionado": "São Carlos Comércio Forte",
            "valor": None,
            "link": FONTES["MEMP_ACTS"],
            "cor": "azul",
        },
        {
            "nome": "Ação orçamentária MEMP 210C",
            "categoria": "Recurso potencial",
            "area": "Comércio",
            "orgao": "MEMP",
            "status": "Diretrizes 2026 publicadas — acompanhar instrumentos de repasse",
            "descricao": (
                "A Portaria MEMP nº 352/2026 aprovou diretrizes programáticas "
                "para transferências voluntárias da ação 210C, executadas por "
                "contratos de repasse. O Radar deve acompanhar quando surgir "
                "instrumento/proposta aplicável ao município."
            ),
            "projeto_relacionado": "São Carlos Comércio Forte",
            "valor": None,
            "link": FONTES["MEMP_PORTARIAS"],
            "cor": "dourado",
        },
        {
            "nome": "SDE/SP — transferências a municípios",
            "categoria": "Recurso potencial",
            "area": "Comércio",
            "orgao": "Governo do Estado de São Paulo / SDE",
            "status": "Dotação orçamentária identificada — aguardar programa ou instrumento",
            "descricao": (
                "A proposta orçamentária estadual de 2026 prevê recursos na "
                "Secretaria de Desenvolvimento Econômico para competitividade, "
                "empreendedorismo e produtividade, incluindo modalidade de "
                "transferências a municípios."
            ),
            "projeto_relacionado": "São Carlos Comércio Forte",
            "valor": 4506852.0,
            "link": FONTES["SDE_ORCAMENTO_2026"],
            "cor": "verde",
        },
    ]


# ============================================================
# HOME
# ============================================================

@app.get("/", response_class=HTMLResponse)
def home(
    request: Request,
    area: str = "Todos",
    publico: str = "Todos",
    tipo: str = "Todos",
    finalidade: str = "Prefeitura",
    natureza: str = "Repasse/Apoio",
    msg: str = "",
):
    hoje = date.today().isoformat()

    filtros = [
        "(data_final IS NULL OR data_final = '' OR data_final >= ?)"
    ]
    params = [hoje]

    if area != "Todos":
        filtros.append("area = ?")
        params.append(area)

    if publico != "Todos":
        filtros.append("(publico = ? OR publico = 'Todos')")
        params.append(publico)

    if tipo != "Todos":
        filtros.append("tipo_oportunidade = ?")
        params.append(tipo)

    if finalidade == "Prefeitura":
        filtros.append("publico = 'Prefeitura'")
    elif finalidade == "Empresas":
        filtros.append("publico IN ('Empresas', 'Startups')")

    if natureza == "Repasse/Apoio":
        filtros.append(
            "COALESCE(tipo_oportunidade, '') NOT LIKE 'Financiamento%'"
        )
    elif natureza == "Financiamento":
        filtros.append(
            "COALESCE(tipo_oportunidade, '') LIKE 'Financiamento%'"
        )

    where = " AND ".join(filtros)

    with conexao() as conn:
        oportunidades = conn.execute(
            f"""
            SELECT *
            FROM oportunidades
            WHERE {where}
            ORDER BY
                CASE publico
                    WHEN 'Prefeitura' THEN 1
                    WHEN 'Empresas' THEN 2
                    WHEN 'Startups' THEN 3
                    ELSE 4
                END,
                CASE
                    WHEN data_final IS NULL OR data_final = '' THEN 1
                    ELSE 0
                END,
                data_final ASC,
                valor DESC
            """,
            params,
        ).fetchall()

    # Métricas do filtro atual
    total_valor = sum(
        (o["valor"] or 0)
        for o in oportunidades
    )

    # Métricas gerais do banco: separam dinheiro/apoio da Prefeitura
    # de financiamento e de oportunidades empresariais.
    with conexao() as conn:
        resumo_geral = conn.execute(
            """
            SELECT
                SUM(
                    CASE
                        WHEN publico = 'Prefeitura'
                         AND COALESCE(tipo_oportunidade, '') NOT LIKE 'Financiamento%'
                        THEN 1 ELSE 0
                    END
                ) AS prefeitura_repasse,
                SUM(
                    CASE
                        WHEN publico = 'Prefeitura'
                         AND COALESCE(tipo_oportunidade, '') LIKE 'Financiamento%'
                        THEN 1 ELSE 0
                    END
                ) AS prefeitura_financiamento,
                SUM(
                    CASE
                        WHEN publico IN ('Empresas', 'Startups')
                        THEN 1 ELSE 0
                    END
                ) AS empresas,
                SUM(
                    CASE
                        WHEN publico = 'Prefeitura'
                         AND COALESCE(tipo_oportunidade, '') NOT LIKE 'Financiamento%'
                        THEN COALESCE(valor, 0) ELSE 0
                    END
                ) AS valor_prefeitura_repasse,
                SUM(
                    CASE
                        WHEN publico = 'Prefeitura'
                         AND COALESCE(tipo_oportunidade, '') LIKE 'Financiamento%'
                        THEN COALESCE(valor, 0) ELSE 0
                    END
                ) AS valor_prefeitura_financiamento
            FROM oportunidades
            WHERE data_final IS NULL
               OR data_final = ''
               OR data_final >= ?
            """,
            (hoje,),
        ).fetchone()

    total_prefeitura = int(resumo_geral["prefeitura_repasse"] or 0)
    total_financiamento_prefeitura = int(
        resumo_geral["prefeitura_financiamento"] or 0
    )
    total_empresas = int(resumo_geral["empresas"] or 0)

    valor_prefeitura = float(
        resumo_geral["valor_prefeitura_repasse"] or 0
    )
    valor_financiamento_prefeitura = float(
        resumo_geral["valor_prefeitura_financiamento"] or 0
    )

    hoje_data = date.today()
    itens = []

    for o in oportunidades:
        dias = None
        status = "Aberto"

        if o["data_final"]:
            prazo = datetime.strptime(
                o["data_final"],
                "%Y-%m-%d",
            ).date()

            dias = (prazo - hoje_data).days

            if dias <= 7:
                status = "Urgente"
            elif dias <= 15:
                status = "Prazo curto"

        grupo = (
            "Ações da Prefeitura"
            if o["publico"] == "Prefeitura"
            else "Empresas de São Carlos"
        )

        registro = dict(o)

        prazo_interno_sugerido = (
            registro.get("prazo_interno")
            or sugerir_prazo_interno(registro.get("data_final") or "")
        )

        itens.append(
            {
                **registro,
                "dias": dias,
                "status": status,
                "grupo": grupo,
                "prazo_interno_sugerido": prazo_interno_sugerido,
            }
        )

    fontes_estrategicas = listar_fontes_estrategicas()

    fontes_status = [
        {"nome": "Ministério das Cidades", "modo": "Automático"},
        {"nome": "MEMP", "modo": "Automático"},
        {"nome": "SDE/SP", "modo": "Automático"},
        {"nome": "SEMIL/SP", "modo": "Automático"},
        {"nome": "Transferegov", "modo": "Programas: consulta oficial"},
        {"nome": "Transferegov Especial", "modo": "API automática"},
        {"nome": "Novo PAC", "modo": "Automático"},
        {"nome": "InvestSP", "modo": "Monitorado"},
        {"nome": "CNPq/MCTI", "modo": "Automático"},
        {"nome": "Finep/FNDCT", "modo": "Automático"},
        {"nome": "BNDES", "modo": "Linhas ativas"},
        {"nome": "SP Produz", "modo": "Monitorado"},
        {"nome": "Desenvolve SP", "modo": "Monitorado"},
    ]

    projetos_prefeitura = listar_projetos_prefeitura()

    vinculos_projetos = vincular_oportunidades_a_projetos(
        itens,
        projetos_prefeitura,
    )

    # Ranking municipal: usa todas as oportunidades abertas para Prefeitura,
    # independentemente do filtro visual atual.
    with conexao() as conn:
        rows_prefeitura = conn.execute(
            """
            SELECT *
            FROM oportunidades
            WHERE publico = 'Prefeitura'
              AND COALESCE(tipo_oportunidade, '') NOT LIKE 'Financiamento%'
              AND (
                    data_final IS NULL
                 OR data_final = ''
                 OR data_final >= ?
              )
            """,
            (hoje,),
        ).fetchall()

    ranking_prefeitura = []

    for row in rows_prefeitura:
        oportunidade = dict(row)
        prio = calcular_prioridade_municipal(
            oportunidade,
            projetos_prefeitura,
        )

        ranking_prefeitura.append(
            {
                "oportunidade": oportunidade,
                "prioridade": prio,
            }
        )

    ranking_prefeitura.sort(
        key=lambda x: (
            -x["prioridade"]["score"],
            x["oportunidade"].get("data_final") or "9999-12-31",
        )
    )

    ranking_prefeitura = ranking_prefeitura[:5]

    with conexao() as conn:
        meta_row = conn.execute(
            "SELECT meta_anual FROM metas_captacao WHERE id = 1"
        ).fetchone()

        meta_anual = float(meta_row["meta_anual"] or 0) if meta_row else 0

        valores_status = conn.execute(
            """
            SELECT
                COALESCE(status_captacao, 'Encontrada') AS status,
                SUM(COALESCE(valor_pretendido, valor, 0)) AS total
            FROM oportunidades
            WHERE publico = 'Prefeitura'
              AND COALESCE(tipo_oportunidade, '') NOT LIKE 'Financiamento%'
            GROUP BY COALESCE(status_captacao, 'Encontrada')
            """
        ).fetchall()

    valor_por_status = {
        row["status"]: float(row["total"] or 0)
        for row in valores_status
    }

    valor_em_analise = (
        valor_por_status.get("Analisar edital", 0)
        + valor_por_status.get("Preparar proposta", 0)
    )
    valor_enviado = (
        valor_por_status.get("Inscrição enviada", 0)
        + valor_por_status.get("Aguardando resultado", 0)
    )
    valor_aprovado = valor_por_status.get("Aprovada", 0)

    percentual_meta = 0
    if meta_anual > 0:
        percentual_meta = min(
            100,
            round((valor_aprovado / meta_anual) * 100, 1),
        )

    with conexao() as conn:
        eixos_rows = conn.execute(
            """
            SELECT
                area,
                COUNT(*) AS total,
                SUM(COALESCE(valor_pretendido, valor, 0)) AS valor
            FROM oportunidades
            WHERE publico = 'Prefeitura'
              AND COALESCE(tipo_oportunidade, '') NOT LIKE 'Financiamento%'
              AND (
                    data_final IS NULL
                 OR data_final = ''
                 OR data_final >= ?
              )
            GROUP BY area
            """,
            (hoje,),
        ).fetchall()

        resumo_eixos = {
            "Comércio": {"total": 0, "valor": 0.0},
            "Indústria": {"total": 0, "valor": 0.0},
            "Startup/Inovação": {"total": 0, "valor": 0.0},
        }

        for row in eixos_rows:
            if row["area"] in resumo_eixos:
                resumo_eixos[row["area"]] = {
                    "total": int(row["total"] or 0),
                    "valor": float(row["valor"] or 0),
                }

        cfg = conn.execute(
            """
            SELECT valor
            FROM radar_config
            WHERE chave = 'ultima_atualizacao'
            """
        ).fetchone()

        ultima_atualizacao = cfg["valor"] if cfg else ""

        proximos_prazos_rows = conn.execute(
            """
            SELECT *
            FROM oportunidades
            WHERE publico = 'Prefeitura'
              AND COALESCE(tipo_oportunidade, '') NOT LIKE 'Financiamento%'
              AND data_final IS NOT NULL
              AND data_final != ''
              AND data_final >= ?
              AND data_final <= ?
            ORDER BY data_final ASC
            LIMIT 5
            """,
            (
                hoje,
                (date.today() + timedelta(days=15)).isoformat(),
            ),
        ).fetchall()

        pendencias_rows = conn.execute(
            """
            SELECT *
            FROM oportunidades
            WHERE publico = 'Prefeitura'
              AND COALESCE(tipo_oportunidade, '') NOT LIKE 'Financiamento%'
              AND COALESCE(status_captacao, 'Encontrada')
                  IN ('Encontrada', 'Analisar edital', 'Preparar proposta')
              AND (
                    data_final IS NULL
                 OR data_final = ''
                 OR data_final >= ?
              )
            ORDER BY
                CASE COALESCE(status_captacao, 'Encontrada')
                    WHEN 'Preparar proposta' THEN 1
                    WHEN 'Analisar edital' THEN 2
                    ELSE 3
                END,
                data_final ASC
            LIMIT 5
            """,
            (hoje,),
        ).fetchall()

        funil_rows = conn.execute(
            """
            SELECT
                COALESCE(status_captacao, 'Encontrada') AS status,
                COUNT(*) AS total
            FROM oportunidades
            WHERE publico = 'Prefeitura'
              AND COALESCE(tipo_oportunidade, '') NOT LIKE 'Financiamento%'
              AND (
                    data_final IS NULL
                 OR data_final = ''
                 OR data_final >= ?
              )
            GROUP BY COALESCE(status_captacao, 'Encontrada')
            """,
            (hoje,),
        ).fetchall()

    proximos_prazos = []
    for row in proximos_prazos_rows:
        item = dict(row)
        prazo = datetime.strptime(item["data_final"], "%Y-%m-%d").date()
        item["dias_restantes"] = (prazo - date.today()).days
        proximos_prazos.append(item)

    pendencias = [dict(r) for r in pendencias_rows]

    contagem_funil = {
        status: 0
        for status in STATUS_CAPTACAO
    }

    for row in funil_rows:
        contagem_funil[row["status"]] = row["total"]

    return templates.TemplateResponse(
        request=request,
        name="index.html",
        context={
            "oportunidades": itens,
            "total_valor": total_valor,
            "total_prefeitura": total_prefeitura,
            "total_empresas": total_empresas,
            "valor_prefeitura": valor_prefeitura,
            "valor_financiamento_prefeitura": valor_financiamento_prefeitura,
            "total_financiamento_prefeitura": total_financiamento_prefeitura,
            "area_atual": area,
            "publico_atual": publico,
            "tipo_atual": tipo,
            "finalidade_atual": finalidade,
            "natureza_atual": natureza,
            "areas": AREAS,
            "publicos": PUBLICOS,
            "tipos": TIPOS,
            "msg": msg,
            "transferegov_consulta": FONTES["TRANSFEREGOV_CONSULTA"],
            "transferegov_parcerias": FONTES["TRANSFEREGOV_PARcerias"],
            "transferegov_programas": FONTES["TRANSFEREGOV_PROGRAMAS"],
            "transferegov_downloads": FONTES["TRANSFEREGOV_DOWNLOADS"],
            "novo_pac_url": FONTES["NOVO_PAC"],
            "fontes_status": fontes_status,
            "fontes_estrategicas": fontes_estrategicas,
            "projetos_prefeitura": projetos_prefeitura,
            "vinculos_projetos": vinculos_projetos,
            "ranking_prefeitura": ranking_prefeitura,
            "status_captacao_opcoes": STATUS_CAPTACAO,
            "contagem_funil": contagem_funil,
            "meta_anual": meta_anual,
            "valor_em_analise": valor_em_analise,
            "valor_enviado": valor_enviado,
            "valor_aprovado": valor_aprovado,
            "percentual_meta": percentual_meta,
            "ultima_atualizacao": ultima_atualizacao,
            "proximos_prazos": proximos_prazos,
            "pendencias": pendencias,
            "resumo_eixos": resumo_eixos,
        },
    )


# ============================================================
# PESQUISA DE OPORTUNIDADES
# ============================================================

@app.get("/pesquisa", response_class=HTMLResponse)
def pesquisa(
    request: Request,
    finalidade: str = "Todos",
    natureza: str = "Todos",
    area: str = "Todos",
    publico: str = "Todos",
    tipo: str = "Todos",
    q: str = "",
):
    hoje = date.today().isoformat()

    filtros = [
        "(data_final IS NULL OR data_final = '' OR data_final >= ?)"
    ]
    params = [hoje]

    if finalidade == "Prefeitura":
        filtros.append("publico = 'Prefeitura'")
    elif finalidade == "Empresas":
        filtros.append("publico IN ('Empresas', 'Startups')")

    if natureza == "Repasse/Apoio":
        filtros.append(
            "COALESCE(tipo_oportunidade, '') NOT LIKE 'Financiamento%'"
        )
    elif natureza == "Financiamento":
        filtros.append(
            "COALESCE(tipo_oportunidade, '') LIKE 'Financiamento%'"
        )

    if area != "Todos":
        filtros.append("area = ?")
        params.append(area)

    if publico != "Todos":
        filtros.append("(publico = ? OR publico = 'Todos')")
        params.append(publico)

    if tipo != "Todos":
        filtros.append("tipo_oportunidade = ?")
        params.append(tipo)

    if q.strip():
        termo = f"%{q.strip()}%"
        filtros.append(
            """
            (
                nome LIKE ?
                OR orgao LIKE ?
                OR fonte LIKE ?
                OR requisitos LIKE ?
                OR motivo_sao_carlos LIKE ?
            )
            """
        )
        params.extend([termo, termo, termo, termo, termo])

    where = " AND ".join(filtros)

    with conexao() as conn:
        rows = conn.execute(
            f"""
            SELECT *
            FROM oportunidades
            WHERE {where}
            ORDER BY
                CASE publico
                    WHEN 'Prefeitura' THEN 1
                    WHEN 'Empresas' THEN 2
                    WHEN 'Startups' THEN 3
                    ELSE 4
                END,
                CASE
                    WHEN data_final IS NULL OR data_final = '' THEN 1
                    ELSE 0
                END,
                data_final ASC,
                valor DESC
            """,
            params,
        ).fetchall()

    hoje_data = date.today()
    itens = []

    for o in rows:
        registro = dict(o)

        dias = None
        status = "Aberto"

        if registro.get("data_final"):
            prazo = datetime.strptime(
                registro["data_final"],
                "%Y-%m-%d",
            ).date()

            dias = (prazo - hoje_data).days

            if dias <= 7:
                status = "Urgente"
            elif dias <= 15:
                status = "Prazo curto"

        registro["dias"] = dias
        registro["status"] = status
        registro["prazo_interno_sugerido"] = (
            registro.get("prazo_interno")
            or sugerir_prazo_interno(
                registro.get("data_final") or ""
            )
        )

        itens.append(registro)

    total_prefeitura = sum(
        1 for o in itens
        if o.get("publico") == "Prefeitura"
    )

    total_empresas = sum(
        1 for o in itens
        if o.get("publico") in ("Empresas", "Startups")
    )

    total_valor = sum(
        float(o.get("valor") or 0)
        for o in itens
    )

    return templates.TemplateResponse(
        request=request,
        name="pesquisa.html",
        context={
            "oportunidades": itens,
            "areas": AREAS,
            "publicos": PUBLICOS,
            "tipos": TIPOS,
            "finalidade_atual": finalidade,
            "natureza_atual": natureza,
            "area_atual": area,
            "publico_atual": publico,
            "tipo_atual": tipo,
            "q": q,
            "total_prefeitura": total_prefeitura,
            "total_empresas": total_empresas,
            "total_valor": total_valor,
            "status_captacao_opcoes": STATUS_CAPTACAO,
        },
    )


# ============================================================
# ROTAS
# ============================================================

@app.post("/atualizar")
def atualizar():
    resultado = atualizar_fontes()

    partes = [
        (
            "Atualização concluída: "
            f"{resultado['incluidas_ou_atualizadas']} oportunidades lidas."
        )
    ]

    for fonte, qtd in resultado["fontes"].items():
        if fonte == "Transferegov":
            partes.append("Transferegov: consulta oficial")
        else:
            partes.append(f"{fonte}: {qtd}")

    if resultado["erros"]:
        partes.append("Alguma fonte apresentou erro; veja o terminal.")

    msg = " | ".join(partes)

    return RedirectResponse(
        url="/?msg=" + requests.utils.quote(msg),
        status_code=303,
    )


@app.post("/cadastrar")
def cadastrar(
    nome: str = Form(...),
    area: str = Form(...),
    orgao: str = Form(""),
    valor: float = Form(0),
    data_final: str = Form(""),
    publico: str = Form("Todos"),
    requisitos: str = Form(""),
    link: str = Form(""),
    tipo_oportunidade: str = Form("Programa estratégico"),
):
    item = {
        "nome": nome,
        "area": area,
        "orgao": orgao,
        "valor": valor or None,
        "data_final": data_final or "",
        "prazo_texto": (
            ""
            if data_final
            else "Sem data final informada"
        ),
        "publico": publico,
        "requisitos": requisitos,
        "link": link,
        "fonte": "Manual",
        "motivo_sao_carlos": motivo_sao_carlos(
            publico,
            area,
        ),
        "tipo_oportunidade": tipo_oportunidade,
    }

    salvar_oportunidade(item)

    return RedirectResponse(url="/", status_code=303)


@app.post("/excluir/{oportunidade_id}")
def excluir(oportunidade_id: int):
    with conexao() as conn:
        conn.execute(
            "DELETE FROM oportunidades WHERE id = ?",
            (oportunidade_id,),
        )
        conn.commit()

    return RedirectResponse(url="/", status_code=303)



@app.post("/projetos/cadastrar")
def cadastrar_projeto(
    nome: str = Form(...),
    area: str = Form(...),
    descricao: str = Form(""),
    valor_estimado: float = Form(0),
    termos_busca: str = Form(""),
    responsavel: str = Form(""),
    fontes_monitoradas: str = Form(""),
):
    with conexao() as conn:
        conn.execute(
            """
            INSERT INTO projetos_prefeitura
            (
                nome,
                area,
                descricao,
                valor_estimado,
                termos_busca,
                responsavel,
                fontes_monitoradas,
                status,
                ativo
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'Buscando recurso', 1)
            """,
            (
                nome,
                area,
                descricao,
                valor_estimado or None,
                termos_busca,
                responsavel,
                fontes_monitoradas,
            ),
        )
        conn.commit()

    return RedirectResponse(
        url="/",
        status_code=303,
    )


@app.post("/projetos/desativar/{projeto_id}")
def desativar_projeto(projeto_id: int):
    with conexao() as conn:
        conn.execute(
            """
            UPDATE projetos_prefeitura
            SET ativo = 0
            WHERE id = ?
            """,
            (projeto_id,),
        )
        conn.commit()

    return RedirectResponse(
        url="/",
        status_code=303,
    )



@app.post("/captacao/meta")
def atualizar_meta_captacao(
    meta_anual: float = Form(...),
):
    with conexao() as conn:
        conn.execute(
            """
            UPDATE metas_captacao
            SET
                meta_anual = ?,
                atualizado_em = CURRENT_TIMESTAMP
            WHERE id = 1
            """,
            (meta_anual,),
        )
        conn.commit()

    return RedirectResponse(
        url="/?msg=Meta+de+captação+atualizada",
        status_code=303,
    )


@app.post("/captacao/ficha/{oportunidade_id}")
def atualizar_ficha_captacao(
    oportunidade_id: int,
    prazo_interno: str = Form(""),
    contrapartida: str = Form(""),
    documentos_necessarios: str = Form(""),
    despesas_elegiveis: str = Form(""),
    projeto_relacionado_manual: str = Form(""),
    valor_pretendido: float = Form(0),
):
    with conexao() as conn:
        conn.execute(
            """
            UPDATE oportunidades
            SET
                prazo_interno = ?,
                contrapartida = ?,
                documentos_necessarios = ?,
                despesas_elegiveis = ?,
                projeto_relacionado_manual = ?,
                valor_pretendido = ?
            WHERE id = ?
            """,
            (
                prazo_interno.strip(),
                contrapartida.strip(),
                documentos_necessarios.strip(),
                despesas_elegiveis.strip(),
                projeto_relacionado_manual.strip(),
                valor_pretendido or None,
                oportunidade_id,
            ),
        )
        conn.commit()

    return RedirectResponse(
        url="/?msg=Ficha+de+captação+atualizada",
        status_code=303,
    )


@app.post("/captacao/status/{oportunidade_id}")
def atualizar_status_captacao(
    oportunidade_id: int,
    status_captacao: str = Form(...),
    responsavel_captacao: str = Form(""),
    observacoes_captacao: str = Form(""),
):
    if status_captacao not in STATUS_CAPTACAO:
        return RedirectResponse(
            url="/?msg=Status+de+captação+inválido",
            status_code=303,
        )

    with conexao() as conn:
        conn.execute(
            """
            UPDATE oportunidades
            SET
                status_captacao = ?,
                responsavel_captacao = ?,
                observacoes_captacao = ?,
                data_status_captacao = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status_captacao,
                responsavel_captacao.strip(),
                observacoes_captacao.strip(),
                oportunidade_id,
            ),
        )
        conn.commit()

    return RedirectResponse(
        url="/?msg=Funil+de+captação+atualizado",
        status_code=303,
    )


@app.get("/api/oportunidades")
def api_oportunidades():
    hoje = date.today().isoformat()

    with conexao() as conn:
        rows = conn.execute(
            """
            SELECT *
            FROM oportunidades
            WHERE data_final IS NULL
               OR data_final = ''
               OR data_final >= ?
            ORDER BY
                CASE publico
                    WHEN 'Prefeitura' THEN 1
                    WHEN 'Empresas' THEN 2
                    WHEN 'Startups' THEN 3
                    ELSE 4
                END,
                data_final ASC
            """,
            (hoje,),
        ).fetchall()

    return [dict(r) for r in rows]


@app.get("/api/atualizar")
def api_atualizar():
    return atualizar_fontes()
