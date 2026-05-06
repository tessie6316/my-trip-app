import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os

# --- クラウド設定 ---
SHEET_ID = '1oj76xzUj-Z7iBp-eLLc9DZ8fgxpchDM3fuWa-SfEFzk'

# --- Googleスプレッドシート連携関数 ---
def get_worksheet():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    # ローカル（Jupyter）とクラウド（Streamlit Cloud）で鍵の読み込み方を変える
    if os.path.exists('key.json'):
        credentials = Credentials.from_service_account_file('key.json', scopes=scopes)
    else:
        # Streamlit Cloud上ではSecrets（安全な金庫）から鍵を読み込む
        credentials = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
    
    gc = gspread.authorize(credentials)
    return gc.open_by_key(SHEET_ID).sheet1

# データの読み込み
def load_data():
    ws = get_worksheet()
    data = ws.get_all_records()
    if not data:
        df = pd.DataFrame({
            '媒体': ['口座', 'PayPay', 'マナカ', 'Suica'],
            '残高': [0, 0, 0, 0]
        })
        save_data(df)
        return df
    else:
        df = pd.DataFrame(data)
        df['残高'] = pd.to_numeric(df['残高'], errors='coerce').fillna(0).astype(int)
        return df

# データの保存
def save_data(df):
    ws = get_worksheet()
    ws.clear() 
    data_to_write = [df.columns.values.tolist()] + df.values.tolist()
    ws.update(data_to_write) 

# --- アプリ起動時にデータ読み込み ---
df_balances = load_data()

st.title('家計簿 ＆ 総資産ダッシュボード')

# --- 1. 収入の入力セクション ---
st.header('👛 収入の登録')
with st.form(key='income_form'):
    medium_list = df_balances['媒体'].tolist()
    selected_medium_inc = st.selectbox('入金媒体を選択', medium_list)
    income_amount = st.number_input('収入金額（円）', min_value=0, step=100, key='income_input')
    
    submit_income = st.form_submit_button(label='収入を足し算する')

    if submit_income:
        if income_amount > 0:
            df_balances.loc[df_balances['媒体'] == selected_medium_inc, '残高'] += income_amount
            save_data(df_balances)
            st.success(f'{selected_medium_inc}に {income_amount:,}円 を足し算しました。')
        else:
            st.warning('収入金額を入力してください。')

st.divider()

# --- 2. 支出の入力セクション ---
st.header('💸 支出の登録')
with st.form(key='expense_form'):
    medium_list = df_balances['媒体'].tolist()
    selected_medium = st.selectbox('支払い媒体を選択', medium_list)
    expense_amount = st.number_input('支出金額（円）', min_value=0, step=100)
    
    submit_expense = st.form_submit_button(label='支出を引き算する')

    if submit_expense:
        if expense_amount > 0:
            df_balances.loc[df_balances['媒体'] == selected_medium, '残高'] -= expense_amount
            save_data(df_balances)
            st.success(f'{selected_medium}から {expense_amount:,}円 を引き算しました。')
        else:
            st.warning('支出金額を入力してください。')

st.divider()

# --- 3. 媒体と残高の登録・更新セクション ---
st.header('🏦 媒体と残高の登録')
with st.form(key='add_medium_form'):
    new_medium = st.text_input('媒体名（例: 口座, PayPay, 楽天Edy など）')
    initial_balance = st.number_input('現在の残高（円）', step=1000)
    
    submit_medium = st.form_submit_button(label='残高を保存する')

    if submit_medium and new_medium:
        if new_medium in df_balances['媒体'].values:
            df_balances.loc[df_balances['媒体'] == new_medium, '残高'] = initial_balance
            st.success(f'{new_medium} の残高を {initial_balance:,}円 に更新しました。')
        else:
            new_row = pd.DataFrame({'媒体': [new_medium], '残高': [initial_balance]})
            df_balances = pd.concat([df_balances, new_row], ignore_index=True)
            st.success(f'新しく {new_medium} を登録しました。')
        
        save_data(df_balances)

st.divider()

# --- 4. 媒体名の編集セクション ---
st.header('✏️ 媒体名の編集')
with st.form(key='edit_medium_form'):
    medium_list = df_balances['媒体'].tolist()
    old_medium = st.selectbox('名前を変更する媒体を選択', medium_list, key='old_medium_select')
    new_medium_name = st.text_input('新しい媒体名')
    
    submit_edit = st.form_submit_button(label='名前を変更する')

    if submit_edit:
        if new_medium_name == "":
            st.warning('新しい媒体名を入力してください。')
        elif new_medium_name in df_balances['媒体'].values:
            st.warning(f'「{new_medium_name}」はすでに存在します。別の名前を入力してください。')
        else:
            df_balances.loc[df_balances['媒体'] == old_medium, '媒体'] = new_medium_name
            save_data(df_balances)
            st.success(f'「{old_medium}」を「{new_medium_name}」に変更しました。')

st.divider()

# --- 5. 現在の資産状況（テキスト出力） ---
st.header('📊 現在の資産状況')

total_assets = df_balances['残高'].sum()
st.subheader(f'💰 総資産: {total_assets:,} 円')

st.write('**【各媒体の残高】**')
for index, row in df_balances.iterrows():
    st.text(f"・{row['媒体']}: {row['残高']:,} 円")
