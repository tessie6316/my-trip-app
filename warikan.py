import streamlit as st
import pandas as pd

st.set_page_config(page_title="割り勘精算", page_icon="💸")

st.title("💸 割り勘精算アプリ")
st.caption("「途中式」が見えるから、みんな納得！")

# ==========================================
# 1. データ入力エリア
# ==========================================
st.subheader("📝 支払いの入力")

# 初期データ
if "money_data" not in st.session_state:
    st.session_state.money_data = pd.DataFrame([
        {"名前": "Aさん", "支払った金額": 12000, "備考": "レンタカー代"},
        {"名前": "Bさん", "支払った金額": 5000, "備考": "高速代"},
        {"名前": "Cさん", "支払った金額": 0, "備考": ""},
        {"名前": "Dさん", "支払った金額": 0, "備考": ""},
    ])

# 編集可能なテーブル
edited_df = st.data_editor(
    st.session_state.money_data,
    num_rows="dynamic",
    column_config={
        "支払った金額": st.column_config.NumberColumn(format="¥%d"),
    },
    use_container_width=True,
    key="money_editor"
)

# セッション状態の更新
st.session_state.money_data = edited_df

# ==========================================
# 2. 計算ロジック
# ==========================================
if st.button("計算する 🧮", type="primary"):
    df = edited_df.copy()
    
    # バリデーション
    if df.empty:
        st.error("メンバーを入力してください。")
        st.stop()
        
    total_payment = df["支払った金額"].sum()
    num_people = len(df)
    
    if num_people == 0:
        st.error("人数が0人です。")
        st.stop()
        
    per_person = int(total_payment / num_people)
    remainder = total_payment % num_people
    
    st.write("---")
    
    # ------------------------------------------
    # ★追加機能：途中式（バランスシート）の表示
    # ------------------------------------------
    st.header("1. 計算の途中経過 🧮")
    st.info(f"合計支払額: **{total_payment:,}円** ÷ {num_people}人 = 1人あたり **{per_person:,}円**")
    
    # 収支（バランス）の計算
    # プラスなら「もらう側」、マイナスなら「払う側」
    df["1人あたり"] = per_person
    df["過不足(収支)"] = df["支払った金額"] - per_person
    
    # 端数調整（とりあえず最初の人が負担する簡易ロジック）
    if remainder > 0:
        df.loc[0, "過不足(収支)"] += remainder
        st.caption(f"※割り切れない端数 {remainder}円 は、表の一番上の人が調整しています。")

    # わかりやすいように表示用データフレーム作成
    display_df = df[["名前", "支払った金額", "1人あたり", "過不足(収支)"]].copy()
    
    # 色付け用の関数
    def highlight_balance(val):
        if val > 0:
            return 'background-color: #d1e7dd; color: #0f5132' # 緑（もらう）
        elif val < 0:
            return 'background-color: #f8d7da; color: #842029' # 赤（払う）
        else:
            return ''

    st.write("👇 **「誰がいくら多く払っているか（プラス）、足りないか（マイナス）」の表**")
    st.dataframe(
        display_df.style
        .format({"支払った金額": "¥{},", "1人あたり": "¥{},", "過不足(収支)": "¥{},"})
        .map(highlight_balance, subset=["過不足(収支)"]),
        use_container_width=True
    )
    
    st.caption("緑色（＋）の人は**もらう側**、赤色（ー）の人は**払う側**です。これをゼロにするように移動させます。")

    # ------------------------------------------
    # 精算ロジック（最適化）
    # ------------------------------------------
    st.write("---")
    st.header("2. 最終的な送金方法 💸")
    
    # 計算用に辞書化
    balance_dict = dict(zip(df["名前"], df["過不足(収支)"]))
    
    receivers = [] # もらう人 (name, amount)
    payers = []    # 払う人 (name, amount)
    
    for name, amount in balance_dict.items():
        if amount > 0:
            receivers.append([name, amount])
        elif amount < 0:
            payers.append([name, -amount]) # 正の値に変換
            
    # マッチング処理
    transactions = []
    
    # ソートして「大きく払う人」と「大きくもらう人」をぶつける（回数削減）
    receivers.sort(key=lambda x: x[1], reverse=True)
    payers.sort(key=lambda x: x[1], reverse=True)
    
    i_r = 0
    i_p = 0
    
    while i_r < len(receivers) and i_p < len(payers):
        r_name, r_amount = receivers[i_r]
        p_name, p_amount = payers[i_p]
        
        # 取引額決定（小さい方に合わせる）
        amount = min(r_amount, p_amount)
        
        if amount > 0:
            transactions.append(f"**{p_name}** ➞ **{r_name}** : `{amount:,}円`")
        
        # 残高更新
        receivers[i_r][1] -= amount
        payers[i_p][1] -= amount
        
        # 完済したら次へ
        if receivers[i_r][1] == 0:
            i_r += 1
        if payers[i_p][1] == 0:
            i_p += 1

    # 結果表示
    if not transactions:
        st.success("🎉 精算なし！全員ピッタリです。")
    else:
        for t in transactions:
            st.success(t)
            
    # LINEコピー用
    st.write("---")
    st.subheader("📋 LINE用テキスト")
    clip_text = f"【割り勘精算】\n1人あたり: {per_person:,}円\n\n"
    for t in transactions:
        # マークダウン除去してテキスト化
        clean_t = t.replace("**", "").replace("`", "")
        clip_text += f"{clean_t}\n"
    
    st.code(clip_text, language="text")
