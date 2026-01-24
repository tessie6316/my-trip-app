import streamlit as st
import pandas as pd # 表計算用にpandasを追加

# ==========================================
# 0. アプリ設定
# ==========================================
st.set_page_config(page_title="割り勘の達人", page_icon="💸")

if 'warikan_data' not in st.session_state:
    st.session_state.warikan_data = {
        "members": [],
        "payments": []
    }

data = st.session_state.warikan_data

# ==========================================
# 1. 計算ロジック & 表示
# ==========================================
def calculate_and_show_warikan():
    if not data["members"]:
        st.error("まずはメンバーを登録してください。")
        return
    if not data["payments"]:
        st.error("支払いデータがありません。")
        return

    # 集計用変数の初期化
    # 1. 実際に財布から出した金額
    paid_totals = {m: 0 for m in data["members"]}
    # 2. 本来負担すべき金額（飲み食いした分）
    burden_totals = {m: 0 for m in data["members"]}
    
    total_amount = 0

    # --- 集計処理 ---
    for p in data["payments"]:
        payer = p["payer"]
        amount = p["amount"]
        mode = p.get("mode", "equal")
        
        total_amount += amount
        
        # 支払った額を加算
        if payer in paid_totals:
            paid_totals[payer] += amount
        
        # 負担額を加算
        if mode == "equal":
            # 均等割り
            targets = p["targets"]
            if targets:
                per_person = amount / len(targets)
                for t in targets:
                    if t in burden_totals:
                        burden_totals[t] += per_person
        
        elif mode == "custom":
            # 金額指定
            details = p["details"]
            for name, debt in details.items():
                if name in burden_totals:
                    burden_totals[name] += debt

    # --- 途中式（収支表）の作成 ---
    summary_data = []
    balances = {} # 精算計算用

    for m in data["members"]:
        paid = paid_totals[m]       # 払った
        burden = burden_totals[m]   # 負担すべき
        balance = paid - burden     # 収支 (+なら受取、-なら支払)
        
        balances[m] = balance # 後で精算ロジックに使う
        
        summary_data.append({
            "名前": m,
            "支払った額": int(paid),
            "本来の負担額": int(burden),
            "収支(過不足)": int(balance)
        })

    # データフレーム作成
    df_summary = pd.DataFrame(summary_data)
    
    # --- 途中式の表示エリア ---
    st.write("---")
    st.header("📊 1. 計算の途中経過")
    st.info("「なぜこの金額になるの？」を確認しましょう。\n\n**数式： 支払った額 － 本来の負担額 ＝ 収支**")
    
    # 収支の色付け関数
    def color_balance(val):
        color = '#d4edda' if val > 0 else '#f8d7da' if val < 0 else ''
        text_color = '#155724' if val > 0 else '#721c24' if val < 0 else ''
        return f'background-color: {color}; color: {text_color}'

    # テーブル表示
    st.dataframe(
        df_summary.style
        .format({"支払った額": "¥{}", "本来の負担額": "¥{}", "収支(過不足)": "¥{}"})
        .map(color_balance, subset=["収支(過不足)"]),
        use_container_width=True
    )
    
    st.caption("🟢 緑色(プラス)の人 = 払いすぎているので**もらう側**\n🔴 赤色(マイナス)の人 = 負担額より払っていないので**払う側**")

    # --- 精算最適化ロジック (既存のコードと同様) ---
    receivers = []
    payers = []

    for name, val in balances.items():
        val = int(round(val))
        if val > 0:
            receivers.append([name, val])
        elif val < 0:
            payers.append([name, -val])

    receivers.sort(key=lambda x: x[1], reverse=True)
    payers.sort(key=lambda x: x[1], reverse=True)

    results = []
    r_idx, p_idx = 0, 0

    while r_idx < len(receivers) and p_idx < len(payers):
        rec_name, rec_val = receivers[r_idx]
        pay_name, pay_val = payers[p_idx]

        move_amount = min(rec_val, pay_val)

        if move_amount > 0:
            results.append(f"{rec_name} ← {pay_name} {move_amount}円")

        receivers[r_idx][1] -= move_amount
        payers[p_idx][1] -= move_amount

        if receivers[r_idx][1] == 0: r_idx += 1
        if payers[p_idx][1] == 0: p_idx += 1

    # --- 最終結果テキストの生成 ---
    st.write("---")
    st.header("💸 2. 最終的な精算リスト")
    
    output_text = "=========支払い==========\n"
    if results:
        for r in results:
            st.success(r) # 画面に見やすく表示
        output_text += "\n".join(results)
    else:
        msg = "精算の必要はありません。"
        st.success(msg)
        output_text += msg
        
    output_text += f"\n\n総額:{int(total_amount)}円"
    output_text += "\n========================"
    
    # コピー用コードブロック
    st.subheader("📋 LINEコピー用")
    st.code(output_text)
    st.caption("右上のコピーボタンを押してLINEに貼り付けてください 👆")

