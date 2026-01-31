import streamlit as st
import pandas as pd
import requests
import base64
import urllib.parse
import json
import io

def check_password():

    """パスワード認証"""

    

    # セッションステートにログイン状態がない場合は初期化

    if 'logged_in' not in st.session_state:

        st.session_state.logged_in = False



    # ログイン済みなら何もしない

    if st.session_state.logged_in:

        return True



    # ログイン画面の表示

    st.title("🔒 旅のしおり作成ツール")

    password = st.text_input("購入した「合言葉」を入力してください", type="password")

    

    # 合言葉の設定（これをnoteの有料部分に書く！）

    SECRET_PASSWORD = "okinawa_saiko" 

    

    if st.button("ログイン"):

        if password == SECRET_PASSWORD:

            st.session_state.logged_in = True

            st.rerun() # 画面を再読み込みしてアプリを表示

        else:

            st.error("合言葉が違います")

    return False



# メイン処理の前に認証チェック

if not check_password():

    st.stop() 

# ==========================================
# 0. アプリ設定 & データ保持
# ==========================================
st.set_page_config(page_title="旅のしおりマスター", page_icon="📝", layout="wide")

# データが消えないように保持
if 'travel_data' not in st.session_state:
    st.session_state.travel_data = {
        "title": "沖縄旅行 2026",
        "hotel_name": "ホテルストーク那覇新都心",
        "members": ["あなた", "友達A", "友達B"],
        "flights": [],
        "spots": [],
        "checklist": ["航空券 (アプリ)", "免許証", "現金", "スマホ", "充電器", "着替え"],
        "payments": []
    }

data = st.session_state.travel_data

# ==========================================
# 1. ロジック関数群
# ==========================================

def get_image_base64(uploaded_file):
    """アップロード画像をBase64に変換"""
    if uploaded_file is None:
        return get_fallback_image()
    try:
        bytes_data = uploaded_file.getvalue()
        encoded = base64.b64encode(bytes_data).decode('utf-8')
        ext = "png" if uploaded_file.name.lower().endswith('.png') else "jpeg"
        return f"data:image/{ext};base64,{encoded}"
    except:
        return get_fallback_image()

def get_fallback_image():
    """デフォルト画像"""
    url = "https://images.unsplash.com/photo-1507525428034-b723cf961d3e?auto=format&fit=crop&w=1000&q=80"
    try:
        response = requests.get(url, timeout=5)
        encoded = base64.b64encode(response.content).decode('utf-8')
        return f"data:image/jpeg;base64,{encoded}"
    except:
        return ""

def calculate_split_settlement():
    """割り勘計算ロジック"""
    if not data["payments"]:
        return "まだ支払いデータがありません。"
    
    total = sum(p['amount'] for p in data['payments'])
    if len(data["members"]) == 0: return "メンバーがいません"
    
    avg = total / len(data["members"])
    
    balances = {m: -avg for m in data["members"]}
    for p in data["payments"]:
        if p['payer'] in balances:
            balances[p['payer']] += p['amount']
        
    receivers = sorted([[n, b] for n, b in balances.items() if b > 0], key=lambda x: x[1], reverse=True)
    payers = sorted([[n, -b] for n, b in balances.items() if b < 0], key=lambda x: x[1], reverse=True)
    
    results = []
    r_idx, p_idx = 0, 0
    while r_idx < len(receivers) and p_idx < len(payers):
        amount = min(receivers[r_idx][1], payers[p_idx][1])
        if amount > 1:
            results.append(f"{receivers[r_idx][0]} ← {payers[p_idx][0]}  {int(amount)}円")
        receivers[r_idx][1] -= amount
        payers[p_idx][1] -= amount
        if receivers[r_idx][1] < 1: r_idx += 1
        if payers[p_idx][1] < 1: p_idx += 1
        
    res_text = "========= 精算レポート =========\\n"
    res_text += "\\n".join(results)
    res_text += f"\\n\\n総額: {int(total)}円 (1人あたり: {int(avg)}円)\\n"
    res_text += "================================"
    return res_text

