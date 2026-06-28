import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
import os
import datetime

# --- クラウド設定 ---
SHEET_ID = '1oj76xzUj-Z7iBp-eLLc9DZ8fgxpchDM3fuWa-SfEFzk'

# --- Googleスプレッドシート連携関数（ブック全体を取得） ---
def get_spreadsheet():
    scopes = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive'
    ]
    if os.path.exists('key.json'):
        credentials = Credentials.from_service_account_file('key.json', scopes=scopes)
    else:
        credentials = Credentials.from_service_account_info(dict(st.secrets["gcp_service_account"]), scopes=scopes)
    
    gc = gspread.authorize(credentials)
    return gc.open_by_key(SHEET_ID)

# --- 残高データ（1枚目のシート）の読み込み ---
def load_balance_data():
    sh = get_spreadsheet()
    ws = sh.get_worksheet(0) # 1枚目のシートを取得
    data = ws.get_all_records()
    if not data:
        df = pd.DataFrame({
            '媒体': ['口座', 'PayPay', 'マナカ', 'Suica'],
            '残高': [0, 0, 0, 0]
        })
        save_balance_data(df)
        return df
    else:
        df = pd.DataFrame(data)
        df['残高'] = pd.to_numeric(df['残高'], errors='coerce').fillna(0).astype(int)
        return df

# --- 残高データ（1枚目のシート）の保存 ---
def save_balance_data(df):
    sh = get_spreadsheet()
    ws = sh.get_worksheet(0)
    ws.clear() 
    data_to_write = [df.columns.values.tolist()] + df.values.tolist()
    ws.update(data_to_write) 

# --- 支出ログ（2枚目のシート）への追記関数 ---
def append_expense_log(date, category, memo, medium, amount):
    sh = get_spreadsheet()
    
    # 2枚目のシート（インデックス1）を取得。無ければ自動作成する。
    try:
        ws_log = sh.get_worksheet(1)
    except Exception:
        ws_log = sh.add_worksheet(title="支出ログ", rows="1000", cols="5")
        # ヘッダー行を作成
        ws_log.append_row(["日付", "大分類", "小分類・メモ", "支払い媒体", "金額"])
        
    # ログを最下段に追記
    ws_log.append_row([str(date), category, memo, medium, amount])


# ==========================================
# UI 構築
# ==========================================

# --- アプリ起動時にデータ読み込み ---
df_balances = load_balance_data()

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
            save_balance_data(df_balances)
            st.success(f'{selected_medium_inc}に {income_amount:,}円 を足し算しました。')
        else:
            st.warning('収入金額を入力してください。')

st.divider()

# --- 2. 支出の入力セクション（内訳・ログ機能追加） ---
st.header('💸 支出の登録（内訳記録）')
with st.form(key='expense_form'):
    col1, col2 = st.columns(2)
    with col1:
        expense_date = st.date_input('日付', datetime.date.today())
        expense_category = st.selectbox('大分類', ['食費', '交通費', '趣味費', '経費','特定支出','自己投資', 'その他'])
    with col2:
        medium_list = df_balances['媒体'].tolist()
        selected_medium = st.selectbox('支払い媒体を選択', medium_list)
        expense_amount = st.number_input('支出金額（円）', min_value=0, step=100)
    
    expense_memo = st.text_input('小分類・メモ（例: ポケカ新弾、彼女との外食、カメラ関連 など）')
    
    submit_expense = st.form_submit_button(label='支出を登録して残高から引く')

    if submit_expense:
        if expense_amount > 0:
            # 1. 残高から引き算してSheet1を更新
            df_balances.loc[df_balances['媒体'] == selected_medium, '残高'] -= expense_amount
            save_balance_data(df_balances)
            
            # 2. 支出ログをSheet2に追記
            append_expense_log(expense_date, expense_category, expense_memo, selected_medium, expense_amount)
            
            st.success(f'{selected_medium}から {expense_amount:,}円 を引き算し、支出ログに記録しました！')
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
        
        save_balance_data(df_balances)

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
            save_balance_data(df_balances)
            st.success(f'「{old_medium}」を「{new_medium_name}」に変更しました。')

st.divider()

# --- 5. 現在の資産状況（テキスト出力） ---
st.header('📊 現在の資産状況')

total_assets = df_balances['残高'].sum()
st.subheader(f'💰 総資産: {total_assets:,} 円')

st.write('**【各媒体の残高】**')
for index, row in df_balances.iterrows():
    st.text(f"・{row['媒体']}: {row['残高']:,} 円")
