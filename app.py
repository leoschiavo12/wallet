import streamlit as st
import yfinance as yf
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import math
import requests
from google.oauth2 import service_account
from googleapiclient.discovery import build
from datetime import date

st.set_page_config(page_title="SmartWallet", layout="wide", page_icon="")

st.markdown("""
    <style>
        html, body, [class*="css"] { font-size: 14px !important; }
        .stDataFrame div [role="gridcell"] > div { justify-content: center !important; text-align: center !important; }
        .stDataFrame div [role="columnheader"] > div { justify-content: center !important; text-align: center !important; }
        [data-testid="stMetricDelta"] { display: none !important; }
    </style>
    """, unsafe_allow_html=True)

@st.cache_resource
def _yf_session():
    """sessão yfinance reutilizada — evita reconexão a cada chamada"""
    return yf

def obter_precos_b3(tickers_lista):
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    try:
        dados = _yf_session().download(tk_formatados, period="5d", progress=False, auto_adjust=True, timeout=7)
        precos = {}
        falhas = []
        for t in tickers_lista:
            try:
                tk = f"{t.upper()}.SA"
                if isinstance(dados.columns, pd.MultiIndex):
                    serie = dados['Close'][tk].ffill()
                else:
                    serie = dados['Close'].ffill()
                v = float(serie.dropna().iloc[-1])
                precos[t.upper()] = v if v > 0 else 0.0
                if v <= 0: falhas.append(t)
            except:
                precos[t.upper()] = 0.0
                falhas.append(t)
        if falhas:
            st.session_state['_precos_falha'] = falhas
        return precos
    except:
        return {t.upper(): 0.0 for t in tickers_lista}

