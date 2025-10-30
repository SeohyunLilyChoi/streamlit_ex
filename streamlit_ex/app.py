import os
from pathlib import Path
import numpy as np
import pandas as pd
import streamlit as st
import altair as alt

st.set_page_config(
    page_title="Student Exam Scores Dashboard",
    page_icon="🧪",
    layout="wide",
    initial_sidebar_state="expanded",
)

alt.data_transformers.disable_max_rows()
alt.themes.enable("opaque")

# --- 표준 컬럼명 정의 ---
REQUIRED_COLS = [
    "student_id",
    "hours_studied",
    "sleep_hours",
    "attendance_percentage",
    "previous_scores",
    "exam_scores",
]
NUM_COLS = [
    "hours_studied",
    "sleep_hours",
    "attendance_percentage",
    "previous_scores",
    "exam_scores",
]

# 다양한 표기를 표준으로 정규화
VARIANT_TO_REQUIRED = {
    "attendance_percent": "attendance_percentage",
    "attendance": "attendance_percentage",
    "attendance_%": "attendance_percentage",
    "ExamScore": "exam_scores",
    "exam_score": "exam_scores",
}

DEFAULT_CSV_NAME = "student_exam_scores.csv"

# =========================
# 유틸: 슬라이더/형 변환
# =========================
def _to_float_series(s: pd.Series) -> pd.Series:
    """Series -> float Series"""
    return pd.to_numeric(s, errors="coerce").astype(float)

def _to_float_frame(df: pd.DataFrame) -> pd.DataFrame:
    """DataFrame -> 모든 열을 float로"""
    out = df.copy()
    for c in out.columns:
        out[c] = pd.to_numeric(out[c], errors="coerce").astype(float)
    return out

def range_slider_num(label: str, series: pd.Series, step_if_int=1.0, step_if_float=0.1):
    """범위(range) 슬라이더: min/max/value/step 모두 float로 통일"""
    s = _to_float_series(series)
    vmin = float(np.nanmin(s))
    vmax = float(np.nanmax(s))
    is_int_like = (s.dropna() % 1 == 0).all()
    step = float(step_if_int if is_int_like else step_if_float)
    return st.sidebar.slider(label, vmin, vmax, (vmin, vmax), step=step)

def slider_num(label: str, series: pd.Series, step_if_int=1.0, step_if_float=0.1):
    """단일값 슬라이더: min/max/value/step 모두 float로 통일"""
    s = _to_float_series(series)
    vmin = float(np.nanmin(s))
    vmax = float(np.nanmax(s))
    vdef = float(np.nanmedian(s))
    is_int_like = (s.dropna() % 1 == 0).all()
    step = float(step_if_int if is_int_like else step_if_float)
    return st.slider(label, vmin, vmax, vdef, step=step)

# =========================
# 데이터 로드/정규화
# =========================
def normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    return df.rename(columns=VARIANT_TO_REQUIRED)

@st.cache_data
def load_csv_any(path_or_buffer) -> pd.DataFrame:
    last_err = None
    if isinstance(path_or_buffer, (str, os.PathLike, Path)):
        for enc in ("utf-8", "utf-8-sig", "cp949"):
            try:
                df = pd.read_csv(path_or_buffer, encoding=enc)
                break
            except Exception as e:
                last_err = e
                df = None
        if df is None:
            raise RuntimeError(f"CSV 읽기 실패: {last_err}")
    else:
        df = pd.read_csv(path_or_buffer)

    df = normalize_columns(df)

    missing = [c for c in REQUIRED_COLS if c not in df.columns]
    if missing:
        raise ValueError(f"필수 컬럼 누락: {missing}")

    for c in NUM_COLS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype(float)
    return df.dropna(subset=NUM_COLS).copy()

# =========================
# 제목, 데이터 설명
# =========================
st.title("🧪 Student Exam Scores Dashboard")
st.markdown("""
이 대시보드는 학생들의 **공부 시간, 수면 시간, 출석률, 이전 점수**와 **현재 시험 점수** 간의 관계를 시각화합니다.
**학습 습관이 성적에 어떤 영향을 미치는지** 직관적으로 탐색할 수 있어요.
""")

