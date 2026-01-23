import streamlit as st
import pandas as pd
import datetime
import gspread
import json
from oauth2client.service_account import ServiceAccountCredentials

# ==========================================
# 0. 設定エリア
# ==========================================
# ローカルで動かすときの鍵ファイル名
SECRET_FILE = 'secret.json'

# あなたのスプレッドシートID
SPREADSHEET_KEY = '1-8cu7x-zC41ot512uYHL0UhD7hxdfnr0zyQ1H3BrlmI'

# ==========================================
# 1. Googleスプレッドシート接続機能 (ハイブリッド版)
# ==========================================
@st.cache_resource
def get_sheet():
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    # Streamlit Cloudの「Secrets」に鍵があるか確認
    if "gcp_key_json" in st.secrets:
        key_dict = json.loads(st.secrets["gcp_key_json"])
        creds = ServiceAccountCredentials.from_json_keyfile_dict(key_dict, scope)
    else:
        # なければ、自分のPCにある 'secret.json' を使う
        try:
            creds = ServiceAccountCredentials.from_json_keyfile_name(SECRET_FILE, scope)
        except FileNotFoundError:
            st.error("鍵ファイルが見つかりません。PCなら 'secret.json' を置いてください。WebならSecretsを設定してください。")
            st.stop()
            
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_KEY).sheet1

def load_data_from_sheet():
    """スプレッドシートからデータを読み込む"""
    try:
        sheet = get_sheet()
        raw_data = sheet.acell('A1').value
        if raw_data:
            return json.loads(raw_data)
    except Exception as e:
        print(f"Log: {e}")
    
    return {
        "title": "未定のイベント",
        "dates": [],       
        "votes": {},       
        "comments": {}     
    }

def save_data_to_sheet(data):
    """スプレッドシートにデータを保存する"""
    try:
        sheet = get_sheet()
        json_str = json.dumps(data, ensure_ascii=False)
        sheet.update_acell('A1', json_str)
    except Exception as e:
        st.error(f"保存エラー: {e}")

# ==========================================
# 2. アプリ設定
# ==========================================
st.set_page_config(page_title="日程調整AI (クラウド版)", page_icon="☁️", layout="wide")

if 'schedule_data' not in st.session_state:
    with st.spinner('クラウドからデータを読み込んでいます...'):
        st.session_state.schedule_data = load_data_from_sheet()

data = st.session_state.schedule_data

# ==========================================
# 3. ロジック関数
# ==========================================
def calculate_best_date():
    if not data["dates"] or not data["votes"]:
        return None, None, []

    df = pd.DataFrame(index=data["dates"])
    users = list(data["votes"].keys())
    
    for user in users:
        user_votes = data["votes"][user]
        df[user] = df.index.map(lambda d: user_votes.get(d, 0))

    df["合計"] = df[users].sum(axis=1)
    
    def get_ng_names(row):
        ng_list = [u for u in users if row[u] == 0]
        return ", ".join(ng_list) if ng_list else ""

    df["NGの人"] = df.apply(get_ng_names, axis=1)
    df["_ng_count"] = (df[users] == 0).sum(axis=1)
    
    df_sorted = df.sort_values(by=["合計", "_ng_count"], ascending=[False, True])
    df_sorted = df_sorted.drop(columns=["_ng_count"])
    
    if not df_sorted.empty:
        max_score = df_sorted["合計"].iloc[0]
        top_dates = df_sorted[df_sorted["合計"] == max_score].index.tolist()
    else:
        top_dates = []

    return df, df_sorted, top_dates

# ==========================================
# 4. UI構築
# ==========================================
st.title("☁️ 日程調整AI (Live Sync)")
st.caption(f"Saving to Spreadsheet ID: ...{SPREADSHEET_KEY[-6:]}")

tab1, tab2, tab3 = st.tabs(["① イベント作成", "② 投票入力", "③ 結果発表"])

# --- タブ1: イベント作成 ---
with tab1:
    c1, c2 = st.columns([2, 1])
    new_title = c1.text_input("イベント名", data["title"])
    
    if new_title != data["title"]:
        data["title"] = new_title
        save_data_to_sheet(data)
        st.toast("タイトルを保存しました")

    st.subheader("候補日の自動生成")
    col_d1, col_d2, col_d3 = st.columns(3)
    date_range = col_d1.date_input("期間", value=[], min_value=datetime.date.today())
    default_time = col_d2.time_input("開始時間", datetime.time(19, 0))
    time_str = default_time.strftime("%H:%M")
    
    target_weekdays = col_d3.multiselect(
        "含める曜日", ["月", "火", "水", "木", "金", "土", "日"], default=["土", "日"]
    )
    weekdays_map = ["月", "火", "水", "木", "金", "土", "日"]

    if len(date_range) == 2:
        start_date, end_date = date_range
        if st.button("候補日リストを作成 🗓️", type="primary"):
            generated_dates = []
            curr = start_date
            while curr <= end_date:
                wd_str = weekdays_map[curr.weekday()]
                if wd_str in target_weekdays:
                    date_str = f"{curr.month}/{curr.day}({wd_str}) {time_str}〜"
                    generated_dates.append(date_str)
                curr += datetime.timedelta(days=1)
            
            data["dates"] = generated_dates
            data["votes"] = {} 
            data["comments"] = {}
            save_data_to_sheet(data)
            st.success("作成＆保存しました！")
            st.rerun()

    st.write("---")
    st.caption("👇 手動編集エリア")
    current_text = "\n".join(data["dates"])
    edited_text = st.text_area("候補日一覧", value=current_text, height=150)
    if st.button("リスト保存"):
        data["dates"] = [d.strip() for d in edited_text.split('\n') if d.strip()]
        save_data_to_sheet(data)
        st.success("保存しました！")