def generate_html_string(header_bg, settlement_text):
    """HTML生成"""
    header_style = f"background-image: url('{header_bg}');" if header_bg else "background-color: #00aeef;"
    
    # フライト情報
    flight_html = ""
    for f in data["flights"]:
        status_url = f"https://www.google.com/search?q={f['no']}+status"
        flight_html += f"""
        <div class="flight-card">
            <div class="f-head"><b>{f['date']}</b> <span>{f['no']}</span></div>
            <div class="f-route">{f['route']}</div>
            <div class="f-memo">{f['memo']}</div>
            <a href="{status_url}" target="_blank" class="f-btn">運航状況を確認</a>
        </div>"""

    # 行程リスト
    itinerary_html = ""
    spots_df = pd.DataFrame(data["spots"])
    if not spots_df.empty:
        spots_df = spots_df.sort_values(by=["day", "time"])
        days_grouped = spots_df.groupby("day")

        for day, group in days_grouped:
            waypoints = "/".join([f"{urllib.parse.quote(row['query'])}" for _, row in group.iterrows()])
            day_map_url = f"https://www.google.com/maps/dir/{waypoints}"
            
            itinerary_html += f"""
            <div class="day-section">
                <div class="day-label">{day}</div>
                <div class="map-btn-area">
                    <a href="{day_map_url}" target="_blank" class="day-map-btn">🗺️ この日のルート地図</a>
                </div>
            """
            prev_spot = None
            for i, (_, s) in enumerate(group.iterrows()):
                encoded_query = urllib.parse.quote(s['query'])
                current_nav_url = f"https://www.google.com/maps/search/?api=1&query={encoded_query}"
                
                if i == 0:
                    if data["hotel_name"] and "1日目" not in day:
                        encoded_hotel = urllib.parse.quote(data["hotel_name"])
                        prev_nav_url = f"https://www.google.com/maps/dir/?api=1&origin={encoded_hotel}&destination={encoded_query}&travelmode=driving"
                        prev_nav_text = "🏨 ホテルから行く"
                    else:
                        prev_nav_url = current_nav_url
                        prev_nav_text = "📍 現在地からナビ"
                else:
                    encoded_origin = urllib.parse.quote(prev_spot['query'])
                    prev_nav_url = f"https://www.google.com/maps/dir/?api=1&origin={encoded_origin}&destination={encoded_query}&travelmode=driving"
                    prev_nav_text = f"🚗 {prev_spot['name']}から行く"
                prev_spot = s

                itinerary_html += f"""
                <div class="s-item">
                    <div class="s-time">{s['time']}</div>
                    <div class="s-info">
                        <div class="s-title">{s['name']} <span class="tag {s['cat']}">{s['cat']}</span></div>
                        <div class="s-memo">{s['memo']}</div>
                        <div class="nav-actions">
                            <a href="{current_nav_url}" target="_blank" class="nav-btn-main">📍 現在地から行く</a>
                            <a href="{prev_nav_url}" target="_blank" class="nav-btn-sub">{prev_nav_text}</a>
                        </div>
                    </div>
                </div>"""
            itinerary_html += "</div>"

    # 持ち物リスト
    checklist_html = ""
    for i, item in enumerate(data["checklist"]):
        checklist_html += f"""<div class="c-item"><input type="checkbox" id="c{i}" class="save-check"><label for="c{i}">{item}</label></div>"""

    # HTMLテンプレート (精算レポート埋め込み付き)
    full_html = f"""
<!DOCTYPE html>
<html lang="ja">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0, user-scalable=no" />
<title>{data['title']}</title>
<style>
    body {{ margin: 0; font-family: -apple-system, sans-serif; background: #f0f2f5; color: #333; padding-bottom: 60px; }}
    .header-container {{ width: 100%; height: 180px; {header_style} background-size: cover; background-position: center; position: relative; }}
    .header-text {{ position: absolute; bottom: 0; left: 0; right: 0; background: rgba(0,0,0,0.5); color: white; padding: 10px 15px; }}
    .header-text h1 {{ margin: 0; font-size: 1.4em; font-weight: normal; }}
    input[name="nav"] {{ display: none; }}
    .nav-label-container {{ display: flex; position: sticky; top: 0; z-index: 100; background: white; border-bottom: 1px solid #ddd; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
    .nav-label {{ flex: 1; padding: 15px 0; text-align: center; font-weight: bold; color: #666; cursor: pointer; border-bottom: 4px solid transparent; }}
    #tab1:checked ~ .nav-label-container label[for="tab1"], #tab2:checked ~ .nav-label-container label[for="tab2"] {{ color: #0041cd; border-bottom-color: #0041cd; background: #f0f8ff; }}
    .content-box {{ display: none; }}
    #tab1:checked ~ #content1 {{ display: block; }} #tab2:checked ~ #content2 {{ display: block; }}
    .day-label {{ background: #0041cd; color: white; padding: 8px 15px; font-weight: bold; font-size: 0.95em; }}
    .map-btn-area {{ padding: 10px 15px; background: #e3f2fd; text-align: center; border-bottom: 1px solid #bbdefb; }}
    .day-map-btn {{ color: #0041cd; text-decoration: none; font-weight: bold; font-size: 0.9em; display: inline-block; }}
    .s-item {{ display: flex; padding: 15px; background: white; border-bottom: 1px solid #eee; align-items: flex-start; }}
    .s-time {{ font-weight: bold; width: 50px; color: #444; margin-top: 2px; }}
    .s-info {{ flex: 1; }}
    .s-title {{ font-weight: bold; font-size: 1.1em; margin-bottom: 5px; }}
    .s-memo {{ font-size: 0.9em; color: #666; margin-bottom: 10px; line-height: 1.4; }}
    .nav-actions {{ display: flex; flex-direction: column; gap: 8px; margin-top: 5px; }}
    .nav-btn-main {{ display: block; text-align: center; background: #34a853; color: white; text-decoration: none; padding: 8px; border-radius: 6px; font-weight: bold; font-size: 0.9em; }}
    .nav-btn-sub {{ display: block; text-align: center; background: #f1f3f4; color: #555; text-decoration: none; padding: 6px; border-radius: 6px; font-size: 0.8em; }}
    .tag {{ font-size: 0.7em; padding: 2px 5px; border-radius: 4px; color: white; margin-left: 5px; vertical-align: middle; }}
    .tag.食事 {{ background: purple; }} .tag.観光 {{ background: green; }} .tag.宿泊 {{ background: #008080; }} .tag.空港 {{ background: blue; }}
    .f-scroll {{ display: flex; overflow-x: auto; padding: 15px; gap: 10px; background: #f0f2f5; }}
    .flight-card {{ min-width: 260px; background: white; padding: 15px; border-radius: 10px; border-left: 5px solid #00aeef; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
    .f-btn {{ display: block; text-align: center; background: #e0f7fa; color: #006064; text-decoration: none; padding: 8px; border-radius: 4px; margin-top: 10px; font-weight: bold; font-size: 0.9em; }}
    .section-head {{ padding: 15px; font-weight: bold; background: #e9ecef; border-bottom: 1px solid #ddd; margin-top: 20px; }}
    .c-item {{ background: white; padding: 15px; border-bottom: 1px solid #eee; display: flex; align-items: center; }}
    .c-item input {{ transform: scale(1.5); margin-right: 15px; }}
    .b-form {{ padding: 15px; background: #fff; display: flex; gap: 10px; border-bottom: 1px solid #eee; }}
    .b-form input {{ padding: 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 16px; -webkit-appearance: none; }}
    .b-total {{ padding: 20px 15px; text-align: right; font-weight: bold; font-size: 1.4em; color: #0041cd; background: #f0f8ff; border-top: 1px solid #ddd; }}
    .del-btn {{ color: red; border: none; background: none; font-weight: bold; font-size: 1.5em; padding: 0 15px; }}
    .settlement-box {{ margin: 20px; padding: 20px; background: #333; color: #fff; font-family: monospace; white-space: pre-wrap; border-radius: 8px; }}
</style>
</head>
<body>
<input type="radio" name="nav" id="tab1" class="tab-radios" checked>
<input type="radio" name="nav" id="tab2" class="tab-radios">

<div class="header-container"><div class="header-text"><h1>{data['title']}</h1></div></div>
<div class="nav-label-container"><label for="tab1" class="nav-label">📅 旅程 & マップ</label><label for="tab2" class="nav-label">🎒 準備 & 予算</label></div>

<div id="content1" class="content-box">
    <div class="f-scroll">{flight_html}</div>
    {itinerary_html}
</div>

<div id="content2" class="content-box">
    <div class="section-head" style="border-top:none;">🎒 持ち物チェック</div>
    {checklist_html}
    <div class="section-head" style="margin-top:20px;">💰 割り勘レポート</div>
    <div class="settlement-box">{settlement_text.replace('\\n', '<br>')}</div>
    
    <div class="section-head">📝 共同財布メモ (アプリ用)</div>
    <div class="b-form">
        <input type="number" id="bp" placeholder="金額" style="width:35%;">
        <input type="text" id="bd" placeholder="用途" style="flex:1;">
        <button onclick="addB()" style="padding:10px; background:#ff9900; color:white; border:none; border-radius:6px;">追加</button>
    </div>
    <div class="b-total" id="bt">合計: 0円</div>
    <div id="bl" style="background:white;"></div>
</div>

<script>
    const checkItems = document.querySelectorAll('.save-check');
    const savedC = JSON.parse(localStorage.getItem('trip_app_chk') || '{{}}');
    checkItems.forEach((el, index) => {{
        const id = 'c' + index;
        if(savedC[id]) el.checked = true;
        el.addEventListener('change', function() {{
            const c = {{}};
            checkItems.forEach((e, i) => {{ c['c'+i] = e.checked; }});
            localStorage.setItem('trip_app_chk', JSON.stringify(c));
        }});
    }});

    let bud = JSON.parse(localStorage.getItem('trip_app_bud') || '[]');
    function addB() {{
        const p = document.getElementById('bp').value;
        const d = document.getElementById('bd').value;
        if(p && d) {{
            bud.push({{p:parseInt(p), d:d}});
            updateB();
            localStorage.setItem('trip_app_bud', JSON.stringify(bud));
            document.getElementById('bp').value = '';
            document.getElementById('bd').value = '';
        }}
    }}
    function updateB() {{
        const list = document.getElementById('bl');
        let total = 0;
        let html = '';
        bud.forEach((item, idx) => {{
            total += item.p;
            html += `<div style="display:flex; justify-content:space-between; padding:15px; border-bottom:1px solid #eee; font-size:1.1em; align-items:center;"><span>${{item.d}}</span><span>¥${{item.p.toLocaleString()}} <button class="del-btn" onclick="delB(${{idx}})">×</button></span></div>`;
        }});
        list.innerHTML = html;
        document.getElementById('bt').innerText = '合計: ¥' + total.toLocaleString();
    }}
    function delB(idx) {{ bud.splice(idx, 1); updateB(); localStorage.setItem('trip_app_bud', JSON.stringify(bud)); }}
    updateB();
</script>
</body>
</html>
"""
    return full_html