with st.expander("📘 데이터 설명"):
    st.markdown("""
    **컬럼 구성**
    - `student_id`: 학생 고유 ID  
    - `hours_studied`: 시험 전 공부 시간(시간)  
    - `sleep_hours`: 하루 평균 수면 시간(시간)  
    - `attendance_percentage`: 출석률(%)  
    - `previous_scores`: 직전 시험 점수  
    - `exam_scores`: 현재 시험 점수  
    """)

# =========================
# 데이터 업로드
# =========================
script_dir = Path(__file__).parent if "__file__" in globals() else Path(os.getcwd())
default_csv_path = script_dir / DEFAULT_CSV_NAME

df = None
if default_csv_path.exists():
    try:
        df = load_csv_any(default_csv_path)
        st.success(f"`{DEFAULT_CSV_NAME}` 자동 로드 완료")
    except Exception as e:
        st.error(f"로컬 파일 로드 오류: {e}")

# 업로더(대체/교체)
st.sidebar.header("📁 데이터 소스")
uploaded = st.sidebar.file_uploader("CSV 업로드(선택)", type=["csv"])
if uploaded is not None:
    try:
        df = load_csv_any(uploaded)
        st.success("✅ 업로드한 CSV로 로드 완료")
    except Exception as e:
        st.error(f"업로드 CSV 오류: {e}")

if df is None:
    st.warning("동일 폴더에 student_exam_scores.csv를 두거나, 좌측에서 CSV를 업로드해 주세요.")
    st.stop()

# =========================
# 필터
# =========================
st.sidebar.header("🔎 필터")
st.sidebar.caption("좌우로 움직여보세요.")
filters = {}
for c in NUM_COLS:
    filters[c] = range_slider_num(c, df[c])

mask = np.ones(len(df), dtype=bool)
for c, (lo, hi) in filters.items():
    s = _to_float_series(df[c])
    mask &= (s >= lo) & (s <= hi)
fdf = df.loc[mask].copy()

if len(fdf) == 0:
    st.warning("현재 필터 조건에 해당하는 데이터가 없습니다. 필터 범위를 넓혀주세요.")
    st.stop()

# =========================
# 지표 요약
# =========================
st.subheader("📊 주요 지표 요약")
k1, k2, k3, k4 = st.columns(4)
k1.metric("표시 중 학생 수", f"{len(fdf):,}")
k2.metric("평균 시험 점수", f"{fdf['exam_scores'].mean():.2f}")
k3.metric("평균 공부시간", f"{fdf['hours_studied'].mean():.2f} h")
k4.metric("평균 출석률", f"{fdf['attendance_percentage'].mean():.2f}%")

st.divider()

# =========================
# 탭: 분포 / 상관 / 관계 / 예측
# =========================
tab1, tab2, tab3, tab4 = st.tabs([
    "📦 분포(히스토그램)",
    "🧩 상관 히트맵",
    "🔗 관계(산점도+회귀)",
    "🤖 간단 예측(다중선형회귀)"
])

# --- 1) 분포 ---
with tab1:
    st.markdown("### 📦 분포(히스토그램)")
    st.caption("각 변수의 분포를 확인합니다. 치우침이나 이상치 여부를 빠르게 파악할 수 있어요.")
    cols = st.multiselect(
        "데이터(컬럼) 선택",
        options=NUM_COLS,
        default=["exam_scores", "hours_studied"]
    )
    for c in cols:
        chart = (
            alt.Chart(fdf)
            .mark_bar()
            .encode(
                x=alt.X(f"{c}:Q", bin=alt.Bin(maxbins=30), title=c),
                y=alt.Y("count():Q", title="count"),
                tooltip=[alt.Tooltip(f"{c}:Q", format=".2f"), alt.Tooltip("count()", title="count")]
            )
            .properties(height=260)
        )
        st.altair_chart(chart, use_container_width=True)