# --- タブ2: 投票入力 ---
with tab2:
    st.header(f"「{data['title']}」への投票")
    
    if not data["dates"]:
        st.warning("候補日がありません。タブ①で作成してください。")
    else:
        st.info("💡 **凡例**: 🤩参加(3点) / 🤔未定(2点) / 🕒条件付(1点) / 🙅不可(0点)")
        
        if st.button("🔄 他の人の投票を読み込む"):
            st.session_state.schedule_data = load_data_from_sheet()
            st.rerun()

        user_name = st.text_input("あなたの名前")
        
        if user_name:
            st.write("---")
            with st.form("vote_form"):
                answers = {}
                comments_temp = {}
                options = ["🤩 参加", "🤔 未定", "🕒 条件", "🙅 不可"]
                
                h1, h2, h3 = st.columns([1.5, 3, 2])
                h1.caption("日程")
                h2.caption("回答")
                h3.caption("備考 (任意)")
                
                for date in data["dates"]:
                    c1, c2, c3 = st.columns([1.5, 3, 2]) 
                    c1.markdown(f"**{date}**")
                    choice = c2.radio(f"{date}", options, horizontal=True, key=f"radio_{date}", label_visibility="collapsed")
                    comment = c3.text_input(f"comment_{date}", placeholder="遅れます etc.", label_visibility="collapsed", key=f"comment_{date}")
                    
                    if "🤩" in choice: score = 3
                    elif "🤔" in choice: score = 2
                    elif "🕒" in choice: score = 1
                    else: score = 0
                    answers[date] = score
                    if comment: comments_temp[date] = comment
                
                st.write("---")
                if st.form_submit_button("投票する & 保存", type="primary"):
                    current_cloud_data = load_data_from_sheet()
                    current_cloud_data["votes"][user_name] = answers
                    if "comments" not in current_cloud_data: current_cloud_data["comments"] = {}
                    if user_name not in current_cloud_data["comments"]: current_cloud_data["comments"][user_name] = {}
                    current_cloud_data["comments"][user_name] = comments_temp
                    
                    save_data_to_sheet(current_cloud_data)
                    st.session_state.schedule_data = current_cloud_data
                    st.success(f"{user_name}さんの投票をクラウドに保存しました！")
                    st.rerun()

# --- タブ3: 結果発表 ---
with tab3:
    st.header("集計結果 🏆")
    
    if st.button("🔄 最新の集計を見る"):
        st.session_state.schedule_data = load_data_from_sheet()
        st.rerun()

    if not data["dates"] or not data["votes"]:
        st.info("データなし")
    else:
        raw_df, ranked_df, top_dates = calculate_best_date()
        
        if top_dates:
            top_score = ranked_df.iloc[0]["合計"]
            st.success(f"🎉 候補日は **{len(top_dates)}つ** あります！（スコア: {int(top_score)}点）")
            
            # --- LINE用テキスト出力機能 ---
            st.write("---")
            st.subheader("📋 LINE連絡用コピー")
            
            # テキスト生成
            clip_text = f"【{data['title']} 日程決定！🎉】\n\n"
            clip_text += f"📅 日時: {top_dates[0]}\n"
            clip_text += f"📊 参加スコア: {int(top_score)}点\n"
            
            ng_name = ranked_df.loc[top_dates[0], "NGの人"]
            if ng_name:
                clip_text += f"⚠️ NG: {ng_name}\n"
            else:
                clip_text += f"✨ 全員参加OK！\n"
            
            clip_text += "\n👇 詳細はこちら\n"
            # 本番ではここにあなたのアプリのURLを入れると親切です
            clip_text += "(ここにURLを貼る)"
            
            st.code(clip_text, language="text")
            st.caption("👆 右上のコピーボタンを押してLINEに貼ってください")
            # ---------------------------

            for d in top_dates:
                ng_ppl = ranked_df.loc[d, "NGの人"]
                if ng_ppl:
                    st.warning(f"👑 **{d}** （NG: {ng_ppl}）")
                else:
                    st.balloons()
                    st.success(f"👑 **{d}** （全員参加可能！）")

            st.write("---")
            st.subheader("📊 詳細ランキング表")
            users = list(data["votes"].keys())
            display_cols = ["合計", "NGの人"] + users
            st.dataframe(ranked_df[display_cols].style.highlight_max(axis=0, subset=["合計"], color="#fffd75"))
            
            st.write("---")
            st.subheader("💬 日程ごとの備考")
            has_comment = False
            for date in data["dates"]:
                day_comments = []
                for user in users:
                    if user in data["comments"] and date in data["comments"][user]:
                        c = data["comments"][user][date]
                        day_comments.append(f"**{user}**: {c}")
                if day_comments:
                    has_comment = True
                    with st.expander(f"📍 {date}", expanded=True):
                        for c in day_comments: st.write(f"- {c}")
            if not has_comment: st.caption("コメントはありません")
        else:
            st.warning("集計エラー")