# ==========================================
# 2. アプリの見た目（UI構築）
# ==========================================

st.title("旅のしおりマスター ✈️")

# タブ定義（6つ！）
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(["基本設定", "🎒 持ち物", "✈️ 移動", "📍 行程", "💰 割り勘", "📤 出力"])

# --- タブ1: 基本設定 ---
with tab1:
    data["title"] = st.text_input("旅行タイトル", data["title"])
    data["hotel_name"] = st.text_input("ホテル名（ナビ起点）", data["hotel_name"])
    m_str = st.text_area("参加メンバー（カンマ区切り）", ",".join(data["members"]))
    data["members"] = [m.strip() for m in m_str.split(",") if m.strip()]
    uploaded_file = st.file_uploader("ヘッダー画像を選択", type=['jpg','png','jpeg'])

# --- タブ2: 持ち物 (復活！) ---
with tab2:
    st.subheader("🎒 持ち物リスト")
    col1, col2 = st.columns([3, 1])
    new_item = col1.text_input("新しい持ち物を追加")
    if col2.button("追加", key="add_item"):
        if new_item:
            data["checklist"].append(new_item)
            st.rerun()
            
    if data["checklist"]:
        for i, item in enumerate(data["checklist"]):
            c1, c2 = st.columns([4, 1])
            c1.write(f"・ {item}")
            if c2.button("削除", key=f"del_item_{i}"):
                data["checklist"].pop(i)
                st.rerun()
    else:
        st.info("持ち物がありません")

