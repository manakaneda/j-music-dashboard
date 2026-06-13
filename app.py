import os
import requests
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import networkx as nx
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://ws.audioscrobbler.com/2.0/"


def get_api_key() -> str:
    # Streamlit Cloud の Secrets → ローカルの .env の順で取得
    try:
        return st.secrets["LASTFM_API_KEY"]
    except Exception:
        return os.getenv("LASTFM_API_KEY", "")

J_GENRES = {
    "🎵 全ジャンル": "japanese",
    "💿 J-Pop": "j-pop",
    "🎸 J-Rock": "j-rock",
    "🌆 City Pop": "city pop",
    "🎌 アニメ": "anime",
    "🎮 ゲーム音楽": "video game music",
    "💎 ビジュアル系": "visual kei",
    "🎤 アイドル": "idol",
    "🎻 演歌": "enka",
}

# ──────────────────────────────────────────────
# API helpers
# ──────────────────────────────────────────────
def api(method: str, **params) -> dict:
    p = {
        "method": method,
        "api_key": get_api_key(),
        "format": "json",
        "limit": params.pop("limit", 50),
        **params,
    }
    r = requests.get(BASE_URL, params=p, timeout=10)
    r.raise_for_status()
    return r.json()


def fmt(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n/1_000:.0f}K"
    return str(n)


# ──────────────────────────────────────────────
# Data fetchers (cached)
# ──────────────────────────────────────────────
@st.cache_data(ttl=1800)
def japan_top_tracks(limit=50):
    try:
        data = api("geo.getTopTracks", country="japan", limit=limit)
        rows = []
        for i, t in enumerate(data.get("tracks", {}).get("track", []), 1):
            rows.append({
                "rank": i,
                "track": t.get("name", ""),
                "artist": t.get("artist", {}).get("name", ""),
                "listeners": int(t.get("listeners", 0)),
                "url": t.get("url", ""),
            })
        return pd.DataFrame(rows)
    except Exception as e:
        return pd.DataFrame()


