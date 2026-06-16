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

            alias_inv = {v: k for k, v in ALIAS.items()}
            nomes = [fii, fii_norm] + ([alias_inv[fii_norm]] if fii_norm in alias_inv else [])

            for data_ex, val_cota in divs_ex.items():
                ops = df_lanc[
                    (df_lanc['Ativo'].isin(nomes)) &
                    (df_lanc['data_dt'] <= data_ex)
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

SHEET_ID  = st.secrets["google_sheets"]["spreadsheet_id"]
SHEET_TAB = "lancamentos"
HEADERS   = ["data", "tipo", "ativo", "classe", "quantidade", "preco_unitario", "total"]

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
    import time; time.sleep(1)
    st.session_state["_lanc_versao"] = st.session_state.get("_lanc_versao", 0) + 1

def deletar_lancamento(idx_linha_sheet: int):
    svc = get_sheets_service()
    start = idx_linha_sheet - 1
    body = {"requests": [{"deleteDimension": {"range": {
        "sheetId": 0, "dimension": "ROWS",
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

    _sinal = "▲" if _var_val >= 0 else "▼"
    _cor   = "#22c55e" if _var_val >= 0 else "#ef4444"
    _pct_fmt = f"{_var_pct:+.1f}%".replace('.', ',')
    _rs_fmt  = formatar_brl(abs(_var_val))
    c2.markdown(
        f"<div style='padding-top:8px'>"
        f"<div style='font-size:0.78rem;color:#aaa;margin-bottom:4px'>vs total investido  ·  {formatar_brl(_custo_total)}</div>"
        f"<div style='font-size:1.15rem;font-weight:700;color:{_cor};font-family:inherit'>"
        f"{_sinal} {_pct_fmt}  ·  {_rs_fmt}</div></div>",
        unsafe_allow_html=True
    )

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

    # ── linha 2: barras horizontais por ativo ────────────────────────────────
    col_barras, = st.columns([1])

    with col_barras:
        df_ativo_sorted = df_ativo.sort_values('Part. %', ascending=True)

        hover_barras = [
            f"<b>{row['Ativo']}</b><br>{str(round(row['Part. %'], 2)).replace('.', ',')}%<br>{formatar_brl(row['Total Atual'])}"
            for _, row in df_ativo_sorted.iterrows()
        ]

        fig_ativo = go.Figure()
        fig_ativo.add_trace(go.Bar(
            x=df_ativo_sorted['Part. %'],
            y=df_ativo_sorted['Ativo'],
            orientation='h',
            marker_color='#1E88E5',
            text=df_ativo_sorted['Part. %'].apply(lambda v: f"{fmt_pct(v)}".replace('.', ',')),
            textposition='outside',
            textfont=dict(size=10, color='white'),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hover_barras,
        ))
        max_pct = df_ativo_sorted['Part. %'].max()
        # ticks a cada 5%; só incluir o próximo nível se o máximo ultrapassar o atual
        _step = 5
        _ultimo_tick = (int(max_pct // _step)) * _step
        _proximo     = _ultimo_tick + _step
        # mostrar próximo nível só se barra está dentro de 90% do limite
        x_max = _proximo if max_pct >= _ultimo_tick * 0.9 else _ultimo_tick
        x_max_plot = x_max * 1.15  # espaço para o label fora da barra
        fig_ativo.update_layout(
            height=max(300, len(df_ativo_sorted) * 28),
            plot_bgcolor='rgba(0,0,0,0)', paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            xaxis=dict(
                showgrid=True, gridcolor='#333',
                range=[0, x_max_plot],
                ticksuffix='%',
                dtick=_step,
            ),
            yaxis=dict(showgrid=False, tickfont=dict(size=11)),
            bargap=0.25,
            margin=dict(t=10, b=10, l=10, r=60)
        )
        st.plotly_chart(fig_ativo, use_container_width=True, config={"displayModeBar": False})

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
        yield_corrente = (div_total / total_fii * 100) if total_fii > 0 and div_total > 0 else None

        c1, c2, c3 = st.columns(3)
        c1.metric("total FIIs", total_fii_k)
        c2.metric(f"dividendos — {meses_pt3[mes_ref_f]}/{ano_ref_f}", formatar_brl(div_total))
        if yield_corrente:
            c3.metric("yield corrente", f"{yield_corrente:.2f}%".replace('.', ','))
        else:
            c3.metric("yield corrente", "—")

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
        df_fii_donut = df_fii.sort_values('Total Atual', ascending=False)
        total_fii_donut = df_fii_donut['Total Atual'].sum()
        hover_fii = [
            f"<b>{row['Ativo']}</b><br>{fmt_pct(row['Total Atual']/total_fii_donut*100)}<br>{formatar_brl(row['Total Atual'])}".replace('.', ',')
            for _, row in df_fii_donut.iterrows()
        ]
        fig_fii_donut = go.Figure(go.Pie(
            labels=df_fii_donut['Ativo'].tolist(),
            values=df_fii_donut['Total Atual'].tolist(),
            hole=0.6,
            textinfo='label+percent',
            textfont=dict(size=11),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hover_fii,
            marker=dict(colors=px.colors.sequential.Blues_r[:len(df_fii_donut)]),
        ))
        fig_fii_donut.update_layout(
            height=320, showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=20, b=20, l=20, r=20)
        )
        st.plotly_chart(fig_fii_donut, use_container_width=True)

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
            yield_m  = (div_cota / preco * 100) if preco > 0 and div_cota > 0 else None
            yield_a  = ((1 + yield_m/100)**12 - 1)*100 if yield_m else None
            linhas_fii.append({
                'ativo':        t,
                'tipo':         info['tipo'],
                'indexador':    info['indexador'] if info['tipo'] == 'papel' and info['indexador'] else '—',
                'qtd':          int(row['Qtd']),
                'preço médio':  pm,
                'preço atual':  preco,
                'total':        row['Total Atual'],
                'part. %':      row['Part. %'],
                'div/cota':     div_cota if div_cota > 0 else None,
                'yield mensal': yield_m,
                'yield anual':  yield_a,
            })

        df_fii_num = pd.DataFrame(linhas_fii).sort_values('total', ascending=False)
        df_fii_fmt = df_fii_num.copy()
        df_fii_fmt['preço médio']  = df_fii_fmt['preço médio'].apply(lambda x: formatar_brl(x) if x else '—')
        df_fii_fmt['preço atual']  = df_fii_fmt['preço atual'].apply(formatar_brl)
        df_fii_fmt['total']        = df_fii_fmt['total'].apply(formatar_brl)
        df_fii_fmt['part. %']      = df_fii_fmt['part. %'].apply(lambda x: f"{x:.2f}%".replace('.', ','))
        df_fii_fmt['div/cota']     = df_fii_fmt['div/cota'].apply(lambda x: formatar_brl(x) if x else '—')
        df_fii_fmt['yield mensal'] = df_fii_fmt['yield mensal'].apply(lambda x: f"{x:.2f}%".replace('.', ',') if x else '—')
        df_fii_fmt['yield anual']  = df_fii_fmt['yield anual'].apply(lambda x: f"{fmt_pct(x)}".replace('.', ',') if x else '—')
        df_fii_fmt['qtd']          = df_fii_fmt['qtd'].apply(str)

        cfg_fii = {c: st.column_config.TextColumn(c, alignment="center") for c in df_fii_fmt.columns}
        st.dataframe(df_fii_fmt, use_container_width=True, hide_index=True, column_config=cfg_fii)

    # ══════════════════════════════════════════════════════════════════════════
    # SUB-ABA: ETFs
    # ══════════════════════════════════════════════════════════════════════════
    with sub_etfs:
        df_etf = df[df['Classe'] == 'ETF'].copy()
        total_etf = df_etf['Total Atual'].sum()
        df_etf['part_classe_%'] = df_etf['Total Atual'] / total_etf * 100
        df_etf_sorted = df_etf.sort_values('Total Atual', ascending=False)

        df_etf_view = pd.DataFrame({
            'ativo':          df_etf_sorted['Ativo'].values,
            'qtd':            df_etf_sorted['Qtd'].apply(lambda x: str(int(x))).values,
            'preço':          df_etf_sorted['preco_unit'].apply(formatar_brl).values,
            'total':          df_etf_sorted['Total Atual'].apply(formatar_brl).values,
            'part. carteira': df_etf_sorted['Part. %'].apply(lambda x: f"{x:.2f}%".replace('.', ',')).values,
            'part. ETFs':     df_etf_sorted['part_classe_%'].apply(lambda x: f"{fmt_pct(x)}".replace('.', ',')).values,
        })
        cfg_etf = {c: st.column_config.TextColumn(c, alignment="center") for c in df_etf_view.columns}
        st.dataframe(df_etf_view, use_container_width=True, hide_index=True, column_config=cfg_etf)

        st.markdown("---")
        st.subheader("distribuição dentro da classe")
        hover_etf = [
            f"<b>{row['Ativo']}</b><br>{fmt_pct(row['Total Atual']/total_etf*100)}<br>{formatar_brl(row['Total Atual'])}"
            for _, row in df_etf.iterrows()
        ]
        fig_etf_donut = go.Figure(go.Pie(
            labels=df_etf['Ativo'].tolist(),
            values=df_etf['Total Atual'].tolist(),
            hole=0.6,
            textinfo='label+percent',
            textfont=dict(size=11),
            hovertemplate='%{customdata}<extra></extra>',
            customdata=hover_etf,
            marker=dict(colors=px.colors.sequential.Blues_r[:len(df_etf)]),
        ))
        fig_etf_donut.update_layout(
            height=320, showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
            margin=dict(t=20, b=20, l=20, r=20)
        )
        st.plotly_chart(fig_etf_donut, use_container_width=True)
        st.info("⚙️ % alvo por ativo será configurado na aba **configurações** — desvios aparecerão aqui quando disponível.", icon="ℹ️")

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

        c1, c2, c3 = st.columns(3)
        c1.metric("quantidade", f"{qtd_btc:.4f}".replace('.', ',') + " BTC")
        c2.metric("preço atual", abreviar_rs(preco_btc_atual))
        c3.metric("total na carteira", abreviar_rs(total_btc))

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
                height=280,
                paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
                showlegend=False,
                xaxis=dict(showgrid=False),
                yaxis=dict(showgrid=True, gridcolor="#333"),
                margin=dict(t=10, b=10, l=10, r=10)
            )
            st.plotly_chart(fig_btc, use_container_width=True)
            st.caption(f"fonte: {hist_fonte}")
        else:
            st.warning("histórico de preços indisponível — coingecko e yfinance não retornaram dados.")

    # ══════════════════════════════════════════════════════════════════════════
    # SUB-ABA: TESOURO
    # ══════════════════════════════════════════════════════════════════════════
    with sub_tesouro:
        df_td = df[df['Classe'] == 'Tesouro Direto'].copy()
        st.subheader("tesouro direto")

        lanc_all = _df_lanc_raw
        for _, row in df_td.iterrows():
            ativo       = row['Ativo']
            qtd         = int(row['Qtd'])
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

            c1, c2, c3, c4 = st.columns(4)
            c1.metric("ativo",               ativo)
            c2.metric("quantidade (títulos)", str(qtd))
            c3.metric("preço atual (PU)",     formatar_brl(preco_atual))
            c4.metric("total atual (venda)",  formatar_brl(total_atual))

            c5, c6, c7 = st.columns(3)
            c5.metric("total investido",  formatar_brl(total_investido) if total_investido > 0 else "—")
            c6.metric("preço médio pago", formatar_brl(pm) if pm > 0 else "—")
            if valorizacao is not None:
                sinal = "+" if valorizacao >= 0 else ""
                c7.metric("valorização mark-to-market", formatar_brl(valorizacao),
                           f"{sinal}{fmt_pct(valorizacao_pct)}".replace('.', ','),
                           delta_color="normal" if valorizacao >= 0 else "inverse")
            else:
                c7.metric("valorização mark-to-market", "—")

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
        c1.metric(f"renda fixa  ·  {abreviar_rs(total_rf)}", f"{fmt_pct(pct_rf)}".replace('.', ','))
        c2.metric(f"renda variável  ·  {abreviar_rs(total_rv)}", f"{fmt_pct(pct_rv)}".replace('.', ','))

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
                'qtd':             df_view.apply(lambda r: f"{r['Qtd']:.6f}".replace('.',',') if r['Qtd'] < 1 else str(int(r['Qtd'])), axis=1).values,
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

        st.info("⚙️ % alvo será vinculado à aba **configurações** quando criada. valores abaixo usam alocação padrão da estratégia.", icon="ℹ️")

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
                            st.rerun(scope="fragment")
                            st.session_state["abrir_form_aporte"] = False
                            st.rerun(scope="fragment")
                        else:
                            st.warning("preencha quantidade e preço.")
                with cb:
                    if st.button("✕ cancelar"):
                        st.session_state["abrir_form_aporte"] = False
                        st.rerun(scope="fragment")

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
            # buscar a linha real no Sheets pelo # selecionado
            sel = df_hist[df_hist["#"] == int(idx_del)]
            if not sel.empty:
                row_prev   = sel.iloc[0]
                pos_sheet  = int(row_prev["_sheet_row"])
                st.caption(f"selecionado: {row_prev['data']} · {row_prev['ativo']} · {row_prev['tipo']} · qtd {row_prev['quantidade']}")
                st.caption(f"⚙️ debug: linha real no Sheets = {pos_sheet}, startIndex = {pos_sheet - 1}")
                if st.button("excluir", type="secondary"):
                    try:
                        deletar_lancamento(pos_sheet)
                        st.success(f"excluído!")
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


# ── Aba configurações (esqueleto) ─────────────────────────────────────────────
with aba_config:
    st.subheader("⚙️ configurações")
    st.caption("esta aba está em construção.")

    st.markdown("---")
    st.subheader("diagnóstico")
    st.caption(st.session_state.get('_pm_status', 'aguardando...'))
    if '_viur_debug' in st.session_state:
        st.caption(st.session_state['_viur_debug'])

    if not _df_pm.empty:
        meses_unicos = sorted(_df_pm['ano_mes'].unique())
        st.caption(f"meses com preços salvos: {len(meses_unicos)} — de {meses_unicos[0]} a {meses_unicos[-1]}")
        # verificar meses faltantes
        import datetime as _dt_cfg
        _hoje_cfg = _dt_cfg.date.today()
        _data_min = pd.to_datetime(_df_lanc_raw['data'], format='%d/%m/%Y', errors='coerce').min().date()
        _mes_ini  = f"{_data_min.year}-{_data_min.month:02d}"
        _mes_fim  = f"{_hoje_cfg.year}-{(_hoje_cfg.month-1 if _hoje_cfg.month > 1 else 12):02d}"
        _faltando = []
        _a, _m = int(_mes_ini[:4]), int(_mes_ini[5:])
        _af, _mf = int(_mes_fim[:4]), int(_mes_fim[5:])
        while (_a, _m) <= (_af, _mf):
            _mes_str = f"{_a}-{_m:02d}"
            if _mes_str not in meses_unicos:
                _faltando.append(_mes_str)
            _m += 1
            if _m > 12: _m, _a = 1, _a + 1
        if _faltando:
            st.warning(f"meses sem preços: {', '.join(_faltando)}")
        else:
            st.success("todos os meses cobertos ✓")

        with st.expander("ver tabela precos_mensais"):
            st.dataframe(_df_pm, use_container_width=True, hide_index=True)
    else:
        st.warning("precos_mensais vazio")

    st.markdown("---")
    st.markdown("**alocação alvo por classe** *(em breve)*")
    st.markdown("**alocação alvo por ativo** *(em breve)*")
    st.markdown("**meta de aporte mensal** *(em breve)*")
    st.markdown("**metas financeiras** *(em breve)*")
