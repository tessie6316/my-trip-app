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

# --- ログ（2枚目のシート）への追記関数 ---
def append_transaction_log(date, category, memo, medium, amount):
    sh = get_spreadsheet()
    
    # 2枚目のシート（インデックス1）を取得。無ければ自動作成する。
    try:
        ws_log = sh.get_worksheet(1)
    except Exception:
        ws_log = sh.add_worksheet(title="トランザクションログ", rows="1000", cols="5")
        # ヘッダー行を作成
        ws_log.append_row(["日付", "大分類", "小分類・メモ", "対象媒体", "金額"])
        
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
    col1, col2 = st.columns(2)
    with col1:
        income_date = st.date_input('日付', datetime.date.today(), key='income_date')
        medium_list = df_balances['媒体'].tolist()
        selected_medium_inc = st.selectbox('入金媒体を選択', medium_list)
    with col2:
        income_amount = st.number_input('収入金額（円）', min_value=0, step=100, key='income_input')
    
    income_memo = st.text_input('メモ（例: 給与、立替の返済、メルカリ売上 など）')
    submit_income = st.form_submit_button(label='収入を登録して残高に足す')

    if submit_income:
        if income_amount > 0:
            df_balances.loc[df_balances['媒体'] == selected_medium_inc, '残高'] += income_amount
            save_balance_data(df_balances)
            
            # 収入ログを追記
            append_transaction_log(income_date, "収入", income_memo, selected_medium_inc, income_amount)
            
            st.success(f'{selected_medium_inc}に {income_amount:,}円 を足し算し、ログに記録しました！')
        else:
            st.warning('収入金額を入力してください。')

st.divider()

# --- 2. 支出の入力セクション ---
st.header('💸 支出の登録（内訳記録）')
with st.form(key='expense_form'):
    col1, col2 = st.columns(2)
    with col1:
        expense_date = st.date_input('日付', datetime.date.today())
        # あなたがカスタマイズした大分類を適用
        expense_category = st.selectbox('大分類', ['食費', '交通費', '宿泊費','趣味費', '経費','特定支出','自己投資', 'その他'])
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
            append_transaction_log(expense_date, expense_category, expense_memo, selected_medium, expense_amount)
            
            st.success(f'{selected_medium}から {expense_amount:,}円 を引き算し、支出ログに記録しました！')
        else:
            st.warning('支出金額を入力してください。')

st.divider()

# --- 3. 🔄 媒体間の振替セクション ---
st.header('🔄 媒体間の振替（資金移動）')
with st.form(key='transfer_form'):
    col1, col2 = st.columns(2)
    with col1:
        transfer_date = st.date_input('日付', datetime.date.today(), key='transfer_date')
        medium_list = df_balances['媒体'].tolist()
        from_medium = st.selectbox('移動元の媒体（引く）', medium_list, key='from_medium_select')
    with col2:
        transfer_amount = st.number_input('振替金額（円）', min_value=0, step=100, key='transfer_input')
        to_medium = st.selectbox('移動先の媒体（足す）', medium_list, key='to_medium_select')
        
    transfer_memo = st.text_input('メモ（例: ATM引き出し、PayPayチャージ など）')
    submit_transfer = st.form_submit_button(label='振替を実行して記録する')

    if submit_transfer:
        if from_medium == to_medium:
            st.warning('移動元と移動先には異なる媒体を選択してください。')
        elif transfer_amount <= 0:
            st.warning('振替金額を入力してください。')
        else:
            # 1. 移動元から引き算、移動先に足し算
            df_balances.loc[df_balances['媒体'] == from_medium, '残高'] -= transfer_amount
            df_balances.loc[df_balances['媒体'] == to_medium, '残高'] += transfer_amount
            save_balance_data(df_balances)
            
            # 2. 証跡としてログに記録（対象媒体を「元→先」と表記）
            log_medium_str = f"{from_medium} → {to_medium}"
            append_transaction_log(transfer_date, "振替", transfer_memo, log_medium_str, transfer_amount)
            
            st.success(f'【振替完了】{from_medium} から {to_medium} へ {transfer_amount:,}円 を移動し、ログに記録しました。')

st.divider()

# --- 4. 媒体と残高の登録・更新セクション ---
st.header('🏦 媒体と残高の登録')
with st.form(key='add_medium_form'):
    new_medium = st.text_input('媒体名（例: 口座, PayPay, 現金（財布）など）')
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

# --- 5. 媒体名の編集セクション ---
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

# --- 6. 現在の資産状況（テキスト出力） ---
st.header('📊 現在の資産状況')

total_assets = df_balances['残高'].sum()
st.subheader(f'💰 総資産: {total_assets:,} 円')

st.write('**【各媒体の残高】**')
for index, row in df_balances.iterrows():
    st.text(f"・{row['媒体']}: {row['残高']:,} 円")