@st.cache_data(ttl=1800)
def japan_top_artists(limit=50):
    try:
        data = api("geo.getTopArtists", country="japan", limit=limit)
        rows = []
        for i, a in enumerate(data.get("topartists", {}).get("artist", []), 1):
            rows.append({
                "rank": i,
                "artist": a.get("name", ""),
                "listeners": int(a.get("listeners", 0)),
                "url": a.get("url", ""),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=1800)
def genre_top_tracks(tag, limit=30):
    try:
        data = api("tag.getTopTracks", tag=tag, limit=limit)
        rows = []
        for i, t in enumerate(data.get("tracks", {}).get("track", []), 1):
            rows.append({
                "rank": i,
                "track": t.get("name", ""),
                "artist": t.get("artist", {}).get("name", ""),
                "url": t.get("url", ""),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=1800)
def genre_top_artists(tag, limit=30):
    try:
        data = api("tag.getTopArtists", tag=tag, limit=limit)
        rows = []
        for i, a in enumerate(data.get("topartists", {}).get("artist", []), 1):
            rows.append({
                "rank": i,
                "artist": a.get("name", ""),
                "url": a.get("url", ""),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_artist_info(name):
    try:
        data = api("artist.getInfo", artist=name, limit=1)
        a = data.get("artist", {})
        stats = a.get("stats", {})
        tags = [t["name"] for t in a.get("tags", {}).get("tag", [])]
        similar = [{"name": s["name"], "url": s.get("url", "")}
                   for s in a.get("similar", {}).get("artist", [])]
        bio = a.get("bio", {}).get("summary", "")
        bio = bio.split("<a href")[0].strip() if bio else ""
        img = next((i["#text"] for i in reversed(a.get("image", [])) if i.get("#text")), "")
        return {
            "name": a.get("name", name),
            "listeners": int(stats.get("listeners", 0)),
            "playcount": int(stats.get("playcount", 0)),
            "tags": tags,
            "similar": similar,
            "bio": bio,
            "image": img,
            "url": a.get("url", ""),
        }
    except Exception:
        return {}


@st.cache_data(ttl=3600)
def get_top_tracks(artist, limit=15):
    try:
        data = api("artist.getTopTracks", artist=artist, limit=limit)
        rows = []
        for i, t in enumerate(data.get("toptracks", {}).get("track", []), 1):
            rows.append({
                "rank": i,
                "track": t.get("name", ""),
                "playcount": int(t.get("playcount", 0)),
                "listeners": int(t.get("listeners", 0)),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_top_albums(artist, limit=8):
    try:
        data = api("artist.getTopAlbums", artist=artist, limit=limit)
        rows = []
        for i, alb in enumerate(data.get("topalbums", {}).get("album", []), 1):
            rows.append({
                "rank": i,
                "album": alb.get("name", ""),
                "playcount": int(alb.get("playcount", 0)),
                "image": next((img["#text"] for img in reversed(alb.get("image", [])) if img.get("#text")), ""),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def get_similar(artist, limit=20):
    try:
        data = api("artist.getSimilar", artist=artist, limit=limit)
        rows = []
        for a in data.get("similarartists", {}).get("artist", []):
            rows.append({
                "artist": a.get("name", ""),
                "match": float(a.get("match", 0)),
                "image": next((i["#text"] for i in reversed(a.get("image", [])) if i.get("#text")), ""),
            })
        return pd.DataFrame(rows)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600)
def search_artists(q, limit=6):
    try:
        data = api("artist.search", artist=q, limit=limit)
        return [a["name"] for a in data.get("results", {}).get("artistmatches", {}).get("artist", [])]
    except Exception:
        return []


# ──────────────────────────────────────────────
# Session state init
# ──────────────────────────────────────────────
def nav(page, artist=None):
    st.session_state.page = page
    if artist:
        st.session_state.artist = artist

if "page" not in st.session_state:
    st.session_state.page = "charts"
if "artist" not in st.session_state:
    st.session_state.artist = ""
if "compare_list" not in st.session_state:
    st.session_state.compare_list = []
if "network_root" not in st.session_state:
    st.session_state.network_root = ""
if "genre_filter" not in st.session_state:
    st.session_state.genre_filter = "🎵 全ジャンル"

# ──────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────
st.set_page_config(page_title="J-Music Dashboard", page_icon="🎌", layout="wide")
st.markdown("""
<style>
    .stApp { background: #0f0f1a; color: #e8e8f0; }
    h1 { color: #ff6b6b; font-size: 1.8rem; }
    h2, h3 { color: #ffd93d; }
    .stButton>button {
        background: transparent; color: #e8e8f0; border: 1px solid #555;
        border-radius: 6px; padding: 4px 12px; font-size: 0.85rem;
    }
    .stButton>button:hover { background: #1e1e3a; border-color: #ff6b6b; color: #ff6b6b; }
    /* サイドバーのナビゲーションボタン */
    [data-testid="stSidebar"] .stButton>button {
        width: 100%; text-align: left;
        background: #1a1a2e; color: #d0d0e8 !important;
        border: 1px solid #444; border-radius: 8px;
        padding: 8px 14px; font-size: 0.9rem; margin-bottom: 4px;
    }
    [data-testid="stSidebar"] .stButton>button:hover {
        background: #252540; border-color: #ff6b6b; color: #ff6b6b !important;
    }
    .active-btn>button {
        background: #2a1a2e !important; border-color: #ff6b6b !important;
        color: #ff6b6b !important;
    }
    div[data-testid="metric-container"] { background: #1a1a2e; border-radius: 8px; padding: 10px; }
</style>
""", unsafe_allow_html=True)

# ──────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────
with st.sidebar:
    st.markdown("## 🎌 J-Music Hub")
    st.markdown("---")

    pages = {
        "charts":  "📊 Japan Charts",
        "genre":   "🎸 Genre Explorer",
        "artist":  "🔍 Artist Deep Dive",
        "compare": "📊 アーティスト比較",
        "network": "🕸️ 探索ネットワーク",
    }
    for key, label in pages.items():
        is_active = st.session_state.page == key
        css = "active-btn" if is_active else "nav-btn"
        st.markdown(f'<div class="{css}">', unsafe_allow_html=True)
        if st.button(label, key=f"nav_{key}"):
            nav(key)
        st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("---")

    if st.session_state.compare_list:
        st.markdown(f"**比較リスト** ({len(st.session_state.compare_list)}人)")
        for name in st.session_state.compare_list:
            c1, c2 = st.columns([3, 1])
            c1.caption(name)
            if c2.button("×", key=f"rm_{name}"):
                st.session_state.compare_list.remove(name)
                st.rerun()
        if st.button("比較ページへ →"):
            nav("compare")
        st.markdown("---")

    if st.button("🔄 キャッシュクリア"):
        st.cache_data.clear()
        st.rerun()

page = st.session_state.page


# ──────────────────────────────────────────────
# Page: Japan Charts
# ──────────────────────────────────────────────
if page == "charts":
    st.title("📊 Japan Charts")

    # Genre filter chips
    st.markdown("**ジャンルで絞り込み**")
    cols = st.columns(len(J_GENRES))
    for i, (label, tag) in enumerate(J_GENRES.items()):
        is_sel = st.session_state.genre_filter == label
        if cols[i].button(label, key=f"gf_{label}", type="primary" if is_sel else "secondary"):
            st.session_state.genre_filter = label
            st.rerun()

    st.markdown("---")
    selected_tag = J_GENRES[st.session_state.genre_filter]

    with st.spinner("データ取得中..."):
        if st.session_state.genre_filter == "🎵 全ジャンル":
            df_tracks = japan_top_tracks(50)
            df_artists = japan_top_artists(50)
        else:
            df_tracks = genre_top_tracks(selected_tag, 50)
            df_artists = genre_top_artists(selected_tag, 50)

    if df_tracks.empty and df_artists.empty:
        st.warning("データを取得できませんでした")
        st.stop()

    m1, m2, m3, m4 = st.columns(4)
    m1.metric("チャート曲数", len(df_tracks))
    m2.metric("チャートアーティスト", df_artists["artist"].nunique() if not df_artists.empty else 0)
    if not df_tracks.empty and "listeners" in df_tracks.columns:
        m3.metric("最高リスナー数", fmt(df_tracks["listeners"].max()))
        m4.metric("平均リスナー数", fmt(int(df_tracks["listeners"].mean())))

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("🎵 トップ曲")
        if not df_tracks.empty:
            metric_col = "listeners" if "listeners" in df_tracks.columns else "rank"
            fig = px.bar(
                df_tracks.head(20), x=metric_col, y="track", orientation="h",
                color=metric_col, color_continuous_scale="Reds",
                hover_data={"artist": True},
                labels={metric_col: "リスナー数" if metric_col == "listeners" else "ランク", "track": ""},
            )
            fig.update_layout(
                yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e8e8f0", height=500, margin=dict(l=0),
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("🎤 トップアーティスト")
        if not df_artists.empty:
            metric_col = "listeners" if "listeners" in df_artists.columns else "rank"
            fig = px.bar(
                df_artists.head(20), x=metric_col, y="artist", orientation="h",
                color=metric_col, color_continuous_scale="Blues",
                labels={metric_col: "リスナー数" if metric_col == "listeners" else "ランク", "artist": ""},
            )
            fig.update_layout(
                yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e8e8f0", height=500, margin=dict(l=0),
            )
            event = st.plotly_chart(fig, use_container_width=True, on_select="rerun", key="artist_chart")
            if event and event.get("selection", {}).get("points"):
                clicked = event["selection"]["points"][0].get("label", "")
                if clicked:
                    nav("artist", clicked)
                    st.rerun()

    # Clickable artist list
    st.subheader("🎤 アーティスト一覧（クリックで詳細）")
    if not df_artists.empty:
        n_cols = 5
        rows = [df_artists.iloc[i:i+n_cols] for i in range(0, min(len(df_artists), 25), n_cols)]
        for row_df in rows:
            cols = st.columns(n_cols)
            for j, (_, a) in enumerate(row_df.iterrows()):
                with cols[j]:
                    if st.button(f"**{a['artist']}**\n{fmt(a['listeners']) if 'listeners' in a and a['listeners'] > 0 else ''}", key=f"ca_{a['artist']}"):
                        nav("artist", a["artist"])
                        st.rerun()


# ──────────────────────────────────────────────
# Page: Genre Explorer
# ──────────────────────────────────────────────
elif page == "genre":
    st.title("🎸 Genre Explorer")

    genre_label = st.selectbox("ジャンルを選択", list(J_GENRES.keys()), key="ge_sel")
    tag = J_GENRES[genre_label]

    with st.spinner(f"「{genre_label}」のデータ取得中..."):
        df_gt = genre_top_tracks(tag, 30)
        df_ga = genre_top_artists(tag, 30)

    col1, col2 = st.columns(2)

    with col1:
        st.subheader(f"{genre_label} — トップ曲")
        if not df_gt.empty:
            fig = px.bar(
                df_gt.head(20), x="rank", y="track", orientation="h",
                color="rank", color_continuous_scale="Reds_r",
                hover_data={"artist": True},
                labels={"rank": "ランク", "track": ""},
            )
            fig.update_layout(
                yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e8e8f0", height=500,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader(f"{genre_label} — トップアーティスト")
        if not df_ga.empty:
            fig = px.bar(
                df_ga.head(20), x="rank", y="artist", orientation="h",
                color="rank", color_continuous_scale="Blues_r",
                labels={"rank": "ランク", "artist": ""},
            )
            fig.update_layout(
                yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e8e8f0", height=500,
            )
            st.plotly_chart(fig, use_container_width=True)

    # Genre comparison
    st.markdown("---")
    st.subheader("📊 ジャンル横断比較")
    selected_genres = st.multiselect(
        "比較するジャンルを選択（最大6つ）",
        list(J_GENRES.keys()),
        default=["💿 J-Pop", "🎸 J-Rock", "🌆 City Pop", "🎌 アニメ"],
        max_selections=6,
    )

    if selected_genres:
        with st.spinner("比較データ取得中..."):
            cmp_rows = []
            for gl in selected_genres:
                df_a = genre_top_artists(J_GENRES[gl], 10)
                cmp_rows.append({
                    "ジャンル": gl,
                    "アーティスト数": len(df_a),
                })
            df_cmp = pd.DataFrame(cmp_rows)

        fig_cmp = px.bar(
            df_cmp, x="ジャンル", y="アーティスト数",
            color="ジャンル", color_discrete_sequence=px.colors.qualitative.Pastel,
            title="ジャンル別チャートアーティスト数",
        )
        fig_cmp.update_layout(
            showlegend=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e8e8f0",
        )
        st.plotly_chart(fig_cmp, use_container_width=True)

    # Clickable artist list
    if not df_ga.empty:
        st.markdown("---")
        st.subheader("アーティスト詳細を見る")
        cols = st.columns(5)
        for i, (_, row) in enumerate(df_ga.head(15).iterrows()):
            with cols[i % 5]:
                if st.button(row["artist"], key=f"ga_{row['artist']}"):
                    nav("artist", row["artist"])
                    st.rerun()


# ──────────────────────────────────────────────
# Page: Artist Deep Dive
# ──────────────────────────────────────────────
elif page == "artist":
    st.title("🔍 Artist Deep Dive")

    search_q = st.text_input(
        "アーティスト名を検索",
        value=st.session_state.artist,
        placeholder="例: 米津玄師、YOASOBI、Ado、Official髭男dism",
    )

    if search_q and search_q != st.session_state.artist:
        with st.spinner("検索中..."):
            results = search_artists(search_q)
        if results:
            chosen = st.selectbox("候補を選択", results)
            if st.button("このアーティストを表示"):
                st.session_state.artist = chosen
                st.rerun()
    elif st.session_state.artist:
        search_q = st.session_state.artist

    if not search_q:
        st.info("アーティスト名を入力してください")
        st.stop()

    with st.spinner(f"「{search_q}」のデータ取得中..."):
        info = get_artist_info(search_q)
        df_top = get_top_tracks(search_q, 15)
        df_albums = get_top_albums(search_q, 8)
        df_sim = get_similar(search_q, 15)

    if not info:
        st.warning("アーティスト情報を取得できませんでした")
        st.stop()

    # Header
    col_img, col_stats = st.columns([1, 4])
    with col_img:
        if info.get("image"):
            st.image(info["image"], width=140)
    with col_stats:
        st.subheader(info["name"])
        m1, m2, m3 = st.columns(3)
        m1.metric("リスナー数", fmt(info["listeners"]))
        m2.metric("総再生数", fmt(info["playcount"]))
        m3.metric("ジャンルタグ", len(info["tags"]))
        if info["tags"]:
            tag_html = " ".join([
                f'<span style="background:#1e1e3a;border:1px solid #ff6b6b;border-radius:12px;padding:2px 10px;font-size:0.8rem;margin:2px;display:inline-block">{t}</span>'
                for t in info["tags"][:8]
            ])
            st.markdown(tag_html, unsafe_allow_html=True)

        # 比較リストに追加
        already = info["name"] in st.session_state.compare_list
        btn_label = "✓ 比較リストに追加済み" if already else "＋ 比較リストに追加"
        if st.button(btn_label, disabled=already, key="add_cmp"):
            st.session_state.compare_list.append(info["name"])
            st.rerun()

    if info.get("bio"):
        with st.expander("📖 アーティスト紹介"):
            st.write(info["bio"])

    st.markdown("---")
    col_l, col_r = st.columns(2)

    with col_l:
        st.subheader("🎵 人気曲トップ15")
        if not df_top.empty:
            fig = px.bar(
                df_top, x="playcount", y="track", orientation="h",
                color="playcount", color_continuous_scale="Reds",
                labels={"playcount": "再生数", "track": ""},
            )
            fig.update_layout(
                yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
                paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e8e8f0", height=430,
            )
            st.plotly_chart(fig, use_container_width=True)

    with col_r:
        st.subheader("💿 人気アルバム")
        if not df_albums.empty:
            img_cols = st.columns(4)
            for i, (_, row) in enumerate(df_albums.head(8).iterrows()):
                with img_cols[i % 4]:
                    if row["image"]:
                        st.image(row["image"], use_column_width=True)
                    st.caption(f"**{row['album'][:16]}**")
                    st.caption(fmt(row["playcount"]))

    # Similar artists
    if not df_sim.empty:
        st.markdown("---")
        st.subheader("🔗 似ているアーティスト（クリックで詳細）")
        sim_cols = st.columns(5)
        for i, (_, row) in enumerate(df_sim.head(10).iterrows()):
            with sim_cols[i % 5]:
                match_pct = int(row["match"] * 100)
                if st.button(f"{row['artist']}\n{match_pct}% 一致", key=f"sim_{row['artist']}"):
                    nav("artist", row["artist"])
                    st.session_state.artist = row["artist"]
                    st.rerun()

        fig_sim = px.bar(
            df_sim.head(12), x="match", y="artist", orientation="h",
            color="match", color_continuous_scale="Purples",
            range_x=[0, 1],
            labels={"match": "類似度", "artist": ""},
        )
        fig_sim.update_layout(
            yaxis=dict(autorange="reversed"), coloraxis_showscale=False,
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e8e8f0", height=380,
        )
        event_sim = st.plotly_chart(fig_sim, use_container_width=True, on_select="rerun", key="sim_chart")
        if event_sim and event_sim.get("selection", {}).get("points"):
            clicked = event_sim["selection"]["points"][0].get("label", "")
            if clicked:
                nav("artist", clicked)
                st.session_state.artist = clicked
                st.rerun()

    # Tags radar
    if info["tags"]:
        st.markdown("---")
        st.subheader("🏷️ ジャンルタグ分布")
        tag_df = pd.DataFrame({"tag": info["tags"][:8], "weight": range(len(info["tags"][:8]), 0, -1)})
        fig_tag = px.pie(
            tag_df, values="weight", names="tag",
            color_discrete_sequence=px.colors.sequential.Reds_r,
            hole=0.4,
        )
        fig_tag.update_layout(paper_bgcolor="rgba(0,0,0,0)", font_color="#e8e8f0", height=350)
        st.plotly_chart(fig_tag, use_container_width=True)


# ──────────────────────────────────────────────
# Page: Compare Artists
# ──────────────────────────────────────────────
elif page == "compare":
    st.title("📊 アーティスト比較")

    all_suggestions = []
    search_add = st.text_input("アーティストを追加検索", placeholder="名前を入力してEnter")
    if search_add:
        with st.spinner():
            results = search_artists(search_add, 5)
        if results:
            chosen = st.selectbox("追加するアーティストを選択", results, key="cmp_add_sel")
            if st.button("比較リストに追加", key="cmp_add_btn"):
                if chosen not in st.session_state.compare_list:
                    st.session_state.compare_list.append(chosen)
                    st.rerun()

    if len(st.session_state.compare_list) < 2:
        st.info("サイドバーまたは Artist Deep Dive から2人以上追加してください")
        st.stop()

    with st.spinner("比較データ取得中..."):
        infos = {name: get_artist_info(name) for name in st.session_state.compare_list}
        tracks = {name: get_top_tracks(name, 10) for name in st.session_state.compare_list}

    # Stats comparison
    st.subheader("📈 スタッツ比較")
    stats_rows = []
    for name, info in infos.items():
        if info:
            stats_rows.append({
                "artist": name,
                "リスナー数": info["listeners"],
                "総再生数": info["playcount"],
            })
    df_stats = pd.DataFrame(stats_rows)

    col1, col2 = st.columns(2)
    with col1:
        fig = px.bar(
            df_stats, x="artist", y="リスナー数",
            color="artist", color_discrete_sequence=px.colors.qualitative.Pastel,
            title="リスナー数比較",
        )
        fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", font_color="#e8e8f0")
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        fig = px.bar(
            df_stats, x="artist", y="総再生数",
            color="artist", color_discrete_sequence=px.colors.qualitative.Pastel,
            title="総再生数比較",
        )
        fig.update_layout(showlegend=False, paper_bgcolor="rgba(0,0,0,0)",
                          plot_bgcolor="rgba(0,0,0,0)", font_color="#e8e8f0")
        st.plotly_chart(fig, use_container_width=True)

    # Radar: リスナー/再生 比率
    st.subheader("🕸️ レーダー比較（正規化）")
    if len(df_stats) >= 2:
        max_l = df_stats["リスナー数"].max() or 1
        max_p = df_stats["総再生数"].max() or 1
        fig_radar = go.Figure()
        colors = px.colors.qualitative.Pastel
        for i, (_, row) in enumerate(df_stats.iterrows()):
            vals = [row["リスナー数"] / max_l, row["総再生数"] / max_p]
            cats = ["リスナー数", "総再生数"]
            fig_radar.add_trace(go.Scatterpolar(
                r=vals + [vals[0]],
                theta=cats + [cats[0]],
                fill="toself",
                name=row["artist"],
                line_color=colors[i % len(colors)],
            ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 1])),
            paper_bgcolor="rgba(0,0,0,0)", font_color="#e8e8f0", height=400,
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    # Tag overlap
    st.subheader("🏷️ ジャンルタグ比較")
    tag_rows = []
    for name, info in infos.items():
        if info:
            for j, tag in enumerate(info["tags"][:6]):
                tag_rows.append({"artist": name, "tag": tag, "weight": 6 - j})
    if tag_rows:
        df_tags = pd.DataFrame(tag_rows)
        fig_tags = px.bar(
            df_tags, x="tag", y="weight", color="artist",
            barmode="group",
            color_discrete_sequence=px.colors.qualitative.Pastel,
            labels={"weight": "重要度", "tag": "タグ"},
            title="アーティスト別ジャンルタグ",
        )
        fig_tags.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#e8e8f0",
        )
        st.plotly_chart(fig_tags, use_container_width=True)

    # Top tracks comparison
    st.subheader("🎵 人気曲比較")
    trk_cols = st.columns(len(st.session_state.compare_list))
    for i, name in enumerate(st.session_state.compare_list):
        with trk_cols[i]:
            st.markdown(f"**{name}**")
            df_t = tracks.get(name, pd.DataFrame())
            if not df_t.empty:
                for _, r in df_t.head(5).iterrows():
                    st.caption(f"{r['rank']}. {r['track'][:24]}")


# ──────────────────────────────────────────────
# Page: Artist Network
# ──────────────────────────────────────────────
elif page == "network":
    st.title("🕸️ アーティスト探索ネットワーク")

    root = st.text_input(
        "起点アーティスト",
        value=st.session_state.network_root or st.session_state.artist,
        placeholder="例: 米津玄師、YOASOBI、Ado",
    )
    depth = st.slider("展開の深さ（1=直接の関連, 2=関連の関連）", 1, 2, 1)

    if not root:
        st.info("アーティスト名を入力してください")
        st.stop()

    st.session_state.network_root = root

    with st.spinner(f"「{root}」のネットワーク構築中..."):
        G = nx.Graph()
        root_info = get_artist_info(root)
        if not root_info:
            st.warning("アーティストが見つかりませんでした")
            st.stop()

        G.add_node(root, listeners=root_info["listeners"], level=0)
        df_sim1 = get_similar(root, 12)
        node_data = {}
        node_data[root] = root_info

        for _, row in df_sim1.iterrows():
            sim_name = row["artist"]
            G.add_node(sim_name, level=1)
            G.add_edge(root, sim_name, weight=row["match"])

            if depth == 2:
                df_sim2 = get_similar(sim_name, 5)
                for _, row2 in df_sim2.iterrows():
                    n2 = row2["artist"]
                    if n2 not in G.nodes:
                        G.add_node(n2, level=2)
                    G.add_edge(sim_name, n2, weight=row2["match"])

    pos = nx.spring_layout(G, seed=42, k=2.5)

    level_colors = {0: "#ff6b6b", 1: "#ffd93d", 2: "#6bcff6"}
    node_x, node_y, node_text, node_color, node_size = [], [], [], [], []
    for node in G.nodes:
        x, y = pos[node]
        level = G.nodes[node].get("level", 1)
        node_x.append(x)
        node_y.append(y)
        node_text.append(node)
        node_color.append(level_colors.get(level, "#aaa"))
        node_size.append(30 if level == 0 else 18 if level == 1 else 12)

    edge_x, edge_y = [], []
    for u, v in G.edges:
        x0, y0 = pos[u]
        x1, y1 = pos[v]
        edge_x += [x0, x1, None]
        edge_y += [y0, y1, None]

    fig_net = go.Figure()
    fig_net.add_trace(go.Scatter(
        x=edge_x, y=edge_y, mode="lines",
        line=dict(width=0.8, color="#444"),
        hoverinfo="none",
    ))
    fig_net.add_trace(go.Scatter(
        x=node_x, y=node_y, mode="markers+text",
        text=node_text, textposition="top center",
        textfont=dict(size=10, color="#e8e8f0"),
        marker=dict(size=node_size, color=node_color, line=dict(width=1, color="#222")),
        hovertemplate="%{text}<extra></extra>",
        customdata=node_text,
    ))
    fig_net.update_layout(
        showlegend=False,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#e8e8f0",
        height=580,
        margin=dict(l=0, r=0, t=30, b=0),
        title=f"🔴 {root}　🟡 直接の関連　🔵 2次の関連",
    )

    event_net = st.plotly_chart(fig_net, use_container_width=True, on_select="rerun", key="net_chart")
    if event_net and event_net.get("selection", {}).get("points"):
        clicked = event_net["selection"]["points"][0].get("text", "")
        if clicked and clicked != root:
            col1, col2, col3 = st.columns(3)
            with col1:
                if st.button(f"🔍 「{clicked}」を詳細表示"):
                    nav("artist", clicked)
                    st.session_state.artist = clicked
                    st.rerun()
            with col2:
                if st.button(f"🕸️ 「{clicked}」を起点にネットワーク展開"):
                    st.session_state.network_root = clicked
                    st.rerun()
            with col3:
                already = clicked in st.session_state.compare_list
                if st.button(f"＋ 比較リストに追加", disabled=already):
                    st.session_state.compare_list.append(clicked)
                    st.rerun()

    st.markdown(f"**ノード数**: {G.number_of_nodes()}　**エッジ数**: {G.number_of_edges()}")
    with st.expander("関連アーティスト一覧"):
        sim_list = [{"アーティスト": n, "レベル": G.nodes[n].get("level", "?")} for n in G.nodes if n != root]
        st.dataframe(pd.DataFrame(sim_list), use_container_width=True, hide_index=True)
