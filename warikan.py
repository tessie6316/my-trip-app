import streamlit as st

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
# 1. 計算ロジック
# ==========================================
def calculate_warikan():
    if not data["members"]:
        return "まずはメンバーを登録してください。"
    if not data["payments"]:
        return "支払いデータがありません。"

    # 各個人の収支バランスを計算
    balances = {m: 0 for m in data["members"]}
    total_amount = 0

    for p in data["payments"]:
        payer = p["payer"]
        amount = p["amount"]
        mode = p.get("mode", "equal") # equal か custom
        
        total_amount += amount
        
        # 1. 払った人は「プラス」（立て替えた分）
        if payer in balances:
            balances[payer] += amount
        
        # 2. 負担する人（消費した人）は「マイナス」
        if mode == "equal":
            # 均等割り
            targets = p["targets"]
            if not targets: continue
            per_person = amount / len(targets)
            for t in targets:
                if t in balances:
                    balances[t] -= per_person
        
        elif mode == "custom":
            # 金額指定
            details = p["details"] # {名前: 金額, 名前: 金額...}
            for name, debt in details.items():
                if name in balances:
                    balances[name] -= debt

    # 精算リストの作成
    receivers = []
    payers = []

    for name, val in balances.items():
        val = int(round(val)) # 1円単位に丸め
        if val > 0:
            receivers.append([name, val])
        elif val < 0:
            payers.append([name, -val])

    # 金額の大きい順にソート
    receivers.sort(key=lambda x: x[1], reverse=True)
    payers.sort(key=lambda x: x[1], reverse=True)

    results = []
    r_idx, p_idx = 0, 0

    while r_idx < len(receivers) and p_idx < len(payers):
        rec_name, rec_val = receivers[r_idx]
        pay_name, pay_val = payers[p_idx]

        # 相殺できる金額
        move_amount = min(rec_val, pay_val)

        if move_amount > 0:
            results.append(f"{rec_name} ← {pay_name} {move_amount}円")

        # 残高更新
        receivers[r_idx][1] -= move_amount
        payers[p_idx][1] -= move_amount

        if receivers[r_idx][1] == 0: r_idx += 1
        if payers[p_idx][1] == 0: p_idx += 1

    # テキスト出力
    output = "=========支払い==========\n"
    if results:
        output += "\n".join(results)
    else:
        output += "精算の必要はありません。"
    output += f"\n\n総額:{int(total_amount)}円"
    output += "\n========================"
    
    return output

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
        # 今まで通りの均等モード
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
        # ★ここを改良: 金額指定（自動補完対応）モード
        st.write("---")
        st.write("👇 負担額を入力（0円の人は残金を山分けします）")
        
        custom_sum = 0
        custom_details = {}
        blank_members = [] # 0円（空欄）の人リスト
        
        cols = st.columns(2)
        for i, member in enumerate(data["members"]):
            with cols[i % 2]:
                val = st.number_input(f"{member}の負担分", min_value=0, step=100, key=f"custom_{i}")
                if val > 0:
                    custom_sum += val
                    custom_details[member] = val
                else:
                    blank_members.append(member)
        
        # 残金計算
        remainder = amount - custom_sum
        
        # 判定ロジック
        is_valid = False
        
        if remainder == 0:
            # ぴったり（全員分指定済み）
            st.success("✅ 合計金額と一致しています！")
            current_payment["details"] = custom_details
            is_valid = True
            
        elif remainder > 0:
            # 残りがある場合
            if blank_members:
                # 空欄の人で山分け
                per_rem = int(remainder / len(blank_members))
                st.info(f"💡 残り {int(remainder)}円 は、未入力の {len(blank_members)}名 ({','.join(blank_members)}) で割り勘します。（一人あたり {per_rem}円）")
                
                # 自動補完データをセット
                for bm in blank_members:
                    custom_details[bm] = remainder / len(blank_members) # 割り切れない分は小数で保持（計算側で処理）
                
                current_payment["details"] = custom_details
                is_valid = True
            else:
                # 残りがあるのに、空欄の人がいない（全員入力済みだが足りない）
                st.warning(f"⚠️ あと {int(remainder)}円 足りません。誰かの金額を増やしてください。")
                
        else:
            # 合計オーバー
            st.error(f"⚠️ {int(-remainder)}円 多すぎます。金額を減らしてください。")

        # 追加ボタン
        if st.button("リストに追加", type="primary", disabled=not is_valid):
            data["payments"].append(current_payment)
            st.rerun()

    # 入力履歴の表示
    if data["payments"]:
        st.write("---")
        st.subheader("履歴")
        for i, p in enumerate(reversed(data["payments"])):
            mode_label = ""
            detail_str = ""
            
            if p.get("mode") == "custom":
                mode_label = " [指定]"
                # 内訳を表示（小数点が出る場合があるので整数丸め表示）
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
    result_text = calculate_warikan()
    st.code(result_text)
    st.caption("右上のコピーボタンでLINEに貼れます 👆")