# --- 2) 상관 히트맵 ---
with tab2:
    st.markdown("### 🧩 상관 히트맵")
    st.caption("변수 간 선형 상관관계를 색으로 표현합니다. 진한 색일수록 절대값이 큰(강한) 상관을 의미합니다.")
    corr = fdf[NUM_COLS].corr().round(3)
    corr_long = (
        corr.reset_index()
            .melt(id_vars="index", var_name="col", value_name="corr")
            .rename(columns={"index": "row"})
    )
    heat = (
        alt.Chart(corr_long)
        .mark_rect()
        .encode(
            x=alt.X("col:N", title=""),
            y=alt.Y("row:N", title=""),
            color=alt.Color("corr:Q", scale=alt.Scale(scheme="blues"), title="corr"),
            tooltip=["row", "col", alt.Tooltip("corr:Q", format=".3f")],
        )
        .properties(height=360)
    )
    text = alt.Chart(corr_long).mark_text().encode(
        x="col:N", y="row:N", text=alt.Text("corr:Q", format=".2f")
    )
    st.altair_chart(heat + text, use_container_width=True)

# --- 3) 관계(산점도 + 회귀선) ---
with tab3:
    st.markdown("### 🔗 관계(산점도 + 회귀선)")
    st.caption("두 변수 간 관계를 시각화합니다. 빨간 회귀선의 기울기 방향으로 영향 방향을 가늠할 수 있어요.")
    x_sel = st.selectbox("X축 변수 선택", options=[c for c in NUM_COLS if c != "exam_scores"])
    scatter = alt.Chart(fdf).mark_circle(opacity=0.7).encode(
        x=alt.X(f"{x_sel}:Q", title=x_sel),
        y=alt.Y("exam_scores:Q", title="exam_scores"),
        tooltip=[x_sel, "exam_scores"]
    )
    reg = alt.Chart(fdf).transform_regression(x_sel, "exam_scores").mark_line(color="red").encode(
        x=f"{x_sel}:Q", y="exam_scores:Q"
    )
    st.altair_chart((scatter + reg).properties(height=400), use_container_width=True)

# --- 4) 간단 예측(다중선형회귀) ---
with tab4:
    st.markdown("### 🤖 간단 예측 (다중선형회귀)")
    st.caption("공부 시간, 수면 시간, 출석률, 이전 점수로 현재 시험 점수를 선형 회귀로 예측해봅니다.")
    feature_cols = ["hours_studied", "sleep_hours", "attendance_percentage", "previous_scores"]

    # ✅ 여기서 Series/Frame 타입에 맞춰 변환
    X = _to_float_frame(fdf[feature_cols]).to_numpy()
    y = _to_float_series(fdf["exam_scores"]).to_numpy()

    if len(y) < 2:
        st.warning("회귀를 수행하기에 표본 수가 너무 적습니다. 필터 범위를 넓혀주세요.")
    else:
        # 절편항 추가 후 최소제곱해
        X_design = np.column_stack([np.ones(len(X)), X])
        coef, *_ = np.linalg.lstsq(X_design, y, rcond=None)
        intercept, betas = coef[0], coef[1:]
        r2 = 1.0 - (np.sum((y - X_design @ coef) ** 2) / np.sum((y - y.mean()) ** 2))

        st.code(
            f"exam_scores = {intercept:.4f}"
            + "".join([f" + ({betas[i]:.4f}) * {feature_cols[i]}" for i in range(len(feature_cols))]),
            language="text",
        )
        st.caption(f"설명력 (R²): **{r2:.3f}** — 1에 가까울수록 선형 설명력이 높음을 의미합니다.")

        # What-if 슬라이더(형 일치 보장)
        hs = slider_num("hours_studied", fdf["hours_studied"])
        sh = slider_num("sleep_hours", fdf["sleep_hours"])
        att = slider_num("attendance_percentage", fdf["attendance_percentage"])
        prev = slider_num("previous_scores", fdf["previous_scores"])

        pred = intercept + betas[0]*hs + betas[1]*sh + betas[2]*att + betas[3]*prev
        st.metric("예상 exam_scores", f"{pred:.2f}")

# =========================
# 데이터 미리보기
# =========================
st.divider()
with st.expander("📜 데이터 미리보기"):
    st.dataframe(fdf.head(50), use_container_width=True)

st.caption(
    f"동일 폴더에 `{DEFAULT_CSV_NAME}`를 두면 자동 로드됩니다. "
)