# ==========================================
# 2. UI構築
# ==========================================
st.title("💸 割り勘の達人")

# --- タブ1: メンバー登録 ---
with st.expander("① メンバー設定", expanded=not bool(data["members"])):
    st.write("まずは割り勘するメンバーを登録してください。")
    
    col1, col2 = st.columns([3, 1])
    new_mem = col1.text_input("名前を追加", placeholder="例: Aさん")
    if col2.button("追加"):
        if new_mem and new_mem not in data["members"]:
            data["members"].append(new_mem)
            st.rerun()
            
    if data["members"]:
        st.write("参加者: " + "、".join(data["members"]))
        if st.button("リセット"):
            data["members"] = []
            data["payments"] = []
            st.rerun()

# --- タブ2: 支払い入力 ---
st.subheader("② 支払い入力")

if not data["members"]:
    st.warning("上でメンバーを登録してください。")
else:
    # 入力モードの選択など
    st.markdown("##### 新しい支払いを追加")
    
    col_a, col_b = st.columns(2)
    payer = col_a.selectbox("払った人", data["members"])
    amount = col_b.number_input("支払総額 (円)", min_value=1, step=100)
    memo = st.text_input("用途 (例: 居酒屋)", placeholder="何代？")
    
    split_mode = st.radio("割り勘モード", ["均等に割る", "金額を指定する"], horizontal=True)

    # データを一時的に構築
    current_payment = {
        "payer": payer,
        "amount": amount,
        "memo": memo,
        "mode": "equal" if split_mode == "均等に割る" else "custom",
        "targets": [],
        "details": {}
    }

    if split_mode == "均等に割る":
        targets = st.multiselect("対象者 (空白なら全員)", data["members"], default=data["members"])
        actual_targets = targets if targets else data["members"]
        current_payment["targets"] = actual_targets
        
        if actual_targets:
            per_person = int(amount / len(actual_targets))
            st.caption(f"💡 1人あたり 約{per_person}円")
            
        if st.button("リストに追加", type="primary"):
            data["payments"].append(current_payment)
            st.rerun()

    else:
        # 金額指定モード
        st.write("---")
        st.write("👇 負担額を入力（0円の人は残金を山分けします）")
        
        custom_sum = 0
        custom_details = {}
        blank_members = []
        
        cols = st.columns(2)
        for i, member in enumerate(data["members"]):
            with cols[i % 2]:
                val = st.number_input(f"{member}の負担分", min_value=0, step=100, key=f"custom_{i}")
                if val > 0:
                    custom_sum += val
                    custom_details[member] = val
                else:
                    blank_members.append(member)
        
        remainder = amount - custom_sum
        is_valid = False
        
        if remainder == 0:
            st.success("✅ 合計金額と一致しています！")
            current_payment["details"] = custom_details
            is_valid = True
            
        elif remainder > 0:
            if blank_members:
                per_rem = int(remainder / len(blank_members))
                st.info(f"💡 残り {int(remainder)}円 は、未入力の {len(blank_members)}名 ({','.join(blank_members)}) で割り勘します。（一人あたり {per_rem}円）")
                for bm in blank_members:
                    custom_details[bm] = remainder / len(blank_members)
                current_payment["details"] = custom_details
                is_valid = True
            else:
                st.warning(f"⚠️ あと {int(remainder)}円 足りません。誰かの金額を増やしてください。")
        else:
            st.error(f"⚠️ {int(-remainder)}円 多すぎます。金額を減らしてください。")

        if st.button("リストに追加", type="primary", disabled=not is_valid):
            data["payments"].append(current_payment)
            st.rerun()

    # 入力履歴
    if data["payments"]:
        st.write("---")
        st.subheader("履歴")
        for i, p in enumerate(reversed(data["payments"])):
            mode_label = ""
            detail_str = ""
            
            if p.get("mode") == "custom":
                mode_label = " [指定]"
                detail_str = ", ".join([f"{k}:{int(v)}" for k,v in p["details"].items()])
            else:
                if len(p["targets"]) == len(data["members"]):
                    detail_str = "全員"
                else:
                    detail_str = ",".join(p["targets"])
                
            st.text(f"📍 {p['memo']}: {p['payer']}が {p['amount']}円{mode_label}\n   (負担: {detail_str})")
            
            if st.button("削除", key=f"del_{i}"):
                actual_index = len(data["payments"]) - 1 - i
                data["payments"].pop(actual_index)
                st.rerun()

# --- タブ3: 精算結果 ---
st.subheader("③ 精算結果")
if st.button("計算する！", type="primary"):
    calculate_and_show_warikan()