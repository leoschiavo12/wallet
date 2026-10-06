import streamlit as st
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import math
import requests
import openpyxl
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import date

st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="")

st.markdown("""
    <style>
        /* ── base ──────────────────────────────────────────────── */
        html, body, [class*="css"] { font-size: 14px !important; }
        .stDataFrame div [role="gridcell"] > div { justify-content: center !important; text-align: center !important; }
        .stDataFrame div [role="columnheader"] > div { justify-content: center !important; text-align: center !important; }
        [data-testid="stMetricDelta"] { display: none !important; }

        /* ── cards (st.metric + cards HTML): tipografia única para o app inteiro ──
           tudo que é "rótulo em cima / número embaixo" usa estes tokens; nenhum container
           deve redefinir tamanho de fonte de card. Mobile só troca os valores das variáveis. */
        :root {
            --card-label-size:  0.85rem;
            --card-value-size:  1.6rem;
            --card-label-color: rgba(250, 250, 250, 0.6);
            --card-value-color: rgba(250, 250, 250, 0.95);
            --card-gap:         0.2rem;   /* espaço entre rótulo e valor */
        }
        [data-testid="stMetric"] { padding: 0 !important; }
        [data-testid="stMetricLabel"],
        [data-testid="stMetric"] label {
            min-height: 0 !important;
            height: auto !important;
            margin: 0 0 var(--card-gap) 0 !important;
            padding: 0 !important;
        }
        [data-testid="stMetricLabel"] p,
        [data-testid="stMetricLabel"] div,
        [data-testid="stMetric"] label,
        .card-label {
            font-size: var(--card-label-size) !important;
            line-height: 1.3 !important;
            font-weight: 400 !important;
            color: var(--card-label-color) !important;
        }
        [data-testid="stMetricValue"],
        [data-testid="stMetricValue"] div,
        .card-value {
            font-size: var(--card-value-size) !important;
            line-height: 1.25 !important;
            font-weight: 500 !important;
        }
        [data-testid="stMetricValue"] { color: var(--card-value-color) !important; padding: 0 !important; }
        .card { margin: 0; padding: 0; }
        /* st.markdown tem margin-bottom:-1rem por padrão — sem isso o card "encolhe" e
           linhas só de cards HTML ficam coladas, ao contrário das linhas de st.metric */
        [data-testid="stMarkdownContainer"]:has(> .card) { margin-bottom: 0 !important; }
        .card-label { margin: 0 0 var(--card-gap) 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
        .card-value { margin: 0; white-space: nowrap; color: var(--card-value-color); }
        .card-value.card-pos    { color: #22c55e !important; }
        .card-value.card-neg    { color: #ef4444 !important; }
        .card-value.card-neutro { color: #888888 !important; }

        /* ── mobile: 2 colunas lado a lado, padding compacto ───── */
        @media (max-width: 768px) {
            /* container-pai das colunas: por padrão o Streamlit empilha (flex-direction:column)
               abaixo de uma certa largura — isso é o que causava o empilhamento mesmo com
               regras nos filhos. Forçamos row+wrap aqui, que é a causa raiz. */
            div[data-testid="stHorizontalBlock"],
            div[class*="stHorizontalBlock"] {
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: wrap !important;
                gap: 0.5rem !important;
            }
            /* 2 colunas no mobile — não empilha, mas limita */
            div[data-testid="column"],
            div[data-testid="stColumn"],
            div[class*="stColumn"] {
                min-width: 46% !important;
                width: 46% !important;
                flex: 1 1 46% !important;
            }
            /* reduz padding lateral */
            .main .block-container {
                padding-left: 0.75rem !important;
                padding-right: 0.75rem !important;
                padding-top: 0.75rem !important;
            }
            /* métricas menores no mobile */
            /* cards: mesmos tokens, escala menor */
            :root {
                --card-label-size: 0.68rem;
                --card-value-size: 1.05rem;
            }
            /* tabs com scroll horizontal */
            [data-testid="stTabs"] > div:first-child {
                overflow-x: auto !important;
                flex-wrap: nowrap !important;
            }
            /* gráficos ocupam largura total */
            [data-testid="stPlotlyChart"] {
                width: 100% !important;
            }
            /* tabelas com scroll horizontal */
            [data-testid="stDataFrame"] {
                overflow-x: auto !important;
            }

            /* ── seções específicas (maior especificidade sobrescreve a regra geral acima) ── */

            /* linha de exposição geográfica: 4 itens numa linha só, mais compactos */
            .st-key-row_geo [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 0.25rem !important;
            }
            .st-key-row_geo [data-testid="column"],
            .st-key-row_geo [data-testid="stColumn"] {
                min-width: 23% !important;
                width: 23% !important;
                flex: 1 1 23% !important;
            }

            /* linha donut + gráfico mensal: empilha em vez de espremer lado a lado */
            .st-key-row_dashboard_chart [data-testid="stHorizontalBlock"] {
                flex-direction: column !important;
            }
            .st-key-row_dashboard_chart [data-testid="column"],
            .st-key-row_dashboard_chart [data-testid="stColumn"] {
                width: 100% !important;
                min-width: 100% !important;
                flex: 1 1 100% !important;
            }

            /* card de valorização: alinhar tamanho de fonte ao st.metric nativo */

            /* linha RF/RV/CDI/IPCA+: 4 itens numa linha só, rótulos curtos */
            .st-key-row_indices [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 0.25rem !important;
            }
            .st-key-row_indices [data-testid="column"],
            .st-key-row_indices [data-testid="stColumn"] {
                min-width: 23% !important;
                width: 23% !important;
                flex: 1 1 23% !important;
            }

            /* bloco resumo dos FIIs: grade 3 colunas, igual aos cards por ativo */
            .st-key-row_fii_dividendos [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 0.3rem !important;
            }
            .st-key-row_fii_dividendos [data-testid="column"],
            .st-key-row_fii_dividendos [data-testid="stColumn"] {
                min-width: 31% !important;
                width: 31% !important;
                flex: 1 1 31% !important;
            }

            /* linha 2 dos FIIs: tijolo e papel lado a lado */
            .st-key-row_fii_tipo [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 0.25rem !important;
            }
            .st-key-row_fii_tipo [data-testid="column"],
            .st-key-row_fii_tipo [data-testid="stColumn"] {
                min-width: 48% !important;
                width: 48% !important;
                flex: 1 1 48% !important;
            }

            /* cards por ETF: 3 infos por linha (ativo/preço/total em cima, valorização/holding embaixo) */
            [class*="st-key-row_etf_"] [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 0.3rem !important;
            }
            [class*="st-key-row_etf_"] [data-testid="column"],
            [class*="st-key-row_etf_"] [data-testid="stColumn"] {
                min-width: 31% !important;
                width: 31% !important;
                flex: 1 1 31% !important;
            }

            /* mesma estrutura (3 colunas, 2 linhas) para cripto, tesouro e FIIs */
            [class*="st-key-row_cripto_"] [data-testid="stHorizontalBlock"],
            [class*="st-key-row_tesouro_"] [data-testid="stHorizontalBlock"],
            [class*="st-key-row_fii_ativo_"] [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 0.3rem !important;
            }
            [class*="st-key-row_cripto_"] [data-testid="column"],
            [class*="st-key-row_cripto_"] [data-testid="stColumn"],
            [class*="st-key-row_tesouro_"] [data-testid="column"],
            [class*="st-key-row_tesouro_"] [data-testid="stColumn"],
            [class*="st-key-row_fii_ativo_"] [data-testid="column"],
            [class*="st-key-row_fii_ativo_"] [data-testid="stColumn"] {
                min-width: 31% !important;
                width: 31% !important;
                flex: 1 1 31% !important;
            }

            /* resumo ETF (total/valorização/holding médio): 3 numa linha */
            .st-key-row_etf_resumo [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 0.3rem !important;
            }
            .st-key-row_etf_resumo [data-testid="column"],
            .st-key-row_etf_resumo [data-testid="stColumn"] {
                min-width: 31% !important;
                width: 31% !important;
                flex: 1 1 31% !important;
            }

            /* variações do BTC: 3 colunas x 2 linhas alinhadas */
            .st-key-row_cripto_variacoes [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 0.3rem !important;
            }
            .st-key-row_cripto_variacoes [data-testid="column"],
            .st-key-row_cripto_variacoes [data-testid="stColumn"] {
                min-width: 31% !important;
                width: 31% !important;
                flex: 1 1 31% !important;
            }

            /* cards de "ver todos os ativos" (mesma estrutura das outras abas) */
            [class*="st-key-row_all_"] [data-testid="stHorizontalBlock"] {
                flex-wrap: wrap !important;
                gap: 0.3rem !important;
            }
            [class*="st-key-row_all_"] [data-testid="column"],
            [class*="st-key-row_all_"] [data-testid="stColumn"] {
                min-width: 31% !important;
                width: 31% !important;
                flex: 1 1 31% !important;
            }

            /* linha 1 do dashboard: patrimônio/saiu do bolso/valorização numa linha só */
            .st-key-row_dash_resumo [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 0.3rem !important;
            }
            .st-key-row_dash_resumo [data-testid="column"],
            .st-key-row_dash_resumo [data-testid="stColumn"] {
                min-width: 31% !important;
                width: 31% !important;
                flex: 1 1 31% !important;
            }

            /* linha 2 do dashboard: dividendos do mês/dividendos totais/lucro total numa linha só */
            .st-key-row_dash_lucro [data-testid="stHorizontalBlock"] {
                flex-wrap: nowrap !important;
                gap: 0.3rem !important;
            }
            .st-key-row_dash_lucro [data-testid="column"],
            .st-key-row_dash_lucro [data-testid="stColumn"] {
                min-width: 31% !important;
                width: 31% !important;
                flex: 1 1 31% !important;
            }
        }

        /* ── tablet: colunas de 4+ ficam em pares ───────────────── */
        @media (min-width: 769px) and (max-width: 1024px) {
            div[data-testid="stHorizontalBlock"],
            div[class*="stHorizontalBlock"] {
                display: flex !important;
                flex-direction: row !important;
                flex-wrap: wrap !important;
            }
            div[data-testid="column"],
            div[data-testid="stColumn"],
            div[class*="stColumn"] {
                min-width: 48% !important;
                flex: 1 1 48% !important;
            }
        }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def _yf_session():
    """sessão yfinance reutilizada — evita reconexão a cada chamada"""
    return yf

# ── agenda de atualização ─────────────────────────────────────────────────────
# pregão: dias úteis (seg–sex) das 10h às 19h, horário de Brasília. Fora disso os dados
# de mercado ficam "congelados" na última leitura — nenhuma consulta nova até o próximo
# pregão. Feriados não são tratados (contam como dia útil). O BTC ignora a agenda e
# atualiza de hora em hora, sempre.
def _agora_sp():
    return pd.Timestamp.now(tz="America/Sao_Paulo")

def janela_mercado(minutos):
    """
    chave de cache que muda a cada `minutos` durante o pregão e fica fixa fora dele.
    Passada como argumento das funções cacheadas: chave nova → nova consulta.
    """
    agora = _agora_sp()
    if agora.weekday() < 5 and 10 <= agora.hour < 19:
        return "aberto-" + agora.floor(f"{minutos}min").strftime("%Y%m%d%H%M")
    # fechado: chave = último pregão encerrado (hoje após 19h, ou o dia útil anterior)
    ref = agora.normalize()
    if not (agora.weekday() < 5 and agora.hour >= 19):
        ref = ref - pd.offsets.BDay(1)
    return "fechado-" + ref.strftime("%Y%m%d")

def janela_horaria():
    """chave que muda a cada hora cheia, todos os dias (BTC)"""
    return _agora_sp().floor("h").strftime("%Y%m%d%H")

@st.cache_data(ttl=4 * 86400, max_entries=20, show_spinner=False)
def _baixar_precos_b3(tickers_tupla, janela):
    """
    cotação atual de cada ativo da B3 → (precos, falhas, momento da consulta).
    1º fast_info.last_price (preço corrente do Yahoo, o mais fresco — o candle diário de
       ETFs da B3 às vezes chega com 1–2 dias de atraso no Yahoo);
    2º fallback: último fechamento do download diário de 5 dias.
    Um ticker por vez (sem threads), mesmo cuidado de obter_variacao_90d.
    """
    precos, falhas = {}, []
    diario = None
    for t in tickers_tupla:
        tk = f"{t.upper()}.SA"
        v = 0.0
        try:
            v = float(yf.Ticker(tk).fast_info.last_price or 0)
        except Exception:
            v = 0.0
        if not v or v <= 0 or pd.isna(v):
            try:
                if diario is None:
                    diario = yf.download([f"{x.upper()}.SA" for x in tickers_tupla], period="5d",
                                         progress=False, auto_adjust=True, threads=False, timeout=10)
                serie = diario['Close'][tk] if isinstance(diario.columns, pd.MultiIndex) else diario['Close']
                v = float(serie.dropna().iloc[-1])
            except Exception:
                v = 0.0
        precos[t.upper()] = v if v and v > 0 else 0.0
        if precos[t.upper()] <= 0:
            falhas.append(t)
    if tickers_tupla and len(falhas) == len(tickers_tupla):
        # nada veio (Yahoo fora do ar): exceção não é cacheada → tenta de novo no próximo acesso
        raise RuntimeError("nenhuma cotação obtida")
    momento = pd.Timestamp.now(tz="America/Sao_Paulo").strftime("%d/%m %H:%M")
    return precos, falhas, momento

def obter_precos_b3(tickers_lista):
    _tk = tuple(sorted(set(tickers_lista)))
    try:
        precos, falhas, momento = _baixar_precos_b3(_tk, janela_mercado(5))
    except Exception:
        precos, falhas, momento = {t.upper(): 0.0 for t in _tk}, list(_tk), "—"
    if falhas:
        st.session_state['_precos_falha'] = falhas
    st.session_state['_precos_momento'] = momento
    return dict(precos)

# FIIs que mudaram de ticker na B3 — lançamentos antigos guardam o nome antigo,
# mas o yfinance só reconhece o ticker atual. Usado por toda função que busca
# dividendos via yfinance a partir do ticker salvo em lançamentos.
ALIAS_FII_TICKERS = {'GALG11': 'GARE11'}

@st.cache_data(ttl=3600)
def calcular_dividendos_mes(df_lancamentos_json, mes_ref, ano_ref):
    """
    dividendos recebidos num mês/ano específico (auto via yfinance + lançamentos manuais
    tipo 'dividendo' datados daquele mês). Função genérica — usada tanto pro card do mês
    mais recente quanto pro backfill histórico mensal.
    """
    import pandas as pd

    df_lanc = pd.DataFrame(df_lancamentos_json)
    if df_lanc.empty:
        return 0.0, {}
    # normalizar nomes de colunas
    df_lanc.columns = [c.title() for c in df_lanc.columns]
    df_lanc['data_dt'] = pd.to_datetime(df_lanc['Data'], format='%d/%m/%Y', errors='coerce')
    df_lanc['sinal']   = df_lanc['Tipo'].str.lower().map({'compra': 1, 'venda': -1}).fillna(0)

    total    = 0.0
    detalhes = {}

    # Classe vem como 'FII' do Sheets — após title() fica 'Fii'
    fiis = list(df_lanc[df_lanc['Classe'].str.upper() == 'FII']['Ativo'].unique())

    for fii in fiis:
        fii_norm = ALIAS_FII_TICKERS.get(fii, fii)
        try:
            tk = yf.Ticker(f"{fii_norm}.SA")
            divs = tk.dividends
            if divs is None or divs.empty:
                continue
            divs.index = divs.index.tz_localize(None) if divs.index.tzinfo else divs.index

            # filtrar pelo mes de referencia apenas
            mask   = (divs.index.month == mes_ref) & (divs.index.year == ano_ref)
            divs_ex = divs[mask]
            if divs_ex.empty:
                continue

            for data_ex, val_cota in divs_ex.items():
                try:
                    data_ex_date = pd.Timestamp(data_ex).normalize()
                    ticker_ops = fii if fii in df_lanc['Ativo'].values else fii_norm
                    ops = df_lanc[
                        (df_lanc['Ativo'] == ticker_ops) &
                        (df_lanc['data_dt'].dt.normalize() < data_ex_date)
                    ]
                    qtd_na_data = (ops['Quantidade'] * ops['sinal']).sum()
                    if qtd_na_data > 0:
                        val_total = float(val_cota) * qtd_na_data
                        if fii_norm not in detalhes:
                            detalhes[fii_norm] = {'por_cota': 0.0, 'total': 0.0, 'qtd': qtd_na_data}
                        detalhes[fii_norm]['por_cota'] += float(val_cota)
                        detalhes[fii_norm]['total']    += val_total
                        total += val_total
                except:
                    continue
        except:
            continue

    # lançamentos manuais de tipo 'dividendo' datados dentro desse mês/ano
    # (ex: AJUSTE-DIVIDENDOS, ou fundos sem histórico no yfinance)
    _manuais_mes = df_lanc[
        (df_lanc['Tipo'].str.strip().str.lower() == 'dividendo') &
        (df_lanc['data_dt'].dt.month == mes_ref) &
        (df_lanc['data_dt'].dt.year == ano_ref)
    ]
    for _, row in _manuais_mes.iterrows():
        ativo_m = row['Ativo']
        valor_m = float(row['Total']) if pd.notna(row['Total']) else 0.0
        if valor_m > 0:
            if ativo_m not in detalhes:
                detalhes[ativo_m] = {'por_cota': 0.0, 'total': 0.0, 'qtd': 0}
            detalhes[ativo_m]['total'] += valor_m
            total += valor_m

    return total, detalhes

def obter_dividendos_mes_anterior(df_lancamentos_json):
    """dividendos do mês anterior ao atual — mantido por compatibilidade com quem já chama assim"""
    from datetime import date
    hoje = date.today()
    if hoje.month == 1:
        mes_ref, ano_ref = 12, hoje.year - 1
    else:
        mes_ref, ano_ref = hoje.month - 1, hoje.year
    return calcular_dividendos_mes(df_lancamentos_json, mes_ref, ano_ref)

@st.cache_data(ttl=2 * 3600, max_entries=5, show_spinner=False)
def _preco_btc_janela(janela):
    v = _consultar_preco_btc_brl()
    if not v or v <= 0:
        raise RuntimeError("sem cotação do BTC")   # exceção não é cacheada → tenta de novo
    return v

def obter_preco_btc_brl():
    """preço do BTC em R$: atualiza de hora em hora, todos os dias"""
    try:
        return _preco_btc_janela(janela_horaria())
    except Exception:
        return 0.0

def _consultar_preco_btc_brl():
    try:
        url = "https://api.coingecko.com/api/v3/simple/price?ids=bitcoin&vs_currencies=brl"
        resp = requests.get(url, timeout=7)
        preco = float(resp.json()['bitcoin']['brl'])
        if preco > 0:
            return preco
    except:
        pass
    try:
        btc_usd = float(requests.get("https://api.coinbase.com/v2/prices/BTC-USD/spot", timeout=7).json()['data']['amount'])
        usd_brl = float(requests.get("https://api.exchangerate-api.com/v4/latest/USD", timeout=7).json()['rates']['BRL'])
        if btc_usd > 0 and usd_brl > 0:
            return btc_usd * usd_brl
    except:
        pass
    try:
        dados = yf.download("BTC-BRL", period="2d", progress=False, auto_adjust=True, timeout=7)
        return float(dados['Close'].ffill().iloc[-1])
    except:
        pass
    return 0.0

@st.cache_data(ttl=86400, show_spinner=False)
def calcular_dividendos_historicos(df_lanc_json):
    """calcula total de dividendos recebidos por FII desde a primeira compra"""
    import pandas as pd
    df = pd.DataFrame(df_lanc_json)
    if df.empty: return {}, 0.0

    df['data_dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
    df['sinal']   = df['tipo'].str.strip().str.lower().map({'compra': 1, 'venda': -1}).fillna(0)

    resultado = {}
    total_geral_divs = 0.0

    fiis = df[df['classe'] == 'FII']['ativo'].unique()

    for ativo in fiis:
        try:
            ativo_norm = ALIAS_FII_TICKERS.get(ativo, ativo)
            tk   = yf.Ticker(f"{ativo_norm}.SA")
            divs = tk.dividends
            if divs is None or divs.empty:
                continue

            # normalizar timezone
            if divs.index.tz is not None:
                divs.index = divs.index.tz_localize(None)

            # compras e vendas deste ativo
            g = df[df['ativo'] == ativo].sort_values('data_dt')
            primeira_compra = g[g['tipo'].str.lower() == 'compra']['data_dt'].min()
            if pd.isna(primeira_compra): continue

            # filtrar dividendos após primeira compra
            divs_filtrados = divs[divs.index >= primeira_compra]
            if divs_filtrados.empty: continue

            total_ativo = 0.0
            for data_div, valor_div in divs_filtrados.items():
                # qtd de cotas na véspera da data-ex (quem compra na data-ex não recebe)
                g_ate = g[g['data_dt'].dt.normalize() < pd.Timestamp(data_div).normalize()]
                qtd = (g_ate['quantidade'] * g_ate['sinal']).sum()
                if qtd > 0:
                    total_ativo += qtd * valor_div

            resultado[ativo] = round(total_ativo, 2)
            total_geral_divs += total_ativo
        except:
            continue

    # lançamentos manuais de tipo 'dividendo' — cobre fundos sem histórico no yfinance
    # (ex: encerrados/incorporados, onde tk.dividends vem vazio e o ativo é pulado acima)
    _manuais_hist = df[df['tipo'].str.strip().str.lower() == 'dividendo']
    for ativo in _manuais_hist['ativo'].unique():
        _soma_manual_ativo = _manuais_hist[_manuais_hist['ativo'] == ativo]['total'].sum()
        if _soma_manual_ativo > 0:
            resultado[ativo] = resultado.get(ativo, 0.0) + _soma_manual_ativo
            total_geral_divs += _soma_manual_ativo

    return resultado, round(total_geral_divs, 2)

@st.cache_data(ttl=86400)
def obter_proventos_12m_por_cota(tickers_tupla, df_lanc_json=None):
    """
    soma dos proventos por cota pagos por cada FII nos últimos 12 meses — todos os
    pagamentos do período, independente de quando você comprou ou de quanto tinha
    em cada data (padrão de mercado: Fundamentus/StatusInvest calculam assim).
    Yield on Cost = proventos_12m_por_cota ÷ preço médio.
    """
    import datetime as _dt
    janela_ini = pd.Timestamp(_dt.date.today() - _dt.timedelta(days=365))
    resultado = {}

    for t in tickers_tupla:
        try:
            t_norm = ALIAS_FII_TICKERS.get(t, t)
            divs = yf.Ticker(f"{t_norm}.SA").dividends
            if divs is None or divs.empty:
                resultado[t] = 0.0
                continue
            if divs.index.tz is not None:
                divs.index = divs.index.tz_localize(None)
            _w = divs[divs.index >= janela_ini]
            _w = _w[_w > 0]
            _soma = float(_w.sum())
            # o yfinance às vezes "pula" meses de FIIs da B3 (ex.: GARE11 vinha com 10 dos 12
            # pagamentos). Se o padrão é mensal (≥6 pagamentos, intervalo mediano ~1 mês) e
            # faltam meses na janela, anualiza pela média dos pagamentos encontrados.
            if 6 <= len(_w) < 12:
                _gap = pd.Series(_w.index).diff().dt.days.median()
                if 25 <= _gap <= 35:
                    _soma = float(_w.mean()) * 12
            resultado[t] = round(_soma, 4)
        except Exception:
            resultado[t] = 0.0

    # lançamentos manuais de tipo 'dividendo' (fundos sem histórico no yfinance) —
    # cada pagamento é dividido pela quantidade que você tinha NAQUELA data (não a
    # quantidade de hoje — senão comprar mais cotas depois "dilui" artificialmente
    # o provento por cota já pago, derrubando o YoC sem motivo real)
    if df_lanc_json:
        df = pd.DataFrame(df_lanc_json)
        if not df.empty:
            df['data_dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
            df['sinal']   = df['tipo'].str.strip().str.lower().map({'compra': 1, 'venda': -1}).fillna(0)
            _manuais = df[(df['tipo'].str.strip().str.lower() == 'dividendo') & (df['data_dt'] >= janela_ini)]
            for ativo in _manuais['ativo'].unique():
                _soma_por_cota = 0.0
                for _, _entrada in _manuais[_manuais['ativo'] == ativo].iterrows():
                    _ops_ate_data = df[(df['ativo'] == ativo) & (df['data_dt'] < _entrada['data_dt'])]
                    _qtd_na_data  = (_ops_ate_data['quantidade'] * _ops_ate_data['sinal']).sum()
                    if _qtd_na_data > 0:
                        _soma_por_cota += _entrada['total'] / _qtd_na_data
                if _soma_por_cota > 0:
                    resultado[ativo] = resultado.get(ativo, 0.0) + _soma_por_cota

    return resultado

def _buscar_historico_btc_brl():
    """busca histórico sem cache — chamada internamente"""
    # tentativa 1: coingecko
    try:
        url = "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart"
        params = {"vs_currency": "brl", "days": "1825", "interval": "daily"}
        r = requests.get(url, params=params, timeout=15)
        if r.status_code == 200:
            prices = r.json().get("prices", [])
            if prices:
                df_h = pd.DataFrame(prices, columns=["ts", "preco"])
                df_h["data"] = pd.to_datetime(df_h["ts"], unit="ms")
                return df_h.set_index("data")["preco"], "coingecko"
    except:
        pass
    # tentativa 2: yfinance BTC-BRL
    try:
        dados = yf.download("BTC-BRL", period="5y", progress=False, auto_adjust=True)
        if not dados.empty:
            close = dados['Close']
            if isinstance(close, pd.DataFrame):
                close = close.iloc[:, 0]
            serie = close.ffill().dropna()
            if not serie.empty:
                return serie, "yfinance"
    except:
        pass
    # tentativa 3: yfinance BTC-USD × BRL=X
    try:
        btc_usd = yf.download("BTC-USD", period="5y", progress=False, auto_adjust=True)['Close']
        usd_brl = yf.download("BRL=X",   period="5y", progress=False, auto_adjust=True)['Close']
        if isinstance(btc_usd, pd.DataFrame): btc_usd = btc_usd.iloc[:, 0]
        if isinstance(usd_brl, pd.DataFrame): usd_brl = usd_brl.iloc[:, 0]
        btc_brl = (btc_usd * usd_brl).ffill().dropna()
        if not btc_brl.empty:
            return btc_brl, "yfinance (USD×BRL)"
    except:
        pass
    return None, "erro"

@st.cache_data(ttl=3600, show_spinner=False)
def _historico_btc_cached(chave_ts):
    """cache com chave de hora — força retry a cada hora"""
    return _buscar_historico_btc_brl()

def obter_historico_btc_brl():
    """wrapper: só cacheia resultado válido; em caso de erro tenta sempre"""
    import time
    # chave muda a cada hora, forçando retry em caso de falha anterior
    chave = int(time.time() // 3600)
    hist, fonte = _historico_btc_cached(chave)
    if hist is None:
        # tenta sem cache imediatamente
        hist, fonte = _buscar_historico_btc_brl()
    return hist, fonte

def _preco_resgate_tesouro_direto(nome_titulo="Renda+ Aposentadoria Extra 2050"):
    """
    PU de RESGATE atual no site do Tesouro Direto (CSV 'rendimento-resgatar'), o mesmo
    valor que aparece no app do Tesouro e na corretora. Atualiza ao longo do dia.
    retorna o PU ou levanta exceção (o site às vezes bloqueia acesso automatizado).
    """
    import re
    url = "https://www.tesourodireto.com.br/documents/d/guest/rendimento-resgatar-csv?download=true"
    r = requests.get(url, timeout=12, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept": "text/csv,application/octet-stream,*/*",
        "Referer": "https://www.tesourodireto.com.br/titulos/precos-e-taxas.htm"})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    try:
        texto = r.content.decode('utf-8')
    except UnicodeDecodeError:
        texto = r.content.decode('latin1')
    for linha in texto.splitlines():
        if 'renda' in linha.lower() and '2050' in linha:
            for campo in linha.split(';'):
                c = campo.replace('R$', '').strip()
                if '%' in c:
                    continue
                if re.fullmatch(r"\d{1,3}(\.\d{3})*,\d{2}", c):
                    pu = float(c.replace('.', '').replace(',', '.'))
                    if pu > 1:
                        return pu
    raise RuntimeError("título não encontrado no CSV")

def _taxa_compra_tesouro_direto():
    """
    taxa de COMPRA atual do Renda+ 2050 (o x de IPCA + x%) no CSV 'rendimento-investir'
    do Tesouro Direto. Leitura tolerante ao formato: procura a coluna de rendimento/taxa
    pelo cabeçalho; se não achar, pega o número que vem depois de 'IPCA' na linha.
    """
    import re
    url = "https://www.tesourodireto.com.br/documents/d/guest/rendimento-investir-csv?download=true"
    r = requests.get(url, timeout=12, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36",
        "Accept": "text/csv,application/octet-stream,*/*",
        "Referer": "https://www.tesourodireto.com.br/titulos/precos-e-taxas.htm"})
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}")
    try:
        texto = r.content.decode('utf-8-sig')
    except UnicodeDecodeError:
        texto = r.content.decode('latin1')
    linhas = [l for l in texto.splitlines() if l.strip()]
    if not linhas:
        raise RuntimeError("CSV vazio")
    sep = ';' if linhas[0].count(';') >= linhas[0].count(',') else ','
    cab = [c.strip().strip('"').lower() for c in linhas[0].split(sep)]
    i_tx = next((i for i, c in enumerate(cab) if 'rendimento' in c or 'taxa' in c or 'rentabilidade' in c), None)
    alvo = [l for l in linhas[1:] if re.search(r"renda\s*\+?", l, re.I) and '2050' in l]
    if not alvo:
        raise RuntimeError(f"título não encontrado (cabeçalho: {'|'.join(cab)[:80]})")
    linha = alvo[0]
    campos = [c.strip().strip('"') for c in linha.split(sep)]

    def _num(s):
        m = re.search(r"(\d{1,2}[.,]\d{1,4})", s.replace('\xa0', ' '))
        return float(m.group(1).replace(',', '.')) if m else None

    if i_tx is not None and i_tx < len(campos):
        v = _num(campos[i_tx])
        if v is not None and 0 < v < 30:
            return v
    m = re.search(r"IPCA\s*\+?\s*(\d{1,2}[.,]\d{1,4})", linha.replace('\xa0', ' '), re.I)
    if m:
        return float(m.group(1).replace(',', '.'))
    raise RuntimeError(f"taxa não reconhecida na linha: {linha[:90]}")

def obter_preco_renda_mais():
    # 1º preço de resgate atual no site do Tesouro Direto (o que o app do Tesouro/corretora mostra)
    _erro_td = None
    try:
        _pu_td = _preco_resgate_tesouro_direto()
        _ref = pd.Timestamp.now(tz="America/Sao_Paulo").strftime('%d/%m/%Y %H:%M')
        _obs_taxa = ""
        try:
            _taxa_td = _taxa_compra_tesouro_direto()
        except Exception as e:
            _taxa_td = None
            _obs_taxa = f" · taxa indisponível: {str(e)[:110]}"
        return _pu_td, f"{_ref} (preço de resgate — Tesouro Direto){_obs_taxa}", _taxa_td
    except Exception as e:
        _erro_td = str(e)[:60]
    # 2º fallback: CSV do Tesouro Transparente — PU de venda da MANHÃ do último dia útil
    try:
        from io import StringIO
        url = "https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"

        # descobrir tamanho e baixar ultimos 500KB
        head = requests.head(url, timeout=10)
        tamanho = int(head.headers.get('Content-Length', 0))
        if tamanho > 0:
            inicio = max(0, tamanho - 500000)
            resp = requests.get(url, headers={'Range': f'bytes={inicio}-'}, timeout=15)
        else:
            resp = requests.get(url, timeout=30)

        if resp.status_code not in (200, 206):
            return None, f'status {resp.status_code}'

        texto = resp.content.decode('latin1')
        linhas = texto.split('\n')

        # montar cabecalho e filtrar linhas relevantes
        cabecalho = 'Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha'
        renda = [l for l in linhas if 'Renda' in l and '2069' in l and len(l) > 10]

        if not renda:
            return None, f'nao encontrado — {len(linhas)} linhas no trecho'

        # parsear com pandas para filtrar corretamente
        csv_str = cabecalho + '\n' + '\n'.join(renda)
        df = pd.read_csv(StringIO(csv_str), sep=';', decimal=',', thousands='.')
        df['Data Base'] = pd.to_datetime(df['Data Base'], format='%d/%m/%Y', errors='coerce')

        # filtrar: titulo contem Renda, vencimento contem 2069
        mask = (
            df['Tipo Titulo'].str.contains('Renda', case=False, na=False) &
            df['Data Vencimento'].str.contains('2069', na=False)
        )
        df_f = df[mask].sort_values('Data Base', ascending=False)

        if df_f.empty:
            return None, f'nenhum registro apos filtro — datas: {df["Data Base"].dt.strftime("%d/%m/%Y").tolist()[-3:]}'

        pu    = float(df_f.iloc[0]['PU Venda Manha'])
        taxa  = float(df_f.iloc[0]['Taxa Compra Manha'])
        dt    = (df_f.iloc[0]['Data Base'].strftime('%d/%m/%Y') +
                 f" manhã (Tesouro Transparente; site do TD indisponível: {_erro_td})")
        return pu, dt, taxa
    except Exception as e:
        return None, str(e), None

@st.cache_data(ttl=604800)  # 7 dias — histórico de datas passadas não muda; só perde os dias mais recentes até expirar
def _baixar_fatia_taxa_renda_mais(fatia_bytes):
    """
    baixa e parseia uma fatia (em bytes, a partir do FIM do arquivo) do CSV de preços/taxas
    do Tesouro Transparente, filtrada só pro Renda+ 2050 (vencimento 2069). Função de baixo
    nível, sem dependência do Sheets — a orquestração (o que já está salvo vs o que falta
    buscar) fica em obter_historico_taxa_renda_mais(), mais abaixo no arquivo.
    Retorna DataFrame[data_dt, taxa] (ou vazio + mensagem de erro).
    """
    try:
        from io import StringIO
        url = "https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"

        head = requests.head(url, timeout=10)
        tamanho = int(head.headers.get('Content-Length', 0))
        if tamanho > 0:
            inicio = max(0, tamanho - fatia_bytes)
            resp = requests.get(url, headers={'Range': f'bytes={inicio}-'}, timeout=90)
        else:
            resp = requests.get(url, timeout=90)

        if resp.status_code not in (200, 206):
            return pd.DataFrame(columns=['data_dt', 'taxa', 'pu']), f'status {resp.status_code}'

        texto = resp.content.decode('latin1')
        linhas = texto.split('\n')
        cabecalho = 'Tipo Titulo;Data Vencimento;Data Base;Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha;PU Base Manha'
        renda = [l for l in linhas if 'Renda' in l and '2069' in l and len(l) > 10]
        if not renda:
            return pd.DataFrame(columns=['data_dt', 'taxa', 'pu']), f'nao encontrado — {len(linhas)} linhas no trecho'

        csv_str = cabecalho + '\n' + '\n'.join(renda)
        df = pd.read_csv(StringIO(csv_str), sep=';', decimal=',', thousands='.')
        df['Data Base'] = pd.to_datetime(df['Data Base'], format='%d/%m/%Y', errors='coerce')

        mask = (
            df['Tipo Titulo'].str.contains('Renda', case=False, na=False) &
            df['Data Vencimento'].str.contains('2069', na=False)
        )
        df_f = df[mask].dropna(subset=['Data Base', 'Taxa Compra Manha'])
        df_f = df_f.rename(columns={'Data Base': 'data_dt', 'Taxa Compra Manha': 'taxa',
                                    'PU Venda Manha': 'pu'})
        return df_f[['data_dt', 'taxa', 'pu']].reset_index(drop=True), None
    except Exception as e:
        return pd.DataFrame(columns=['data_dt', 'taxa']), str(e)

def arredondar_teto(valor, multiplo):
    return math.ceil(valor / multiplo) * multiplo

def gerar_ticks_rs(y_max_rs, n_ticks=5):
    bruto = y_max_rs / (n_ticks - 1)
    magnitude = 10 ** math.floor(math.log10(bruto))
    candidatos = [magnitude, 2*magnitude, 5*magnitude, 10*magnitude]
    step = next(c for c in candidatos if c >= bruto)
    teto = arredondar_teto(y_max_rs, step)
    vals = [round(step * i) for i in range(n_ticks) if step * i <= teto + 1]
    return teto, vals

def gerar_ticks_pct(max_pct_ativo, step=5):
    teto = arredondar_teto(max_pct_ativo * 1.1, step)
    teto = max(teto, step)
    vals = list(range(0, teto + 1, step))
    return teto, vals

def abreviar_rs(valor):
    if valor >= 1_000_000:
        return f"R${fmt_num(valor/1_000_000, 1)}M"
    elif valor >= 1_000:
        v = valor / 1_000
        s = f"{v:.1f}".replace('.', ',')
        if s.endswith(',0'):
            s = s[:-2]
        return f"R${s}k"
    else:
        return f"R${int(valor)}"

def fmt_num(valor, casas=2, milhar=False):
    """número com vírgula decimal; esconde a parte decimal quando ela é toda zero
    (31,00 → 31 · 4,0 → 4 · 0,92 → 0,92). milhar=True usa ponto como separador de milhar."""
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return "—"
    s = f"{float(valor):,.{casas}f}" if milhar else f"{float(valor):.{casas}f}"
    if casas > 0:
        inteiro, dec = s.split('.')
        s = inteiro if set(dec) <= {'0'} else f"{inteiro}.{dec}"
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return "0" if s in ("-0", "-0,0") else s

def formatar_brl(valor):
    return f"R${fmt_num(valor, 2, milhar=True)}"

def fmt_pct(valor, casas=1):
    """formata % sem casa decimal se for zero"""
    return f"{fmt_num(valor, casas)}%"

def fmt_holding(meses):
    """holding em meses (até 12) ou anos (acima de 12), sem decimal quando for zero"""
    if meses is None or meses <= 0: return "—"
    if round(meses, 1) <= 12:
        s = fmt_num(meses, 1)
        return f"{s} mês" if s == "1" else f"{s} meses"
    s = fmt_num(meses / 12, 1)
    return f"{s} ano" if s == "1" else f"{s} anos"

def tag_var(rs, pct):
    """tag colorida de valorização ▲/▼ %  ·  R$"""
    sinal = "▲" if rs >= 0 else "▼"
    cor   = "#22c55e" if rs >= 0 else "#ef4444"
    return (f"<span style='color:{cor};font-weight:600;font-family:inherit'>"
            f"{sinal} {'+' if pct>=0 else ''}{fmt_pct(pct)}  ·  {abreviar_rs(abs(rs))}</span>")

def card_html(col, label, valor, tom=None):
    """card HTML com a mesma tipografia do st.metric (tokens .card-label / .card-value no CSS).
    tom: None (cor padrão) · 'pos' (verde) · 'neg' (vermelho) · 'neutro' (cinza)"""
    _cls = f" card-{tom}" if tom else ""
    col.markdown(
        f"<div class='card'><p class='card-label'>{label}</p>"
        f"<p class='card-value{_cls}'>{valor}</p></div>",
        unsafe_allow_html=True
    )

def card_valorizacao(col, rs, pct, label="variação"):
    """card de valorização: label (padrão 'valorização') · R$X, valor colorido ▲/▼ %"""
    sinal    = "▲" if rs >= 0 else "▼"
    _pct_str = ("+" if pct >= 0 else "") + fmt_pct(pct)
    _rs_str  = f"({abreviar_rs(abs(rs))})" if rs < 0 else abreviar_rs(rs)   # negativo entre parênteses
    card_html(col, f"{label}  ·  {_rs_str}", f"{sinal} {_pct_str}", "pos" if rs >= 0 else "neg")

def metric_tag(col, label, valor, rs, pct):
    """st.metric nativo — col já é a coluna certa"""
    col.metric(label, valor)

def metric_tag_simples(col, label, valor):
    col.metric(label, valor)

def holding_ponderado_meses(ativo, df_lanc):
    """holding médio ponderado pelo valor de cada compra, em meses — usado em ETFs, tesouro, cripto e FIIs"""
    import datetime
    hoje = datetime.date.today()
    compras = df_lanc[(df_lanc['ativo'] == ativo) & (df_lanc['tipo'].str.lower() == 'compra')].copy()
    if compras.empty: return None
    compras['data_dt'] = pd.to_datetime(compras['data'], format='%d/%m/%Y', errors='coerce')
    compras['valor']   = compras['quantidade'] * compras['preco_unitario']
    total_val = compras['valor'].sum()
    if total_val == 0: return None
    meses_pond = sum(
        (row['valor'] / total_val) *
        ((hoje - row['data_dt'].date()).days / 30.44)
        for _, row in compras.iterrows()
        if pd.notna(row['data_dt'])
    )
    return round(meses_pond, 1)


# ── Tesouro Direto: lê de st.secrets, fallback para valor hardcoded ──────────
def preco_td_de_secrets(nome, fallback):
    try:
        return float(st.secrets["tesouro_direto"][nome])
    except:
        return fallback

def data_td_de_secrets(nome):
    try:
        return st.secrets["tesouro_direto_data"][nome]
    except:
        return "nao definida"

@st.cache_data(ttl=21600)  # 6h — evita repetir ~10-14 downloads sequenciais a cada rerun do app
def obter_variacao_90d(tickers_tupla):
    """retorna dict {ticker: variação_90d} via yfinance, um ticker por vez (threads=False evita segfault)"""
    import datetime as _dt
    data_90d = _dt.date.today() - _dt.timedelta(days=90)
    var_90d = {}
    for ativo in tickers_tupla:
        try:
            t90 = f"{ativo}.SA"
            h = yf.download(t90, start=str(data_90d), progress=False,
                             auto_adjust=True, threads=False)
            if not h.empty and 'Close' in h.columns:
                s = h['Close'].dropna()
                if len(s) >= 2:
                    var_90d[ativo] = float((s.iloc[-1] - s.iloc[0]) / s.iloc[0])
        except Exception:
            continue
    return var_90d

def render_variacoes(key, variacoes, nota=None):
    """grade 3×2 de variação por janela (mesmo visual da aba cripto)"""
    with st.container(key=key):
        r1 = st.columns(3)
        r2 = st.columns(3)
        for col, (lbl, (v, _)) in zip(r1 + r2, variacoes.items()):
            if v is None:
                tom, texto = "neutro", "—"
            elif v >= 0:
                tom, texto = "pos", f"▲ +{fmt_pct(v)}"
            else:
                tom, texto = "neg", f"▼ {fmt_pct(v)}"
            card_html(col, lbl, texto, tom)
    if nota:
        st.caption(nota)

@st.cache_data(ttl=4 * 86400, max_entries=20, show_spinner=False)
def _preco_renda_mais_janela(janela):
    return obter_preco_renda_mais()

def obter_preco_renda_mais_cached():
    """preço/taxa do Renda+: a cada 1h no pregão, congelado fora dele"""
    return _preco_renda_mais_janela(janela_mercado(60))

def calcular_projecao_renda_mais(saldo_atual, taxa_real_aa, aporte_mensal, ano_conversao=2050,
                                  anos_pagamento=20, mes_atual=None, ano_atual=None):
    """
    Projeta o saldo acumulado do Renda+ na data de conversão e a parcela mensal
    real (poder de compra de hoje) resultante da anuidade de 240 pagamentos.

    Aproximação: usa uma única taxa real (IPCA+X% a.a.) para todo o saldo —
    inclusive o que já foi acumulado a taxas diferentes no passado — porque o
    app não guarda a taxa contratada em cada compra individual. Não considera
    IR (tabela regressiva) nem taxa de custódia sobre o excedente de 6 SM.
    """
    import datetime as _dt
    hoje = _dt.date.today()
    ano_atual  = ano_atual  or hoje.year
    mes_atual  = mes_atual  or hoje.month
    meses_ate_conversao = max((ano_conversao - ano_atual) * 12 - (mes_atual - 1), 0)

    taxa_m = (1 + taxa_real_aa) ** (1/12) - 1

    fv_saldo = saldo_atual * (1 + taxa_m) ** meses_ate_conversao
    if taxa_m > 0:
        fv_aportes = aporte_mensal * (((1 + taxa_m) ** meses_ate_conversao - 1) / taxa_m)
    else:
        fv_aportes = aporte_mensal * meses_ate_conversao

    saldo_conversao = fv_saldo + fv_aportes

    n_pag = anos_pagamento * 12
    if taxa_m > 0:
        parcela_mensal = saldo_conversao * taxa_m / (1 - (1 + taxa_m) ** -n_pag)
    else:
        parcela_mensal = saldo_conversao / n_pag

    return {
        'meses_ate_conversao': meses_ate_conversao,
        'saldo_conversao': saldo_conversao,
        'parcela_mensal': parcela_mensal,
        'total_recebido_20anos': parcela_mensal * n_pag,
    }

def calcular_trajetoria_renda_mais(saldo_atual, taxa_real_aa, aporte_mensal, ano_conversao=2050,
                                    anos_pagamento=20, mes_atual=None, ano_atual=None):
    """
    Série anual do saldo do Renda+: acumulação (hoje até a conversão) + consumo
    da anuidade (conversão até o fim dos 20 anos de pagamento). Usada só para o gráfico
    (a projeção "oficial" de saldo/parcela vem de calcular_projecao_renda_mais).
    """
    import datetime as _dt
    hoje = _dt.date.today()
    ano_atual = ano_atual or hoje.year
    mes_atual = mes_atual or hoje.month
    taxa_m = (1 + taxa_real_aa) ** (1/12) - 1
    meses_ate_conversao = max((ano_conversao - ano_atual) * 12 - (mes_atual - 1), 0)

    pontos = []
    saldo = saldo_atual
    for m in range(0, meses_ate_conversao + 1):
        ano_ref = ano_atual + (mes_atual - 1 + m) / 12
        if m % 12 == 0 or m == meses_ate_conversao:
            pontos.append({'ano': ano_ref, 'saldo': saldo, 'fase': 'acumulação'})
        saldo = saldo * (1 + taxa_m) + aporte_mensal

    saldo_conversao = pontos[-1]['saldo'] if pontos else saldo_atual
    n_pag = anos_pagamento * 12
    parcela = (saldo_conversao * taxa_m / (1 - (1 + taxa_m) ** -n_pag)) if taxa_m > 0 else (saldo_conversao / n_pag)

    saldo2 = saldo_conversao
    for m in range(1, n_pag + 1):
        saldo2 = saldo2 * (1 + taxa_m) - parcela
        ano_ref = ano_conversao + m / 12
        if m % 12 == 0 or m == n_pag:
            pontos.append({'ano': ano_ref, 'saldo': max(saldo2, 0), 'fase': 'pagamento'})

    return pd.DataFrame(pontos)

SHEET_PM_TAB = "precos_mensais"
PM_HEADERS   = ["ano_mes", "ativo", "preco_fechamento"]

# ── helpers de normalização (compartilhado) ────────────────────────────────────
def normalizar_numero(s):
    s = str(s).strip()
    if s in ('', 'nan', 'None'): return None
    s = s.replace('R$', '').replace(' ', '')
    if ',' in s and '.' not in s:
        s = s.replace(',', '.')
    elif ',' in s and '.' in s:
        if s.rindex(',') > s.rindex('.'):
            s = s.replace('.', '').replace(',', '.')
        else:
            s = s.replace(',', '')
    elif s.count('.') > 1:
        parts = s.split('.')
        if parts[0] in ('0', ''):
            s = parts[0] + '.' + ''.join(parts[1:])
        else:
            s = ''.join(parts[:-1]) + '.' + parts[-1] if len(parts[-1]) <= 2 else ''.join(parts)
    try: return float(s)
    except: return None

# ── lançamentos → posição atual ───────────────────────────────────────────────
def calcular_posicao(df_lanc):
    """retorna DataFrame com ativo, classe, qtd_atual, custo_total, preco_medio"""
    if df_lanc.empty:
        return pd.DataFrame(columns=['ativo','classe','qtd_atual','custo_total','preco_medio'])

    df = df_lanc.copy()
    df['tipo'] = df['tipo'].str.strip().str.lower()
    df['sinal'] = df['tipo'].map({'compra': 1, 'venda': -1}).fillna(0)

    ativos = df['ativo'].unique()
    rows = []
    for ativo in ativos:
        g = df[df['ativo'] == ativo]
        qtd_atual = (g['quantidade'] * g['sinal']).sum()
        if qtd_atual <= 0.000001:
            continue
        classe    = g['classe'].iloc[-1]
        compras   = g[g['tipo'] == 'compra']
        qtd_comp  = compras['quantidade'].sum()
        custo     = (compras['quantidade'] * compras['preco_unitario']).sum()
        pm        = custo / qtd_comp if qtd_comp > 0 else 0
        rows.append({
            'ativo':       ativo,
            'classe':      classe,
            'qtd_atual':   qtd_atual,
            'custo_total': custo,
            'preco_medio': pm,
        })
    return pd.DataFrame(rows)

# ── preços mensais (Sheets) ───────────────────────────────────────────────────
def ler_precos_mensais():
    try:
        svc  = get_sheets_service()
        res  = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_PM_TAB}!A:C").execute()
        rows = res.get("values", [])
        if len(rows) <= 1:
            return pd.DataFrame(columns=PM_HEADERS)
        n      = len(PM_HEADERS)
        padded = [(r + [''] * n)[:n] for r in rows[1:]]
        df_pm  = pd.DataFrame(padded, columns=PM_HEADERS)
        df_pm['preco_fechamento'] = df_pm['preco_fechamento'].apply(normalizar_numero)
        return df_pm
    except:
        return pd.DataFrame(columns=PM_HEADERS)

def pu_renda_fim_mes(df_hist, ultimo_dia):
    """PU de venda (manhã) do Renda+ 2050 no último dia útil até ultimo_dia, ou None"""
    if df_hist is None or df_hist.empty or 'pu' not in df_hist.columns:
        return None
    h = df_hist.dropna(subset=['pu'])
    h = h[h['data_dt'] <= pd.Timestamp(ultimo_dia)]
    if h.empty or (pd.Timestamp(ultimo_dia) - h['data_dt'].iloc[-1]).days > 10:
        return None
    return float(h['pu'].iloc[-1])

def migrar_precos_renda_mtm(df_pm, df_hist):
    """uma vez: troca o preço médio de compra do Renda+ nos meses gravados pelo PU de mercado"""
    if df_pm is None or df_pm.empty or df_hist is None or df_hist.empty:
        return df_pm, False
    import calendar
    df = df_pm.copy()
    mudou = False
    for i, r in df[df['ativo'] == 'Renda+ 2050'].iterrows():
        ano, m = int(str(r['ano_mes'])[:4]), int(str(r['ano_mes'])[5:7])
        pu = pu_renda_fim_mes(df_hist, pd.Timestamp(ano, m, calendar.monthrange(ano, m)[1]))
        if pu and pu > 1:
            df.at[i, 'preco_fechamento'] = round(pu, 4)
            mudou = True
    if mudou:
        svc = get_sheets_service()
        svc.values().clear(spreadsheetId=SHEET_ID, range=f"{SHEET_PM_TAB}!A:C").execute()
        corpo = [PM_HEADERS] + [[str(x['ano_mes']), str(x['ativo']), float(x['preco_fechamento'])]
                                for _, x in df.iterrows()]
        svc.values().update(spreadsheetId=SHEET_ID, range=f"{SHEET_PM_TAB}!A1",
                            valueInputOption="RAW", body={"values": corpo}).execute()
    return df, mudou

def migrar_precos_mensais_sem_ajuste(df_pm):
    """
    executa uma vez (marca na aba metas): recalcula, com fechamento SEM ajuste, os preços
    mensais de FIIs/ETFs já gravados (BTC e Tesouro não mudam) e regrava a aba.
    retorna o df atualizado.
    """
    if df_pm is None or df_pm.empty:
        return df_pm
    import calendar
    nao_b3 = {'BTC', 'Renda+ 2050', 'Tesouro Selic 2031', 'Tesouro SELIC 2031', 'Tesouro Prefixado 2032'}
    alias  = {'GALG11': 'GARE11'}
    df = df_pm.copy()
    for i, r in df.iterrows():
        a = str(r['ativo']).strip()
        if a in nao_b3:
            continue
        try:
            ano, m = int(str(r['ano_mes'])[:4]), int(str(r['ano_mes'])[5:7])
            ult = pd.Timestamp(ano, m, calendar.monthrange(ano, m)[1])
            p = obter_preco_historico_yfinance(f"{alias.get(a, a)}.SA", ult)
            if p and p >= 1.0:
                df.at[i, 'preco_fechamento'] = round(p, 4)
        except Exception:
            continue
    svc = get_sheets_service()
    svc.values().clear(spreadsheetId=SHEET_ID, range=f"{SHEET_PM_TAB}!A:C").execute()
    corpo = [PM_HEADERS] + [[str(r['ano_mes']), str(r['ativo']), float(r['preco_fechamento'])]
                            for _, r in df.iterrows()]
    svc.values().update(spreadsheetId=SHEET_ID, range=f"{SHEET_PM_TAB}!A1",
                        valueInputOption="RAW", body={"values": corpo}).execute()
    return df

def salvar_precos_mensais(rows_list):
    """rows_list: lista de [ano_mes, ativo, preco]"""
    try:
        svc = get_sheets_service()
        # garantir cabeçalho
        res = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_PM_TAB}!A1:C1").execute()
        if not res.get("values"):
            svc.values().update(
                spreadsheetId=SHEET_ID, range=f"{SHEET_PM_TAB}!A1",
                valueInputOption="RAW", body={"values": [PM_HEADERS]}
            ).execute()
        fmt_rows = [[r[0], r[1], str(r[2]).replace('.', ',')] for r in rows_list]
        svc.values().append(
            spreadsheetId=SHEET_ID, range=f"{SHEET_PM_TAB}!A:C",
            valueInputOption="USER_ENTERED", body={"values": fmt_rows}
        ).execute()
    except Exception as e:
        st.warning(f"erro ao salvar preços mensais: {e}")

@st.cache_data(ttl=6 * 3600, show_spinner=False)
def _fechamentos_historicos(ticker_sa):
    """
    fechamentos diários REAIS (auto_adjust=False) desde 2022 — o preço que de fato foi
    negociado. Com auto_adjust=True o yfinance desconta do passado todos os proventos
    pagos depois, e um FII de 2 anos atrás aparecia ~20% mais barato do que era.
    Um download por ticker (antes era um por mês).
    """
    dados = yf.download(ticker_sa, start="2022-01-01", progress=False,
                        auto_adjust=False, threads=False)
    if dados is None or dados.empty:
        return pd.Series(dtype=float)
    close = dados['Close']
    if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
    close = close.dropna()
    idx = pd.to_datetime(close.index)
    close.index = (idx.tz_localize(None) if idx.tz is not None else idx).normalize()
    return close.astype(float)

def obter_preco_historico_yfinance(ticker_sa, data_fim):
    """preço de fechamento (sem ajuste) do último pregão até data_fim"""
    try:
        s = _fechamentos_historicos(ticker_sa)
        s = s[s.index <= pd.Timestamp(data_fim)]
        if s.empty or (pd.Timestamp(data_fim) - s.index[-1]).days > 10:
            return None
        return float(s.iloc[-1])
    except Exception:
        return None

# ── Google Sheets helpers ─────────────────────────────────────────────────────
def get_sheets_service():
    creds = service_account.Credentials.from_service_account_info(
        st.secrets["gcp_service_account"],
        scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return build("sheets", "v4", credentials=creds).spreadsheets()

SHEET_ID   = st.secrets["google_sheets"]["spreadsheet_id"]
SHEET_TAB  = "lancamentos"
SHEET_CFG  = "configuracoes"
HEADERS    = ["data", "tipo", "ativo", "classe", "quantidade", "preco_unitario", "total"]

# ── taxas contratadas do Renda+ (extrato analítico Tesouro Direto) ────────────
SHEET_RENDA_TAB = "renda_mais_taxas"

# metas de longo prazo (chave → valor), editáveis em configurações
SHEET_METAS_TAB = "metas"
METAS_HEADERS   = ["chave", "valor", "descricao"]
METAS_PADRAO    = {"renda_2050_titulos_dez2045": (450.0, "títulos de Renda+ 2050 a acumular até dez/2045")}

def _num_br(s):
    """'450' · '450,5' · '1.200' · '1.200,50' · 450.0 → float"""
    import re
    if isinstance(s, (int, float)):
        return float(s)
    s = str(s).strip()
    if ',' in s:
        return float(s.replace('.', '').replace(',', '.'))
    if re.fullmatch(r"\d{1,3}(\.\d{3})+", s):
        return float(s.replace('.', ''))
    return float(s)

def ler_metas():
    """lê a aba metas → dict {chave: float}; cria a aba com os valores padrão se não existir"""
    metas = {}
    try:
        svc  = get_sheets_service()
        rows = svc.values().get(spreadsheetId=SHEET_ID,
                                range=f"{SHEET_METAS_TAB}!A:C").execute().get("values", [])
        for r in rows[1:]:
            if len(r) >= 2 and r[0].strip():
                try:
                    metas[r[0].strip()] = _num_br(r[1])
                except ValueError:
                    pass
    except Exception:
        pass
    for k, (v, desc) in METAS_PADRAO.items():
        if k not in metas:
            try:
                salvar_meta(k, v, desc)
            except Exception:
                pass
            metas[k] = v
    return metas

def salvar_meta(chave, valor, descricao=""):
    """grava/atualiza uma meta na aba metas (cria a aba se precisar)"""
    svc = get_sheets_service()
    _garantir_aba_existe(svc, SHEET_METAS_TAB, METAS_HEADERS)
    rows = svc.values().get(spreadsheetId=SHEET_ID,
                            range=f"{SHEET_METAS_TAB}!A:C").execute().get("values", [])
    nova = [chave, float(valor), descricao]
    for i, r in enumerate(rows[1:], start=2):
        if r and r[0].strip() == chave:
            if not descricao and len(r) > 2:
                nova[2] = r[2]
            svc.values().update(spreadsheetId=SHEET_ID, range=f"{SHEET_METAS_TAB}!A{i}:C{i}",
                                valueInputOption="RAW", body={"values": [nova]}).execute()
            break
    else:
        svc.values().append(spreadsheetId=SHEET_ID, range=f"{SHEET_METAS_TAB}!A:C",
                            valueInputOption="RAW", body={"values": [nova]}).execute()
    st.session_state.pop("_metas", None)

# classificação dos ativos (tipo/indexador dos FIIs, país dos ETFs) — editável pelo app
SHEET_ATIVOS_INFO_TAB = "ativos_info"
ATIVOS_INFO_HEADERS   = ["ativo", "classe", "tipo", "indexador", "pais"]

# valores de partida (os ativos que já existiam antes da aba); a aba prevalece sobre eles
FII_INFO_PADRAO = {
    'TRXF11': {'tipo': 'tijolo',  'indexador': None},
    'XPML11': {'tipo': 'tijolo',  'indexador': None},
    'XPLG11': {'tipo': 'tijolo',  'indexador': None},
    'KNRI11': {'tipo': 'tijolo',  'indexador': None},
    'BTLG11': {'tipo': 'tijolo',  'indexador': None},
    'GARE11': {'tipo': 'tijolo',  'indexador': None},
    'RZTR11': {'tipo': 'tijolo',  'indexador': None},
    'BTCI11': {'tipo': 'papel',   'indexador': 'IPCA'},
    'VGIR11': {'tipo': 'papel',   'indexador': 'CDI'},
    'MCCI11': {'tipo': 'papel',   'indexador': 'IPCA'},
    'KNCR11': {'tipo': 'papel',   'indexador': 'CDI'},
}
GEO_ETF_PADRAO = {'IVVB11': 'EUA', 'DIVO11': 'Brasil', 'PKIN11': 'China', 'LFTB11': 'Brasil'}
PAISES_ETF     = ['Brasil', 'EUA', 'China', 'Europa', 'Emergentes', 'Global']

def ler_ativos_info():
    """lê a aba ativos_info → dict {ativo: {classe, tipo, indexador, pais}} (vazio se não existir)"""
    try:
        svc  = get_sheets_service()
        rows = svc.values().get(spreadsheetId=SHEET_ID,
                                range=f"{SHEET_ATIVOS_INFO_TAB}!A:E").execute().get("values", [])
    except Exception:
        return {}
    info = {}
    for r in rows[1:]:
        r = (r + [''] * 5)[:5]
        a = r[0].strip().upper()
        if a:
            info[a] = {'classe': r[1].strip(), 'tipo': r[2].strip() or None,
                       'indexador': r[3].strip() or None, 'pais': r[4].strip() or None}
    return info

def salvar_ativo_info(ativo, classe, tipo=None, indexador=None, pais=None):
    """grava/atualiza a classificação de um ativo na aba ativos_info (cria a aba se precisar)"""
    svc = get_sheets_service()
    _garantir_aba_existe(svc, SHEET_ATIVOS_INFO_TAB, ATIVOS_INFO_HEADERS)
    rows = svc.values().get(spreadsheetId=SHEET_ID,
                            range=f"{SHEET_ATIVOS_INFO_TAB}!A:E").execute().get("values", [])
    nova = [ativo.upper(), classe, tipo or '', indexador or '', pais or '']
    for i, r in enumerate(rows[1:], start=2):
        if r and r[0].strip().upper() == ativo.upper():
            svc.values().update(spreadsheetId=SHEET_ID, range=f"{SHEET_ATIVOS_INFO_TAB}!A{i}:E{i}",
                                valueInputOption="RAW", body={"values": [nova]}).execute()
            break
    else:
        svc.values().append(spreadsheetId=SHEET_ID, range=f"{SHEET_ATIVOS_INFO_TAB}!A:E",
                            valueInputOption="RAW", body={"values": [nova]}).execute()
    st.session_state.pop("_ativos_info", None)

@st.cache_data(ttl=3600, show_spinner=False)
def validar_ticker_b3(ticker):
    """último fechamento do ticker na B3 (0 se não existir) — valida ativo novo antes de salvar"""
    try:
        h = yf.download(f"{ticker.upper()}.SA", period="5d", progress=False,
                        auto_adjust=True, threads=False)
        if h is None or h.empty:
            return 0.0
        c = h['Close']
        if isinstance(c, pd.DataFrame):
            c = c.iloc[:, 0]
        c = c.dropna()
        return float(c.iloc[-1]) if not c.empty else 0.0
    except Exception:
        return 0.0
RENDA_HEADERS   = ["data", "valor_investido", "taxa_contratada_pct"]

@st.cache_data(ttl=3600)
def ler_renda_taxas():
    """lê histórico de taxas contratadas por aporte no Renda+: DataFrame [data, valor_investido, taxa_contratada_pct]"""
    try:
        svc  = get_sheets_service()
        res  = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_RENDA_TAB}!A:C").execute()
        rows = res.get("values", [])
        if len(rows) <= 1:
            return pd.DataFrame(columns=RENDA_HEADERS)
        n      = len(RENDA_HEADERS)
        padded = [(r + [''] * n)[:n] for r in rows[1:]]
        df_rt  = pd.DataFrame(padded, columns=RENDA_HEADERS)
        df_rt['valor_investido']     = df_rt['valor_investido'].apply(normalizar_numero)
        df_rt['taxa_contratada_pct'] = df_rt['taxa_contratada_pct'].apply(normalizar_numero)
        return df_rt.dropna(subset=['valor_investido', 'taxa_contratada_pct'])
    except Exception:
        return pd.DataFrame(columns=RENDA_HEADERS)

def _garantir_aba_existe(svc, nome_aba, headers=None):
    """cria a aba no Sheets se ainda não existir, com cabeçalho opcional"""
    meta = svc.get(spreadsheetId=SHEET_ID).execute()
    existentes = [s['properties']['title'] for s in meta.get('sheets', [])]
    if nome_aba not in existentes:
        svc.batchUpdate(
            spreadsheetId=SHEET_ID,
            body={"requests": [{"addSheet": {"properties": {"title": nome_aba}}}]}
        ).execute()
        if headers:
            svc.values().update(
                spreadsheetId=SHEET_ID, range=f"{nome_aba}!A1",
                valueInputOption="USER_ENTERED", body={"values": [headers]}
            ).execute()

def salvar_renda_taxas(df_novo):
    """sobrescreve a aba inteira com o conteúdo do extrato mais recente (fonte é sempre o extrato completo)"""
    try:
        svc = get_sheets_service()
        _garantir_aba_existe(svc, SHEET_RENDA_TAB, RENDA_HEADERS)
        svc.values().clear(spreadsheetId=SHEET_ID, range=f"{SHEET_RENDA_TAB}!A:C").execute()
        fmt_rows = [RENDA_HEADERS] + [
            [r['data'], str(r['valor_investido']).replace('.', ','), str(r['taxa_contratada_pct']).replace('.', ',')]
            for _, r in df_novo.iterrows()
        ]
        svc.values().update(
            spreadsheetId=SHEET_ID, range=f"{SHEET_RENDA_TAB}!A1",
            valueInputOption="USER_ENTERED", body={"values": fmt_rows}
        ).execute()
        return True
    except Exception as e:
        st.warning(f"erro ao salvar taxas do Renda+: {e}")
        return False

# ── histórico de taxa de mercado do Renda+ 2050 (persistido, atualizado incrementalmente) ──
SHEET_RENDA_MERCADO_TAB = "renda_mais_taxa_mercado"
RENDA_MERCADO_HEADERS   = ["data", "taxa_compra_manha", "pu_venda_manha"]

def ler_historico_taxa_mercado():
    """lê o histórico de taxa de mercado já salvo no Sheets — rápido, não bate no Tesouro Transparente"""
    try:
        svc = get_sheets_service()
        res = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_RENDA_MERCADO_TAB}!A:C").execute()
        rows = res.get("values", [])
        if len(rows) <= 1:
            return pd.DataFrame(columns=['data_dt', 'taxa', 'pu'])
        n = len(RENDA_MERCADO_HEADERS)
        df = pd.DataFrame([(r + [''] * n)[:n] for r in rows[1:]], columns=RENDA_MERCADO_HEADERS)
        df['data_dt'] = pd.to_datetime(df['data'], format='%d/%m/%Y', errors='coerce')
        df['taxa']    = df['taxa_compra_manha'].apply(normalizar_numero)
        df['pu']      = df['pu_venda_manha'].apply(lambda x: normalizar_numero(x) if str(x).strip() else None)
        return df.dropna(subset=['data_dt', 'taxa'])[['data_dt', 'taxa', 'pu']].sort_values('data_dt').reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=['data_dt', 'taxa', 'pu'])

def salvar_historico_taxa_mercado(df_completo):
    """sobrescreve a aba inteira com a série completa e atualizada (cria a aba se não existir)"""
    try:
        svc = get_sheets_service()
        _garantir_aba_existe(svc, SHEET_RENDA_MERCADO_TAB, RENDA_MERCADO_HEADERS)
        svc.values().clear(spreadsheetId=SHEET_ID, range=f"{SHEET_RENDA_MERCADO_TAB}!A:C").execute()
        linhas = [RENDA_MERCADO_HEADERS] + [
            [r['data_dt'].strftime('%d/%m/%Y'), str(r['taxa']).replace('.', ','),
             (str(r['pu']).replace('.', ',') if pd.notna(r.get('pu')) else '')]
            for _, r in df_completo.iterrows()
        ]
        svc.values().update(
            spreadsheetId=SHEET_ID, range=f"{SHEET_RENDA_MERCADO_TAB}!A1",
            valueInputOption="USER_ENTERED", body={"values": linhas}
        ).execute()
        return True
    except Exception as e:
        st.warning(f"erro ao salvar histórico de taxa de mercado: {e}")
        return False

# ── dividendos mensais (persistido: valor do mês + acumulado) ─────────────────
SHEET_DIV_MENSAL_TAB = "dividendos_mensais"
DIV_MENSAL_HEADERS   = ["ano_mes", "valor_mes", "acumulado"]

def ler_dividendos_mensais():
    """lê o histórico de dividendos mensais já salvo — rápido, não recalcula nada"""
    try:
        svc = get_sheets_service()
        res = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_DIV_MENSAL_TAB}!A:C").execute()
        rows = res.get("values", [])
        if len(rows) <= 1:
            return pd.DataFrame(columns=DIV_MENSAL_HEADERS)
        df_dm = pd.DataFrame(rows[1:], columns=DIV_MENSAL_HEADERS)
        df_dm['valor_mes'] = df_dm['valor_mes'].apply(normalizar_numero)
        df_dm['acumulado'] = df_dm['acumulado'].apply(normalizar_numero)
        return df_dm.dropna(subset=['ano_mes']).sort_values('ano_mes').reset_index(drop=True)
    except Exception:
        return pd.DataFrame(columns=DIV_MENSAL_HEADERS)

def salvar_dividendos_mensais_lote(rows):
    """adiciona novas linhas (ano_mes, valor_mes, acumulado) — nunca sobrescreve as já salvas"""
    try:
        svc = get_sheets_service()
        _garantir_aba_existe(svc, SHEET_DIV_MENSAL_TAB, DIV_MENSAL_HEADERS)
        fmt_rows = [[r[0], str(r[1]).replace('.', ','), str(r[2]).replace('.', ',')] for r in rows]
        svc.values().append(
            spreadsheetId=SHEET_ID, range=f"{SHEET_DIV_MENSAL_TAB}!A:C",
            valueInputOption="USER_ENTERED", body={"values": fmt_rows}
        ).execute()
        return True
    except Exception as e:
        st.warning(f"erro ao salvar dividendos mensais: {e}")
        return False

@st.cache_data(ttl=43200)  # 12h — evita recalcular/rebater no yfinance a cada rerun
def atualizar_dividendos_mensais(df_lanc_json):
    """
    mantém a aba dividendos_mensais sempre completa até o último mês fechado: calcula e
    grava só os meses que ainda não foram salvos (na primeira vez, faz o backfill de todos
    os meses desde a primeira compra de FII). Meses já salvos NUNCA são recalculados —
    são histórico fechado, inclusive preservando ajustes manuais feitos direto na planilha
    (como o AJUSTE-DIVIDENDOS). Retorna o DataFrame completo (existente + novo).
    """
    import datetime as _dt_div

    df_existente = ler_dividendos_mensais()
    meses_salvos = set(df_existente['ano_mes']) if not df_existente.empty else set()

    df_lanc_raw_div = pd.DataFrame(df_lanc_json)
    if df_lanc_raw_div.empty:
        return df_existente
    df_lanc_raw_div['data_dt'] = pd.to_datetime(df_lanc_raw_div['data'], format='%d/%m/%Y', errors='coerce')
    _primeira_data = df_lanc_raw_div[df_lanc_raw_div['classe'].str.upper() == 'FII']['data_dt'].min()
    if pd.isna(_primeira_data):
        return df_existente

    hoje = _dt_div.date.today()
    _periodo_fim = pd.Period(hoje, freq='M') - 1  # último mês fechado
    _periodo_ini = _primeira_data.to_period('M')
    if _periodo_ini > _periodo_fim:
        return df_existente

    _todos_meses = pd.period_range(start=_periodo_ini, end=_periodo_fim, freq='M')
    _meses_faltando = sorted(str(m) for m in _todos_meses if str(m) not in meses_salvos)
    if not _meses_faltando:
        return df_existente

    _acumulado = float(df_existente['acumulado'].iloc[-1]) if not df_existente.empty else 0.0
    _novas_linhas = []
    for _mes_str in _meses_faltando:
        _ano_m, _mes_m = int(_mes_str[:4]), int(_mes_str[5:7])
        _valor_mes, _ = calcular_dividendos_mes(df_lanc_json, _mes_m, _ano_m)
        _acumulado += _valor_mes
        _novas_linhas.append([_mes_str, round(_valor_mes, 2), round(_acumulado, 2)])

    salvar_dividendos_mensais_lote(_novas_linhas)

    return pd.concat([
        df_existente, pd.DataFrame(_novas_linhas, columns=DIV_MENSAL_HEADERS)
    ], ignore_index=True).sort_values('ano_mes').reset_index(drop=True)

@st.cache_data(ttl=43200)  # 12h — evita rebater no Sheets/Tesouro Transparente a cada rerun
@st.cache_data(ttl=4 * 86400, max_entries=10, show_spinner=False)
def _historico_renda_janela(janela):
    return _obter_historico_taxa_renda_mais()

def obter_historico_taxa_renda_mais():
    """histórico de taxa e PU do Renda+ — relido a cada 1h no pregão, congelado fora dele"""
    return _historico_renda_janela(janela_mercado(60))

def _obter_historico_taxa_renda_mais():
    """
    série histórica completa da taxa de mercado do Renda+ 2050, mantida permanentemente
    na aba renda_mais_taxa_mercado: na primeira vez (aba vazia) faz um backfill completo
    baixando uma fatia grande do CSV do Tesouro Transparente; nas vezes seguintes baixa só
    uma fatia pequena (cobre algumas semanas/meses) e soma apenas os dias que ainda não
    estavam salvos. Nunca mais rebaixa anos de histórico que já tem guardado.
    """
    df_armazenado = ler_historico_taxa_mercado()

    # backfill completo quando não tem nada salvo OU quando falta o PU (aba antiga, só com taxa);
    # senão, incremento pequeno
    _falta_pu = (not df_armazenado.empty) and ('pu' not in df_armazenado.columns
                                               or df_armazenado['pu'].isna().any())
    fatia = 200_000_000 if (df_armazenado.empty or _falta_pu) else 8_000_000
    df_novo, erro = _baixar_fatia_taxa_renda_mais(fatia)

    if df_novo.empty:
        return df_armazenado, erro

    if df_armazenado.empty or _falta_pu:
        _extra = df_armazenado[~df_armazenado['data_dt'].dt.date.isin(set(df_novo['data_dt'].dt.date))] \
            if not df_armazenado.empty else df_armazenado
        df_completo = pd.concat([df_novo, _extra], ignore_index=True) if not _extra.empty else df_novo
    else:
        datas_existentes = set(df_armazenado['data_dt'].dt.date)
        df_novo_filtrado = df_novo[~df_novo['data_dt'].dt.date.isin(datas_existentes)]
        if df_novo_filtrado.empty:
            return df_armazenado, None  # nada novo pra adicionar, já está tudo salvo
        df_completo = pd.concat([df_armazenado, df_novo_filtrado], ignore_index=True)

    df_completo = df_completo.sort_values('data_dt').drop_duplicates(subset=['data_dt']).reset_index(drop=True)
    salvar_historico_taxa_mercado(df_completo)
    return df_completo, None

def parse_extrato_renda_mais(arquivo_upload):
    """
    parseia o Extrato Analítico do Tesouro Renda+ (xlsx baixado do Tesouro Direto/corretora).
    retorna DataFrame [data, valor_investido, taxa_contratada_pct] com uma linha por aporte.
    """
    import re
    wb = openpyxl.load_workbook(arquivo_upload, data_only=True)
    ws = wb.worksheets[0]

    def _to_float(v):
        if v is None:
            return None
        if isinstance(v, (int, float)):
            return float(v)
        s = str(v).strip().replace('.', '').replace(',', '.')
        try:
            return float(s)
        except Exception:
            return None

    registros = []
    for row in ws.iter_rows(min_row=1, values_only=True):
        if not row or row[0] is None:
            continue
        data_str = str(row[0]).strip()
        # linhas de aporte começam com data no formato DD/MM/AAAA
        if not re.match(r'^\d{2}/\d{2}/\d{4}$', data_str):
            continue
        valor_investido = _to_float(row[3]) if len(row) > 3 else None   # coluna D
        taxa_raw = row[4] if len(row) > 4 else None                    # coluna E: "IPCA + 6,36%"
        if valor_investido is None or not taxa_raw:
            continue
        m = re.search(r'([\d,]+)\s*%', str(taxa_raw))
        if not m:
            continue
        taxa = float(m.group(1).replace(',', '.'))
        registros.append({'data': data_str, 'valor_investido': valor_investido, 'taxa_contratada_pct': taxa})

    return pd.DataFrame(registros)

def taxas_aportes_renda_mais(df_lanc, df_hist_taxa, df_extrato=None):
    """
    taxa contratada de cada aporte no Renda+ 2050, sem upload manual:
    para cada compra nos lançamentos, pega a taxa de mercado do dia (Taxa Compra Manhã do
    Tesouro Transparente; em fim de semana/feriado, a do último dia útil anterior).
    Se a aba renda_mais_taxas (extrato antigo) tiver a mesma data, usa a taxa do extrato,
    que é a exata. retorna DataFrame [data, data_dt, valor_investido, taxa_contratada_pct, fonte]
    """
    cols = ['data', 'data_dt', 'valor_investido', 'taxa_contratada_pct', 'fonte']
    if df_lanc is None or df_lanc.empty or df_hist_taxa is None or df_hist_taxa.empty:
        return pd.DataFrame(columns=cols)
    c = df_lanc[(df_lanc['ativo'].astype(str).str.contains('renda', case=False)) &
                (df_lanc['tipo'].astype(str).str.strip().str.lower() == 'compra')].copy()
    if c.empty:
        return pd.DataFrame(columns=cols)
    c['data_dt'] = pd.to_datetime(c['data'], format='%d/%m/%Y', errors='coerce').dt.normalize()
    c = c.dropna(subset=['data_dt'])
    c['valor_investido'] = (pd.to_numeric(c['quantidade'], errors='coerce') *
                            pd.to_numeric(c['preco_unitario'], errors='coerce'))
    c = c[c['valor_investido'] > 0]

    hist = df_hist_taxa[['data_dt', 'taxa']].dropna().copy()
    hist['data_dt'] = pd.to_datetime(hist['data_dt']).dt.normalize()
    hist = hist.sort_values('data_dt').drop_duplicates('data_dt')
    c = pd.merge_asof(c.sort_values('data_dt'), hist, on='data_dt', direction='backward')
    c['taxa_contratada_pct'] = c['taxa']
    c['fonte'] = 'mercado'

    # extrato antigo (taxa exata) prevalece na mesma data
    if df_extrato is not None and not df_extrato.empty:
        ext = df_extrato.copy()
        ext['data_dt'] = pd.to_datetime(ext['data'], format='%d/%m/%Y', errors='coerce').dt.normalize()
        ext = ext.dropna(subset=['data_dt']).groupby('data_dt')['taxa_contratada_pct'].mean()
        _m = c['data_dt'].isin(ext.index)
        c.loc[_m, 'taxa_contratada_pct'] = c.loc[_m, 'data_dt'].map(ext)
        c.loc[_m, 'fonte'] = 'extrato'

    c = c.dropna(subset=['taxa_contratada_pct'])
    c['data'] = c['data_dt'].dt.strftime('%d/%m/%Y')
    return c[cols].reset_index(drop=True)

def calcular_taxa_media_ponderada_renda(df_taxas):
    """taxa média ponderada pelo valor investido em cada aporte. retorna None se não houver dados."""
    if df_taxas is None or df_taxas.empty:
        return None
    total = df_taxas['valor_investido'].sum()
    if total <= 0:
        return None
    return float((df_taxas['valor_investido'] * df_taxas['taxa_contratada_pct']).sum() / total)

def ler_configuracoes():
    """lê alvos do Sheets: retorna dict {ativo: {min, alvo, max}}"""
    try:
        svc = get_sheets_service()
        res = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_CFG}!A:D").execute()
        rows = res.get("values", [])
        if len(rows) <= 1:
            return {}
        cfg = {}
        def _pf(s):
            try: return float(str(s).replace(',', '.')) if s else None
            except: return None
        for row in rows[1:]:
            if not row: continue
            ativo = row[0].strip()
            if len(row) == 2:
                # formato antigo: ativo | alvo_pct
                cfg[ativo] = {'min': None, 'alvo': _pf(row[1]), 'max': None}
            elif len(row) >= 3:
                # formato novo: ativo | min | alvo | max
                cfg[ativo] = {
                    'min':  _pf(row[1]),
                    'alvo': _pf(row[2]),
                    'max':  _pf(row[3]) if len(row) > 3 else None,
                }
        return cfg
    except:
        return {}

def _get_banda(cfg, ativo):
    """retorna dict {min, alvo, max} tolerante a formato antigo (float) e novo (dict)"""
    v = cfg.get(ativo, {})
    if isinstance(v, dict):
        return v
    if isinstance(v, (int, float)):
        return {'min': None, 'alvo': float(v), 'max': None}
    return {}

def salvar_configuracoes(cfg: dict):
    """salva dict {ativo: {min, alvo, max}} no Sheets"""
    try:
        svc = get_sheets_service()
        svc.values().clear(spreadsheetId=SHEET_ID, range=f"{SHEET_CFG}!A:D").execute()
        values = [["ativo", "alvo_min", "alvo_pct", "alvo_max"]]
        for ativo, banda in cfg.items():
            values.append([
                ativo,
                banda.get('min', ''),
                banda.get('alvo', ''),
                banda.get('max', ''),
            ])
        svc.values().update(
            spreadsheetId=SHEET_ID, range=f"{SHEET_CFG}!A1",
            valueInputOption="USER_ENTERED", body={"values": values}
        ).execute()
        return True
    except Exception as e:
        st.error(f"erro ao salvar: {e}")
        return False

def ler_lancamentos(_versao=0):
    try:
        svc  = get_sheets_service()
        res  = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A:G").execute()
        rows = res.get("values", [])
        if len(rows) <= 1:
            return pd.DataFrame(columns=HEADERS)
        n = len(HEADERS)
        padded = [(r + [''] * n)[:n] for r in rows[1:]]
        df_l = pd.DataFrame(padded, columns=HEADERS)
        for col in ["quantidade", "preco_unitario", "total"]:
            df_l[col] = df_l[col].apply(normalizar_numero)
            df_l[col] = pd.to_numeric(df_l[col], errors="coerce")
        return df_l
    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        return pd.DataFrame(columns=HEADERS)

def salvar_lancamento(row: list):
    def fmt_num(v):
        return str(v).replace('.', ',')
    row_fmt = [row[0], row[1], row[2], row[3],
               fmt_num(row[4]), fmt_num(row[5]), fmt_num(row[6])]
    svc = get_sheets_service()
    svc.values().append(
        spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A:G",
        valueInputOption="USER_ENTERED", body={"values": [row_fmt]}
    ).execute()
    st.session_state["_lanc_versao"] = st.session_state.get("_lanc_versao", 0) + 1

def salvar_lancamentos_lote(rows: list):
    """salva vários lançamentos de uma vez — rows: lista de [data, tipo, ativo, classe, quantidade, preco_unitario, total]"""
    def fmt_num(v):
        return str(v).replace('.', ',')
    rows_fmt = [[r[0], r[1], r[2], r[3], fmt_num(r[4]), fmt_num(r[5]), fmt_num(r[6])] for r in rows]
    svc = get_sheets_service()
    svc.values().append(
        spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A:G",
        valueInputOption="USER_ENTERED", body={"values": rows_fmt}
    ).execute()
    st.session_state["_lanc_versao"] = st.session_state.get("_lanc_versao", 0) + 1

def _get_sheet_id(svc, nome_aba):
    """retorna o sheetId numérico real da aba pelo nome"""
    meta = svc.get(spreadsheetId=SHEET_ID, fields="sheets.properties").execute()
    for s in meta.get("sheets", []):
        p = s.get("properties", {})
        if p.get("title") == nome_aba:
            return p["sheetId"]
    raise ValueError(f"aba '{nome_aba}' não encontrada no spreadsheet")

def deletar_lancamento(idx_linha_sheet: int):
    svc = get_sheets_service()
    sheet_id_real = _get_sheet_id(svc, SHEET_TAB)
    start = idx_linha_sheet - 1
    body = {"requests": [{"deleteDimension": {"range": {
        "sheetId": sheet_id_real, "dimension": "ROWS",
        "startIndex": start, "endIndex": start + 1
    }}}]}
    svc.batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
    st.session_state["_lanc_versao"] = st.session_state.get("_lanc_versao", 0) + 1

def garantir_cabecalho():
    try:
        svc = get_sheets_service()
        res = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A1:H1").execute()
        if not res.get("values"):
            svc.values().update(
                spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A1",
                valueInputOption="RAW", body={"values": [HEADERS]}
            ).execute()
    except:
        pass

garantir_cabecalho()

def popular_precos_mensais(df_lanc, df_pm_existente):
    """verifica meses sem preço e popula via yfinance, retorna df_pm atualizado"""
    import datetime, calendar
    if df_lanc.empty: return df_pm_existente

    df_lanc = df_lanc.copy()
    df_lanc['data_dt'] = pd.to_datetime(df_lanc['data'], format='%d/%m/%Y', errors='coerce')
    hoje = datetime.date.today()
    mes_atual = f"{hoje.year}-{hoje.month:02d}"

    # todos os meses desde o primeiro lançamento até o mês anterior ao atual
    data_min = df_lanc['data_dt'].dropna().min().date()
    ano0, m0 = data_min.year, data_min.month
    ano1, m1 = hoje.year, hoje.month
    # recuar 1 mês para não incluir o mês atual
    m1 -= 1
    if m1 == 0: m1, ano1 = 12, ano1 - 1

    meses = []
    a, m = ano0, m0
    while (a, m) <= (ano1, m1):
        meses.append(f"{a}-{m:02d}")
        m += 1
        if m > 12: m, a = 1, a + 1

    ALIAS_B3 = {'GALG11': 'GARE11'}
    TESOURO  = ['Renda+ 2050', 'Tesouro Selic 2031', 'Tesouro SELIC 2031', 'Tesouro Prefixado 2032']
    try:
        _hist_renda_pm, _ = obter_historico_taxa_renda_mais()
    except Exception:
        _hist_renda_pm = None
    novos = []

    for mes in meses:
        df_ate = df_lanc[df_lanc['data_dt'].dt.to_period('M').astype(str) <= mes].copy()
        pos = calcular_posicao(df_ate)
        if pos.empty: continue

        for _, row in pos.iterrows():
            ativo = row['ativo']
            if not df_pm_existente.empty:
                existe = ((df_pm_existente['ano_mes'] == mes) &
                          (df_pm_existente['ativo']   == ativo)).any()
                if existe: continue

            ano, m = int(mes[:4]), int(mes[5:7])
            ultimo_dia = datetime.date(ano, m, calendar.monthrange(ano, m)[1])

            if ativo == 'BTC':
                preco = None
                # tentativa 1: CoinGecko history
                try:
                    url = "https://api.coingecko.com/api/v3/coins/bitcoin/history"
                    r = requests.get(url, params={"date": ultimo_dia.strftime('%d-%m-%Y')}, timeout=10)
                    if r.status_code == 200:
                        preco = r.json()['market_data']['current_price']['brl']
                except: pass
                # tentativa 2: yfinance BTC-BRL direto
                if not preco:
                    try:
                        start_str = str(ultimo_dia - datetime.timedelta(days=7))
                        end_str   = str(ultimo_dia + datetime.timedelta(days=1))
                        dados = yf.download("BTC-BRL", start=start_str, end=end_str,
                                            progress=False, auto_adjust=True)
                        if not dados.empty:
                            c = dados['Close']
                            if isinstance(c, pd.DataFrame): c = c.iloc[:,0]
                            v = float(c.ffill().dropna().iloc[-1])
                            if v > 1000: preco = v
                    except: pass
                # tentativa 3: yfinance BTC-USD × USDBRL
                if not preco:
                    try:
                        start_str = str(ultimo_dia - datetime.timedelta(days=7))
                        end_str   = str(ultimo_dia + datetime.timedelta(days=1))
                        btc_usd = yf.download("BTC-USD", start=start_str, end=end_str,
                                              progress=False, auto_adjust=True)['Close']
                        usd_brl = yf.download("BRL=X",   start=start_str, end=end_str,
                                              progress=False, auto_adjust=True)['Close']
                        if isinstance(btc_usd, pd.DataFrame): btc_usd = btc_usd.iloc[:,0]
                        if isinstance(usd_brl, pd.DataFrame): usd_brl = usd_brl.iloc[:,0]
                        btc_brl = (btc_usd * usd_brl).ffill().dropna()
                        if not btc_brl.empty:
                            v = float(btc_brl.iloc[-1])
                            if v > 1000: preco = v
                    except: pass
            elif ativo == 'Renda+ 2050' and pu_renda_fim_mes(_hist_renda_pm, ultimo_dia):
                preco = pu_renda_fim_mes(_hist_renda_pm, ultimo_dia)
            elif ativo in TESOURO:
                comp = df_lanc[(df_lanc['ativo'] == ativo) & (df_lanc['tipo'] == 'compra')]
                comp_ate = comp[comp['data_dt'].dt.to_period('M').astype(str) <= mes]
                if not comp_ate.empty and comp_ate['quantidade'].sum() > 0:
                    preco = (comp_ate['quantidade'] * comp_ate['preco_unitario']).sum() / comp_ate['quantidade'].sum()
                else:
                    preco = row['preco_medio']
            else:
                ativo_norm = ALIAS_B3.get(ativo, ativo)
                preco = obter_preco_historico_yfinance(f"{ativo_norm}.SA", ultimo_dia)
                # validar preço mínimo para FIIs (evitar dados corrompidos do yfinance)
                if preco and preco < 1.0:
                    preco = None

            if preco and preco > 0:
                novos.append([mes, ativo, round(preco, 4)])

    if novos:
        salvar_precos_mensais(novos)
        df_novos = pd.DataFrame(novos, columns=PM_HEADERS)
        df_novos['preco_fechamento'] = pd.to_numeric(df_novos['preco_fechamento'])
        return pd.concat([df_pm_existente, df_novos], ignore_index=True)

    return df_pm_existente

def investimento_liquido(df_lanc):
    """
    dinheiro líquido aplicado = Σ compras − Σ vendas (quantidade × preço unitário).
    O que volta de vendas e é reaplicado não conta como dinheiro novo; lucro realizado
    numa venda fica do lado do ganho de capital.
    """
    if df_lanc is None or df_lanc.empty:
        return 0.0
    t = df_lanc['tipo'].astype(str).str.strip().str.lower()
    v = (pd.to_numeric(df_lanc['quantidade'], errors='coerce').fillna(0) *
         pd.to_numeric(df_lanc['preco_unitario'], errors='coerce').fillna(0))
    return float(v[t == 'compra'].sum() - v[t == 'venda'].sum())

@st.cache_data(ttl=3600, show_spinner=False)
def calcular_valores_mensais(df_lanc_json, df_pm_json):
    """calcula valor da carteira por mês — cacheado por 1h"""
    import datetime
    df_lanc = pd.DataFrame(df_lanc_json)
    df_pm   = pd.DataFrame(df_pm_json)
    if df_lanc.empty or df_pm.empty:
        return []
    hoje      = datetime.date.today()
    mes_atual = f"{hoje.year}-{hoje.month:02d}"
    meses_pm  = sorted(df_pm['ano_mes'].unique())
    meses_pm  = [m for m in meses_pm if m < mes_atual]
    if not meses_pm:
        return []
    df_lanc['data_dt'] = pd.to_datetime(df_lanc['data'], format='%d/%m/%Y', errors='coerce')
    vals = []
    ultimo_total, ultimo_custo = 0.0, 0.0
    ano0, m0 = int(meses_pm[0][:4]), int(meses_pm[0][5:7])
    ano1, m1 = int(meses_pm[-1][:4]), int(meses_pm[-1][5:7])
    todos_meses, a, m = [], ano0, m0
    while (a, m) <= (ano1, m1):
        todos_meses.append(f"{a}-{m:02d}")
        m += 1
        if m > 12: m, a = 1, a + 1
    for mes in todos_meses:
        if mes in meses_pm:
            df_ate  = df_lanc[df_lanc['data_dt'].dt.to_period('M').astype(str) <= mes].copy()
            pos_mes = calcular_posicao(df_ate)
            # dinheiro líquido aplicado até o mês (compras − vendas)
            custo_mes = investimento_liquido(df_ate)
            total_mes = 0.0
            for _, pr in pos_mes.iterrows():
                pm_row = df_pm[(df_pm['ano_mes'] == mes) & (df_pm['ativo'] == pr['ativo'])]
                preco_hist = float(pm_row['preco_fechamento'].iloc[0]) if not pm_row.empty else pr['preco_medio']
                total_mes += pr['qtd_atual'] * preco_hist
            ultimo_total, ultimo_custo = total_mes, custo_mes
        else:
            total_mes, custo_mes = ultimo_total, ultimo_custo
        vals.append({'mes': f"{mes}-01", 'total': total_mes, 'custo': custo_mes, 'atual': False})
    return vals

# ── expiração da sessão: aba aberta há horas/dias não fica com dados velhos ──
# lançamentos, preços mensais, alvos, classificação e metas são relidos do Sheets
# quando a janela muda (30 em 30 min no pregão; uma vez por dia fora dele)
_janela_sessao = janela_mercado(30)
if st.session_state.get("_janela_sessao") != _janela_sessao:
    for _k in ["_df_lanc_raw_cached", "_cache_versao", "_df_pm", "cfg_alvos",
               "_ativos_info", "_metas", "_precos_falha"]:
        st.session_state.pop(_k, None)
    st.session_state["_janela_sessao"] = _janela_sessao

# ── carregar dados principais (session_state cache) ──────────────────────────
# relê do Sheets só na primeira renderização da sessão
# ou após salvar/excluir lançamento (_lanc_versao muda)
_versao_atual = st.session_state.get("_lanc_versao", 0)
_cache_versao = st.session_state.get("_cache_versao", -1)

if _versao_atual != _cache_versao or "_df_lanc_raw_cached" not in st.session_state:
    with st.spinner("carregando lançamentos..."):
        st.session_state["_df_lanc_raw_cached"] = ler_lancamentos()
        st.session_state["_cache_versao"] = _versao_atual

_df_lanc_raw = st.session_state["_df_lanc_raw_cached"]

# calcular posição atual
_posicao = calcular_posicao(_df_lanc_raw)

# carregar alvos do Sheets
if "cfg_alvos" not in st.session_state:
    st.session_state["cfg_alvos"] = ler_configuracoes()
_cfg_alvos = st.session_state["cfg_alvos"]


# preços atuais — a cada 5 min no pregão (seg–sex, 10h–19h), congelados fora dele
_todos_b3 = [r['ativo'] for _, r in _posicao.iterrows()
             if r['classe'] in ('ETF', 'FII') and r['ativo'] != 'BTC']
precos = obter_precos_b3(_todos_b3)
precos['BTC'] = obter_preco_btc_brl()

# preço Renda+ (API ou secrets)
_resultado_renda = obter_preco_renda_mais_cached()
if _resultado_renda and _resultado_renda[0]:
    precos['Renda+ 2050'] = _resultado_renda[0]
    st.session_state['preco_renda_auto'] = _resultado_renda[0]
    st.session_state['data_renda_auto']  = _resultado_renda[1]
    if len(_resultado_renda) > 2 and _resultado_renda[2]:
        st.session_state['taxa_renda_auto'] = _resultado_renda[2]
    else:
        st.session_state.pop('taxa_renda_auto', None)   # não mostrar taxa de outra fonte/dia
else:
    precos['Renda+ 2050'] = preco_td_de_secrets('Renda+ 2050', 490.02)
    if _resultado_renda:
        st.session_state['preco_renda_erro'] = _resultado_renda[1]

precos['Tesouro Selic 2031']     = preco_td_de_secrets('Tesouro Selic 2031', 13000.0)
precos['Tesouro SELIC 2031']     = precos['Tesouro Selic 2031']
precos['Tesouro Prefixado 2032'] = preco_td_de_secrets('Tesouro Prefixado 2032', 700.0)

# alerta de preços com problema
_falhas = st.session_state.pop('_precos_falha', [])
if _falhas:
    st.warning(f"⚠️ preço não obtido para: {', '.join(_falhas)} — verifique os tickers.", icon="⚠️")

# construir df principal
linhas = []
for _, r in _posicao.iterrows():
    ativo  = r['ativo']
    classe = r['classe']
    qtd    = r['qtd_atual']
    prc    = precos.get(ativo, precos.get(ativo.upper(), 0.0))
    linhas.append({
        'Ativo':         ativo,
        'Classe':        classe,
        'preco_unit':    prc,
        'Qtd':           qtd,
        'Total Atual':   qtd * prc,
        'custo_total':   r['custo_total'],
        'preco_medio':   r['preco_medio'],
    })

df = pd.DataFrame(linhas)
if df.empty:
    df = pd.DataFrame(columns=['Ativo','Classe','preco_unit','Qtd','Total Atual','custo_total','preco_medio'])

total_geral = df['Total Atual'].sum()
df['Part. %'] = (df['Total Atual'] / total_geral * 100) if total_geral > 0 else 0
df_resumo_classe = df.groupby('Classe')['Total Atual'].sum().reset_index()
df_resumo_classe = df_resumo_classe.sort_values('Total Atual', ascending=False).reset_index(drop=True)
df_ativo = df.sort_values(by='Total Atual', ascending=False)

# MINHA_CARTEIRA para formulário de lançamento
MINHA_CARTEIRA = {
    'ETF': {r['ativo']: r['qtd_atual'] for _, r in _posicao[_posicao['classe']=='ETF'].iterrows()},
    'FII': {r['ativo']: r['qtd_atual'] for _, r in _posicao[_posicao['classe']=='FII'].iterrows()},
    'Cripto': {r['ativo']: r['qtd_atual'] for _, r in _posicao[_posicao['classe']=='Cripto'].iterrows()},
    'Tesouro Direto': {r['ativo']: r['qtd_atual'] for _, r in _posicao[_posicao['classe']=='Tesouro Direto'].iterrows()},
}

# popular preços mensais — session_state cache para não rodar a cada render
if "_df_pm" not in st.session_state:
    try:
        with st.spinner("atualizando histórico de preços..."):
            _df_pm_lido = ler_precos_mensais()
            # migração única para fechamentos sem ajuste de proventos
            if "_metas" not in st.session_state:
                st.session_state["_metas"] = ler_metas()
            if not st.session_state["_metas"].get("precos_mensais_sem_ajuste"):
                _df_pm_lido = migrar_precos_mensais_sem_ajuste(_df_pm_lido)
                salvar_meta("precos_mensais_sem_ajuste", 1,
                            "preços mensais de FIIs/ETFs regravados sem ajuste de proventos")
            if not st.session_state.get("_metas", {}).get("precos_mensais_renda_mtm"):
                _hist_mig, _ = obter_historico_taxa_renda_mais()
                _df_pm_lido, _ok_mig = migrar_precos_renda_mtm(_df_pm_lido, _hist_mig)
                if _ok_mig:
                    salvar_meta("precos_mensais_renda_mtm", 1,
                                "Renda+ 2050 nos preços mensais pelo PU de mercado (não pelo custo)")
            _antes = len(_df_pm_lido)
            _df_pm_lido = popular_precos_mensais(_df_lanc_raw, _df_pm_lido)
            st.session_state["_df_pm"] = _df_pm_lido
            st.session_state['_pm_status'] = f"✓ precos_mensais: {_antes} → {len(_df_pm_lido)} registros"
    except Exception as _e_pm:
        st.session_state['_pm_status'] = f"✗ erro: {_e_pm}"
        st.session_state["_df_pm"] = pd.DataFrame(columns=PM_HEADERS)

_df_pm = st.session_state["_df_pm"]

# ── Classificação dos ativos (padrões do código + aba ativos_info) ──────────
if "_ativos_info" not in st.session_state:
    st.session_state["_ativos_info"] = ler_ativos_info()
_ativos_info = st.session_state["_ativos_info"]

FII_INFO = {a: dict(v) for a, v in FII_INFO_PADRAO.items()}
GEO_ETF  = dict(GEO_ETF_PADRAO)
for _a, _v in _ativos_info.items():
    if _v.get('classe') == 'FII':
        FII_INFO[_a] = {'tipo': _v.get('tipo') or 'tijolo', 'indexador': _v.get('indexador')}
    elif _v.get('classe') == 'ETF' and _v.get('pais'):
        GEO_ETF[_a] = _v['pais']

# classe de cada ativo em carteira (base das listas do simulador e das configurações)
_classe_de = dict(zip(_posicao['ativo'], _posicao['classe'])) if not _posicao.empty else {}

aba_dash, aba_detalhe, aba_lanc, aba_aportes, aba_config = st.tabs(["dashboard", "detalhe", "lançamentos", "simulador", "configurações"])

with aba_dash:

    # base por fluxo de caixa: compras − vendas. variação = ganho de capital (realizado + não realizado)
    _invest_liq  = investimento_liquido(_df_lanc_raw)
    _var_val     = total_geral - _invest_liq
    _var_pct     = (_var_val / _invest_liq * 100) if _invest_liq > 0 else 0

    # dividendos do mês de referência — lidos do histórico mensal persistido (calculado e
    # gravado uma vez por mês fechado; não recalcula via yfinance a cada carregamento)
    _df_div_mensal = atualizar_dividendos_mensais(_df_lanc_raw.to_dict(orient='records'))
    _meses_abrev3_dash = {1:'jan',2:'fev',3:'mar',4:'abr',5:'mai',6:'jun',
                           7:'jul',8:'ago',9:'set',10:'out',11:'nov',12:'dez'}
    if not _df_div_mensal.empty:
        _ultimo_mes_div = _df_div_mensal.iloc[-1]
        _ano_ref_dash, _mes_ref_dash = int(_ultimo_mes_div['ano_mes'][:4]), int(_ultimo_mes_div['ano_mes'][5:7])
        _label_div_dash  = f"{_meses_abrev3_dash[_mes_ref_dash]}/{str(_ano_ref_dash)[-2:]}"
        _div_mes_total   = _ultimo_mes_div['valor_mes']
        _total_divs_geral = _ultimo_mes_div['acumulado']
    else:
        _label_div_dash, _div_mes_total, _total_divs_geral = "—", 0.0, 0.0

    # lucro total = ganho de capital (valorização) + dividendos recebidos (acumulado persistido)
    _lucro_total = _var_val + _total_divs_geral

    # "saiu do bolso": dividendos reinvestidos viram novas compras nos lançamentos,
    # então já estão dentro de custo_total como se fossem dinheiro novo — subtrai pra isolar
    # só o que realmente saiu do bolso (não o que já era lucro reaplicado)
    _valor_investido_proprio = max(_invest_liq - _total_divs_geral, 0)

    with st.container(key="row_dash_resumo"):
        c1, c2, c3 = st.columns([1, 1, 1])
        c1.metric("patrimônio", formatar_brl(total_geral))
        c2.metric("saiu do bolso", formatar_brl(_valor_investido_proprio))
        card_valorizacao(c3, _var_val, _var_pct)

    with st.container(key="row_dash_lucro"):
        l1, l2, l3 = st.columns([1, 1, 1])
        l1.metric(f"dividendos  ·  {_label_div_dash}", formatar_brl(_div_mes_total))
        l2.metric("dividendos totais", formatar_brl(_total_divs_geral))
        card_valorizacao(
            l3, _lucro_total,
            (_lucro_total / _valor_investido_proprio * 100) if _valor_investido_proprio > 0 else 0,
            label="lucro total"
        )

    st.caption(f"cotações de {st.session_state.get('_precos_momento', '—')}")

    st.markdown('---')

    # ── linha 1: donut + gráfico mensal lado a lado (empilha no mobile) ───────
    _ctx_dashboard_chart = st.container(key="row_dashboard_chart")
    with _ctx_dashboard_chart:
        col_donut, col_mensal = st.columns([1, 2])

        with col_donut:
            total_classe = df_resumo_classe['Total Atual'].sum()
            labels_donut, hover_donut = [], []
            for _, row in df_resumo_classe.iterrows():
                pct    = row['Total Atual'] / total_classe * 100
                labels_donut.append(f"{row['Classe']}<br>{fmt_pct(pct)}".replace('.', ','))
                hover_donut.append(f"<b>{row['Classe']}</b><br>{fmt_pct(pct)}<br>{formatar_brl(row['Total Atual'])}")

            fig_donut = go.Figure(go.Pie(
                labels=labels_donut,
                values=df_resumo_classe['Total Atual'].tolist(),
                hole=0.75,
                textinfo='label',
                textposition='outside',
                textfont=dict(size=10),
                hovertemplate='%{customdata}<extra></extra>',
                customdata=hover_donut,
                marker=dict(colors=px.colors.sequential.Blues_r[:len(df_resumo_classe)]),
                domain=dict(x=[0.1, 0.9], y=[0.1, 0.9])
            ))
            fig_donut.update_layout(
                dragmode=False,
                margin=dict(t=60, b=60, l=60, r=60),
                height=400, showlegend=False,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)'
            )
            st.plotly_chart(
                fig_donut, width="stretch",
                config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False}
            )

        with col_mensal:
            import calendar as _cal
            import datetime as _dt
            hoje_dt   = _dt.date.today()
            mes_atual = f"{hoje_dt.year}-{hoje_dt.month:02d}"

            if not _df_pm.empty and 'ano_mes' in _df_pm.columns:
                meses_pm = sorted(_df_pm['ano_mes'].unique())
                meses_pm = [m for m in meses_pm if m < mes_atual]
            else:
                meses_pm = []

            if meses_pm:
                # usar função cacheada — evita recalcular 39× a cada render
                _vals_cache = calcular_valores_mensais(
                    _df_lanc_raw.to_dict(orient='records'),
                    _df_pm.to_dict(orient='records')
                )
                # dividendos acumulados até cada mês (histórico gravado em dividendos_mensais)
                _acum_div = {}
                if _df_div_mensal is not None and not _df_div_mensal.empty:
                    _acum_div = dict(zip(_df_div_mensal['ano_mes'], _df_div_mensal['acumulado']))

                def _decompor(total, custo, divs):
                    """patrimônio = saiu do bolso + dividendos reinvestidos + ganho de capital"""
                    divs  = min(max(float(divs or 0), 0.0), max(custo, 0.0))
                    bolso = max(custo - divs, 0.0)
                    return bolso, divs, total - custo

                vals_mensais = []
                _ult_div = 0.0
                for v in _vals_cache:
                    _dt_v = pd.to_datetime(v['mes'])
                    _ult_div = float(_acum_div.get(_dt_v.strftime('%Y-%m'), _ult_div) or 0)
                    b, d, g = _decompor(v['total'], v.get('custo', 0.0), _ult_div)
                    vals_mensais.append({'mes': _dt_v, 'total': v['total'], 'bolso': b, 'divs': d,
                                         'ganho': g, 'label': _dt_v.strftime('%b/%y'), 'atual': False})

                # mês atual com valores correntes (mesmos números dos cards acima)
                b, d, g = _decompor(total_geral, _invest_liq, _total_divs_geral)
                vals_mensais.append({
                    'mes': pd.to_datetime(f"{mes_atual}-01"), 'total': total_geral,
                    'bolso': b, 'divs': d, 'ganho': g,
                    'label': pd.to_datetime(f"{mes_atual}-01").strftime('%b/%y'), 'atual': True,
                })

                df_mensal = pd.DataFrame(vals_mensais)
                # camada clara = tudo que a carteira rendeu: dividendos reinvestidos + ganho de capital
                df_mensal['rendeu'] = df_mensal['divs'] + df_mensal['ganho']
                df_mensal['hover'] = df_mensal.apply(
                    lambda r: f"<b>{r['label']}</b>" + (" <i>(atual)</i>" if r['atual'] else "")
                              + f"<br>patrimônio: {formatar_brl(r['total'])}"
                              + f"<br>saiu do bolso: {formatar_brl(r['bolso'])}"
                              + f"<br>dividendos reinvestidos: {formatar_brl(r['divs'])}"
                              + f"<br>ganho de capital: "
                              + (f"({formatar_brl(abs(r['ganho']))})" if r['ganho'] < 0 else formatar_brl(r['ganho'])),
                    axis=1)

                # eixo: próxima meta (múltiplo de 10k) em cima; espaço embaixo se houver ganho negativo
                _topo  = (df_mensal['bolso'] + df_mensal['rendeu'].clip(lower=0)).max()
                _meta  = (int(_topo // 10000) + 1) * 10000
                _neg   = float(df_mensal['rendeu'].clip(upper=0).min())
                _base  = -(int(abs(_neg) // 10000) * 10000)      # só marca (10k) se descer tanto
                _ticks = list(range(_base, int(_meta) + 1, 10000))
                _y_min = min(_neg * 1.4, 0)                          # folga só do tamanho necessário

                fig_mensal = go.Figure()
                # mesmas cores do gráfico de rosca (as duas mais escuras de Blues_r)
                for _col, _nome, _cor in [("bolso",  "saiu do bolso", px.colors.sequential.Blues_r[0]),
                                          ("rendeu", "dividendos + ganho de capital", px.colors.sequential.Blues_r[1])]:
                    fig_mensal.add_trace(go.Bar(
                        x=df_mensal['mes'], y=df_mensal[_col], name=_nome,
                        marker_color=_cor,
                        hovertemplate="%{customdata}<extra></extra>",
                        customdata=df_mensal['hover'].tolist(),
                    ))
                fig_mensal.update_layout(
                    barmode="relative",                  # ganho negativo desce abaixo do zero
                    dragmode=False,
                    height=400,
                    plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                    showlegend=True,
                    legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="center", x=0.5,
                                font=dict(size=11)),
                    bargap=0.2,
                    xaxis=dict(showgrid=False, tickformat="%b/%y", tickangle=-45, fixedrange=True),
                    yaxis=dict(
                        showgrid=True, gridcolor="#333",
                        range=[_y_min, _meta * 1.05],
                        tickmode='array',
                        tickvals=_ticks,
                        ticktext=[(f"{v//1000:.0f}k" if v > 0 else (f"({abs(v)//1000:.0f}k)" if v < 0 else "0"))
                                  for v in _ticks],
                        fixedrange=True,
                        zeroline=True, zerolinecolor="#666",
                    ),
                    margin=dict(t=30, b=10, l=10, r=10)
                )
                st.plotly_chart(
                    fig_mensal, width="stretch",
                    config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False}
                )
            else:
                st.info("preços mensais históricos ainda não disponíveis. serão populados automaticamente no próximo carregamento.")

    st.markdown('---')


with aba_detalhe:
    sub_resumo, sub_fiis, sub_etfs, sub_cripto, sub_tesouro = st.tabs(
        ["carteira", "FIIs", "ETFs", "cripto", "tesouro"]
    )

    # ── helpers compartilhados ────────────────────────────────────────────────
    def _lanc_json_cached():
        # usa _df_lanc_raw já carregado — sem releitura do Sheets
        return _df_lanc_raw.to_dict(orient='records')

    # ══════════════════════════════════════════════════════════════════════════
    # SUB-ABA: FIIs
    # ══════════════════════════════════════════════════════════════════════════
    with sub_fiis:
        from datetime import date as _d
        hoje_d    = _d.today()
        mes_ref_f = hoje_d.month - 1 if hoje_d.month > 1 else 12
        ano_ref_f = hoje_d.year if hoje_d.month > 1 else hoje_d.year - 1
        meses_pt3 = {1:'janeiro',2:'fevereiro',3:'março',4:'abril',5:'maio',6:'junho',
                     7:'julho',8:'agosto',9:'setembro',10:'outubro',11:'novembro',12:'dezembro'}

        lanc_json = _lanc_json_cached()
        div_total, div_detalhe = obter_dividendos_mes_anterior(lanc_json)
        # total do mês vem da aba dividendos_mensais quando o mês já está gravado (mesmo número
        # do dashboard e respeita correções feitas na planilha); o cálculo ao vivo fica só
        # para o detalhamento por FII e para o caso de o mês ainda não ter sido gravado
        _linha_mes_planilha = _df_div_mensal[_df_div_mensal['ano_mes'] == f"{ano_ref_f}-{mes_ref_f:02d}"] \
            if _df_div_mensal is not None and not _df_div_mensal.empty else None
        if _linha_mes_planilha is not None and not _linha_mes_planilha.empty \
                and pd.notna(_linha_mes_planilha['valor_mes'].iloc[-1]):
            div_total = float(_linha_mes_planilha['valor_mes'].iloc[-1])

        df_fii = df[df['Classe'] == 'FII'].copy()
        total_fii = df_fii['Total Atual'].sum()

        # proventos por cota dos últimos 12 meses (padrão de mercado) — base do Yield on Cost
        _proventos_12m = obter_proventos_12m_por_cota(tuple(sorted(df_fii['Ativo'].unique())), lanc_json)
        n_tijolo  = sum(1 for t in df_fii['Ativo'] if FII_INFO.get(t, {}).get('tipo') == 'tijolo')
        n_papel   = sum(1 for t in df_fii['Ativo'] if FII_INFO.get(t, {}).get('tipo') == 'papel')

        # ── linha 1: total, dividendos, yield corrente ───────────────────────
        total_fii_k = abreviar_rs(total_fii)

        # yield = dividendos_mês_ref / valor_carteira_FIIs_fim_mês_anterior
        # denominador do yield = valor dos FIIs no fechamento do mês de referência
        # usando quantidade calculada pelos lançamentos até o último dia do mês ref
        # evita que compras após data ex (mas no mesmo mês) distorçam o yield
        _mes_base = f"{ano_ref_f}-{mes_ref_f:02d}"
        import calendar as _cal
        _ultimo_dia_ref = pd.Timestamp(ano_ref_f, mes_ref_f,
                          _cal.monthrange(ano_ref_f, mes_ref_f)[1])
        _total_fii_base = 0.0
        if not _df_pm.empty and not _df_lanc_raw.empty:
            for _, _pm_row_g in _df_pm[_df_pm['ano_mes'] == _mes_base].iterrows():
                _ativo_pm = _pm_row_g['ativo']
                if _ativo_pm not in [r['Ativo'] for _, r in df_fii.iterrows()]:
                    continue
                # quantidade no último dia do mês ref pelos lançamentos
                _ops_ref = _df_lanc_raw[
                    (_df_lanc_raw['ativo'] == _ativo_pm) &
                    (pd.to_datetime(_df_lanc_raw['data'], format='%d/%m/%Y', errors='coerce')
                     .dt.normalize() <= _ultimo_dia_ref)
                ]
                _sinal_ref = _ops_ref['tipo'].map({'compra': 1, 'venda': -1}).fillna(0)
                _qtd_ref = (_ops_ref['quantidade'] * _sinal_ref).sum()
                if _qtd_ref > 0:
                    _total_fii_base += _qtd_ref * float(_pm_row_g['preco_fechamento'])
        if _total_fii_base == 0.0:
            _total_fii_base = total_fii  # fallback

        yield_mensal = (div_total / _total_fii_base * 100) if _total_fii_base > 0 and div_total > 0 else None

        # total histórico de dividendos = acumulado da aba dividendos_mensais
        # (mesma fonte do dashboard; respeita ajustes manuais feitos na planilha)
        _total_divs = _total_divs_geral

        _var_fii_rs  = total_fii - df_fii['custo_total'].sum()
        _var_fii_pct = _var_fii_rs / df_fii['custo_total'].sum() * 100 if df_fii['custo_total'].sum() > 0 else 0
        _pct_fii_carteira = total_fii / total_geral * 100 if total_geral > 0 else 0

        # YoC (yield on cost): proventos 12m × qtd atual (receita hipotética) ÷ custo de aquisição total
        _custo_total_fii   = df_fii['custo_total'].sum()
        _receita_12m_fii   = sum(_proventos_12m.get(r['Ativo'], 0.0) * r['Qtd'] for _, r in df_fii.iterrows())
        _yoc_12m_carteira  = (_receita_12m_fii / _custo_total_fii * 100) if _custo_total_fii > 0 and _receita_12m_fii > 0 else None
        # YoC do mês: base = custo da posição em FIIs no fim do mês de referência
        # (Σ cotas no fim do mês × preço médio até ali) — compras feitas depois não diluem o mês
        _lanc_ate_ref = _df_lanc_raw[
            pd.to_datetime(_df_lanc_raw['data'], format='%d/%m/%Y', errors='coerce').dt.normalize() <= _ultimo_dia_ref
        ] if not _df_lanc_raw.empty else _df_lanc_raw
        _pos_ref = calcular_posicao(_lanc_ate_ref)
        _pos_ref = _pos_ref[_pos_ref['classe'] == 'FII'] if not _pos_ref.empty else _pos_ref
        _custo_fii_ref = float((_pos_ref['qtd_atual'] * _pos_ref['preco_medio']).sum()) if not _pos_ref.empty else 0.0
        _yoc_mes_carteira  = (div_total / _custo_fii_ref * 100) if _custo_fii_ref > 0 and div_total > 0 else None

        _yield_str     = fmt_pct(yield_mensal, 2) if yield_mensal else "—"
        _yoc_12m_str   = fmt_pct(_yoc_12m_carteira, 2) if _yoc_12m_carteira else "—"
        _yoc_mes_str   = fmt_pct(_yoc_mes_carteira, 2) if _yoc_mes_carteira else "—"
        _meses_abrev3 = {1:'jan',2:'fev',3:'mar',4:'abr',5:'mai',6:'jun',
                          7:'jul',8:'ago',9:'set',10:'out',11:'nov',12:'dez'}
        _label_mes = f"{_meses_abrev3[mes_ref_f]}/{str(ano_ref_f)[-2:]}"

        # ── bloco resumo: grade 3 colunas, mesmo padrão dos cards por ativo ──
        #    posição em cima · mês de referência no meio · acumulados (div. totais / YoC 12m) embaixo
        # holding médio ponderado pelo custo de cada FII (mesma lógica da aba ETFs)
        _holding_fii_classe = 0.0
        for _, _row_h in df_fii.iterrows():
            _h_fii = holding_ponderado_meses(_row_h['Ativo'], _df_lanc_raw)
            if _h_fii and _custo_total_fii > 0:
                _holding_fii_classe += (_h_fii * _row_h['custo_total'] / _custo_total_fii)

        with st.container(key="row_fii_dividendos"):
            r1c1, r1c2, r1c3 = st.columns(3)
            r1c1.metric(f"total FIIs  ·  {total_fii_k}", fmt_pct(_pct_fii_carteira))
            card_valorizacao(r1c2, _var_fii_rs, _var_fii_pct)
            r1c3.metric("holding médio", fmt_holding(_holding_fii_classe))

            r2c1, r2c2, r2c3 = st.columns(3)
            r2c1.metric(_label_mes, formatar_brl(div_total))
            r2c2.metric(f"yield — {_label_mes}", _yield_str)

            r3c1, r3c2, r3c3 = st.columns(3)
            r3c1.metric("dividendos totais", formatar_brl(_total_divs))
            r3c2.metric(f"YoC — {_label_mes}", _yoc_mes_str)
            r3c3.metric("YoC (12m)", _yoc_12m_str)

        st.markdown("---")

        # ── linha 2: tijolo vs papel ─────────────────────────────────────────
        df_fii['tipo_fii'] = df_fii['Ativo'].map(lambda t: FII_INFO.get(t, {}).get('tipo', '?'))
        resumo_tipo = df_fii.groupby('tipo_fii')['Total Atual'].sum().reset_index()

        df_papel = df_fii[df_fii['tipo_fii'] == 'papel'].copy()
        df_papel['indexador'] = df_papel['Ativo'].map(lambda t: FII_INFO.get(t, {}).get('indexador', '?'))
        total_papel = df_papel['Total Atual'].sum() if not df_papel.empty else 0

        # montar subtexto CDI/IPCA para o card papel
        idx_info = ""
        if not df_papel.empty:
            resumo_idx = df_papel.groupby('indexador')['Total Atual'].sum().reset_index()
            partes = []
            for _, ri in resumo_idx.sort_values('Total Atual', ascending=False).iterrows():
                pct_idx = ri['Total Atual'] / total_papel * 100 if total_papel > 0 else 0
                partes.append(f"{ri['indexador']} {pct_idx:.0f}%".replace('.', ','))
            idx_info = "  ·  " + " / ".join(partes)

        with st.container(key="row_fii_tipo"):
            c_tij, c_pap = st.columns(2)
            for _, r in resumo_tipo.sort_values('Total Atual', ascending=False).iterrows():
                pct  = r['Total Atual'] / total_fii * 100 if total_fii > 0 else 0
                col  = c_tij if r['tipo_fii'] == 'tijolo' else c_pap
                n    = n_tijolo if r['tipo_fii'] == 'tijolo' else n_papel
                sufx = idx_info if r['tipo_fii'] == 'papel' else ""
                col.metric(f"{r['tipo_fii']} ({n})  ·  {abreviar_rs(r['Total Atual'])}{sufx}".replace('.', ','),
                           f"{fmt_pct(pct)}".replace('.', ','))

        st.markdown("---")

        # donut distribuição por ativo dentro dos FIIs
        # ── gráfico de barras por FII com linha de meta e média ────────────
        df_fii_bar = df_fii.copy()
        df_fii_bar['pct'] = df_fii_bar['Total Atual'] / total_geral * 100
        df_fii_bar = df_fii_bar.sort_values('pct', ascending=True)
        _n_fiis    = len(df_fii_bar)
        _media_fii = df_fii_bar['pct'].sum() / _n_fiis if _n_fiis > 0 else 0

        hover_fii_bar = [
            f"<b>{row['Ativo']}</b><br>{fmt_pct(row['pct'])}<br>{formatar_brl(row['Total Atual'])}"
            for _, row in df_fii_bar.iterrows()
        ]
        fig_fii_bar = go.Figure()
        fig_fii_bar.add_trace(go.Bar(
            x=df_fii_bar['pct'],
            y=df_fii_bar['Ativo'],
            orientation='h',
            marker_color='#1E88E5',
            text=df_fii_bar['pct'].apply(fmt_pct),
            textposition='outside',
            textfont=dict(size=10, color='white'),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hover_fii_bar,
        ))
        _max_pct_fii = df_fii_bar['pct'].max()
        _step_fii    = 1
        _x_max_fii   = max(_max_pct_fii * 1.25, _media_fii * 1.5)
        _banda_fii_cfg = _get_banda(_cfg_alvos, "__FIIs__")
        _alvo_fii_total = _banda_fii_cfg.get('alvo') or 0
        _min_fii_total  = _banda_fii_cfg.get('min') or 0
        _max_fii_total  = _banda_fii_cfg.get('max') or 0
        _meta_fii  = _alvo_fii_total / _n_fiis if _n_fiis > 0 and _alvo_fii_total > 0 else None
        _min_fii_i = _min_fii_total  / _n_fiis if _n_fiis > 0 and _min_fii_total  > 0 else None
        _max_fii_i = _max_fii_total  / _n_fiis if _n_fiis > 0 and _max_fii_total  > 0 else None
        if _min_fii_i and _max_fii_i:
            fig_fii_bar.add_shape(
                type='rect', x0=_min_fii_i, x1=_max_fii_i, y0=-0.5, y1=_n_fiis - 0.5,
                fillcolor='rgba(255,255,255,0.04)', line=dict(color='rgba(255,255,255,0.15)', width=1)
            )
        if _meta_fii:
            fig_fii_bar.add_shape(
                type='line', x0=_meta_fii, x1=_meta_fii, y0=-0.5, y1=_n_fiis - 0.5,
                line=dict(color='#ffffff', width=1.5, dash='dash')
            )
            fig_fii_bar.add_annotation(
                x=_meta_fii, y=_n_fiis - 0.5,
                text=f"alvo {fmt_pct(_meta_fii)}",
                showarrow=False, xanchor='left', xshift=6,
                font=dict(size=10, color='rgba(255,255,255,0.8)')
            )
        fig_fii_bar.update_layout(
            height=max(300, _n_fiis * 28),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False, dragmode=False,
            xaxis=dict(showgrid=True, gridcolor='#333', range=[0, _x_max_fii],
                       ticksuffix='%', fixedrange=True),
            yaxis=dict(showgrid=False, tickfont=dict(size=11), fixedrange=True),
            bargap=0.25, margin=dict(t=20, b=10, l=10, r=60)
        )
        st.plotly_chart(fig_fii_bar, width="stretch",
                        config={"displayModeBar": False, "scrollZoom": False})

        st.markdown("---")

        # ── cards por FII (mesmo padrão de ETFs/tesouro/cripto) ────────────────
        for _, row in df_fii.sort_values('Total Atual', ascending=False).iterrows():
            _ativo_f  = row['Ativo']
            _qtd_f    = float(row['Qtd'])
            _preco_f  = row['preco_unit']
            _total_f  = row['Total Atual']
            _custo_f  = row['custo_total']
            _pm_f     = row['preco_medio']
            _var_f_rs  = _total_f - _custo_f
            _var_f_pct = _var_f_rs / _custo_f * 100 if _custo_f > 0 else 0
            _holding_f = holding_ponderado_meses(_ativo_f, _df_lanc_raw)
            _qtd_f_str = fmt_num(_qtd_f, 2)

            _proventos_f   = _proventos_12m.get(_ativo_f, 0.0)
            _yoc_f_12m_pct = (_proventos_f / _pm_f * 100) if _pm_f and _pm_f > 0 and _proventos_f > 0 else None
            _yoc_f_str     = fmt_pct(_yoc_f_12m_pct, 2) if _yoc_f_12m_pct else "—"

            # yield (12m) = proventos por cota dos últimos 12 meses ÷ preço atual
            # (mesmo numerador do YoC; só muda o denominador: preço de mercado vs. preço médio)
            _yield_f_str = fmt_pct(_proventos_f / _preco_f * 100, 2) if _proventos_f > 0 and _preco_f else "—"

            with st.container(key=f"row_fii_ativo_{_ativo_f}"):
                r1c1, r1c2, r1c3 = st.columns(3)
                r1c1.metric("ativo", _ativo_f)
                r1c2.metric(f"total  ·  ({_qtd_f_str})", abreviar_rs(_total_f))
                r1c3.metric("~holding", fmt_holding(_holding_f))

                r2c1, r2c2, r2c3 = st.columns(3)
                r2c2.metric(f"preço  ·  (~{formatar_brl(_pm_f)})", formatar_brl(_preco_f))
                card_valorizacao(r2c3, _var_f_rs, _var_f_pct)

                r3c1, r3c2, r3c3 = st.columns(3)
                r3c2.metric("yield (12m)", _yield_f_str)
                r3c3.metric("YoC (12m)", _yoc_f_str)

            st.markdown("---")

    # ══════════════════════════════════════════════════════════════════════════
    # SUB-ABA: ETFs
    # ══════════════════════════════════════════════════════════════════════════
    with sub_etfs:
        df_etf = df[df['Classe'] == 'ETF'].copy()
        total_etf        = df_etf['Total Atual'].sum()
        total_inv_etf    = df_etf['custo_total'].sum()
        var_etf_rs       = total_etf - total_inv_etf
        var_etf_pct      = var_etf_rs / total_inv_etf * 100 if total_inv_etf > 0 else 0
        df_etf['part_classe_%'] = df_etf['Total Atual'] / total_etf * 100

        # holding médio ponderado da classe
        _holding_classe = 0.0
        for _, row in df_etf.iterrows():
            _h = holding_ponderado_meses(row['Ativo'], _df_lanc_raw)
            if _h and total_inv_etf > 0:
                _holding_classe += (_h * row['custo_total'] / total_inv_etf)

        # ── linha 1: resumo da classe + donut ────────────────────────────────
        with st.container(key="row_etf_resumo"):
            c1, c2, c3 = st.columns(3)
            _pct_etf_carteira = total_etf / total_geral * 100 if total_geral > 0 else 0
            c1.metric(f"total ETFs  ·  {abreviar_rs(total_etf)}", fmt_pct(_pct_etf_carteira))
            card_valorizacao(c2, var_etf_rs, var_etf_pct)
            c3.metric("holding médio", fmt_holding(_holding_classe))

        st.markdown("---")

        # ── gráfico de barras ETF com alvos por ativo ─────────────────────────
        df_etf_bar = df_etf.copy()
        df_etf_bar['pct'] = df_etf_bar['Total Atual'] / total_geral * 100
        df_etf_bar = df_etf_bar.sort_values('pct', ascending=True)
        _n_etfs = len(df_etf_bar)

        hover_etf_bar = [
            f"<b>{row['Ativo']}</b><br>{fmt_pct(row['pct'])}<br>{formatar_brl(row['Total Atual'])}"
            for _, row in df_etf_bar.iterrows()
        ]
        fig_etf_bar = go.Figure()
        fig_etf_bar.add_trace(go.Bar(
            x=df_etf_bar['pct'],
            y=df_etf_bar['Ativo'],
            orientation='h',
            marker_color='#1E88E5',
            text=df_etf_bar['pct'].apply(fmt_pct),
            textposition='outside',
            textfont=dict(size=10, color='white'),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hover_etf_bar,
        ))
        # banda + alvo por ativo
        for i, row in df_etf_bar.reset_index(drop=True).iterrows():
            _banda_etf = _get_banda(_cfg_alvos, row['Ativo'])
            _alvo_e = _banda_etf.get('alvo')
            _min_e  = _banda_etf.get('min')
            _max_e  = _banda_etf.get('max')
            if _min_e and _max_e:
                fig_etf_bar.add_shape(
                    type='rect', x0=_min_e, x1=_max_e, y0=i-0.4, y1=i+0.4,
                    fillcolor='rgba(255,255,255,0.04)', line=dict(color='rgba(255,255,255,0.15)', width=1)
                )
            if _alvo_e:
                fig_etf_bar.add_shape(
                    type='line', x0=_alvo_e, x1=_alvo_e, y0=i-0.4, y1=i+0.4,
                    line=dict(color='#ffffff', width=2, dash='dash')
                )
        _all_alvos_etf = [(_cfg_alvos.get(a,{}) or {}).get('max') or 0 for a in df_etf_bar['Ativo']]
        _x_max_etf = max(df_etf_bar['pct'].max(), max(_all_alvos_etf, default=0)) * 1.25
        fig_etf_bar.update_layout(
            height=max(200, _n_etfs * 50),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False, dragmode=False,
            xaxis=dict(showgrid=True, gridcolor='#333', range=[0, _x_max_etf],
                       ticksuffix='%', fixedrange=True),
            yaxis=dict(showgrid=False, tickfont=dict(size=11), fixedrange=True),
            bargap=0.3, margin=dict(t=10, b=10, l=10, r=60)
        )
        st.plotly_chart(fig_etf_bar, width="stretch",
                        config={"displayModeBar": False, "scrollZoom": False})

        st.markdown("---")

        # ── cards por ETF ──────────────────────────────────────────────────────
        for _, row in df_etf.sort_values('Total Atual', ascending=False).iterrows():
            ativo       = row['Ativo']
            qtd         = float(row['Qtd'])
            preco       = row['preco_unit']
            total_atual = row['Total Atual']
            custo       = row['custo_total']
            pm          = row['preco_medio']
            var_rs      = total_atual - custo
            var_pct_e   = var_rs / custo * 100 if custo > 0 else 0
            holding     = holding_ponderado_meses(ativo, _df_lanc_raw)

            with st.container(key=f"row_etf_{ativo}"):
                _qtd_str = fmt_num(qtd, 2)
                r1c1, r1c2, r1c3 = st.columns(3)
                r1c1.metric("ativo", ativo)
                r1c2.metric(f"total  ·  ({_qtd_str})", abreviar_rs(total_atual))
                r1c3.metric("~holding", fmt_holding(holding))

                r2c1, r2c2, r2c3 = st.columns(3)
                r2c2.metric(f"preço  ·  (~{formatar_brl(pm)})", formatar_brl(preco))
                card_valorizacao(r2c3, var_rs, var_pct_e)

            st.markdown("---")


    # ══════════════════════════════════════════════════════════════════════════
    # SUB-ABA: CRIPTO
    # ══════════════════════════════════════════════════════════════════════════
    with sub_cripto:
        preco_btc_atual = precos.get('BTC', 0.0)
        _btc_pos = _posicao[_posicao['ativo'] == 'BTC']
        qtd_btc  = float(_btc_pos['qtd_atual'].iloc[0]) if not _btc_pos.empty else 0.0
        total_btc = preco_btc_atual * qtd_btc
        hist, hist_fonte = obter_historico_btc_brl()

        def var_pct(serie, dias):
            if serie is None or serie.empty or len(serie) < dias + 1:
                return None
            preco_ant = serie.iloc[-(dias+1)]
            return (preco_btc_atual / preco_ant - 1) * 100 if preco_ant > 0 else None

        var_1d  = var_pct(hist, 1)
        var_7d  = var_pct(hist, 7)
        var_30d = var_pct(hist, 30)
        var_6m  = var_pct(hist, 182)
        var_1a  = var_pct(hist, 365)
        var_5a  = var_pct(hist, 1825)

        def fmt_var(v):
            if v is None: return "—"
            sinal = "+" if v >= 0 else ""
            return f"{sinal}{fmt_pct(v)}".replace('.', ',')

        _btc_custo = float(_btc_pos['custo_total'].iloc[0]) if not _btc_pos.empty else 0.0
        _btc_pm    = float(_btc_pos['preco_medio'].iloc[0]) if not _btc_pos.empty else 0.0
        _btc_var_rs  = total_btc - _btc_custo
        _btc_var_pct = (_btc_var_rs / _btc_custo * 100) if _btc_custo > 0 else 0.0

        _btc_qtd_str  = fmt_num(qtd_btc, 4)
        _btc_holding  = holding_ponderado_meses('BTC', _df_lanc_raw)
        with st.container(key="row_cripto_BTC"):
            r1c1, r1c2, r1c3 = st.columns(3)
            r1c1.metric("ativo", "BTC")
            r1c2.metric(f"total  ·  ({_btc_qtd_str})", abreviar_rs(total_btc))
            r1c3.metric("~holding", fmt_holding(_btc_holding))

            r2c1, r2c2, r2c3 = st.columns(3)
            r2c2.metric(f"preço  ·  (~{abreviar_rs(_btc_pm)})", abreviar_rs(preco_btc_atual))
            card_valorizacao(r2c3, _btc_var_rs, _btc_var_pct)

        st.markdown("---")

        render_variacoes("row_cripto_variacoes", {
            "hoje": (var_1d, 1.0), "7 dias": (var_7d, 1.0), "30 dias": (var_30d, 1.0),
            "6 meses": (var_6m, 1.0), "1 ano": (var_1a, 1.0), "5 anos": (var_5a, 1.0),
        })

        st.markdown("---")
        if hist is not None and not hist.empty:
            st.markdown(
                "<p style='font-size:1rem;font-weight:600;margin:0 0 0.5rem 0'>últimos 12 meses</p>",
                unsafe_allow_html=True
            )
            corte = hist.index.max() - pd.DateOffset(days=365)
            hist_1a = hist[hist.index >= corte]
            fig_btc = go.Figure()
            fig_btc.add_trace(go.Scatter(
                x=hist_1a.index, y=hist_1a.values,
                mode="lines",
                line=dict(color="#F7931A", width=2),
                hovertemplate="%{x|%d/%m/%Y}<br>R$%{y:,.0f}<extra></extra>"
            ))
            fig_btc.update_layout(
            dragmode=False,
                height=280,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#333"),
                margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(fig_btc, width="stretch", config={"displayModeBar": False, "scrollZoom": False})
            st.caption(f"fonte: {hist_fonte}")
        else:
            st.warning("histórico de preços indisponível — coingecko e yfinance não retornaram dados.")

    # ══════════════════════════════════════════════════════════════════════════
    # SUB-ABA: TESOURO
    # ══════════════════════════════════════════════════════════════════════════
    with sub_tesouro:
        df_td = df[df['Classe'] == 'Tesouro Direto'].copy()

        lanc_all = _df_lanc_raw
        for _, row in df_td.iterrows():
            ativo       = row['Ativo']
            qtd         = float(row['Qtd'])
            preco_atual = row['preco_unit']
            total_atual = row['Total Atual']

            if not lanc_all.empty:
                compras_td      = lanc_all[(lanc_all['ativo'] == ativo) & (lanc_all['tipo'] == 'compra')]
                total_investido = (compras_td['quantidade'] * compras_td['preco_unitario']).sum()
                qtd_comprada    = compras_td['quantidade'].sum()
                pm              = total_investido / qtd_comprada if qtd_comprada > 0 else 0
            else:
                total_investido, pm = 0.0, 0.0

            valorizacao     = total_atual - total_investido if total_investido > 0 else None
            valorizacao_pct = (valorizacao / total_investido * 100) if total_investido > 0 and valorizacao else None

            _qtd_fmt    = fmt_num(qtd, 2)
            _pm_fmt     = formatar_brl(pm) if pm > 0 else "—"
            _td_holding = holding_ponderado_meses(ativo, _df_lanc_raw)
            with st.container(key=f"row_tesouro_{ativo}"):
                r1c1, r1c2, r1c3 = st.columns(3)
                r1c1.metric("ativo", ativo)
                r1c2.metric(f"total  ·  ({_qtd_fmt})", abreviar_rs(total_atual))
                r1c3.metric("~holding", fmt_holding(_td_holding))

                # sua taxa média de compra (ponderada pelo valor de cada aporte) — só o Renda+
                _taxa_td_card = None
                if ativo == 'Renda+ 2050':
                    try:
                        _hist_tx_card, _ = obter_historico_taxa_renda_mais()
                        _taxa_td_card = calcular_taxa_media_ponderada_renda(
                            taxas_aportes_renda_mais(_df_lanc_raw, _hist_tx_card, ler_renda_taxas()))
                    except Exception:
                        _taxa_td_card = None
                r2c1, r2c2, r2c3 = st.columns(3)
                # mesmo padrão do card de preço: rótulo = sua média (~), valor = taxa de compra atual
                _taxa_atual_card = st.session_state.get('taxa_renda_auto') if ativo == 'Renda+ 2050' else None
                _tx_media_lbl = f"~{fmt_pct(_taxa_td_card, 2)}" if _taxa_td_card else "~—"
                r2c2.metric(f"taxa  ·  ({_tx_media_lbl})",
                            f"IPCA + {fmt_pct(_taxa_atual_card, 2)}" if _taxa_atual_card else "—")
                r2c3.metric(f"preço  ·  (~{_pm_fmt})", formatar_brl(preco_atual))

                r3c1, r3c2, r3c3 = st.columns(3)
                if ativo == 'Renda+ 2050':
                    # contagem regressiva: meses que faltam até dez/2045 (sem contar o mês atual)
                    _hoje_c = pd.Timestamp.today()
                    _meses_ate_2045 = max((2045 - _hoje_c.year) * 12 + (12 - _hoje_c.month), 0)
                    r3c1.metric("até 2045", f"{_meses_ate_2045} meses")

                    # meta: títulos por mês necessários até dez/2045
                    if "_metas" not in st.session_state:
                        st.session_state["_metas"] = ler_metas()
                    _meta_tit = st.session_state["_metas"].get("renda_2050_titulos_dez2045")
                    if _meta_tit:
                        _faltam_tit = max(_meta_tit - qtd, 0)
                        if _faltam_tit <= 0:
                            _txt_meta = "atingida"
                        elif _meses_ate_2045 > 0:
                            _txt_meta = f"{fmt_num(_faltam_tit / _meses_ate_2045, 2)} por mês"
                        else:
                            _txt_meta = f"faltam {fmt_num(_faltam_tit, 2)}"
                        r3c2.metric(f"meta 2045  ·  ({fmt_num(_meta_tit, 2)})", _txt_meta)
                if valorizacao is not None and valorizacao_pct is not None:
                    card_valorizacao(r3c3, valorizacao, valorizacao_pct)
                else:
                    r3c3.metric("variação", "—")

            if ativo == 'Renda+ 2050':
                if 'preco_renda_auto' in st.session_state:
                    st.caption(f"preço obtido automaticamente — referência: {st.session_state.get('data_renda_auto','')}")
                elif 'preco_renda_erro' in st.session_state:
                    st.caption(f"preço manual (secrets) — API: {st.session_state.get('preco_renda_erro','')}")

            if ativo == 'Renda+ 2050':
                # taxa de cada aporte = taxa de mercado no dia da compra (lançamentos),
                # sem upload manual; datas que já estavam no extrato antigo usam a taxa exata dele
                _df_hist_taxa, _erro_hist_taxa = obter_historico_taxa_renda_mais()
                _taxa_hoje = st.session_state.get('taxa_renda_auto')
                if (_taxa_hoje and 'Tesouro Direto' in str(st.session_state.get('data_renda_auto', ''))
                        and not _df_hist_taxa.empty):
                    _hoje_tx = pd.Timestamp.today().normalize()
                    _df_hist_taxa = _df_hist_taxa.copy()
                    _df_hist_taxa['data_dt'] = pd.to_datetime(_df_hist_taxa['data_dt'])
                    _df_hist_taxa = pd.concat([
                        _df_hist_taxa[_df_hist_taxa['data_dt'] < _hoje_tx],
                        pd.DataFrame({'data_dt': [_hoje_tx], 'taxa': [float(_taxa_hoje)]})
                    ], ignore_index=True)
                _df_rt = taxas_aportes_renda_mais(_df_lanc_raw, _df_hist_taxa, ler_renda_taxas())
                _taxa_media_chart = calcular_taxa_media_ponderada_renda(_df_rt)

                if not _df_hist_taxa.empty:
                    fig_taxa_mercado = go.Figure()
                    fig_taxa_mercado.add_trace(go.Scatter(
                        x=_df_hist_taxa['data_dt'], y=_df_hist_taxa['taxa'],
                        mode='lines', name='taxa de mercado',
                        line=dict(color='#A8A8A8', width=1.5),
                        hovertemplate='%{x|%d/%m/%Y}: IPCA+%{y:.2f}%<extra></extra>'
                    ))
                    if not _df_rt.empty:
                        fig_taxa_mercado.add_trace(go.Scatter(
                            x=_df_rt['data_dt'], y=_df_rt['taxa_contratada_pct'],
                            mode='markers', name='meus aportes',
                            marker=dict(size=9, color='#F59E0B',
                                        line=dict(width=1, color='#0E1117')),
                            hovertemplate='%{x|%d/%m/%Y}: IPCA+%{y:.2f}%<extra></extra>'
                        ))
                    if _taxa_media_chart is not None:
                        fig_taxa_mercado.add_hline(
                            y=_taxa_media_chart, line_dash='dash', line_color='gray',
                            annotation_text=f"média: IPCA+{fmt_pct(_taxa_media_chart, 2)}",
                            annotation_position='top left'
                        )
                    fig_taxa_mercado.update_layout(
                        height=280, margin=dict(l=10, r=10, t=30, b=10),
                        plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
                        showlegend=True,
                        legend=dict(orientation='h', yanchor='bottom', y=1.02, x=0),
                        xaxis=dict(showgrid=False, fixedrange=True),
                        yaxis=dict(showgrid=True, gridcolor='#333', fixedrange=True, ticksuffix='%'),
                    )
                    st.plotly_chart(
                        fig_taxa_mercado, width="stretch",
                        config={"displayModeBar": False, "scrollZoom": False, "doubleClick": False}
                    )
                else:
                    st.caption(f"não consegui obter o histórico de taxa de mercado ({_erro_hist_taxa}).")

    # ══════════════════════════════════════════════════════════════════════════
    # SUB-ABA: CARTEIRA
    # ══════════════════════════════════════════════════════════════════════════
    with sub_resumo:
        # ── linha 1: exposição geográfica ─────────────────────────────────────
        GEO_FLAG = {'Brasil': '🇧🇷', 'EUA': '🇺🇸', 'China': '🇨🇳', 'Europa': '🇪🇺',
                    'Emergentes': '🌏', 'Global': '🌐', 'Global (cripto)': '🌍'}
        geo_totais = {}
        for _, row in df[df['Classe'] == 'ETF'].iterrows():
            pais = GEO_ETF.get(row['Ativo'], 'Brasil')
            geo_totais[pais] = geo_totais.get(pais, 0) + row['Total Atual']
        geo_totais['Brasil'] = geo_totais.get('Brasil', 0) \
            + df[df['Classe'] == 'FII']['Total Atual'].sum() \
            + df[df['Classe'] == 'Tesouro Direto']['Total Atual'].sum()
        geo_totais['Global (cripto)'] = df[df['Classe'] == 'Cripto']['Total Atual'].sum()
        geo_sorted = sorted(geo_totais.items(), key=lambda x: -x[1])

        with st.container(key="row_geo"):
            cols_geo = st.columns(len(geo_sorted))
            for i, (pais, val) in enumerate(geo_sorted):
                pct   = val / total_geral * 100 if total_geral > 0 else 0
                flag  = GEO_FLAG.get(pais, '')
                val_k = abreviar_rs(val)
                cols_geo[i].metric(f"{flag}  ·  {val_k}", f"{fmt_pct(pct)}".replace('.', ','))

        st.markdown("---")

        # ── linha 2: renda fixa/variável + CDI/IPCA, tudo junto ────────────────
        # LFTB11 é ETF de renda fixa (replica Tesouro Selic) — vai para RF
        _etfs_rf = ['LFTB11']
        total_rf = df[df['Classe'] == 'Tesouro Direto']['Total Atual'].sum() + \
                   df[df['Ativo'].isin(_etfs_rf)]['Total Atual'].sum()
        total_rv = df[(df['Classe'].isin(['ETF','FII','Cripto'])) & (~df['Ativo'].isin(_etfs_rf))]['Total Atual'].sum()
        pct_rf   = total_rf / total_geral * 100 if total_geral > 0 else 0
        pct_rv   = total_rv / total_geral * 100 if total_geral > 0 else 0

        # CDI = LFTB11 + FIIs papel CDI · IPCA = Renda+ 2050 + FIIs papel IPCA
        _df_fii_idx = df[df['Classe'] == 'FII'].copy()
        _df_fii_idx['indexador'] = _df_fii_idx['Ativo'].map(
            lambda t: FII_INFO.get(t, {}).get('indexador'))

        total_cdi  = df[df['Ativo'] == 'LFTB11']['Total Atual'].sum() + \
                     _df_fii_idx[_df_fii_idx['indexador'] == 'CDI']['Total Atual'].sum()
        total_ipca = df[df['Ativo'] == 'Renda+ 2050']['Total Atual'].sum() + \
                     _df_fii_idx[_df_fii_idx['indexador'] == 'IPCA']['Total Atual'].sum()
        pct_cdi    = total_cdi  / total_geral * 100 if total_geral > 0 else 0
        pct_ipca   = total_ipca / total_geral * 100 if total_geral > 0 else 0

        with st.container(key="row_indices"):
            c1, c2, c3, c4 = st.columns(4)
            c1.metric(f"RF  ·  {abreviar_rs(total_rf)}", f"{fmt_pct(pct_rf)}")
            c2.metric(f"RV  ·  {abreviar_rs(total_rv)}", f"{fmt_pct(pct_rv)}")
            c3.metric(f"CDI  ·  {abreviar_rs(total_cdi)}", fmt_pct(pct_cdi))
            c4.metric(f"IPCA+  ·  {abreviar_rs(total_ipca)}", fmt_pct(pct_ipca))

        st.markdown("---")

        # ── distribuição por ativo ────────────────────────────────────────────
        df_ativo_sorted = df_ativo.sort_values('Part. %', ascending=True)
        hover_barras = [
            f"<b>{row['Ativo']}</b><br>{fmt_pct(row['Part. %'])}<br>{formatar_brl(row['Total Atual'])}"
            for _, row in df_ativo_sorted.iterrows()
        ]
        fig_ativo = go.Figure()
        fig_ativo.add_trace(go.Bar(
            x=df_ativo_sorted['Part. %'],
            y=df_ativo_sorted['Ativo'],
            orientation='h',
            marker_color='#1E88E5',
            text=df_ativo_sorted['Part. %'].apply(fmt_pct),
            textposition='outside',
            textfont=dict(size=10, color='white'),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hover_barras,
        ))
        # alvos por ativo: banda + linha
        for i, row in df_ativo_sorted.reset_index(drop=True).iterrows():
            _ativo_n = row['Ativo']
            # FIIs usam alvo da classe dividido
            if _classe_de.get(_ativo_n) == 'FII':
                _banda_c = _get_banda(_cfg_alvos, '__FIIs__')
                _n_f = len([a for a, c in _classe_de.items() if c == 'FII'])
                _alvo_i = (_banda_c.get('alvo') or 0) / _n_f if _n_f > 0 else None
                _min_i  = (_banda_c.get('min')  or 0) / _n_f if _n_f > 0 else None
                _max_i  = (_banda_c.get('max')  or 0) / _n_f if _n_f > 0 else None
            else:
                _banda_c = _get_banda(_cfg_alvos, _ativo_n)
                _alvo_i  = _banda_c.get('alvo')
                _min_i   = _banda_c.get('min')
                _max_i   = _banda_c.get('max')
            if _min_i and _max_i:
                fig_ativo.add_shape(
                    type='rect', x0=_min_i, x1=_max_i, y0=i-0.4, y1=i+0.4,
                    fillcolor='rgba(255,255,255,0.04)', line=dict(color='rgba(255,255,255,0.15)', width=1)
                )
            if _alvo_i:
                fig_ativo.add_shape(
                    type='line', x0=_alvo_i, x1=_alvo_i, y0=i-0.4, y1=i+0.4,
                    line=dict(color='#ffffff', width=2, dash='dash')
                )
        _all_max = [(_get_banda(_cfg_alvos, r['Ativo']).get('max') or 0) for _, r in df_ativo_sorted.iterrows()]
        _max_pct   = df_ativo_sorted['Part. %'].max()
        _step      = 5
        _ult_tick  = (int(_max_pct // _step)) * _step
        _x_max     = max((_ult_tick + _step) if _max_pct >= _ult_tick * 0.9 else _ult_tick,
                         max(_all_max, default=0) * 1.1)
        fig_ativo.update_layout(
            height=max(300, len(df_ativo_sorted) * 28),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False, dragmode=False,
            xaxis=dict(showgrid=True, gridcolor='#333', range=[0, _x_max * 1.15],
                       ticksuffix='%', dtick=_step, fixedrange=True),
            yaxis=dict(showgrid=False, tickfont=dict(size=11), fixedrange=True),
            bargap=0.25, margin=dict(t=10, b=10, l=10, r=60)
        )
        st.plotly_chart(fig_ativo, width="stretch",
                        config={"displayModeBar": False, "scrollZoom": False})

        st.markdown("---")

        # ── cards de todos os ativos (mesmo padrão das demais abas) ──────────
        def _fmt_preco_geral(ativo_nome, preco):
            return abreviar_rs(preco) if ativo_nome == 'BTC' else formatar_brl(preco)

        for _, row in df.sort_values('Total Atual', ascending=False).iterrows():
            _ativo_g  = row['Ativo']
            _qtd_g    = float(row['Qtd'])
            _preco_g  = row['preco_unit']
            _total_g  = row['Total Atual']
            _custo_g  = row['custo_total']
            _pm_g     = row['preco_medio']
            _var_g_rs  = _total_g - _custo_g
            _var_g_pct = _var_g_rs / _custo_g * 100 if _custo_g > 0 else 0
            _holding_g = holding_ponderado_meses(_ativo_g, _df_lanc_raw)
            _qtd_g_str = fmt_num(_qtd_g, 6 if _qtd_g < 1 else 2)

            with st.container(key=f"row_all_{_ativo_g}"):
                r1c1, r1c2, r1c3 = st.columns(3)
                r1c1.metric("ativo", _ativo_g)
                r1c2.metric(f"total  ·  ({_qtd_g_str})", abreviar_rs(_total_g))
                r1c3.metric("~holding", fmt_holding(_holding_g))

                r2c1, r2c2, r2c3 = st.columns(3)
                r2c2.metric(f"preço  ·  (~{_fmt_preco_geral(_ativo_g, _pm_g)})", _fmt_preco_geral(_ativo_g, _preco_g))
                card_valorizacao(r2c3, _var_g_rs, _var_g_pct)

            st.markdown("---")


# ── Aba lancamentos ────────────────────────────────────────────────────────────
with aba_lanc:

    _opcoes = []
    for t in sorted(MINHA_CARTEIRA.get('ETF', {}).keys()):
        _opcoes.append((t, 'ETF'))
    for t in sorted(MINHA_CARTEIRA.get('FII', {}).keys()):
        _opcoes.append((t, 'FII'))
    _opcoes.append(('BTC', 'Cripto'))
    _opcoes.append(('Renda+ 2050', 'Tesouro Direto'))
    _opcoes.append(('__novo__', None))
    _nomes = ['novo ativo…' if t == '__novo__' else t for t, _ in _opcoes]

    @st.fragment
    def aba_lancamentos_fragment():
        from datetime import date as _date

        # ── lê dados frescos sempre que o fragment reroda ─────────────────────
        _versao = st.session_state.get("_lanc_versao", 0)
        df_lanc = ler_lancamentos(_versao=_versao)
        if not df_lanc.empty:
            df_lanc["data_dt"] = pd.to_datetime(df_lanc["data"], format="%d/%m/%Y", errors="coerce")
            df_lanc["sinal"]   = df_lanc["tipo"].map({"compra": 1, "venda": -1}).fillna(0)
            df_lanc["valor"]   = df_lanc["total"] * df_lanc["sinal"]

        meses_pt = {1:'janeiro',2:'fevereiro',3:'março',4:'abril',5:'maio',6:'junho',
                    7:'julho',8:'agosto',9:'setembro',10:'outubro',11:'novembro',12:'dezembro'}
        hoje      = pd.Timestamp.today()
        mes_atual = hoje.month
        ano_atual = hoje.year

        # calcular métricas
        if not df_lanc.empty:
            df_mes = df_lanc[
                (df_lanc["data_dt"].dt.month == mes_atual) &
                (df_lanc["data_dt"].dt.year  == ano_atual)
            ].copy()
            df_mes["sinal_m"] = df_mes["tipo"].map({"compra": 1, "venda": -1}).fillna(0)
            aporte_mes = (df_mes["total"] * df_mes["sinal_m"]).sum()

            _meses = []
            for i in range(1, 7):
                ref = hoje - pd.DateOffset(months=i)
                df_ref = df_lanc[
                    (df_lanc["data_dt"].dt.month == ref.month) &
                    (df_lanc["data_dt"].dt.year  == ref.year)
                ].copy()
                df_ref["sinal_r"] = df_ref["tipo"].map({"compra": 1, "venda": -1}).fillna(0)
                _meses.append((df_ref["total"] * df_ref["sinal_r"]).sum())
            media_6m = sum(_meses) / 6
        else:
            aporte_mes, media_6m = 0.0, 0.0

        # ── cabeçalho: métricas + formulário ─────────────────────────────────
        aberto = st.session_state.get("abrir_form_aporte", False)

        if not aberto:
            c1, c2, c3 = st.columns([1.4, 1, 0.7])
            c1.metric(f"total aportado em {meses_pt[mes_atual]}", formatar_brl(aporte_mes))
            c2.metric("média mensal (6m)", formatar_brl(media_6m))
            with c3:
                st.markdown("<br>", unsafe_allow_html=True)
                if st.button("+ novo aporte", type="primary", width="stretch"):
                    st.session_state["abrir_form_aporte"] = True
                    st.rerun(scope="fragment")
        else:
            with st.container(border=True):
                c1, c2, c3 = st.columns([1.1, 0.7, 1.5])
                with c1:
                    f_data = st.date_input("data", value=_date.today(),
                                           format="DD/MM/YYYY", max_value=_date.today(),
                                           label_visibility="collapsed")
                with c2:
                    f_tipo = st.selectbox("tipo", ["compra", "venda"], label_visibility="collapsed")
                with c3:
                    idx = st.selectbox("ativo", range(len(_nomes)),
                                       format_func=lambda i: _nomes[i],
                                       label_visibility="collapsed")
                    f_ativo  = _opcoes[idx][0]
                    f_classe = _opcoes[idx][1]

                # ── ativo novo: ticker + classe + classificação ────────────────
                _novo = f_ativo == '__novo__'
                n_tipo = n_idx = n_pais = None
                if _novo:
                    n1, n2, n3 = st.columns([1.1, 0.8, 1.2])
                    with n1:
                        f_ativo = st.text_input("ticker", placeholder="ticker (ex.: HGLG11)",
                                                label_visibility="collapsed").strip().upper()
                    with n2:
                        f_classe = st.selectbox("classe", ["FII", "ETF"], label_visibility="collapsed")
                    with n3:
                        if f_classe == "FII":
                            n_tipo = st.selectbox("tipo FII", ["tijolo", "papel"], label_visibility="collapsed")
                        else:
                            n_pais = st.selectbox("país", PAISES_ETF, label_visibility="collapsed")
                    if f_classe == "FII" and n_tipo == "papel":
                        n_idx = st.selectbox("indexador", ["CDI", "IPCA"], label_visibility="collapsed")
                c4, c5, c6 = st.columns([0.9, 1.1, 0.9])
                with c4:
                    f_qtd_str = st.text_input("qtd", placeholder="quantidade",
                                              label_visibility="collapsed")
                with c5:
                    f_preco_str = st.text_input("preco", placeholder="preço unitário",
                                                label_visibility="collapsed")
                with c6:
                    try:
                        f_qtd   = float(f_qtd_str.replace(',','.')) if f_qtd_str else 0.0
                        f_preco = float(f_preco_str.replace(',','.')) if f_preco_str else 0.0
                    except:
                        f_qtd, f_preco = 0.0, 0.0
                    f_total = f_qtd * f_preco
                    st.markdown(f"<div style='padding-top:6px;font-size:13px'>{formatar_brl(f_total)}</div>",
                                unsafe_allow_html=True)

                ca, cb = st.columns([1, 5])
                with ca:
                    if st.button("salvar", type="primary", width="stretch"):
                        _erro_novo = None
                        if _novo:
                            import re as _re
                            if not _re.fullmatch(r"[A-Z]{4}\d{1,2}", f_ativo or ""):
                                _erro_novo = "ticker inválido — use o formato da B3 (ex.: HGLG11)."
                            elif f_ativo in _classe_de:
                                _erro_novo = f"{f_ativo} já está na carteira — selecione na lista."
                            elif f_tipo != "compra":
                                _erro_novo = "o primeiro lançamento de um ativo novo precisa ser compra."
                            elif validar_ticker_b3(f_ativo) <= 0:
                                _erro_novo = f"não encontrei cotação para {f_ativo} na B3."
                        if _erro_novo:
                            st.warning(_erro_novo)
                        elif f_qtd > 0 and f_preco > 0:
                            if _novo:
                                salvar_ativo_info(f_ativo, f_classe, tipo=n_tipo,
                                                  indexador=n_idx, pais=n_pais)
                            salvar_lancamento([
                                f_data.strftime("%d/%m/%Y"),
                                f_tipo, f_ativo, f_classe,
                                float(f_qtd), float(f_preco), float(round(f_total, 2))
                            ])
                            st.session_state["abrir_form_aporte"] = False
                            st.rerun(scope="app")
                        else:
                            st.warning("preencha quantidade e preço.")
                with cb:
                    if st.button("✕ cancelar"):
                        st.session_state["abrir_form_aporte"] = False
                        st.rerun()

        st.markdown("---")

        if df_lanc.empty:
            st.info("nenhum lançamento registrado ainda.")
            return

        # ── histórico ────────────────────────────────────────────────────────
        # guardar índice original (posição no Sheets = índice + 2)
        df_hist = df_lanc.copy().reset_index(drop=True)
        df_hist["_sheet_row"] = df_hist.index + 2  # linha real no Sheets (1-based, +1 header)
        df_hist = df_hist.sort_values("data_dt", ascending=False).reset_index(drop=True)
        n = len(df_hist)
        df_hist.insert(0, "#", range(n, 0, -1))

        df_hist_fmt = df_hist.copy()
        df_hist_fmt["preco_unitario"] = df_hist_fmt["preco_unitario"].apply(
            lambda x: formatar_brl(x) if pd.notna(x) else "")
        df_hist_fmt["total"] = df_hist_fmt["total"].apply(
            lambda x: formatar_brl(x) if pd.notna(x) else "")
        df_hist_fmt["quantidade"] = df_hist_fmt["quantidade"].apply(
            lambda x: f"{x:.8f}".rstrip('0').rstrip('.').replace('.', ',')
            if pd.notna(x) and x < 1 else (f"{x:g}".replace('.', ',') if pd.notna(x) else ""))
        df_hist_fmt["valor"] = df_hist_fmt["valor"].apply(
            lambda x: formatar_brl(x) if pd.notna(x) else "")

        with st.expander("histórico", expanded=False):
            cols_show = ["#", "data", "tipo", "ativo", "classe", "quantidade", "preco_unitario", "total"]
            cfg_hist  = {c: st.column_config.TextColumn(c, alignment="center") for c in cols_show}
            st.dataframe(df_hist_fmt[cols_show], width="stretch",
                         hide_index=True, column_config=cfg_hist)

            st.markdown("---")

            # ── excluir lançamento (aqui, junto com o histórico que ele referencia) ──
            st.caption("excluir lançamento")
            idx_del = st.number_input(
                "número # do lançamento (conforme tabela acima)",
                min_value=1, max_value=n, step=1, value=1,
                key="idx_del_input"
            )
            sel = df_hist[df_hist["#"] == int(idx_del)]
            if not sel.empty:
                row_prev = sel.iloc[0]
                st.caption(f"selecionado: {row_prev['data']} · {row_prev['ativo']} · {row_prev['tipo']} · qtd {row_prev['quantidade']}")
                if st.button("excluir", type="secondary"):
                    try:
                        # buscar linha real no Sheets pelo conteúdo (data + ativo + tipo)
                        svc_del = get_sheets_service()
                        res_del = svc_del.values().get(
                            spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A:G"
                        ).execute()
                        rows_del = res_del.get("values", [])
                        linha_real = None
                        for i, r in enumerate(rows_del):
                            if (len(r) >= 4 and
                                r[0] == row_prev['data'] and
                                r[2] == row_prev['ativo'] and
                                r[1] == row_prev['tipo']):
                                linha_real = i  # 0-based para deleteDimension
                                break
                        if linha_real is not None:
                            deletar_lancamento(linha_real + 1)  # +1 para converter para 1-based
                            st.success("excluído!")
                        else:
                            st.error("linha não encontrada no Sheets — verifique os dados.")
                    except Exception as e:
                        st.error(f"erro: {e}")
                    st.rerun(scope="fragment")

    aba_lancamentos_fragment()


# ── Aba simular novos aportes ─────────────────────────────────────────────────
with aba_aportes:
    # ── inputs ────────────────────────────────────────────────────────────────
    col_v1, _ = st.columns([1, 2])
    _val_aporte_str = col_v1.text_input("$ disponível", value="1800,00", placeholder="ex: 1800,00")

    def _pv(s):
        try: return float(str(s).replace('R$','').replace('.','').replace(',','.').strip())
        except: return 0.0

    _total_disponivel = _pv(_val_aporte_str)

    # ── sugestão resumida (linha 2) ──────────────────────────────────────────
    if _total_disponivel > 0 and _cfg_alvos:
        # pré-calcula para exibir antes da tabela — valores serão recalculados abaixo
        pass  # placeholder — resumo real aparece após cálculo

    st.markdown("---")

    if _total_disponivel <= 0:
        st.info("informe o valor disponível para o aporte.")
    elif not _cfg_alvos:
        st.warning("configure os alvos por ativo na aba ⚙️ configurações antes de simular.")
    else:
        # ── calcular desvios ──────────────────────────────────────────────────
        _etfs_sim   = sorted(a for a, c in _classe_de.items() if c == 'ETF')
        _fiis_sim   = sorted(a for a, c in _classe_de.items() if c == 'FII')
        _outros_sim = ['Renda+ 2050', 'BTC']
        _n_fiis_sim = len(_fiis_sim)

        # alvo por ativo em %
        def _alvo_sim(ativo):
            if ativo in _fiis_sim:
                return (_get_banda(_cfg_alvos, '__FIIs__').get('alvo') or 0) / _n_fiis_sim if _n_fiis_sim > 0 else 0
            return _get_banda(_cfg_alvos, ativo).get('alvo') or 0

        def _min_sim(ativo):
            if ativo in _fiis_sim:
                return (_get_banda(_cfg_alvos, '__FIIs__').get('min') or 0) / _n_fiis_sim if _n_fiis_sim > 0 else 0
            return _get_banda(_cfg_alvos, ativo).get('min') or 0

        # todos os ativos relevantes (exceto Tesouro Selic)
        _ativos_sim = [a for a in (_etfs_sim + _fiis_sim + _outros_sim)
                       if a in _posicao['ativo'].tolist() or a in _etfs_sim + _outros_sim]

        # patrimônio total atual + aporte
        _total_futuro = total_geral + _total_disponivel

        linhas_sim = []
        for ativo in _ativos_sim:
            _df_row = df[df['Ativo'] == ativo]
            _total_atual_a = float(_df_row['Total Atual'].iloc[0]) if not _df_row.empty else 0.0
            _alvo_pct = _alvo_sim(ativo)
            _min_pct  = _min_sim(ativo)
            _alvo_rs  = _alvo_pct / 100 * _total_futuro
            _min_rs   = _min_pct  / 100 * _total_futuro
            _desvio_rs = _total_atual_a - (_alvo_pct / 100 * total_geral)
            _desvio_pct = (_total_atual_a / total_geral * 100 - _alvo_pct) if total_geral > 0 else 0
            _abaixo_min = _total_atual_a < _min_rs

            linhas_sim.append({
                'ativo':       ativo,
                'atual_rs':    _total_atual_a,
                'atual_pct':   _total_atual_a / total_geral * 100 if total_geral > 0 else 0,
                'alvo_pct':    _alvo_pct,
                'desvio_rs':   _desvio_rs,
                'desvio_pct':  _desvio_pct,
                'abaixo_min':  _abaixo_min,
                'prioridade':  -_desvio_rs,  # base: desvio negativo
                'pm':          (_df_row['preco_medio'].iloc[0] if not _df_row.empty else 0.0),
            })

        df_sim = pd.DataFrame(linhas_sim)
        # score combinado: desvio + bônus por desconto vs PM
        _fator_pm_val = float(st.session_state.get("cfg_fator_pm", 0.3))
        def _score(row):
            base = row['prioridade']  # -desvio_rs (positivo = abaixo do alvo)
            if base <= 0:
                return base  # acima do alvo — não altera
            pm_row = row.get('pm', 0)
            preco_row_val = _precos_sim.get(row['ativo'], pm_row) if '_precos_sim' in dir() else pm_row
            desconto = (pm_row - preco_row_val) / pm_row if pm_row > 0 else 0
            bonus = base * desconto * _fator_pm_val
            return base + bonus
        # _precos_sim ainda não existe aqui — será usado na parte de sugestão
        # ordenar por desvio apenas; ajuste de score acontece dentro do bloco com preços
        df_sim = df_sim.sort_values('prioridade', ascending=False)

        # ── alocação sugerida com restrição de inteiro de cotas ─────────────
        _FRACIONADOS = {'Renda+ 2050', 'BTC'}  # permitem compra fracionada
        _com_desvio_neg = df_sim[df_sim['desvio_rs'] < 0].copy()

        if _com_desvio_neg.empty:
            st.success("✅ carteira equilibrada — nenhum ativo com desvio negativo.")
            _sugestao = {}
        else:
            # buscar preços atuais e PM
            _precos_sim = {row['Ativo']: row['preco_unit'] for _, row in df.iterrows()}
            _pm_sim     = {row['Ativo']: row['preco_medio'] for _, row in df.iterrows()}
            _fator_pm   = float(st.session_state.get("cfg_fator_pm", 0.3))
            _fator_perf = float(st.session_state.get("cfg_fator_perf", 0.2))

            # variação 90 dias via yfinance (cacheado — evita repetir a cada rerun)
            _tickers_90 = tuple(sorted(a for a in _precos_sim if a not in ('BTC', 'Renda+ 2050')))
            _var_90d = obter_variacao_90d(_tickers_90)

            # score normalizado: cada componente compete no range 0-1
            # peso: 60% desvio alocação · fator_pm% desconto PM · fator_perf% queda 90d
            _neg = _com_desvio_neg.copy()

            # componente 1: desvio normalizado (já é prioridade = -desvio_rs, positivo)
            _max_desv = _neg['prioridade'].max()
            _neg['_c_desv'] = _neg['prioridade'] / _max_desv if _max_desv > 0 else 0

            # componente 2: desconto vs PM normalizado
            def _desc_pm(row):
                pm_r = row.get('pm', 0)
                pr   = _precos_sim.get(row['ativo'], pm_r)
                return max((pm_r - pr) / pm_r, 0) if pm_r > 0 else 0
            _neg['_c_pm'] = _neg.apply(_desc_pm, axis=1)
            _max_pm = _neg['_c_pm'].max()
            _neg['_c_pm'] = _neg['_c_pm'] / _max_pm if _max_pm > 0 else 0

            # componente 3: queda 90d normalizada
            _neg['_c_perf'] = _neg['ativo'].map(lambda a: max(-_var_90d.get(a, 0), 0))
            _max_perf = _neg['_c_perf'].max()
            _neg['_c_perf'] = _neg['_c_perf'] / _max_perf if _max_perf > 0 else 0

            # peso total: 60% desvio + fator_pm * 20% + fator_perf * 20%
            # (fator_pm e fator_perf escalam de 0 a 1 sua contribuição nos 40% restantes)
            _w_desv  = 0.6
            _w_pm    = _fator_pm   * 0.2
            _w_perf  = _fator_perf * 0.2
            _neg['score'] = (_neg['_c_desv'] * _w_desv +
                             _neg['_c_pm']   * _w_pm   +
                             _neg['_c_perf'] * _w_perf)
            _com_desvio_neg = _neg.sort_values('score', ascending=False)

            _soma_desvios = _com_desvio_neg['score'].sum()
            _sugestao = {}
            _restante = _total_disponivel

            # 1ª passagem: distribuir proporcionalmente ao score, arredondando para inteiro
            for _, row in _com_desvio_neg.iterrows():
                ativo = row['ativo']
                _prop = row['score'] / _soma_desvios if _soma_desvios > 0 else 0
                _valor_ideal = _total_disponivel * _prop
                _preco = _precos_sim.get(ativo, 0)
                if _preco <= 0:
                    continue
                if ativo in _FRACIONADOS:
                    _valor_compra = min(_valor_ideal, _restante)
                else:
                    _cotas = int(_valor_ideal / _preco)
                    _valor_compra = min(_cotas * _preco, _restante)
                if _valor_compra > 0:
                    _sugestao[ativo] = _sugestao.get(ativo, 0) + _valor_compra
                    _restante -= _valor_compra

            # 2ª passagem: redistribuir saldo restante por prioridade até não caber mais nenhuma cota
            _mudou = True
            while _mudou and _restante > 0.5:
                _mudou = False
                for _, row in _com_desvio_neg.iterrows():
                    ativo = row['ativo']
                    _preco = _precos_sim.get(ativo, 0)
                    if _preco <= 0:
                        continue
                    if ativo in _FRACIONADOS:
                        if _restante > 0.01:
                            _add = min(_restante, _preco * 0.1)  # adiciona fração mínima
                            _sugestao[ativo] = _sugestao.get(ativo, 0) + _add
                            _restante -= _add
                            _mudou = True
                    else:
                        if _restante >= _preco:
                            _sugestao[ativo] = _sugestao.get(ativo, 0) + _preco
                            _restante -= _preco
                            _mudou = True
                    if _restante < 0.5:
                        break

        # ── resumo da sugestão (linha 2, acima da tabela) ────────────────────
        _ativos_sug = {k: v for k, v in _sugestao.items() if v > 0.5} if _sugestao else {}
        if _ativos_sug:
            _cols_sug = st.columns(min(len(_ativos_sug), 5))
            for i, (ativo, valor) in enumerate(_ativos_sug.items()):
                _preco_a = _precos_sim.get(ativo, 0)
                if ativo == 'BTC':
                    _display = abreviar_rs(valor)
                elif ativo in _FRACIONADOS:
                    _qtd_f = valor / _preco_a if _preco_a > 0 else 0
                    _display = f"{fmt_num(_qtd_f, 4)} un"
                else:
                    _display = f"{int(round(valor/_preco_a))} cotas" if _preco_a > 0 else "—"
                _cols_sug[i % len(_cols_sug)].metric(ativo, _display)
            _soma_sug = sum(_sugestao.values())
            _nao_alocado = _total_disponivel - _soma_sug
            if _nao_alocado > 0.5:
                st.caption(f"↳ não alocado: {formatar_brl(_nao_alocado)}")
        else:
            # valor insuficiente para cota inteira do ativo prioritário
            # 1) tentar comprar o de maior score que o valor consegue cobrir
            _compra_alt = None
            _compra_val = 0.0
            for _, row in _com_desvio_neg.iterrows():  # ordenado por score
                ativo  = row['ativo']
                _preco = _precos_sim.get(ativo, 0)
                if _preco <= 0:
                    continue
                if ativo in _FRACIONADOS or _preco <= _total_disponivel:
                    _compra_alt = ativo
                    _compra_val = _total_disponivel if ativo in _FRACIONADOS else _preco
                    break
            if _compra_alt:
                _sugestao[_compra_alt] = _compra_val
                _preco_a = _precos_sim.get(_compra_alt, 0)
                if _compra_alt == 'BTC':
                    _display = abreviar_rs(_compra_val)
                elif _compra_alt in _FRACIONADOS:
                    _qtd_f = _compra_val / _preco_a if _preco_a > 0 else 0
                    _display = f"{fmt_num(_qtd_f, 4)} un"
                else:
                    _display = f"{int(round(_compra_val/_preco_a))} cotas" if _preco_a > 0 else "—"
                st.columns([1,3])[0].metric(_compra_alt, _display)
            else:
                # nenhum ativo acessível — mostrar o mais próximo de ser comprado
                _proximo = None
                _falta   = None
                _menor_falta = 9e9
                for _, row in _com_desvio_neg.iterrows():
                    ativo  = row['ativo']
                    _preco = _precos_sim.get(ativo, 0)
                    if _preco <= 0 or ativo in _FRACIONADOS:
                        continue
                    _f = _preco - _total_disponivel
                    if _f < _menor_falta:
                        _menor_falta = _f
                        _proximo = ativo
                        _falta   = _f
                if _proximo:
                    st.info(
                        f"valor insuficiente para qualquer cota inteira com desvio negativo. "
                        f"mais próximo: **{_proximo}** · faltam **{formatar_brl(_falta)}**"
                    )
                else:
                    # nenhum com desvio negativo acessível — buscar em todos os ativos por menor preço
                    _proximo2 = None
                    _falta2   = None
                    _menor2   = 9e9
                    for _, row in df_sim.iterrows():
                        ativo  = row['ativo']
                        _preco = _precos_sim.get(ativo, 0)
                        if _preco <= 0 or ativo in _FRACIONADOS:
                            continue
                        if _preco <= _total_disponivel:
                            # consegue comprar — usar direto
                            _proximo2 = ativo
                            _falta2   = 0.0
                            break
                        _f = _preco - _total_disponivel
                        if _f < _menor2:
                            _menor2   = _f
                            _proximo2 = ativo
                            _falta2   = _f
                    if _proximo2 and _falta2 == 0.0:
                        _sugestao[_proximo2] = _precos_sim.get(_proximo2, 0)
                        _preco_a = _precos_sim.get(_proximo2, 0)
                        _display2 = f"1 cota" if _preco_a > 0 else "—"
                        st.columns([1,3])[0].metric(_proximo2, _display2)
                    elif _proximo2:
                        st.info(
                            f"nenhum ativo acessível com {formatar_brl(_total_disponivel)}. "
                            f"mais próximo: **{_proximo2}** · faltam **{formatar_brl(_falta2)}**"
                        )

        st.markdown("---")

        # ── tabela de desvios ─────────────────────────────────────────────────
        st.markdown("**desvios atuais**")
        _total_alocado     = sum(_sugestao.values())
        # denominador = soma atual dos ativos simulados + o que foi alocado
        _total_sim_atual   = df_sim['atual_rs'].sum()
        _total_futuro_real = _total_sim_atual + _total_alocado
        _rows_disp = []
        for _, row in df_sim.iterrows():
            _sug = _sugestao.get(row['ativo'], 0.0)
            _novo_total = row['atual_rs'] + _sug
            _novo_pct   = _novo_total / _total_futuro_real * 100 if _total_futuro_real > 0 else 0
            _status = "🔴 abaixo mín" if row['abaixo_min'] else ("🟢 ok" if row['desvio_rs'] >= 0 else "🟡 desvio")
            _preco_a = _precos_sim.get(row['ativo'], 0)
            if _sug > 0 and _preco_a > 0:
                if row['ativo'] in _FRACIONADOS:
                    _cotas_str = fmt_num(_sug/_preco_a, 4)
                else:
                    _cotas_str = str(int(round(_sug / _preco_a)))
            else:
                _cotas_str = '—'
            _rows_disp.append({
                'ativo':          row['ativo'],
                'atual %':        fmt_pct(row['atual_pct']),
                'alvo %':         fmt_pct(row['alvo_pct']),
                'desvio R$':      ('+' if row['desvio_rs'] >= 0 else '') + formatar_brl(row['desvio_rs']),
                'status':         _status,
                'sugestão':       _cotas_str if row['ativo'] != 'BTC' else (abreviar_rs(_sug) if _sug > 0 else '—'),
                'após aporte %':  fmt_pct(_novo_pct),
            })

        df_disp = pd.DataFrame(_rows_disp)
        _cfg_disp = {c: st.column_config.TextColumn(c, alignment="center") for c in df_disp.columns}
        st.dataframe(df_disp, width="stretch", hide_index=True, column_config=_cfg_disp)

        # ── resumo da sugestão ────────────────────────────────────────────────


# ── Aba configurações ─────────────────────────────────────────────────────────
with aba_config:
    _ativos_cfg = sorted(_posicao['ativo'].tolist()) if not _posicao.empty else []
    _fiis_cfg   = [a for a in _ativos_cfg if _classe_de.get(a) == 'FII']
    _etfs_cfg   = [a for a in _ativos_cfg if _classe_de.get(a) == 'ETF']
    _td_cfg     = [a for a in _ativos_cfg if a in ['Renda+ 2050']]
    _cripto_cfg = [a for a in _ativos_cfg if a in ['BTC']]
    _alvos_edit = dict(st.session_state.get("cfg_alvos", {}))
    _n_fiis_cfg = len(_fiis_cfg)

    def _parse_alvo(s):
        try: return float(str(s).replace(',', '.').strip())
        except: return None

    def _fmt_v(cfg_ativo, campo):
        banda = _get_banda({"_": cfg_ativo}, "_") if not isinstance(cfg_ativo, dict) else cfg_ativo
        v = banda.get(campo)
        return f"{v:.1f}".replace('.', ',') if v is not None else ""

    def _inputs_banda(container, ativo, cfg):
        """renderiza 3 colunas mín/alvo/máx para um ativo"""
        _banda = cfg.get(ativo, {})
        c1, c2, c3 = container.columns(3)
        c1.caption("mín")
        c2.caption("alvo")
        c3.caption("máx")
        _min  = c1.text_input(f"{ativo}_min",  value=_fmt_v(_banda, 'min'),  label_visibility="collapsed", placeholder="ex: 18,0", key=f"min_{ativo}")
        _alvo = c2.text_input(f"{ativo}_alvo", value=_fmt_v(_banda, 'alvo'), label_visibility="collapsed", placeholder="ex: 20,0", key=f"alvo_{ativo}")
        _max  = c3.text_input(f"{ativo}_max",  value=_fmt_v(_banda, 'max'),  label_visibility="collapsed", placeholder="ex: 22,0", key=f"max_{ativo}")
        return _min, _alvo, _max

    # ── resumo por classe (topo) ──────────────────────────────────────────────
    if _alvos_edit:
        def _alvo_c(ativo): return _get_banda(_alvos_edit, ativo).get('alvo') or 0
        _alvo_fii_cl = _get_banda(_alvos_edit, '__FIIs__').get('alvo') or 0
        _soma_etfs_r = sum(_alvo_c(a) for a in _etfs_cfg)
        _soma_td_r   = sum(_alvo_c(a) for a in _td_cfg)
        _soma_cri_r  = sum(_alvo_c(a) for a in _cripto_cfg)
        _soma_total_r = _soma_etfs_r + _alvo_fii_cl + _soma_td_r + _soma_cri_r
        _cor_r = "🟢" if abs(_soma_total_r - 100) < 0.01 else "🔴"
        st.caption(f"{_cor_r} soma dos alvos: **{fmt_pct(_soma_total_r)}**")
        _cols_rc = st.columns(4)
        _cols_rc[0].metric("ETFs", fmt_pct(_soma_etfs_r))
        _cols_rc[1].metric("FIIs", fmt_pct(_alvo_fii_cl))
        _cols_rc[2].metric("Tesouro Direto", fmt_pct(_soma_td_r))
        _cols_rc[3].metric("Cripto", fmt_pct(_soma_cri_r))
        if _n_fiis_cfg > 0 and _alvo_fii_cl > 0:
            st.caption(f"→ cada FII: {fmt_pct(_alvo_fii_cl / _n_fiis_cfg)} ({_n_fiis_cfg} ativos)")
        st.markdown("---")

    # ── formulário ───────────────────────────────────────────────────────────
    st.caption("valores em % do total da carteira · a soma dos alvos deve fechar em 100%")

    # ── fator de desconto vs PM ───────────────────────────────────────────────
    st.markdown("#### pesos do simulador de aportes")
    st.caption("fatores que ajustam a prioridade de cada ativo além do desvio de alocação")
    _cf1, _cf2 = st.columns(2)

    _fator_pm_atual = st.session_state.get("cfg_fator_pm", 0.3)
    _fator_pm_str = _cf1.text_input(
        "desconto vs preço médio (0–1)",
        value=f"{_fator_pm_atual:.1f}".replace('.', ','),
        placeholder="ex: 0,3", key="fator_pm_input",
        help="0 = ignora · 1 = mesmo peso do desvio · recomendado: 0,3"
    )
    try:
        _fpm = max(0.0, min(1.0, float(_fator_pm_str.replace(',', '.'))))
        st.session_state["cfg_fator_pm"] = _fpm
    except: pass

    _fator_perf_atual = st.session_state.get("cfg_fator_perf", 0.2)
    _fator_perf_str = _cf2.text_input(
        "queda nos últimos 90 dias (0–1)",
        value=f"{_fator_perf_atual:.1f}".replace('.', ','),
        placeholder="ex: 0,2", key="fator_perf_input",
        help="0 = ignora · 1 = mesmo peso do desvio · recomendado: 0,2"
    )
    try:
        _fperf = max(0.0, min(1.0, float(_fator_perf_str.replace(',', '.'))))
        st.session_state["cfg_fator_perf"] = _fperf
    except: pass
    st.markdown("---")

    with st.form("form_cfg"):
        st.markdown("**ETFs**")
        _inp_etf = {}
        for a in _etfs_cfg:
            st.markdown(f"*{a}*")
            _inp_etf[a] = _inputs_banda(st, a, _alvos_edit)

        st.markdown("**FIIs** *(alvo da classe — dividido igualmente entre os {n} ativos)*".format(n=_n_fiis_cfg))
        _banda_fii = _alvos_edit.get("__FIIs__", {}) or {}
        _cf1, _cf2, _cf3 = st.columns(3)
        _cf1.caption("mín"); _cf2.caption("alvo"); _cf3.caption("máx")
        _fii_min  = _cf1.text_input("fii_min",  value=_fmt_v(_banda_fii,'min'),  label_visibility="collapsed", placeholder="ex: 22,0", key="min___FIIs__")
        _fii_alvo = _cf2.text_input("fii_alvo", value=_fmt_v(_banda_fii,'alvo'), label_visibility="collapsed", placeholder="ex: 25,0", key="alvo___FIIs__")
        _fii_max  = _cf3.text_input("fii_max",  value=_fmt_v(_banda_fii,'max'),  label_visibility="collapsed", placeholder="ex: 28,0", key="max___FIIs__")

        st.markdown("**Tesouro Direto**")
        _inp_td = {}
        for a in _td_cfg:
            st.markdown(f"*{a}*")
            _inp_td[a] = _inputs_banda(st, a, _alvos_edit)

        st.markdown("**Cripto**")
        _inp_cri = {}
        for a in _cripto_cfg:
            st.markdown(f"*{a}*")
            _inp_cri[a] = _inputs_banda(st, a, _alvos_edit)

        _salvar = st.form_submit_button("salvar")
        if _salvar:
            _cfg_nova = {}
            _ok = True
            def _parse_banda(mn, al, mx, nome):
                vmin  = _parse_alvo(mn)
                valvo = _parse_alvo(al)
                vmax  = _parse_alvo(mx)
                if al.strip() and valvo is None:
                    st.error(f"valor inválido para {nome}"); return None, False
                if mn.strip() and vmin is None:
                    st.error(f"mín inválido para {nome}"); return None, False
                if mx.strip() and vmax is None:
                    st.error(f"máx inválido para {nome}"); return None, False
                return {'min': vmin, 'alvo': valvo, 'max': vmax}, True

            for grp in [_inp_etf, _inp_td, _inp_cri]:
                for a, (mn, al, mx) in grp.items():
                    banda, ok = _parse_banda(mn, al, mx, a)
                    if not ok: _ok = False
                    else: _cfg_nova[a] = banda

            banda_fii, ok_fii = _parse_banda(_fii_min, _fii_alvo, _fii_max, "FIIs")
            if not ok_fii: _ok = False
            else: _cfg_nova["__FIIs__"] = banda_fii

            if _ok:
                _soma_alvos = sum((v.get('alvo') or 0) for k,v in _cfg_nova.items() if k != "__FIIs__")
                _soma_alvos += (_cfg_nova.get("__FIIs__", {}) or {}).get('alvo') or 0
                if abs(_soma_alvos - 100) > 0.01:
                    st.error(f"soma dos alvos: {fmt_pct(_soma_alvos)} — ajuste para fechar em 100%")
                else:
                    if salvar_configuracoes(_cfg_nova):
                        st.session_state["cfg_alvos"] = _cfg_nova
                        st.success("configurações salvas.")
                        st.rerun(scope="app")

    # ── metas de longo prazo ─────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### metas")
    if "_metas" not in st.session_state:
        st.session_state["_metas"] = ler_metas()
    _mc1, _mc2 = st.columns([3, 1], vertical_alignment="bottom")
    _meta_str = _mc1.text_input(
        "Renda+ 2050 — títulos até dez/2045",
        value=fmt_num(st.session_state["_metas"].get("renda_2050_titulos_dez2045", 450), 2),
        key="meta_renda_2045_input")
    if _mc2.button("salvar meta", key="btn_salvar_meta", width="stretch"):
        try:
            _v_meta = float(_meta_str.replace('.', '').replace(',', '.'))
            if _v_meta <= 0:
                raise ValueError
            salvar_meta("renda_2050_titulos_dez2045", _v_meta)
            st.success("meta salva.")
            st.rerun(scope="app")
        except ValueError:
            st.error("valor inválido — use um número, ex.: 450")
