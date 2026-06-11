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
    </style>
    """, unsafe_allow_html=True)

def obter_precos_b3(tickers_lista):
    tk_formatados = [f"{t.upper()}.SA" for t in tickers_lista]
    try:
        dados = yf.download(tk_formatados, period="5d", group_by='ticker', progress=False, auto_adjust=True, timeout=7)
        return {t.upper(): float(dados[f"{t.upper()}.SA"]['Close'].ffill().iloc[-1]) for t in tickers_lista}
    except:
        return {t.upper(): 100.0 for t in tickers_lista}

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

def obter_preco_renda_mais():
    try:
        # Tesouro Renda+ 2050 via Yahoo Finance
        dados = yf.download("BRENDS2050.SA", period="5d", progress=False, auto_adjust=True, timeout=7)
        if not dados.empty:
            preco = float(dados['Close'].ffill().iloc[-1])
            data  = dados.index[-1].strftime('%d/%m/%Y')
            return preco, data
    except Exception:
        pass
    # fallback: API Tesouro Transparente (lenta, ultimo recurso)
    try:
        csv_url = "https://www.tesourotransparente.gov.br/ckan/dataset/df56aa42-484a-4a59-8184-7676580c81e3/resource/796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
        df_td = pd.read_csv(csv_url, sep=';', decimal=',', encoding='latin1')
        mask = (
            df_td['Tipo Titulo'].str.contains('Renda', case=False, na=False) &
            df_td['Data Vencimento'].str.contains('2050', na=False)
        )
        df_renda = df_td[mask].copy()
        if df_renda.empty:
            return None, 'titulo nao encontrado'
        df_renda['Data Base'] = pd.to_datetime(df_renda['Data Base'], format='%d/%m/%Y', errors='coerce')
        df_renda = df_renda.sort_values('Data Base', ascending=False)
        pu = df_renda.iloc[0]['PU Venda Manha']
        if isinstance(pu, str):
            pu = float(pu.replace('.', '').replace(',', '.'))
        data = df_renda.iloc[0]['Data Base'].strftime('%d/%m/%Y')
        return float(pu), data
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

@st.cache_data(ttl=0)
def obter_preco_renda_mais_cached():
    return obter_preco_renda_mais()

MINHA_CARTEIRA = {
    'ETF': {'IVVB11': 8, 'DIVO11': 27, 'PKIN11': 5, 'LFTB11': 30},
    'FII': {'TRXF11': 25, 'XPML11': 15, 'XPLG11': 22, 'KNRI11': 4, 'BTLG11': 8, 'BTCI11': 177, 'VGIR11': 150, 'MCCI11': 10, 'GARE11': 255, 'RZTR11': 15, 'KNCR11': 2},
    'Cripto': {'BTC': 0.01492559},
    # (qtd, preco_fallback) — preco real vem de st.secrets
    'Tesouro Direto': {'Renda+ 2050': (24, 490.02)}
}

todos_b3 = [t for cls in ['ETF', 'FII'] for t in MINHA_CARTEIRA[cls].keys()]
precos = obter_precos_b3(todos_b3)
precos['BTC'] = obter_preco_btc_brl()

linhas = []
for cls, ativos in MINHA_CARTEIRA.items():
    for t, v in ativos.items():
        if isinstance(v, tuple):
            q = v[0]
            # tentar preco automatico via Tesouro Transparente
            if 'Renda' in t:
                resultado_api = obter_preco_renda_mais_cached()
                if resultado_api and len(resultado_api) == 2 and resultado_api[0] and not isinstance(resultado_api[0], str):
                    prc = resultado_api[0]
                    st.session_state['preco_renda_auto'] = resultado_api[0]
                    st.session_state['data_renda_auto']  = resultado_api[1]
                    st.session_state['preco_renda_erro'] = None
                else:
                    prc = preco_td_de_secrets(t, v[1])
                    erro = resultado_api[1] if resultado_api and len(resultado_api) > 1 else 'retornou None'
                    st.session_state['preco_renda_erro'] = erro
            else:
                prc = preco_td_de_secrets(t, v[1])
        else:
            q   = v
            prc = precos.get(t.upper(), 0.0)
        linhas.append({'Ativo': t, 'Classe': cls, 'preco_unit': prc, 'Qtd': q, 'Total Atual': q * prc})

df = pd.DataFrame(linhas)
total_geral = df['Total Atual'].sum()
df['Part. %'] = (df['Total Atual'] / total_geral) * 100
df_resumo_classe = df.groupby('Classe')['Total Atual'].sum().reset_index()
df_resumo_classe = df_resumo_classe.sort_values('Total Atual', ascending=False).reset_index(drop=True)
df_ativo = df.sort_values(by='Total Atual', ascending=False)

aba_dash, aba_detalhe, aba_lanc, aba_aportes = st.tabs(["dashboard", "detalhe", "lancamentos", "simular novos aportes"])

with aba_dash:
    st.metric("patrimonio total", formatar_brl(total_geral))

    # aviso preco TD
    for cls, ativos in MINHA_CARTEIRA.items():
        for nome, v in ativos.items():
            if isinstance(v, tuple):
                if st.session_state.get('preco_renda_auto'):
                    prc_td  = st.session_state['preco_renda_auto']
                    data_td = st.session_state['data_renda_auto']
                    st.caption(f"preco TD: **{nome}**: {formatar_brl(prc_td)} · {data_td} (automatico)")
                elif st.session_state.get('preco_renda_erro'):
                    st.caption(f"preco TD: **{nome}**: {formatar_brl(v[1])} (fallback — erro API: {st.session_state['preco_renda_erro']})")
                else:
                    st.caption(f"preco TD: **{nome}**: {formatar_brl(preco_td_de_secrets(nome, v[1]))} (secrets)")

    st.markdown('---')

    col_donut, col_barras = st.columns([1, 2])

    with col_donut:
        total_classe = df_resumo_classe['Total Atual'].sum()
        labels_donut = []
        hover_donut  = []
        for _, row in df_resumo_classe.iterrows():
            pct     = row['Total Atual'] / total_classe * 100
            pct_str = f"{pct:.1f}%".replace('.', ',')
            rs_str  = formatar_brl(row['Total Atual'])
            labels_donut.append(f"{row['Classe']}<br>{pct_str}")
            hover_donut.append(f"<b>{row['Classe']}</b><br>{pct_str}<br>{rs_str}")

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
            height=400,
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig_donut, use_container_width=True)

    with col_barras:
        max_pct = df_ativo['Part. %'].max()
        max_rs  = df_ativo['Total Atual'].max()

        y_max_pct, ticks_pct = gerar_ticks_pct(max_pct, step=5)

        # ticks % visiveis: apenas os menores que o maximo real
        ticks_pct_show = [v for v in ticks_pct if v <= max_pct]

        # eixo direito: mesmos pontos do eixo %, convertidos para R$
        # tick_rs = tick_pct / 100 * total_geral  (escala perfeita)
        ticks_rs_labels = [f"R$ {v/100*total_geral:,.0f}".replace(',', '.') for v in ticks_pct_show]

        shapes = []
        for p in ticks_pct_show[1:]:
            shapes.append(dict(
                type='line', xref='paper', x0=0, x1=1,
                yref='y', y0=p, y1=p,
                line=dict(color='rgba(255,255,255,0.08)', width=1, dash='dot')
            ))

        hover_barras = [
            f"<b>{row['Ativo']}</b><br>{str(round(row['Part. %'], 2)).replace('.', ',')}%<br>{formatar_brl(row['Total Atual'])}"
            for _, row in df_ativo.iterrows()
        ]

        fig_ativo = go.Figure()
        fig_ativo.add_trace(
            go.Bar(
                x=df_ativo['Ativo'], y=df_ativo['Part. %'],
                marker_color='#1E88E5',
                text=df_ativo['Ativo'],
                textposition='outside', textangle=-90,
                textfont=dict(size=9, color='white'),
                cliponaxis=False,
                hovertemplate='%{customdata}<extra></extra>',
                customdata=hover_barras,
                yaxis='y'
            )
        )
        # trace invisivel no yaxis2 para forca-lo a aparecer
        fig_ativo.add_trace(
            go.Scatter(
                x=[df_ativo['Ativo'].iloc[0]],
                y=[0],
                mode='markers',
                marker=dict(color='rgba(0,0,0,0)', size=0),
                hoverinfo='skip',
                showlegend=False,
                yaxis='y2'
            )
        )

        fig_ativo.update_layout(
            height=400,
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)',
            showlegend=False,
            shapes=shapes,
            xaxis=dict(showticklabels=False),
            bargap=0.15,
            margin=dict(t=10, b=10, l=10, r=10)
        )
        # eixo esquerdo: part. %
        fig_ativo.update_yaxes(
            title_text="",
            showgrid=True, gridcolor='#333', side='left',
            range=[0, y_max_pct * 1.2],
            tickvals=ticks_pct_show,
            ticktext=[f"{str(v).replace('.', ',')}%" for v in ticks_pct_show]
        )

        # eixo direito: mesmo range e mesmos pontos do eixo %
        # labels convertidos para R$ — escala perfeitamente alinhada
        fig_ativo.update_layout(
            yaxis2=dict(
                overlaying='y',
                side='right',
                showgrid=False,
                range=[0, y_max_pct * 1.2],
                tickvals=ticks_pct_show,
                ticktext=ticks_rs_labels,
                title_text=""
            )
        )
        st.plotly_chart(fig_ativo, use_container_width=True)

with aba_detalhe:
    avisos = []
    for cls, ativos in MINHA_CARTEIRA.items():
        for nome, v in ativos.items():
            if isinstance(v, tuple):
                if 'Renda' in nome and 'preco_renda_auto' in st.session_state:
                    prc_atual  = st.session_state['preco_renda_auto']
                    data_atual = st.session_state['data_renda_auto']
                    avisos.append(f"**{nome}**: {formatar_brl(prc_atual)} · atualizado em {data_atual} (automatico)")
                else:
                    prc_atual  = preco_td_de_secrets(nome, v[1])
                    data_atual = data_td_de_secrets(nome)
                    avisos.append(f"**{nome}**: {formatar_brl(prc_atual)} · atualizado em {data_atual} (manual)")
    if avisos:
        st.caption("preco TD: " + " · ".join(avisos))
    if st.session_state.get('preco_renda_erro'):
        st.caption(f"DEBUG API erro: {st.session_state['preco_renda_erro']}")

    df_display = df.copy()
    df_display['preco_unit']  = df_display['preco_unit'].apply(formatar_brl)
    df_display['Total Atual'] = df_display['Total Atual'].apply(formatar_brl)
    df_display['Part. %']     = df_display['Part. %'].apply(lambda x: f"{x:.2f}%".replace('.', ','))
    df_display['Qtd']         = df_display['Qtd'].apply(lambda x: f"{x:g}".replace('.', ','))

    config = {
        'Ativo':       st.column_config.TextColumn("ativo",          alignment="center"),
        'Classe':      st.column_config.TextColumn("classe",         alignment="center"),
        'preco_unit':  st.column_config.TextColumn("preco unidade",  alignment="center"),
        'Qtd':         st.column_config.TextColumn("qtd",            alignment="center"),
        'Total Atual': st.column_config.TextColumn("total atual",    alignment="center"),
        'Part. %':     st.column_config.TextColumn("part. %",        alignment="center"),
    }
    st.dataframe(df_display, use_container_width=True, hide_index=True, column_config=config)

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

@st.cache_data(ttl=0)
def ler_lancamentos():
    try:
        svc  = get_sheets_service()
        res  = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A:H").execute()
        rows = res.get("values", [])
        if len(rows) <= 1:
            return pd.DataFrame(columns=HEADERS)
        # truncar para len(HEADERS) colunas e preencher faltantes
        # (planilha pode ter colunas extras legadas como observacao)
        n = len(HEADERS)
        padded = [(r + [''] * n)[:n] for r in rows[1:]]
        df_l = pd.DataFrame(padded, columns=HEADERS)
        # normalizar numeros que podem vir em diferentes formatos do Sheets:
        # "1234.56" (EN), "1234,56" (PT virgula decimal), "1.234,56" (PT ponto milhar)
        def normalizar_numero(s):
            s = str(s).strip()
            if s in ('', 'nan', 'None'):
                return None
            s = s.replace('R$', '').replace(' ', '')
            # virgula sem ponto: decimal PT-BR ("9,21" → 9.21)
            if ',' in s and '.' not in s:
                s = s.replace(',', '.')
            # ambos: detectar qual e decimal pelo ultimo
            elif ',' in s and '.' in s:
                if s.rindex(',') > s.rindex('.'):
                    s = s.replace('.', '').replace(',', '.')
                else:
                    s = s.replace(',', '')
            # multiplos pontos: todos sao milhar, ultimo e decimal
            elif s.count('.') > 1:
                parts = s.split('.')
                s = ''.join(parts[:-1]) + '.' + parts[-1]
            try:
                return float(s)
            except:
                return None

        for col in ["quantidade", "preco_unitario", "total"]:
            df_l[col] = df_l[col].apply(normalizar_numero)
            df_l[col] = pd.to_numeric(df_l[col], errors="coerce")


        return df_l
    except Exception as e:
        st.error(f"Erro ao ler planilha: {e}")
        return pd.DataFrame(columns=HEADERS)

def salvar_lancamento(row: list):
    svc = get_sheets_service()
    svc.values().append(
        spreadsheetId=SHEET_ID,
        range=f"{SHEET_TAB}!A:H",
        valueInputOption="USER_ENTERED",
        body={"values": [row]}
    ).execute()
    st.cache_data.clear()

def deletar_lancamento(idx_linha_sheet: int):
    # idx_linha_sheet: 1-based, linha 1 = header
    svc = get_sheets_service()
    body = {"requests": [{"deleteDimension": {"range": {
        "sheetId": 0,
        "dimension": "ROWS",
        "startIndex": idx_linha_sheet,
        "endIndex":   idx_linha_sheet + 1
    }}}]}
    svc.batchUpdate(spreadsheetId=SHEET_ID, body=body).execute()
    st.cache_data.clear()

def garantir_cabecalho():
    try:
        svc = get_sheets_service()
        res = svc.values().get(spreadsheetId=SHEET_ID, range=f"{SHEET_TAB}!A1:H1").execute()
        if not res.get("values"):
            svc.values().update(
                spreadsheetId=SHEET_ID,
                range=f"{SHEET_TAB}!A1",
                valueInputOption="RAW",
                body={"values": [HEADERS]}
            ).execute()
    except:
        pass

garantir_cabecalho()

# ── Aba lancamentos ────────────────────────────────────────────────────────────
with aba_lanc:

    df_lanc = ler_lancamentos()


    if not df_lanc.empty:
        df_lanc["data_dt"] = pd.to_datetime(df_lanc["data"], format="%d/%m/%Y", errors="coerce")
        df_lanc["sinal"]   = df_lanc["tipo"].map({"compra": 1, "venda": -1}).fillna(0)
        df_lanc["valor"]   = df_lanc["total"] * df_lanc["sinal"]

        meses_pt = {
            1: 'janeiro', 2: 'fevereiro', 3: 'marco', 4: 'abril',
            5: 'maio', 6: 'junho', 7: 'julho', 8: 'agosto',
            9: 'setembro', 10: 'outubro', 11: 'novembro', 12: 'dezembro'
        }
        hoje      = pd.Timestamp.today()
        mes_atual = hoje.month
        ano_atual = hoje.year

        # ── Resumo do mes corrente ────────────────────────────────────────────
        df_mes = df_lanc[
            (df_lanc["data_dt"].dt.month == mes_atual) &
            (df_lanc["data_dt"].dt.year  == ano_atual)
        ].copy()
        df_mes["sinal_m"] = df_mes["tipo"].map({"compra": 1, "venda": -1}).fillna(0)
        aporte_mes = (df_mes["total"] * df_mes["sinal_m"]).sum()

        # media dos ultimos 6 meses (excluindo mes atual)
        meses = []
        for i in range(1, 7):
            ref = hoje - pd.DateOffset(months=i)
            df_ref = df_lanc[
                (df_lanc["data_dt"].dt.month == ref.month) &
                (df_lanc["data_dt"].dt.year  == ref.year)
            ].copy()
            df_ref["sinal_r"] = df_ref["tipo"].map({"compra": 1, "venda": -1}).fillna(0)
            val = (df_ref["total"] * df_ref["sinal_r"]).sum()
            meses.append(val)
        media_6m = sum(meses) / 6

        nome_mes = meses_pt[mes_atual]

        col_r1, col_r2, col_r3 = st.columns([1.4, 1, 0.7])
        col_r1.metric(f"total aportado em {nome_mes}", formatar_brl(aporte_mes))
        col_r2.metric("media mensal (6m)", formatar_brl(media_6m))
        with col_r3:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("+ novo aporte", type="primary", use_container_width=True):
                st.session_state["abrir_form_aporte"] = True
        st.markdown("---")

    # ── Formulario de novo lancamento ────────────────────────────────────────
    with st.expander("+ novo aporte", expanded=st.session_state.get("abrir_form_aporte", False)):
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            f_data  = st.date_input("data", value=date.today())
            f_tipo  = st.selectbox("tipo", ["compra", "venda"])
        with col2:
            todos_ativos = sorted(set(
                [t for cls in MINHA_CARTEIRA.values() for t in cls.keys()] +
                ["Tesouro SELIC 2031", "Renda+ 2050"]
            ))
            f_ativo  = st.selectbox("ativo", todos_ativos)
            f_classe = next(
                (cls for cls, atv in MINHA_CARTEIRA.items() for t in atv.keys() if t == f_ativo),
                "Tesouro Direto" if "Tesouro" in f_ativo or "Renda" in f_ativo else "Outro"
            )
            st.text_input("classe", value=f_classe, disabled=True)
        with col3:
            f_qtd   = st.number_input("quantidade", min_value=0.0, step=0.001, format="%.6f")
            f_preco = st.number_input("preco unitario (R$)", min_value=0.0, step=0.01, format="%.2f")
        with col4:
            f_total = f_qtd * f_preco
            st.metric("total", formatar_brl(f_total))


        if st.button("salvar lancamento", type="primary"):
            if f_qtd > 0 and f_preco > 0:
                salvar_lancamento([
                    f_data.strftime("%d/%m/%Y"),
                    f_tipo, f_ativo, f_classe,
                    f_qtd, f_preco, round(f_total, 2)
                ])
                st.session_state["abrir_form_aporte"] = False
                st.success("lancamento salvo!")
                st.rerun()
            else:
                st.warning("preencha quantidade e preco.")

    st.markdown("---")

    if df_lanc.empty:
        st.info("nenhum lancamento registrado ainda.")
    else:
        # ── Historico: mais novo no topo, indice decrescente a partir de 1 ──
        st.subheader("historico")

        df_hist = df_lanc.copy()
        df_hist = df_hist.sort_values("data_dt", ascending=False).reset_index(drop=True)
        n = len(df_hist)
        df_hist.insert(0, "#", range(n, 0, -1))  # indice decrescente, sem 0

        df_hist_fmt = df_hist.copy()
        df_hist_fmt["preco_unitario"] = df_hist_fmt["preco_unitario"].apply(
            lambda x: formatar_brl(x) if pd.notna(x) else "")
        df_hist_fmt["total"] = df_hist_fmt["total"].apply(
            lambda x: formatar_brl(x) if pd.notna(x) else "")
        df_hist_fmt["quantidade"] = df_hist_fmt["quantidade"].apply(
            lambda x: f"{x:g}".replace(".", ",") if pd.notna(x) else "")
        df_hist_fmt["valor"]   = df_hist_fmt["valor"].apply(
            lambda x: formatar_brl(x) if pd.notna(x) else "")

        cols_show = ["#", "data", "tipo", "ativo", "classe", "quantidade", "preco_unitario", "total"]
        cfg_hist  = {c: st.column_config.TextColumn(c, alignment="center") for c in cols_show}
        st.dataframe(
            df_hist_fmt[cols_show],
            use_container_width=True, hide_index=True, column_config=cfg_hist
        )

        st.markdown("---")

        # ── Exclusao por indice ───────────────────────────────────────────────
        with st.expander("excluir lancamento"):
            idx_del = st.number_input(
                "numero # do lancamento (conforme tabela acima)",
                min_value=1, max_value=n, step=1, value=n
            )
            if st.button("excluir", type="secondary"):
                # converter # decrescente para posicao na sheet (crescente)
                # # = n → linha mais antiga = sheet linha 2; # = 1 → linha mais recente
                pos_sheet = (n - idx_del) + 1  # 1-based, pula header
                deletar_lancamento(pos_sheet)
                st.success("lancamento excluido!")
                st.rerun()

        st.markdown("---")

        # ── Preco medio por ativo ────────────────────────────────────────────
        st.subheader("preco medio por ativo")
        compras = df_lanc[df_lanc["tipo"] == "compra"].copy()
        if not compras.empty:
            saldo_ativo = df_lanc.groupby("ativo").apply(
                lambda g: (g["quantidade"] * g["sinal"]).sum()
            ).reset_index()
            saldo_ativo.columns = ["ativo", "saldo"]
            # apenas ativos com saldo positivo (ainda na carteira)
            ativos_ativos = saldo_ativo[saldo_ativo["saldo"] > 0.001]["ativo"].tolist()

            def calc_pm(g):
                c = g[g["tipo"] == "compra"]
                qtd_c = c["quantidade"].sum()
                tot_c = (c["quantidade"] * c["preco_unitario"]).sum()
                return pd.Series({
                    "total investido": tot_c,
                    "qtd comprada":    qtd_c,
                    "preco medio":     tot_c / qtd_c if qtd_c > 0 else 0
                })

            pm = df_lanc[df_lanc["ativo"].isin(ativos_ativos)].groupby("ativo").apply(calc_pm).reset_index()
            pm_fmt = pm.copy()
            pm_fmt["total investido"] = pm_fmt["total investido"].apply(formatar_brl)
            pm_fmt["qtd comprada"]    = pm_fmt["qtd comprada"].apply(lambda x: f"{x:g}".replace(".", ","))
            pm_fmt["preco medio"]     = pm_fmt["preco medio"].apply(formatar_brl)
            cfg_pm = {c: st.column_config.TextColumn(c, alignment="center") for c in pm_fmt.columns}
            st.dataframe(pm_fmt, use_container_width=True, hide_index=True, column_config=cfg_pm)

        st.markdown("---")

        # ── Evolucao do patrimonio investido ─────────────────────────────────
        st.subheader("evolucao do patrimonio investido")
        df_evo = df_lanc.sort_values("data_dt").copy()
        df_evo["sinal_evo"] = df_evo["tipo"].map({"compra": 1, "venda": -1}).fillna(0)
        df_evo["total"]     = pd.to_numeric(df_evo["total"], errors="coerce").fillna(0)
        df_evo["valor_evo"] = df_evo["total"] * df_evo["sinal_evo"]
        # agrupar por data para mostrar saldo liquido do dia
        df_evo = df_evo.groupby("data_dt")["valor_evo"].sum().reset_index()
        df_evo = df_evo.sort_values("data_dt")
        df_evo["acum"] = df_evo["valor_evo"].cumsum()

        fig_evo = go.Figure()
        fig_evo.add_trace(go.Scatter(
            x=df_evo["data_dt"], y=df_evo["acum"],
            mode="lines+markers",
            line=dict(color="#1E88E5", width=2),
            marker=dict(size=5),
            hovertemplate="%{x|%d/%m/%Y}<br>R$ %{y:,.2f}<extra></extra>"
        ))
        fig_evo.update_layout(
            height=300,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            showlegend=False,
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=True, gridcolor="#333")
        )
        st.plotly_chart(fig_evo, use_container_width=True)