# --- タブ3: 移動 (復活！) ---
with tab3:
    st.subheader("✈️ フライト・移動情報")
    with st.form("flight_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        f_date = c1.text_input("日付", "2/17(火)")
        f_no = c2.text_input("便名", "ANA309")
        f_route = st.text_input("区間", "中部 -> 那覇")
        f_memo = st.text_input("メモ", "10分前集合")
        if st.form_submit_button("フライトを追加"):
            data["flights"].append({"date": f_date, "no": f_no, "route": f_route, "memo": f_memo})
            st.rerun()
            
    if data["flights"]:
        st.table(pd.DataFrame(data["flights"]))
        if st.button("全削除", key="del_flights"):
            data["flights"] = []
            st.rerun()

# --- タブ4: 行程 ---
with tab4:
    st.subheader("📍 スポット設定")
    with st.form("spot_form", clear_on_submit=True):
        c1, c2 = st.columns(2)
        s_day = c1.text_input("日程", "1日目 2/17(火)")
        s_time = c2.text_input("時間", "12:00")
        s_name = st.text_input("場所名（表示用）")
        s_query = st.text_input("検索名（Googleマップ用）", placeholder="空欄なら場所名と同じになります")
        s_cat = st.selectbox("カテゴリ", ["観光", "食事", "宿泊", "空港", "体験"])
        s_memo = st.text_area("メモ")
        
        if st.form_submit_button("スポットを追加") and s_name:
            q = s_query if s_query else s_name
            data["spots"].append({"day": s_day, "time": s_time, "name": s_name, "query": q, "cat": s_cat, "memo": s_memo})
            st.rerun()

    if data["spots"]:
        st.dataframe(pd.DataFrame(data["spots"]))
        if st.button("全削除", key="del_spots"):
            data["spots"] = []
            st.rerun()

# --- タブ5: 割り勘 ---
with tab5:
    st.subheader("💰 割り勘入力")
    if not data["members"]:
        st.warning("基本設定タブでメンバーを登録してください")
    else:
        with st.form("pay_form", clear_on_submit=True):
            p = st.selectbox("誰が払った？", data["members"])
            a = st.number_input("いくら？", min_value=0, step=100)
            m = st.text_input("何に？")
            if st.form_submit_button("支払い記録"):
                data["payments"].append({"payer":p, "amount":a, "memo":m})
                st.rerun()
                
        # 支払い履歴の表示
        if data["payments"]:
            st.write("---")
            st.write("履歴:")
            for i, p in enumerate(data["payments"]):
                col_a, col_b = st.columns([4, 1])
                col_a.text(f"{p['payer']}が {p['amount']}円 ({p['memo']})")
                if col_b.button("削除", key=f"del_pay_{i}"):
                    data["payments"].pop(i)
                    st.rerun()
            
            st.write("---")
            st.code(calculate_split_settlement()) # 計算結果表示

# --- タブ6: 出力 ---
with tab6:
    st.header("最終出力")
    st.markdown("設定が完了したらダウンロードしてください。")
    
    header_base64 = get_image_base64(uploaded_file)
    settlement_text = calculate_split_settlement()
    
    html_string = generate_html_string(header_base64, settlement_text)
    
    st.download_button(
        label="📥 しおりHTMLをダウンロード",
        data=html_string,
        file_name="my_ultimate_trip.html",
        mime="text/html"
    )