@st.cache_data(ttl=3600)
def obter_dividendos_mes_anterior(df_lancamentos_json):
    import pandas as pd
    from datetime import date
    hoje    = date.today()
    # mes de referencia = mes anterior (pagamento)
    if hoje.month == 1:
        mes_ref, ano_ref = 12, hoje.year - 1
    else:
        mes_ref, ano_ref = hoje.month - 1, hoje.year

    df_lanc = pd.DataFrame(df_lancamentos_json)
    if df_lanc.empty:
        return 0.0, {}
    # normalizar nomes de colunas
    df_lanc.columns = [c.title() for c in df_lanc.columns]
    df_lanc['data_dt'] = pd.to_datetime(df_lanc['Data'], format='%d/%m/%Y', errors='coerce')
    df_lanc['sinal']   = df_lanc['Tipo'].str.lower().map({'compra': 1, 'venda': -1}).fillna(0)

    total    = 0.0
    detalhes = {}
    ALIAS    = {'GALG11': 'GARE11'}

    # Classe vem como 'FII' do Sheets — após title() fica 'Fii'
    fiis = list(df_lanc[df_lanc['Classe'].str.upper() == 'FII']['Ativo'].unique())

    for fii in fiis:
        fii_norm = ALIAS.get(fii, fii)
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
                # normalizar data_ex para só data (sem horário) e usar <=
                # para capturar quem detinha na data-base (inclusive)
                data_ex_date = pd.Timestamp(data_ex).normalize()
                ops = df_lanc[
                    (df_lanc['Ativo'] == fii) &
                    (df_lanc['data_dt'].dt.normalize() <= data_ex_date)
                ]
                if ops.empty and fii != fii_norm:
                    ops = df_lanc[
                        (df_lanc['Ativo'] == fii_norm) &
                        (df_lanc['data_dt'].dt.normalize() <= data_ex_date)
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

    return total, detalhes

def obter_preco_btc_brl():
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
            tk   = yf.Ticker(f"{ativo}.SA")
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
                # qtd de cotas na data do dividendo
                g_ate = g[g['data_dt'] <= data_div]
                qtd = (g_ate['quantidade'] * g_ate['sinal']).sum()
                if qtd > 0:
                    total_ativo += qtd * valor_div

            resultado[ativo] = round(total_ativo, 2)
            total_geral_divs += total_ativo
        except:
            continue

    # somar lançamentos manuais de tipo 'dividendo' (ajustes para fundos sem histórico yfinance)
    _divs_manuais = df[df['tipo'].str.strip().str.lower() == 'dividendo']
    for _, row in _divs_manuais.iterrows():
        ativo = row['ativo']
        valor = float(row['total']) if pd.notna(row['total']) else 0.0
        if valor > 0:
            resultado[ativo] = resultado.get(ativo, 0.0) + valor
            total_geral_divs += valor

    return resultado, round(total_geral_divs, 2)

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

def obter_preco_renda_mais():
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
        df = pd.read_csv(StringIO(csv_str), sep=';', decimal=',')
        df['Data Base'] = pd.to_datetime(df['Data Base'], format='%d/%m/%Y', errors='coerce')

        # filtrar: titulo contem Renda, vencimento contem 2069
        mask = (
            df['Tipo Titulo'].str.contains('Renda', case=False, na=False) &
            df['Data Vencimento'].str.contains('2069', na=False)
        )
        df_f = df[mask].sort_values('Data Base', ascending=False)

        if df_f.empty:
            return None, f'nenhum registro apos filtro — datas: {df["Data Base"].dt.strftime("%d/%m/%Y").tolist()[-3:]}'

        pu  = float(df_f.iloc[0]['PU Venda Manha'])
        dt  = df_f.iloc[0]['Data Base'].strftime('%d/%m/%Y')
        return pu, dt
    except Exception as e:
        return None, str(e)
    except Exception as e:
        return None, str(e)

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
        v = f"{valor/1_000_000:.1f}".replace('.', ',')
        return f"R$ {v}M"
    elif valor >= 1_000:
        v = valor / 1_000
        s = f"{v:.1f}".replace('.', ',')
        if s.endswith(',0'):
            s = s[:-2]
        return f"R$ {s}k"
    else:
        return f"R$ {int(valor)}"

def formatar_brl(valor):
    s = f"{valor:,.2f}"
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f"R$ {s}"

def fmt_pct(valor):
    """formata % sem casa decimal se for ,0"""
    s = f"{valor:.1f}".replace('.', ',')
    if s.endswith(',0'):
        s = s[:-2]
    return f"{s}%"

def fmt_holding(meses):
    """formata holding em meses (<12) ou anos (>=12), com vírgula"""
    if meses is None: return "—"
    if meses < 12:
        s = f"{meses:.1f}".replace('.', ',')
        if s.endswith(',0'): s = s[:-2]
        return f"{s} meses"
    else:
        anos = meses / 12
        s = f"{anos:.1f}".replace('.', ',')
        if s.endswith(',0'): s = s[:-2]
        return f"{s} anos"

def tag_var(rs, pct):
    """tag colorida de valorização ▲/▼ %  ·  R$"""
    sinal = "▲" if rs >= 0 else "▼"
    cor   = "#22c55e" if rs >= 0 else "#ef4444"
    return (f"<span style='color:{cor};font-weight:600;font-family:inherit'>"
            f"{sinal} {'+' if pct>=0 else ''}{fmt_pct(pct)}  ·  {abreviar_rs(abs(rs))}</span>")

def card_valorizacao(col, rs, pct):
    """card HTML de valorização: label=valorização · R$ X, valor grande colorido"""
    sinal    = "▲" if rs >= 0 else "▼"
    cor      = "#22c55e" if rs >= 0 else "#ef4444"
    _pct_str = ("+" if pct >= 0 else "") + fmt_pct(pct)
    _rs_str  = ("-" if rs < 0 else "") + abreviar_rs(abs(rs))
    col.markdown(
        f"<div style='padding-top:4px'>"
        f"<p style='font-size:0.875rem;color:rgba(250,250,250,0.6);margin:0 0 6px 0'>"
        f"valorização · {_rs_str}</p>"
        f"<p style='font-size:1.75rem;font-weight:500;color:{cor};margin:0;line-height:1.1'>"
        f"{sinal} {_pct_str}</p></div>",
        unsafe_allow_html=True
    )

def metric_tag(col, label, valor, rs, pct):
    """st.metric nativo — col já é a coluna certa"""
    col.metric(label, valor)

def metric_tag_simples(col, label, valor):
    col.metric(label, valor)


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

@st.cache_data(ttl=86400)
def obter_preco_renda_mais_cached():
    return obter_preco_renda_mais()

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

def obter_preco_historico_yfinance(ticker_sa, data_fim):
    """preço de fechamento do último dia útil até data_fim"""
    try:
        import datetime
        data_ini = data_fim - datetime.timedelta(days=10)
        dados = yf.download(ticker_sa, start=data_ini.strftime('%Y-%m-%d'),
                            end=(data_fim + datetime.timedelta(days=1)).strftime('%Y-%m-%d'),
                            progress=False, auto_adjust=True)
        if dados.empty: return None
        close = dados['Close']
        if isinstance(close, pd.DataFrame): close = close.iloc[:, 0]
        return float(close.ffill().dropna().iloc[-1])
    except:
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
    ultimo_total = 0.0
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
            total_mes = 0.0
            for _, pr in pos_mes.iterrows():
                pm_row = df_pm[(df_pm['ano_mes'] == mes) & (df_pm['ativo'] == pr['ativo'])]
                preco_hist = float(pm_row['preco_fechamento'].iloc[0]) if not pm_row.empty else pr['preco_medio']
                total_mes += pr['qtd_atual'] * preco_hist
            ultimo_total = total_mes
        else:
            total_mes = ultimo_total
        vals.append({'mes': f"{mes}-01", 'total': total_mes, 'atual': False})
    return vals

# ── carregar dados principais (session_state cache) ──────────────────────────
# relê do Sheets só na primeira renderização da sessão
# ou após salvar/excluir lançamento (_lanc_versao muda)
_versao_atual = st.session_state.get("_lanc_versao", 0)
_cache_versao = st.session_state.get("_cache_versao", -1)

if _versao_atual != _cache_versao or "_df_lanc_raw" not in st.session_state:
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

# remover diagnóstico VIUR11 (não mais necessário)

# preços atuais — cacheados por 1h via @st.cache_data em obter_precos_b3
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
            _antes = len(_df_pm_lido)
            _df_pm_lido = popular_precos_mensais(_df_lanc_raw, _df_pm_lido)
            st.session_state["_df_pm"] = _df_pm_lido
            st.session_state['_pm_status'] = f"✓ precos_mensais: {_antes} → {len(_df_pm_lido)} registros"
    except Exception as _e_pm:
        st.session_state['_pm_status'] = f"✗ erro: {_e_pm}"
        st.session_state["_df_pm"] = pd.DataFrame(columns=PM_HEADERS)

_df_pm = st.session_state["_df_pm"]

# ── Classificação dos FIIs ───────────────────────────────────────────────────
FII_INFO = {
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

# ── Configurações de alocação alvo (será migrado para aba configs no futuro) ─
ALVO_CLASSE = {
    'ETF':            40.0,
    'FII':            25.0,
    'Tesouro Direto': 20.0,
    'Cripto':         10.0,
    # Tesouro Selic 2031 = 0% (sendo zerado)
}

aba_dash, aba_detalhe, aba_lanc, aba_aportes, aba_config = st.tabs(["dashboard", "detalhe", "lançamentos", "simular novos aportes", "⚙️ configurações"])

with aba_dash:
    total_k = abreviar_rs(total_geral)

    # total investido = custo de todas as compras − total de vendas
    _custo_total = df['custo_total'].sum()
    _var_val     = total_geral - _custo_total
    _var_pct     = (_var_val / _custo_total * 100) if _custo_total > 0 else 0

    c1, c2 = st.columns([1, 1])
    c1.metric("patrimônio", total_k)

    card_valorizacao(c2, _var_val, _var_pct)

    st.markdown('---')

    # ── linha 1: donut + gráfico mensal lado a lado ───────────────────────────
    col_donut, col_mensal = st.columns([1, 2])

    with col_donut:
        total_classe = df_resumo_classe['Total Atual'].sum()
        labels_donut, hover_donut = [], []
        for _, row in df_resumo_classe.iterrows():
            pct    = row['Total Atual'] / total_classe * 100
            labels_donut.append(f"{row['Classe']}<br>{fmt_pct(pct)}".replace('.', ','))
            hover_donut.append(f"<b>{row['Classe']}</b><br>{fmt_pct(pct)}<br>{formatar_brl(row['Total Atual'])}".replace('.', ','))

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
        st.plotly_chart(fig_donut, use_container_width=True, config={"displayModeBar": False})

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
            vals_mensais = [{'mes': pd.to_datetime(v['mes']), 'total': v['total'],
                             'label': pd.to_datetime(v['mes']).strftime('%b/%y'), 'atual': False}
                            for v in _vals_cache]

            # adicionar barra do mês atual com valor de mercado corrente
            vals_mensais.append({
                'mes':   pd.to_datetime(f"{mes_atual}-01"),
                'total': total_geral,
                'label': pd.to_datetime(f"{mes_atual}-01").strftime('%b/%y') + " ●",
                'atual': True,
            })

            df_mensal = pd.DataFrame(vals_mensais)
            df_mensal['cor']   = df_mensal['atual'].apply(lambda x: "#64B5F6" if x else "#1E88E5")
            df_mensal['hover'] = df_mensal.apply(
                lambda r: f"<b>{r['label'].replace(' ●','')}</b>"
                          + (" <i>(atual)</i>" if r['atual'] else "")
                          + f"<br>{formatar_brl(r['total'])}", axis=1
            )

            # próxima meta — próximo múltiplo de 10k acima do máximo
            _max_val = df_mensal['total'].max()
            _meta    = (int(_max_val // 10000) + 1) * 10000
            y_max    = _meta * 1.05
            _ticks   = list(range(0, int(_meta) + 1, 10000))

            fig_mensal = go.Figure()
            fig_mensal.add_trace(go.Bar(
                x=df_mensal['mes'], y=df_mensal['total'],
                marker_color=df_mensal['cor'].tolist(),
                hovertemplate="%{customdata}<extra></extra>",
                customdata=df_mensal['hover'].tolist(),
            ))
            fig_mensal.update_layout(
            dragmode=False,
                height=400,
                plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)",
                showlegend=False, bargap=0.2,
                xaxis=dict(showgrid=False, tickformat="%b/%y", tickangle=-45),
                yaxis=dict(
                    showgrid=True, gridcolor="#333",
                    range=[0, y_max],
                    tickmode='array',
                    tickvals=_ticks,
                    ticktext=[f"{v//1000:.0f}k" if v > 0 else "0" for v in _ticks],
                ),
                margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(fig_mensal, use_container_width=True, config={"displayModeBar": False})
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

        df_fii = df[df['Classe'] == 'FII'].copy()
        total_fii = df_fii['Total Atual'].sum()
        n_tijolo  = sum(1 for t in df_fii['Ativo'] if FII_INFO.get(t, {}).get('tipo') == 'tijolo')
        n_papel   = sum(1 for t in df_fii['Ativo'] if FII_INFO.get(t, {}).get('tipo') == 'papel')

        # ── linha 1: total, dividendos, yield corrente ───────────────────────
        total_fii_k = abreviar_rs(total_fii)

        # yield = dividendos_mês_ref / valor_carteira_FIIs_fim_mês_anterior
        # ex: dividendos de maio → base = valor FIIs em 30/abr
        _mes_base = f"{ano_ref_f}-{mes_ref_f:02d}"
        _total_fii_base = 0.0
        if not _df_pm.empty:
            for _, _pr in df_fii.iterrows():
                _pm_row = _df_pm[(_df_pm['ano_mes'] == _mes_base) & (_df_pm['ativo'] == _pr['Ativo'])]
                if not _pm_row.empty:
                    _total_fii_base += _pr['Qtd'] * float(_pm_row['preco_fechamento'].iloc[0])
        if _total_fii_base == 0.0:
            _total_fii_base = total_fii  # fallback para valor atual

        yield_mensal = (div_total / _total_fii_base * 100) if _total_fii_base > 0 and div_total > 0 else None

        # calcular total histórico de dividendos (cacheado 24h)
        _divs_hist, _total_divs = calcular_dividendos_historicos(
            _df_lanc_raw.to_dict(orient='records')
        )

        _var_fii_rs  = total_fii - df_fii['custo_total'].sum()
        _var_fii_pct = _var_fii_rs / df_fii['custo_total'].sum() * 100 if df_fii['custo_total'].sum() > 0 else 0
        _pct_fii_carteira = total_fii / total_geral * 100 if total_geral > 0 else 0

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric(f"total FIIs  ·  {total_fii_k}", fmt_pct(_pct_fii_carteira))
        card_valorizacao(c2, _var_fii_rs, _var_fii_pct)
        _yield_str = f"{yield_mensal:.2f}%".replace('.', ',') if yield_mensal else "—"
        _label_mes = f"{meses_pt3[mes_ref_f]}/{ano_ref_f}"
        c3.metric(f"dividendos — {_label_mes}", formatar_brl(div_total))
        c4.metric(f"yield — {_label_mes}", _yield_str)
        c5.metric("dividendos recebidos (total)", abreviar_rs(_total_divs))

        st.markdown("---")

        # ── linha 2: tijolo vs papel com CDI/IPCA fundido ───────────────────
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

        c1, c2 = st.columns(2)
        for _, r in resumo_tipo.sort_values('Total Atual', ascending=False).iterrows():
            pct  = r['Total Atual'] / total_fii * 100 if total_fii > 0 else 0
            col  = c1 if r['tipo_fii'] == 'tijolo' else c2
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
        st.plotly_chart(fig_fii_bar, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False})

        st.markdown("---")

        # calcular preço médio por FII dos lançamentos
        lanc_df = _df_lanc_raw
        pm_fii = {}
        if not lanc_df.empty:
            for t in df_fii['Ativo']:
                compras = lanc_df[(lanc_df['ativo'] == t) & (lanc_df['tipo'] == 'compra')]
                if not compras.empty:
                    total_c = (compras['quantidade'] * compras['preco_unitario']).sum()
                    qtd_c   = compras['quantidade'].sum()
                    pm_fii[t] = total_c / qtd_c if qtd_c > 0 else 0

        # tabela detalhada (no final)
        linhas_fii = []
        for _, row in df_fii.iterrows():
            t        = row['Ativo']
            info     = FII_INFO.get(t, {'tipo': '?', 'indexador': None})
            preco    = row['preco_unit']
            pm       = pm_fii.get(t, None)
            div_info = div_detalhe.get(t, {})
            div_cota = div_info.get('por_cota', 0.0)
            # YoC = div/cota ÷ preço médio de aquisição (yield on cost)
            yoc_m = (div_cota / pm * 100) if pm and pm > 0 and div_cota > 0 else None
            yoc_a = yoc_m * 12 if yoc_m else None
            linhas_fii.append({
                'ativo':      t,
                'tipo':       info['tipo'],
                'indexador':  info['indexador'] if info['tipo'] == 'papel' and info['indexador'] else '—',
                'qtd':        int(row['Qtd']),
                'preço médio': pm,
                'preço atual': preco,
                'total':      row['Total Atual'],
                'part. %':    row['Part. %'],
                'div/cota':   div_cota if div_cota > 0 else None,
                'YoC mensal': yoc_m,
                'YoC anual':  yoc_a,
            })

        df_fii_num = pd.DataFrame(linhas_fii).sort_values('total', ascending=False)
        df_fii_fmt = df_fii_num.copy()
        df_fii_fmt['preço médio']  = df_fii_fmt['preço médio'].apply(lambda x: formatar_brl(x) if x else '—')
        df_fii_fmt['preço atual']  = df_fii_fmt['preço atual'].apply(formatar_brl)
        df_fii_fmt['total']        = df_fii_fmt['total'].apply(formatar_brl)
        df_fii_fmt['part. %']      = df_fii_fmt['part. %'].apply(lambda x: f"{x:.2f}%".replace('.', ','))
        df_fii_fmt['div/cota']     = df_fii_fmt['div/cota'].apply(lambda x: formatar_brl(x) if x else '—')
        df_fii_fmt['YoC mensal']   = df_fii_fmt['YoC mensal'].apply(lambda x: f"{x:.2f}%".replace('.', ',') if x else '—')
        df_fii_fmt['YoC anual']    = df_fii_fmt['YoC anual'].apply(lambda x: fmt_pct(x) if x else '—')
        df_fii_fmt['qtd']          = df_fii_fmt['qtd'].apply(str)

        with st.expander("ver tabela de FIIs", expanded=False):
            cfg_fii = {c: st.column_config.TextColumn(c, alignment="center") for c in df_fii_fmt.columns}
            st.dataframe(df_fii_fmt, use_container_width=True, hide_index=True, column_config=cfg_fii)

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

        def holding_ponderado_meses(ativo, df_lanc):
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

        # holding médio ponderado da classe
        _holding_classe = 0.0
        for _, row in df_etf.iterrows():
            _h = holding_ponderado_meses(row['Ativo'], _df_lanc_raw)
            if _h and total_inv_etf > 0:
                _holding_classe += (_h * row['custo_total'] / total_inv_etf)

        # ── linha 1: resumo da classe + donut ────────────────────────────────
        c1, c2, c3 = st.columns(3)
        _pct_etf_carteira = total_etf / total_geral * 100 if total_geral > 0 else 0
        c1.metric(f"total ETFs  ·  {abreviar_rs(total_etf)}", fmt_pct(_pct_etf_carteira))
        card_valorizacao(c2, var_etf_rs, var_etf_pct)
        c3.metric("holding médio (classe)", f"{round(_holding_classe, 1):.1f}".replace('.', ',') + " meses" if _holding_classe > 0 else "—")



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
        st.plotly_chart(fig_etf_bar, use_container_width=True,
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

            c1, c2, c3, c4, c5 = st.columns(5)
            _qtd_str = str(int(qtd)) if qtd == int(qtd) else f"{qtd:.2f}".replace('.', ',')
            c1.metric("ativo", ativo)
            c2.metric(f"preço  ·  (~{formatar_brl(pm)})", formatar_brl(preco))
            card_valorizacao(c3, var_rs, var_pct_e)
            c4.metric(f"total  ·  ({_qtd_str})", abreviar_rs(total_atual))
            c5.metric("holding ponderado", fmt_holding(holding))

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

        _btc_qtd_str  = f"{qtd_btc:.4f}".replace('.', ',')
        _btc_holding  = holding_ponderado_meses('BTC', _df_lanc_raw)
        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("ativo", "BTC")
        c2.metric(f"preço  ·  (~{abreviar_rs(_btc_pm)})", abreviar_rs(preco_btc_atual))
        card_valorizacao(c3, _btc_var_rs, _btc_var_pct)
        c4.metric(f"total  ·  ({_btc_qtd_str})", abreviar_rs(total_btc))
        c5.metric("holding ponderado", fmt_holding(_btc_holding))

        st.markdown("---")

        c1, c2, c3, c4, c5, c6 = st.columns(6)
        for col, label, v in [
            (c1, "hoje",    var_1d),
            (c2, "7 dias",  var_7d),
            (c3, "30 dias", var_30d),
            (c4, "6 meses", var_6m),
            (c5, "1 ano",   var_1a),
            (c6, "5 anos",  var_5a),
        ]:
            if v is None:
                cor, texto = "#888888", "—"
            elif v >= 0:
                cor, texto = "#22c55e", f"+{fmt_pct(v)}".replace('.', ',')
            else:
                cor, texto = "#ef4444", f"{fmt_pct(v)}".replace('.', ',')
            col.markdown(
                f"<div style='font-size:0.78rem;color:#aaa;margin-bottom:4px;font-family:inherit'>{label}</div>"
                f"<div style='font-size:1.6rem;font-weight:700;color:{cor};font-family:inherit'>{texto}</div>",
                unsafe_allow_html=True
            )

        st.markdown("---")
        if hist is not None and not hist.empty:
            st.subheader("últimos 12 meses")
            corte = hist.index.max() - pd.DateOffset(days=365)
            hist_1a = hist[hist.index >= corte]
            fig_btc = go.Figure()
            fig_btc.add_trace(go.Scatter(
                x=hist_1a.index, y=hist_1a.values,
                mode="lines",
                line=dict(color="#F7931A", width=2),
                hovertemplate="%{x|%d/%m/%Y}<br>R$ %{y:,.0f}<extra></extra>"
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
            st.plotly_chart(fig_btc, use_container_width=True, config={"displayModeBar": False, "scrollZoom": False})
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

            _qtd_fmt    = f"{qtd:.2f}".replace(".", ",") if qtd != int(qtd) else str(int(qtd))
            _pm_fmt     = formatar_brl(pm) if pm > 0 else "—"
            _td_holding = holding_ponderado_meses(ativo, _df_lanc_raw)
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric("ativo", ativo)
            c2.metric(f"preço  ·  (~{_pm_fmt})", formatar_brl(preco_atual))
            if valorizacao is not None and valorizacao_pct is not None:
                card_valorizacao(c3, valorizacao, valorizacao_pct)
            else:
                c3.metric("valorização", "—")
            c4.metric(f"total  ·  ({_qtd_fmt})", abreviar_rs(total_atual))
            c5.metric("holding ponderado", fmt_holding(_td_holding))

            if 'preco_renda_auto' in st.session_state:
                st.caption(f"preço obtido automaticamente — referência: {st.session_state.get('data_renda_auto','')}")
            elif 'preco_renda_erro' in st.session_state:
                st.caption(f"preço manual (secrets) — API: {st.session_state.get('preco_renda_erro','')}")

    # ══════════════════════════════════════════════════════════════════════════
    # SUB-ABA: CARTEIRA
    # ══════════════════════════════════════════════════════════════════════════
    with sub_resumo:
        # ── linha 1: exposição geográfica ─────────────────────────────────────
        GEO_FLAG = {'Brasil': '🇧🇷', 'EUA': '🇺🇸', 'China': '🇨🇳', 'Global (cripto)': '🌍'}
        GEO_ETF  = {'IVVB11': 'EUA', 'DIVO11': 'Brasil', 'PKIN11': 'China', 'LFTB11': 'Brasil'}
        geo_totais = {}
        for _, row in df[df['Classe'] == 'ETF'].iterrows():
            pais = GEO_ETF.get(row['Ativo'], 'Brasil')
            geo_totais[pais] = geo_totais.get(pais, 0) + row['Total Atual']
        geo_totais['Brasil'] = geo_totais.get('Brasil', 0) \
            + df[df['Classe'] == 'FII']['Total Atual'].sum() \
            + df[df['Classe'] == 'Tesouro Direto']['Total Atual'].sum()
        geo_totais['Global (cripto)'] = df[df['Classe'] == 'Cripto']['Total Atual'].sum()
        geo_sorted = sorted(geo_totais.items(), key=lambda x: -x[1])
        cols_geo = st.columns(len(geo_sorted))
        for i, (pais, val) in enumerate(geo_sorted):
            pct   = val / total_geral * 100 if total_geral > 0 else 0
            flag  = GEO_FLAG.get(pais, '')
            val_k = abreviar_rs(val)
            cols_geo[i].metric(f"{flag}  ·  {val_k}", f"{fmt_pct(pct)}".replace('.', ','))

        st.markdown("---")

        # ── linha 2: renda fixa vs variável ──────────────────────────────────
        # LFTB11 é ETF de renda fixa (replica Tesouro Selic) — vai para RF
        _etfs_rf = ['LFTB11']
        total_rf = df[df['Classe'] == 'Tesouro Direto']['Total Atual'].sum() + \
                   df[df['Ativo'].isin(_etfs_rf)]['Total Atual'].sum()
        total_rv = df[(df['Classe'].isin(['ETF','FII','Cripto'])) & (~df['Ativo'].isin(_etfs_rf))]['Total Atual'].sum()
        pct_rf   = total_rf / total_geral * 100 if total_geral > 0 else 0
        pct_rv   = total_rv / total_geral * 100 if total_geral > 0 else 0
        c1, c2 = st.columns(2)
        c1.metric(f"renda fixa  ·  {abreviar_rs(total_rf)}", f"{fmt_pct(pct_rf)}")
        c2.metric(f"renda variável  ·  {abreviar_rs(total_rv)}", f"{fmt_pct(pct_rv)}")

        st.markdown("---")

        # ── linha 3: CDI vs IPCA ──────────────────────────────────────────────
        # CDI = LFTB11 + FIIs papel CDI
        # IPCA = Renda+ 2050 + FIIs papel IPCA
        _df_fii_idx = df[df['Classe'] == 'FII'].copy()
        _df_fii_idx['indexador'] = _df_fii_idx['Ativo'].map(
            lambda t: FII_INFO.get(t, {}).get('indexador'))

        total_cdi  = df[df['Ativo'] == 'LFTB11']['Total Atual'].sum() + \
                     _df_fii_idx[_df_fii_idx['indexador'] == 'CDI']['Total Atual'].sum()
        total_ipca = df[df['Ativo'] == 'Renda+ 2050']['Total Atual'].sum() + \
                     _df_fii_idx[_df_fii_idx['indexador'] == 'IPCA']['Total Atual'].sum()
        pct_cdi    = total_cdi  / total_geral * 100 if total_geral > 0 else 0
        pct_ipca   = total_ipca / total_geral * 100 if total_geral > 0 else 0

        c1, c2 = st.columns(2)
        c1.metric(f"CDI  ·  {abreviar_rs(total_cdi)}", fmt_pct(pct_cdi))
        c2.metric(f"IPCA+  ·  {abreviar_rs(total_ipca)}", fmt_pct(pct_ipca))

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
        _max_pct   = df_ativo_sorted['Part. %'].max()
        _step      = 5
        _ult_tick  = (int(_max_pct // _step)) * _step
        _x_max     = (_ult_tick + _step) if _max_pct >= _ult_tick * 0.9 else _ult_tick
        fig_ativo.update_layout(
            height=max(300, len(df_ativo_sorted) * 28),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False, dragmode=False,
            xaxis=dict(showgrid=True, gridcolor='#333', range=[0, _x_max * 1.15],
                       ticksuffix='%', dtick=_step, fixedrange=True),
            yaxis=dict(showgrid=False, tickfont=dict(size=11), fixedrange=True),
            bargap=0.25, margin=dict(t=10, b=10, l=10, r=60)
        )
        st.plotly_chart(fig_ativo, use_container_width=True,
                        config={"displayModeBar": False, "scrollZoom": False})

        st.markdown("---")

        # ── tabela geral de todos os ativos ──────────────────────────────────
        with st.expander("ver todos os ativos", expanded=False):
            def fmt_preco(row):
                if row['Ativo'] == 'BTC':
                    return abreviar_rs(row['preco_unit'])
                s = f"{row['preco_unit']:,.2f}".replace(',','X').replace('.',',').replace('X','.')
                return f"R$ {s}"

            df_view = df.copy().sort_values('Total Atual', ascending=False)
            df_view['variacao_rs']  = df_view['Total Atual'] - df_view['custo_total']
            df_view['variacao_pct'] = df_view.apply(
                lambda r: (r['variacao_rs'] / r['custo_total'] * 100) if r['custo_total'] > 0 else 0, axis=1
            )
            df_geral_fmt = pd.DataFrame({
                'ativo':           df_view['Ativo'].values,
                'classe':          df_view['Classe'].values,
                'qtd':             df_view.apply(lambda r: (
                    f"{float(r['Qtd']):.6f}".replace('.',',') if float(r['Qtd']) < 1
                    else f"{float(r['Qtd']):.2f}".replace('.',',') if r['Classe'] == 'Tesouro Direto'
                    else str(int(float(r['Qtd'])))
                ), axis=1).values,
                'preço médio':     df_view['preco_medio'].apply(formatar_brl).values,
                'total investido': df_view['custo_total'].apply(formatar_brl).values,
                'preço atual':     df_view.apply(fmt_preco, axis=1).values,
                'total atual':     df_view['Total Atual'].apply(formatar_brl).values,
                'variação R$':     df_view['variacao_rs'].apply(
                    lambda x: f"+{formatar_brl(x)}" if x >= 0 else f"−{formatar_brl(abs(x))}"
                ).values,
                'variação %':      df_view['variacao_pct'].apply(
                    lambda x: f"{'+' if x >= 0 else ''}{fmt_pct(x)}".replace('.', ',')
                ).values,
                'part. %':         df_view['Part. %'].apply(lambda x: f"{x:.2f}%".replace('.',',')).values,
            })
            cfg_geral = {c: st.column_config.TextColumn(c, alignment="center") for c in df_geral_fmt.columns}
            st.dataframe(df_geral_fmt, use_container_width=True, hide_index=True, column_config=cfg_geral)

        st.markdown("---")


        # ── alocação por classe ───────────────────────────────────────────────
        st.subheader("alocação por classe")
        linhas_resumo = []
        for cls, alvo in ALVO_CLASSE.items():
            total_cls = df[df['Classe'] == cls]['Total Atual'].sum()
            atual_pct = total_cls / total_geral * 100 if total_geral > 0 else 0
            desvio    = atual_pct - alvo
            semaforo  = "🟡" if abs(desvio) < 2 else ("🔴" if desvio < 0 else "🟢")
            linhas_resumo.append({
                'classe':  cls,
                'alvo':    f"{fmt_pct(alvo)}".replace('.', ','),
                'atual':   f"{fmt_pct(atual_pct)}".replace('.', ','),
                'desvio':  f"{'+' if desvio >= 0 else ''}{fmt_pct(desvio)}".replace('.', ','),
                'status':  semaforo,
                'total':   formatar_brl(total_cls),
            })
        df_resumo_view = pd.DataFrame(linhas_resumo)
        cfg_res = {c: st.column_config.TextColumn(c, alignment="center") for c in df_resumo_view.columns}
        st.dataframe(df_resumo_view, use_container_width=True, hide_index=True, column_config=cfg_res)

# ── Aba lancamentos ────────────────────────────────────────────────────────────
with aba_lanc:

    _opcoes = []
    for t in sorted(MINHA_CARTEIRA.get('ETF', {}).keys()):
        _opcoes.append((t, 'ETF'))
    for t in sorted(MINHA_CARTEIRA.get('FII', {}).keys()):
        _opcoes.append((t, 'FII'))
    _opcoes.append(('BTC', 'Cripto'))
    _opcoes.append(('Renda+ 2050', 'Tesouro Direto'))
    _nomes = [t for t, _ in _opcoes]

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
                if st.button("+ novo aporte", type="primary", use_container_width=True):
                    st.session_state["abrir_form_aporte"] = True
                    st.rerun(scope="fragment")
        else:
            with st.container(border=True):
                c1, c2, c3, c4, c5, c6 = st.columns([1.1, 0.7, 1.5, 0.9, 1.1, 0.9])
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
                    if st.button("salvar", type="primary", use_container_width=True):
                        if f_qtd > 0 and f_preco > 0:
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
        st.subheader("histórico")
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

        cols_show = ["#", "data", "tipo", "ativo", "classe", "quantidade", "preco_unitario", "total"]
        cfg_hist  = {c: st.column_config.TextColumn(c, alignment="center") for c in cols_show}
        st.dataframe(df_hist_fmt[cols_show], use_container_width=True,
                     hide_index=True, column_config=cfg_hist)

        st.markdown("---")

        # ── excluir ──────────────────────────────────────────────────────────
        with st.expander("excluir lançamento"):
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

        st.markdown("---")

        # ── preço médio por ativo ─────────────────────────────────────────────
        st.subheader("preço médio por ativo")
        saldo_ativo = df_lanc.groupby("ativo").apply(
            lambda g: (g["quantidade"] * g["sinal"]).sum()
        ).reset_index()
        saldo_ativo.columns = ["ativo", "saldo"]
        ativos_ativos = saldo_ativo[saldo_ativo["saldo"] > 0.001]["ativo"].tolist()

        rows_pm = []
        for ativo in sorted(ativos_ativos):
            compras_a = df_lanc[(df_lanc['ativo'] == ativo) & (df_lanc['tipo'] == 'compra')]
            if not compras_a.empty:
                tot_c = (compras_a['quantidade'] * compras_a['preco_unitario']).sum()
                qtd_c = compras_a['quantidade'].sum()
                rows_pm.append({
                    'ativo': ativo,
                    'total investido': tot_c,
                    'qtd comprada': qtd_c,
                    'preco medio': tot_c / qtd_c if qtd_c > 0 else 0
                })

        if rows_pm:
            pm_fmt = pd.DataFrame(rows_pm)
            pm_fmt['total investido'] = pm_fmt['total investido'].apply(formatar_brl)
            pm_fmt['qtd comprada']    = pm_fmt['qtd comprada'].apply(
                lambda x: f"{x:.8f}".rstrip('0').rstrip('.').replace('.', ',') if x < 1
                else f"{x:g}".replace('.', ',')
            )
            pm_fmt['preco medio'] = pm_fmt['preco medio'].apply(formatar_brl)
            cfg_pm = {c: st.column_config.TextColumn(c, alignment="center") for c in pm_fmt.columns}
            st.dataframe(pm_fmt, use_container_width=True, hide_index=True, column_config=cfg_pm)

    aba_lancamentos_fragment()


# ── Aba configurações ─────────────────────────────────────────────────────────
with aba_config:
    _ativos_cfg = sorted(_posicao['ativo'].tolist()) if not _posicao.empty else []
    _fiis_cfg   = [a for a in _ativos_cfg if a in FII_INFO]
    _etfs_cfg   = [a for a in _ativos_cfg if a in ['IVVB11','DIVO11','PKIN11','LFTB11']]
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
        st.caption(f"{_cor_r} soma dos alvos: **{_soma_total_r:.1f}%**")
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
                    st.error(f"soma dos alvos: {_soma_alvos:.1f}% — ajuste para fechar em 100%")
                else:
                    if salvar_configuracoes(_cfg_nova):
                        st.session_state["cfg_alvos"] = _cfg_nova
                        st.success("configurações salvas.")
                        st.rerun(scope="app")
