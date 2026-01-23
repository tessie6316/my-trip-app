import streamlit as st
import pandas as pd
import datetime

# ==========================================
# 1. アプリ設定
# ==========================================
st.set_page_config(page_title="Routine Keeper", page_icon="⏰")

st.title("☀️ 朝の支度司令塔")
st.caption("「到着時間」または「出発時間」から完璧なルーチンを逆算します。")

# ==========================================
# 2. データ管理
# ==========================================
if "tasks_df" not in st.session_state:
    default_data = [
        {"task": "靴を履く・荷物チェック", "min": 5},
        {"task": "着替え・身支度", "min": 15},
        {"task": "歯磨き・洗顔", "min": 10},
        {"task": "朝ごはん", "min": 20},
        {"task": "起きて水を飲む", "min": 5},
    ]
    st.session_state.tasks_df = pd.DataFrame(default_data)

# ==========================================
# 3. サイドバー：ゴール設定 & タスク編集
# ==========================================
with st.sidebar:
    st.header("🎯 ゴール設定")
    
    # ゴールの種類を選ぶ
    goal_type = st.radio(
        "基準にするのは？",
        ["🏃 家を出る時間", "🏁 目的地に着く時間"]
    )
    
    # 時間入力
    target_time = st.time_input("設定時刻", datetime.time(8, 0))
    
    # 目的地着の場合は「移動時間」を聞く
    travel_time = 0
    if "目的地" in goal_type:
        travel_time = st.number_input("🚃 移動時間 (分)", min_value=1, value=30, step=5)
        st.info(f"移動時間を引くと、家を出るリミットは **{(datetime.datetime.combine(datetime.date.today(), target_time) - datetime.timedelta(minutes=travel_time)).strftime('%H:%M')}** です。")

    st.write("---")
    st.header("📝 ルーチン編集")
    
    edited_df = st.data_editor(
        st.session_state.tasks_df,
        num_rows="dynamic",
        column_config={
            "task": st.column_config.TextColumn("タスク名", required=True),
            "min": st.column_config.NumberColumn("分", min_value=1, format="%d分"),
        },
        use_container_width=True,
        hide_index=True,
        key="editor"
    )
    st.session_state.tasks_df = edited_df

# ==========================================
# 4. 逆算ロジック
# ==========================================
schedule = []

# 計算の基準となる日時オブジェクトを作成
base_dt = datetime.datetime.combine(datetime.date.today(), target_time)

# --- ステップ1: 移動時間の処理（目的地着の場合のみ） ---
if "目的地" in goal_type:
    departure_dt = base_dt - datetime.timedelta(minutes=travel_time)
    # 移動もスケジュールに追加（一番最後に来るように）
    schedule.append({
        "task": "🚃 移動（目的地へ）",
        "start": departure_dt.strftime("%H:%M"),
        "end": base_dt.strftime("%H:%M"),
        "duration": travel_time,
        "type": "travel" # 色分け用
    })
    current_calc_time = departure_dt
else:
    # 家を出る時間基準なら、そこがスタート
    current_calc_time = base_dt

# --- ステップ2: タスクの逆算 ---
tasks_for_calc = edited_df.iloc[::-1] # 下から順に計算

for index, row in tasks_for_calc.iterrows():
    task_name = row["task"]
    duration = int(row["min"])
    
    end_time = current_calc_time
    start_time = end_time - datetime.timedelta(minutes=duration)
    
    schedule.append({
        "task": task_name,
        "start": start_time.strftime("%H:%M"),
        "end": end_time.strftime("%H:%M"),
        "duration": duration,
        "type": "task"
    })
    
    current_calc_time = start_time

# 表示順を時系列（朝→ゴール）に戻す
schedule.reverse()

if schedule:
    first_action_time = schedule[0]["start"]
else:
    first_action_time = target_time.strftime("%H:%M")

# ==========================================
# 5. メイン画面表示
# ==========================================
c1, c2 = st.columns([3, 1])

if "目的地" in goal_type:
    c1.info(f"🏁 **{target_time.strftime('%H:%M')}** に着くには、**{first_action_time}** に行動開始！")
else:
    c1.info(f"🏃 **{target_time.strftime('%H:%M')}** に出るには、**{first_action_time}** に行動開始！")

if not schedule:
    st.warning("👈 サイドバーでタスクを追加してください！")
else:
    st.subheader("📅 今日のタイムライン")
    
    for item in schedule:
        with st.container():
            # デザイン調整：移動時間はちょっと色を変えたりアイコン変えたり
            if item.get("type") == "travel":
                prefix = "🚃"
                bg_color = "background-color: #e0f7fa; padding: 10px; border-radius: 5px;"
            else:
                prefix = "👉"
                bg_color = ""
            
            # カラムレイアウト
            c_time, c_content, c_min = st.columns([1, 4, 1])
            
            c_time.markdown(f"### {item['start']}")
            
            # 少しリッチな表示
            content_html = f"""
            <div style="{bg_color}">
                <strong>{prefix} {item['task']}</strong><br>
                <span style="color:gray; font-size:0.8em">{item['start']} - {item['end']}</span>
            </div>
            """
            c_content.markdown(content_html, unsafe_allow_html=True)
            
            c_min.markdown(f"⏱️ `{item['duration']}分`")
            
            st.divider()