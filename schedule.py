import streamlit as st
import pandas as pd
import datetime

# ==========================================
# 0. アプリ設定 (ワイドモード)
# ==========================================
st.set_page_config(page_title="日程調整AI", page_icon="🗓️", layout="wide")

if 'schedule_data' not in st.session_state:
    st.session_state.schedule_data = {
        "title": "未定のイベント",
        "dates": [],       
        "votes": {},       # { "ユーザー名": {日付: 点数} }
        "comments": {}     # { "ユーザー名": {日付: "コメント"} } ★日付ごとに保存する形に変更
    }

data = st.session_state.schedule_data

# ==========================================
# 1. ロジック関数
# ==========================================
def calculate_best_date():
    if not data["dates"] or not data["votes"]:
        return None, None, []

    df = pd.DataFrame(index=data["dates"])
    users = list(data["votes"].keys())
    
    # 投票データの展開
    for user in users:
        user_votes = data["votes"][user]
        df[user] = df.index.map(lambda d: user_votes.get(d, 0))

    # 集計列の作成
    df["合計"] = df[users].sum(axis=1)
    
    # NGの人リストを作成
    def get_ng_names(row):
        ng_list = [u for u in users if row[u] == 0]
        return ", ".join(ng_list) if ng_list else ""

    df["NGの人"] = df.apply(get_ng_names, axis=1)

    # ランキングソート
    df["_ng_count"] = (df[users] == 0).sum(axis=1)
    df_sorted = df.sort_values(by=["合計", "_ng_count"], ascending=[False, True])
    df_sorted = df_sorted.drop(columns=["_ng_count"])
    
    # 1位タイを抽出
    if not df_sorted.empty:
        max_score = df_sorted["合計"].iloc[0]
        top_dates = df_sorted[df_sorted["合計"] == max_score].index.tolist()
    else:
        top_dates = []

    return df, df_sorted, top_dates

# ==========================================
# 2. UI構築
# ==========================================
st.title("🗓️ 日程調整AI")

tab1, tab2, tab3 = st.tabs(["① イベント作成", "② 投票入力", "③ 結果発表"])

# --- タブ1: イベント作成 ---
with tab1:
    c1, c2 = st.columns([2, 1])
    data["title"] = c1.text_input("イベント名", data["title"])

    st.subheader("候補日の自動生成")
    
    col_d1, col_d2, col_d3 = st.columns(3)
    date_range = col_d1.date_input("期間", value=[], min_value=datetime.date.today())
    default_time = col_d2.time_input("開始時間", datetime.time(19, 0))
    time_str = default_time.strftime("%H:%M")
    
    target_weekdays = col_d3.multiselect(
        "含める曜日", 
        ["月", "火", "水", "木", "金", "土", "日"], 
        default=["土", "日"]
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
            data["comments"] = {} # リセット
            st.success(f"{len(generated_dates)}日分の候補日を作成しました！")
            st.rerun()

    st.write("---")
    st.caption("👇 手動編集エリア")
    current_text = "\n".join(data["dates"])
    edited_text = st.text_area("候補日一覧", value=current_text, height=150)
    if st.button("リスト保存"):
        data["dates"] = [d.strip() for d in edited_text.split('\n') if d.strip()]
        st.success("更新しました")

# --- タブ2: 投票入力 ---
with tab2:
    st.header(f"「{data['title']}」への投票")
    
    if not data["dates"]:
        st.warning("候補日がありません。タブ①で作成してください。")
    else:
        st.info("💡 **凡例**: 🤩参加(3点) / 🤔未定(2点) / 🕒条件付(1点) / 🙅不可(0点)")
        
        user_name = st.text_input("あなたの名前")
        
        if user_name:
            st.write("---")
            with st.form("vote_form"):
                answers = {}
                comments_temp = {}
                options = ["🤩 参加", "🤔 未定", "🕒 条件", "🙅 不可"]
                
                # ★ここが進化した入力欄
                # ヘッダーで見出しをつける
                h1, h2, h3 = st.columns([1.5, 3, 2])
                h1.caption("日程")
                h2.caption("回答")
                h3.caption("備考 (任意)")
                
                for date in data["dates"]:
                    # 1行に3要素を並べる
                    c1, c2, c3 = st.columns([1.5, 3, 2]) 
                    
                    # 1. 日付
                    c1.markdown(f"**{date}**")
                    
                    # 2. ラジオボタン
                    choice = c2.radio(
                        f"{date}", 
                        options, 
                        horizontal=True, 
                        key=f"radio_{date}",
                        label_visibility="collapsed"
                    )
                    
                    # 3. 備考入力欄（ここに追加！）
                    comment = c3.text_input(
                        f"comment_{date}", 
                        placeholder="遅れます etc.",
                        label_visibility="collapsed",
                        key=f"comment_{date}"
                    )
                    
                    # データ格納処理
                    if "🤩" in choice: score = 3
                    elif "🤔" in choice: score = 2
                    elif "🕒" in choice: score = 1
                    else: score = 0
                    answers[date] = score
                    
                    if comment:
                        comments_temp[date] = comment
                
                st.write("---")
                if st.form_submit_button("投票する", type="primary"):
                    data["votes"][user_name] = answers
                    data["comments"][user_name] = comments_temp
                    st.success(f"{user_name}さんの投票を受け付けました！")
                    st.rerun()

# --- タブ3: 結果発表 ---
with tab3:
    st.header("集計結果 🏆")
    
    if not data["dates"] or not data["votes"]:
        st.info("データなし")
    else:
        raw_df, ranked_df, top_dates = calculate_best_date()
        
        if top_dates:
            top_score = ranked_df.iloc[0]["合計"]
            st.success(f"🎉 候補日は **{len(top_dates)}つ** あります！（スコア: {int(top_score)}点）")
            
            for d in top_dates:
                ng_ppl = ranked_df.loc[d, "NGの人"]
                if ng_ppl:
                    st.warning(f"👑 **{d}** （NG: {ng_ppl}）")
                else:
                    st.balloons()
                    st.success(f"👑 **{d}** （全員参加可能！）")

            # 詳細表
            st.write("---")
            st.subheader("📊 詳細ランキング表")
            users = list(data["votes"].keys())
            display_cols = ["合計", "NGの人"] + users
            st.dataframe(
                ranked_df[display_cols].style.highlight_max(axis=0, subset=["合計"], color="#fffd75")
            )
            
            # ★進化: 日付ごとのコメント表示
            st.write("---")
            st.subheader("💬 日程ごとの備考")
            
            has_comment = False
            # 全ユーザーのコメントを集約して、日付ごとに整理
            for date in data["dates"]:
                day_comments = []
                for user in users:
                    # そのユーザーのその日のコメントを取得
                    if user in data["comments"] and date in data["comments"][user]:
                        c = data["comments"][user][date]
                        day_comments.append(f"**{user}**: {c}")
                
                # コメントがある日だけ表示
                if day_comments:
                    has_comment = True
                    # 展開できるパネルで表示
                    with st.expander(f"📍 {date}", expanded=True):
                        for c in day_comments:
                            st.write(f"- {c}")
                            
            if not has_comment:
                st.caption("コメントはありません")

        else:
            st.warning("集計エラー")